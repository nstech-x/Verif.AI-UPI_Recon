import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from config import UPLOAD_DIR
from core.security import get_current_user
from dependencies import audit, file_handler, rollback_manager
from services.file_validation import validate_file_columns

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["upload"])


@router.post("/upload", status_code=201)
async def upload_files(
    cycle: Optional[str] = Query(None, description="Cycle e.g., 1C..10C"),
    run_date: str = Query(None, description="Run date YYYY-MM-DD"),
    direction: str = Query("INWARD", description="INWARD or OUTWARD"),
    cbs_inward: UploadFile = File(None),
    cbs_outward: UploadFile = File(None),
    switch: UploadFile = File(None),
    npci_inward: UploadFile = File(None),
    npci_outward: UploadFile = File(None),
    ntsl: UploadFile = File(None),
    adjustment: UploadFile = File(None),
    files: List[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
):
    """Uploads the required files for a reconciliation run"""
    try:
        run_id = f"RUN_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Validate cycle format only if provided
        valid_cycles = [f"{i}C" for i in range(1, 11)]
        if cycle and cycle not in valid_cycles:
            raise HTTPException(status_code=400, detail=f"Invalid cycle. Valid cycles: {', '.join(valid_cycles)}")

        # Required file mapping
        required_files = {
            'cbs_inward': cbs_inward,
            'cbs_outward': cbs_outward,
            'switch': switch,
            'npci_inward': npci_inward,
            'npci_outward': npci_outward,
            'ntsl': ntsl,
            'adjustment': adjustment,
        }

        # Map generic files list
        if files:
            for upfile in files:
                fname = upfile.filename.lower()
                assigned = False
                if 'cbs' in fname and 'in' in fname:
                    required_files['cbs_inward'] = upfile
                    assigned = True
                elif 'cbs' in fname and 'out' in fname:
                    required_files['cbs_outward'] = upfile
                    assigned = True
                elif 'switch' in fname:
                    required_files['switch'] = upfile
                    assigned = True
                elif 'npci' in fname and 'in' in fname:
                    required_files['npci_inward'] = upfile
                    assigned = True
                elif 'npci' in fname and 'out' in fname:
                    required_files['npci_outward'] = upfile
                    assigned = True
                elif 'ntsl' in fname or 'national' in fname:
                    required_files['ntsl'] = upfile
                    assigned = True
                elif 'adjust' in fname or 'adj' in fname:
                    required_files['adjustment'] = upfile
                    assigned = True

                if not assigned:
                    for k, v in required_files.items():
                        if v is None:
                            required_files[k] = upfile
                            break

        uploaded_files_content = {}
        invalid_files = []
        validation_warnings = []
        MAX_BYTES = 100 * 1024 * 1024
        # Map original filename -> field key (e.g., 'ntsl', 'npci_inward')
        original_field_map: Dict[str, str] = {}

        for key, upfile in required_files.items():
            if upfile is None:
                invalid_files.append({
                    "field": key,
                    "error": "required file is missing",
                    "suggestion": f"Please upload a {key.replace('_', ' ')} file",
                })
                continue

            try:
                content = await upfile.read()
                # Map original filename to the field key for later processing
                original_field_map[upfile.filename] = key
            except Exception as e:
                invalid_files.append({
                    "filename": upfile.filename,
                    "error": f"failed to read file content: {str(e)}",
                })
                continue

            if not content or len(content) == 0:
                invalid_files.append({
                    "filename": upfile.filename,
                    "error": "file is empty",
                    "suggestion": "Please ensure the file contains data",
                })
                continue

            if len(content) > MAX_BYTES:
                invalid_files.append({
                    "filename": upfile.filename,
                    "error": f"file size ({len(content)/1024/1024:.1f} MB) exceeds limit (100 MB)",
                })
                continue

            # Validate file
            is_valid, err = file_handler.validate_file_bytes(content, upfile.filename)
            if not is_valid:
                invalid_files.append({
                    "filename": upfile.filename,
                    "error": err,
                    "suggestion": "Please check file format and ensure it contains valid financial transaction data",
                })
                continue

            # Validate columns
            validation_result = await validate_file_columns(content, upfile.filename, key)
            if not validation_result["valid"]:
                invalid_files.append({
                    "filename": upfile.filename,
                    "error": validation_result["error"],
                    "missing_columns": validation_result.get("missing_columns", []),
                    "suggestion": validation_result.get("suggestion", "Please check column headers in your file"),
                })
                continue

            if validation_result.get("warnings"):
                validation_warnings.extend(validation_result["warnings"])

            uploaded_files_content[upfile.filename] = content

        if invalid_files:
            for bad in invalid_files:
                try:
                    rollback_manager.ingestion_rollback(run_id, bad.get('filename', bad.get('field', '')), bad.get('error', ''))
                except Exception:
                    pass

            if validation_warnings:
                logger.info(f"Upload validation warnings: {validation_warnings}")

            logger.warning(f"Upload contained invalid files: {invalid_files}")
            error_response = {"invalid_files": invalid_files}
            if validation_warnings:
                error_response["warnings"] = validation_warnings
            raise HTTPException(status_code=400, detail=error_response)

        # If NTSL file present and no cycle provided, try to extract cycle from filename or file content
        per_file_cycles: Dict[str, str] = {}
        try:
            import re
            for fname, content in list(uploaded_files_content.items()):
                mapped_field = original_field_map.get(fname)
                if mapped_field == 'ntsl':
                    # Try filename pattern: ^(Cycle\d+)_(\d{4}-\d{2}-\d{2})_(.+)$
                    m = re.match(r'^(Cycle\d+)_(\d{4}-\d{2}-\d{2})_(.+)$', fname, flags=re.IGNORECASE)
                    extracted_cycle = None
                    if m:
                        grp = m.group(1)  # e.g., Cycle1
                        dig = re.search(r'\d+', grp)
                        if dig:
                            extracted_cycle = f"{dig.group()}C"
                    if not extracted_cycle:
                        # Fallback: try to extract from file content (first few lines)
                        try:
                            text = content.decode('utf-8', errors='ignore')
                            lines = text.splitlines()[:10]
                            for line in lines:
                                rm = re.search(r'Cycle\s*[:=_-]?\s*(?:Cycle)?(\d+)', line, flags=re.IGNORECASE)
                                if rm:
                                    extracted_cycle = f"{rm.group(1)}C"
                                    break
                                rm2 = re.search(r'(\d{1,2}C)', line, flags=re.IGNORECASE)
                                if rm2:
                                    extracted_cycle = rm2.group(1).upper()
                                    break
                        except Exception:
                            extracted_cycle = None

                    if not extracted_cycle:
                        raise HTTPException(status_code=400, detail={"error": "Could not determine cycle for NTSL file", "file": fname})

                    per_file_cycles[fname] = extracted_cycle
                    # If run-level cycle absent, set it to extracted cycle for compatibility
                    if not cycle:
                        cycle = extracted_cycle
        except HTTPException:
            raise
        except Exception:
            # don't block other files if cycle extraction has issues here; let save handler manage
            pass

        # Save files
        run_folder = file_handler.save_uploaded_files(
            uploaded_files_content,
            run_id,
            cycle=cycle,
            direction=direction,
            run_date=run_date,
            per_file_cycles=per_file_cycles,
        )

        # Audit
        for fname, content in uploaded_files_content.items():
            audit.log_file_upload(run_id, fname, len(content), user_id='system', status='success')

        logger.info(f"Files for {run_id} uploaded successfully to {run_folder}")

        return JSONResponse(content={"status": "success", "run_id": run_id}, status_code=201)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="File upload process failed")


@router.get("/upload/metadata")
async def get_upload_metadata(run_id: Optional[str] = None):
    """Get metadata for a specific run or latest run if not specified"""
    try:
        # If no run_id provided, use the latest run
        if not run_id:
            runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
            if not runs:
                return {
                    "run_id": None,
                    "uploaded_files": [],
                    "status": "no_runs_found",
                }
            run_id = sorted(runs)[-1]

        # Search for metadata in nested directories
        run_folder = os.path.join(UPLOAD_DIR, run_id)
        metadata_path = None

        for root_dir, dirs, files in os.walk(run_folder):
            if 'metadata.json' in files:
                metadata_path = os.path.join(root_dir, 'metadata.json')
                break

        if not metadata_path or not os.path.exists(metadata_path):
            logger.warning(f"Metadata not found for run {run_id}")
            return {
                "run_id": run_id,
                "uploaded_files": [],
                "status": "metadata_not_found",
            }

        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        # Extract uploaded file types from saved_files dict
        uploaded_files = []
        if isinstance(metadata.get('saved_files'), dict):
            uploaded_files = list(metadata['saved_files'].keys())

        logger.info(f"Retrieved metadata for {run_id}: {uploaded_files}")

        return {
            "run_id": run_id,
            "uploaded_files": uploaded_files,
            "saved_files": metadata.get('saved_files', {}),
            "cycle_id": metadata.get('cycle_id'),
            "direction": metadata.get('direction'),
            "run_date": metadata.get('run_date'),
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Get metadata error: {str(e)}")
        return {
            "run_id": None,
            "uploaded_files": [],
            "status": "error",
            "error": str(e),
        }
