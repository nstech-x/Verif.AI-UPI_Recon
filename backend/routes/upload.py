import json
import logging
import os
from datetime import datetime, date
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from config import UPLOAD_DIR
from core.security import get_current_user
from dependencies import audit, file_handler, rollback_manager
from services.file_validation import validate_file_columns
from services.file_naming import parse_upi_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["upload"])


def _load_requirements() -> Dict:
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "file_requirements.json")
    cfg_path = os.path.abspath(cfg_path)
    if not os.path.exists(cfg_path):
        return {"required_counts": {}, "required_rows": {}}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"required_counts": {}, "required_rows": {}}


def _load_run_metadata(run_id: str) -> Dict:
    meta_path = os.path.join(UPLOAD_DIR, run_id, "metadata.json")
    if not os.path.exists(meta_path):
        return {}
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post("/upload", status_code=201)
async def upload_files(
    cycle: Optional[str] = Query(None, description="Cycle e.g., 1C..10C"),
    run_date: str = Query(None, description="Run date YYYY-MM-DD"),
    direction: str = Query("INWARD", description="INWARD or OUTWARD"),
    uploaded_by: Optional[str] = Query(None, description="Uploader username or AUTO"),
    cbs_inward: UploadFile = File(None),
    cbs_outward: UploadFile = File(None),
    switch: UploadFile = File(None),
    npci_inward: UploadFile = File(None),
    npci_outward: UploadFile = File(None),
    drc: UploadFile = File(None),
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

        # Required single files and optional multi-files
        required_files = {
            'cbs_inward': cbs_inward,
            'cbs_outward': cbs_outward,
            'switch': switch,
        }
        optional_multi_files: Dict[str, List[UploadFile]] = {
            'npci_inward': [],
            'npci_outward': [],
            'drc': [],
            'ntsl': [],
            'adjustment': [],
        }
        duplicate_required: List[str] = []

        # Include any named optional files if present
        if npci_inward:
            optional_multi_files['npci_inward'].append(npci_inward)
        if npci_outward:
            optional_multi_files['npci_outward'].append(npci_outward)
        if drc:
            optional_multi_files['drc'].append(drc)
        if ntsl:
            optional_multi_files['ntsl'].append(ntsl)
        if adjustment:
            optional_multi_files['adjustment'].append(adjustment)

        # Map generic files list
        if files:
            for upfile in files:
                fname = upfile.filename.lower()
                assigned = False
                parsed = parse_upi_filename(upfile.filename)
                if parsed:
                    if parsed.get("direction") == "INWARD":
                        optional_multi_files['npci_inward'].append(upfile)
                    else:
                        optional_multi_files['npci_outward'].append(upfile)
                    assigned = True
                if 'cbs' in fname and 'in' in fname:
                    if required_files['cbs_inward'] is None:
                        required_files['cbs_inward'] = upfile
                    else:
                        duplicate_required.append(upfile.filename)
                    assigned = True
                elif 'cbs' in fname and 'out' in fname:
                    if required_files['cbs_outward'] is None:
                        required_files['cbs_outward'] = upfile
                    else:
                        duplicate_required.append(upfile.filename)
                    assigned = True
                elif 'switch' in fname:
                    if required_files['switch'] is None:
                        required_files['switch'] = upfile
                    else:
                        duplicate_required.append(upfile.filename)
                    assigned = True
                elif 'npci' in fname and 'in' in fname:
                    optional_multi_files['npci_inward'].append(upfile)
                    assigned = True
                elif 'npci' in fname and 'out' in fname:
                    optional_multi_files['npci_outward'].append(upfile)
                    assigned = True
                elif 'drc' in fname:
                    optional_multi_files['drc'].append(upfile)
                    assigned = True
                elif 'ntsl' in fname or 'national' in fname:
                    optional_multi_files['ntsl'].append(upfile)
                    assigned = True
                elif 'adjust' in fname or 'adj' in fname:
                    optional_multi_files['adjustment'].append(upfile)
                    assigned = True

                if not assigned:
                    for k, v in required_files.items():
                        if v is None:
                            required_files[k] = upfile
                            assigned = True
                            break
                if not assigned:
                    # If still unassigned, treat as optional adjustment fallback
                    optional_multi_files['adjustment'].append(upfile)

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

        for fname in duplicate_required:
            invalid_files.append({
                "filename": fname,
                "error": "multiple files detected for a required type",
                "suggestion": "Please upload only one file for CBS Inward, CBS Outward, and Switch",
            })

        def validate_filename_cycle_date(file_type: str, filename: str) -> Optional[str]:
            """Validate filename format and date for NPCI/NTSL/Adjustment files."""
            if file_type not in ('npci_inward', 'npci_outward', 'ntsl', 'adjustment', 'drc'):
                return None

            # Prefer new ISSR/ACQR naming convention
            try:
                from services.file_naming import parse_upi_filename
                parsed = parse_upi_filename(filename)
            except Exception:
                parsed = None

            if file_type in ('npci_inward', 'npci_outward'):
                if parsed:
                    # cycle mandatory for NPCI
                    if not parsed.get('cycle'):
                        return "NPCI filename must include cycle (e.g., _1C)"
                    # direction must match
                    if file_type == 'npci_inward' and parsed.get('direction') != 'INWARD':
                        return "NPCI inward file must be ISSR (Issuer/Inward)"
                    if file_type == 'npci_outward' and parsed.get('direction') != 'OUTWARD':
                        return "NPCI outward file must be ACQR (Acquirer/Outward)"
                    # date must be present
                    if not parsed.get('date'):
                        return "NPCI filename must include a valid date (DDMMYY)"
                    return None

            # Fallback legacy pattern
            name = filename.lower()
            import re
            cycle_match = re.search(r'cycle\s*0*(\d{1,2})', name)
            type_match = re.search(r'(?:^|[_-])(inward|outward)(?:[_-]|$)', name)
            date_match = re.search(r'(\d{2})(\d{2})(\d{4})', name)

            if file_type in ('npci_inward', 'npci_outward'):
                if not cycle_match or not date_match or not type_match:
                    return "NPCI filename must include cycle, direction, and date"

                cycle_num = int(cycle_match.group(1))
                if cycle_num < 1 or cycle_num > 10:
                    return "Cycle number in filename must be between 1 and 10"

                dd = int(date_match.group(1))
                mm = int(date_match.group(2))
                yyyy = int(date_match.group(3))

                try:
                    date(yyyy, mm, dd)
                except Exception:
                    return "Invalid date in filename (expected DDMMYYYY)"

                if file_type == 'npci_inward' and type_match.group(1) != 'inward':
                    return "NPCI inward file name must include 'inward'"
                if file_type == 'npci_outward' and type_match.group(1) != 'outward':
                    return "NPCI outward file name must include 'outward'"

            # NTSL cycle optional; no strict validation beyond presence of file
            if file_type == 'drc':
                import re
                if not re.match(r'^DRCREPORT[A-Z0-9]{4}\d{6}', filename, flags=re.IGNORECASE):
                    return "DRC filename must follow DRCReport + BANK + DDMMYY"

            return None

        def iter_files():
            for key, upfile in required_files.items():
                if upfile is not None:
                    yield key, upfile
            for key, files_list in optional_multi_files.items():
                for upfile in files_list:
                    yield key, upfile

        for key, upfile in iter_files():
            # Optional NPCI/NTSL/Adjustment filename validation
            filename_error = validate_filename_cycle_date(key, upfile.filename)
            if filename_error:
                invalid_files.append({
                    "filename": upfile.filename,
                    "error": filename_error,
                    "suggestion": "Rename the file to include cycle, direction, and today's date",
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
                        # NTSL cycle is optional; do not block upload
                        extracted_cycle = None

                    if extracted_cycle:
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
        uploader = uploaded_by or user.get('username') or 'AUTO'
        run_folder = file_handler.save_uploaded_files(
            uploaded_files_content,
            run_id,
            cycle=cycle,
            direction=direction,
            run_date=run_date,
            per_file_cycles=per_file_cycles,
            uploaded_by=uploader,
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
            "files_detail": metadata.get('files_detail', {}),
            "uploaded_by": metadata.get('uploaded_by'),
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


@router.get("/upload/validation")
async def get_upload_validation(run_id: Optional[str] = None):
    """Return file count and row count validations for a run."""
    try:
        if not run_id:
            runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
            if not runs:
                return {
                    "run_id": None,
                    "status": "no_runs_found",
                    "summary": [],
                }
            run_id = sorted(runs)[-1]

        metadata = _load_run_metadata(run_id)
        files_detail = metadata.get("files_detail", {})

        requirements = _load_requirements()
        required_counts = requirements.get("required_counts", {})
        required_rows = requirements.get("required_rows", {})

        counts: Dict[str, int] = {}
        for original_name, info in files_detail.items():
            file_type = info.get("file_type", "unknown")
            parsed = info.get("parsed") or parse_upi_filename(original_name) or {}
            txn_type = (parsed.get("txn_type") or "").lower()

            key = file_type
            if file_type.startswith("npci_") and txn_type:
                key = f"{file_type}_{txn_type}"

            counts[key] = counts.get(key, 0) + 1

        def _path_for_file(info: Dict) -> Optional[str]:
            legacy = info.get("legacy_path")
            if legacy and os.path.exists(legacy):
                return legacy
            std_name = info.get("standardized_name")
            if std_name:
                candidate = os.path.join(UPLOAD_DIR, run_id, std_name)
                if os.path.exists(candidate):
                    return candidate
            return None

        summary = []
        for key, required in required_counts.items():
            uploaded = counts.get(key, 0)
            row_error = False
            data_error = False
            req_rows = required_rows.get(key)
            if req_rows is not None:
                for original_name, info in files_detail.items():
                    file_type = info.get("file_type", "unknown")
                    parsed = info.get("parsed") or parse_upi_filename(original_name) or {}
                    txn_type = (parsed.get("txn_type") or "").lower()
                    computed_key = file_type
                    if file_type.startswith("npci_") and txn_type:
                        computed_key = f"{file_type}_{txn_type}"
                    if computed_key != key:
                        continue
                    if info.get("row_count", 0) != req_rows:
                        row_error = True
                        break

            # Row-level data quality validation (RRN length, numeric amount, etc.)
            for original_name, info in files_detail.items():
                file_type = info.get("file_type", "unknown")
                parsed = info.get("parsed") or parse_upi_filename(original_name) or {}
                txn_type = (parsed.get("txn_type") or "").lower()
                computed_key = file_type
                if file_type.startswith("npci_") and txn_type:
                    computed_key = f"{file_type}_{txn_type}"
                if computed_key != key:
                    continue
                fpath = _path_for_file(info)
                if not fpath:
                    continue
                try:
                    with open(fpath, "rb") as fb:
                        content = fb.read()
                    vr = await validate_file_columns(content, original_name, file_type)
                    if (not vr.get("valid", True)) or bool(vr.get("row_errors")):
                        data_error = True
                        break
                except Exception:
                    data_error = True
                    break
            summary.append({
                "key": key,
                "required_count": required,
                "uploaded_count": uploaded,
                "error": uploaded < required or row_error or data_error,
                "row_error": row_error,
                "data_error": data_error,
            })

        return {
            "run_id": run_id,
            "status": "success",
            "summary": summary,
        }
    except Exception as e:
        logger.error(f"Validation summary error: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute validation summary")


@router.get("/upload/validation/detail")
async def get_upload_validation_detail(run_id: Optional[str] = None, key: Optional[str] = None):
    """Return row count validation detail for a specific file key."""
    try:
        if not run_id:
            runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
            if not runs:
                return {
                    "run_id": None,
                    "status": "no_runs_found",
                    "details": [],
                }
            run_id = sorted(runs)[-1]

        if not key:
            raise HTTPException(status_code=400, detail="key is required")

        metadata = _load_run_metadata(run_id)
        files_detail = metadata.get("files_detail", {})

        requirements = _load_requirements()
        required_rows = requirements.get("required_rows", {})
        required_counts = requirements.get("required_counts", {})
        required_row_count = required_rows.get(key)
        required_count = required_counts.get(key)

        def _path_for_file(info: Dict) -> Optional[str]:
            legacy = info.get("legacy_path")
            if legacy and os.path.exists(legacy):
                return legacy
            std_name = info.get("standardized_name")
            if std_name:
                candidate = os.path.join(UPLOAD_DIR, run_id, std_name)
                if os.path.exists(candidate):
                    return candidate
            return None

        uploaded_count = 0
        details = []
        for original_name, info in files_detail.items():
            file_type = info.get("file_type", "unknown")
            parsed = info.get("parsed") or parse_upi_filename(original_name) or {}
            txn_type = (parsed.get("txn_type") or "").lower()

            computed_key = file_type
            if file_type.startswith("npci_") and txn_type:
                computed_key = f"{file_type}_{txn_type}"

            if computed_key != key:
                continue

            uploaded_count += 1
            row_count = info.get("row_count", 0)
            row_error = required_row_count is not None and row_count != required_row_count
            row_errors = []
            validation_error = None
            validation_warnings = []
            fpath = _path_for_file(info)
            if fpath:
                try:
                    with open(fpath, "rb") as fb:
                        content = fb.read()
                    vr = await validate_file_columns(content, original_name, file_type)
                    row_errors = vr.get("row_errors", []) or []
                    validation_warnings = vr.get("warnings", []) or []
                    if not vr.get("valid", True):
                        validation_error = vr.get("error")
                except Exception as e:
                    validation_error = str(e)

            details.append({
                "file_name": original_name,
                "required_rows": required_row_count,
                "required_rows_display": required_row_count if required_row_count is not None else row_count,
                "uploaded_rows": row_count,
                "uploaded_by": info.get("uploaded_by", metadata.get("uploaded_by", "AUTO")),
                "error": row_error or bool(row_errors) or bool(validation_error) or bool(validation_warnings),
                "validation_error": validation_error,
                "validation_warnings": validation_warnings,
                "row_errors": row_errors,
                "row_error_count": len(row_errors),
                "error_message": (
                    validation_error
                    or (f"{len(row_errors)} row-level issue(s)" if row_errors else None)
                    or ("; ".join(validation_warnings) if validation_warnings else None)
                ),
            })

        key_error_message = None
        if required_count is not None and uploaded_count < required_count:
            key_error_message = f"Missing file(s): required {required_count}, uploaded {uploaded_count}"
        elif required_row_count is not None and any(d.get("uploaded_rows") != required_row_count for d in details):
            key_error_message = f"Row count mismatch: each file should have {required_row_count} rows"
        elif any(d.get("error") for d in details):
            key_error_message = "Validation error found in one or more files"

        return {
            "run_id": run_id,
            "status": "success",
            "key": key,
            "required_count": required_count,
            "uploaded_count": uploaded_count,
            "key_error_message": key_error_message,
            "required_rows": required_row_count,
            "details": details,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation detail error: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute validation detail")
