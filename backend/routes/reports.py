import io
import json
import logging
import os
import zipfile
from typing import Optional
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from config import OUTPUT_DIR, UPLOAD_DIR
from core.security import get_current_user
from dependencies import audit, file_handler
from services.ttum import get_ttum_files, write_ttum_csv, write_ttum_xlsx
from services.report_catalog import (
    resolve_run_id,
    generate_listing_report,
    generate_matched_transactions_report,
    generate_unmatched_transactions_report,
    generate_adjustment_listing,
    generate_ttum_listing,
    generate_annexure_iv_split,
    generate_mis_report,
    generate_datewise_income_expense,
    generate_monthly_settlement_report,
    generate_ntsl_settlement_ttum,
    generate_dispute_tracker,
    generate_rbi_reporting,
    find_gl_statement,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

@router.post("/listing")
async def generate_listing_reports(run_id: str = Query(...), user: dict = Depends(get_current_user)):
    """Generate raw listing reports immediately after upload and before reconciliation.
    Produces CSV dumps of the uploaded files under OUTPUT_DIR/<run_id>/reports.
    """
    try:
        run_root = os.path.join(UPLOAD_DIR, run_id)
        if not os.path.isdir(run_root):
            raise HTTPException(status_code=404, detail=f"Run ID '{run_id}' not found")
        # locate the folder that actually contains uploaded files
        target_folder = None
        for root_dir, dirs, files in os.walk(run_root):
            if 'file_mapping.json' in files:
                target_folder = root_dir
                break
        if not target_folder:
            target_folder = run_root
        # Load through existing loader to normalize content
        dataframes = file_handler.load_files_for_recon(target_folder)
        out_dir = os.path.join(OUTPUT_DIR, run_id, 'reports')
        os.makedirs(out_dir, exist_ok=True)
        generated = []
        for idx, df in enumerate(dataframes):
            try:
                name = f"listing_{idx+1}.csv"
                path = os.path.join(out_dir, name)
                df.to_csv(path, index=False, encoding='utf-8-sig')
                generated.append(path)
            except Exception as e:
                logger.warning(f"Failed to write listing {idx+1}: {e}")
                continue
        return JSONResponse(content={"status": "ok", "generated": generated, "count": len(generated)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate listing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate listing reports")

@router.get("/gl-statement")
async def download_gl_statement(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download GL statement for a run"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        # Look for GL statement in OUTPUT_DIR first, then UPLOAD_DIR
        gl_files = []
        out_gl = os.path.join(OUTPUT_DIR, target, 'gl_statement')
        if os.path.exists(out_gl):
            gl_files = [os.path.join(out_gl, f) for f in os.listdir(out_gl) if f.endswith(('.xlsx', '.csv'))]

        if not gl_files:
            up_gl = os.path.join(UPLOAD_DIR, target, 'gl_statement')
            if os.path.exists(up_gl):
                gl_files = [os.path.join(up_gl, f) for f in os.listdir(up_gl) if f.endswith(('.xlsx', '.csv'))]

        if not gl_files:
            raise HTTPException(status_code=404, detail="GL statement not found")

        # Return first GL file found
        gl_file = gl_files[0]

        # Audit log download
        audit.log_data_export(target, os.path.basename(gl_file), 'gl_statement', user_id=user.get('username', 'system'))

        return FileResponse(
            gl_file,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if gl_file.endswith('.xlsx') else 'text/csv',
            filename=os.path.basename(gl_file),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GL statement download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download GL statement")


@router.get("/ttum")
async def download_ttum(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Package TTUM CSVs/XLSX for a run into a ZIP and return."""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        # Get TTUM files
        candidate_dirs = []
        out_ttum = os.path.join(OUTPUT_DIR, target, 'ttum')
        up_ttum = None
        run_folder = os.path.join(UPLOAD_DIR, target)
        for root_dir, dirs, files in os.walk(run_folder):
            if 'ttum' in dirs:
                up_ttum = os.path.join(root_dir, 'ttum')
                break
        if os.path.exists(out_ttum):
            candidate_dirs.append(out_ttum)
        if up_ttum and os.path.exists(up_ttum):
            candidate_dirs.append(up_ttum)

        if not candidate_dirs:
            raise HTTPException(status_code=404, detail="TTUM folder not found for run")

        ttum_dir = candidate_dirs[0]
        zip_path = os.path.join(ttum_dir, f"ttum_{target}.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fname in os.listdir(ttum_dir):
                fp = os.path.join(ttum_dir, fname)
                if os.path.isfile(fp):
                    zf.write(fp, arcname=fname)

        # Set download flag
        try:
            meta_path = os.path.join(out_ttum, 'download_meta.json')
            os.makedirs(out_ttum, exist_ok=True)
            with open(meta_path, 'w') as mf:
                json.dump({
                    'is_downloaded': True,
                    'downloaded_at': datetime.utcnow().isoformat(),
                    'downloaded_by': user.get('username', 'unknown'),
                }, mf, indent=2)
        except Exception:
            pass

        return FileResponse(zip_path, media_type='application/zip', filename=os.path.basename(zip_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTUM download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to prepare TTUM files")


@router.get("/ttum/csv")
async def download_ttum_csv(user: dict = Depends(get_current_user), run_id: Optional[str] = None, cycle_id: Optional[str] = None):
    """Download TTUM data in CSV format (all files zipped if multiple cycles).
    Sets a persistent is_downloaded flag.
    """
    try:
        # Default to latest run
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target_run = run_id if run_id else sorted(runs)[-1]

        # Get TTUM files from output directory
        ttum_files = get_ttum_files(target_run, cycle_id, format='csv')

        logger.info(f"TTUM CSV files found for run {target_run}: {ttum_files}")

        if not ttum_files:
            raise HTTPException(status_code=404, detail="No TTUM CSV files found")

        # Check file existence and sizes
        for fp in ttum_files:
            if os.path.exists(fp):
                size = os.path.getsize(fp)
                logger.info(f"TTUM file exists: {fp}, size: {size} bytes")
                # Log first few lines to verify content
                try:
                    with open(fp, 'r', encoding='utf-8-sig') as f:
                        lines = []
                        for i, line in enumerate(f):
                            if i >= 5:  # First 5 lines
                                break
                            lines.append(repr(line.strip()))
                        logger.info(f"TTUM file content preview: {lines}")
                except Exception as e:
                    logger.error(f"Error reading TTUM file content: {e}")
            else:
                logger.error(f"TTUM file missing: {fp}")

        # If only one file, return it directly
        if len(ttum_files) == 1:
            ttum_file = ttum_files[0]
            filename = os.path.basename(ttum_file)

            # Mark download
            try:
                meta_path = os.path.join(os.path.dirname(ttum_file), 'download_meta.json')
                with open(meta_path, 'w') as mf:
                    json.dump({
                        'is_downloaded': True,
                        'downloaded_at': datetime.utcnow().isoformat(),
                        'downloaded_by': user.get('username', 'unknown'),
                    }, mf, indent=2)
            except Exception:
                pass

            return FileResponse(ttum_file, media_type='text/csv', filename=filename)

        # Multiple files - zip them
        zip_path = os.path.join(OUTPUT_DIR, target_run, f"ttum_csv_{target_run}.zip")
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in ttum_files:
                zf.write(file_path, arcname=os.path.basename(file_path))

        # Mark download
        try:
            meta_path = os.path.join(OUTPUT_DIR, target_run, 'ttum', 'download_meta.json')
            os.makedirs(os.path.dirname(meta_path), exist_ok=True)
            with open(meta_path, 'w') as mf:
                json.dump({
                    'is_downloaded': True,
                    'downloaded_at': datetime.utcnow().isoformat(),
                    'downloaded_by': user.get('username', 'unknown'),
                }, mf, indent=2)
        except Exception:
            pass

        return FileResponse(zip_path, media_type='application/zip', filename=os.path.basename(zip_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTUM CSV download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download TTUM CSV files")

@router.get("/ttum/xlsx")
async def download_ttum_xlsx(user: dict = Depends(get_current_user), run_id: Optional[str] = None, cycle_id: Optional[str] = None):
    """Download TTUM data in XLSX format (all files zipped if multiple cycles).
    Sets a persistent is_downloaded flag.
    """
    try:
        # Default to latest run
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target_run = run_id if run_id else sorted(runs)[-1]

        # Get TTUM files from output directory
        ttum_files = get_ttum_files(target_run, cycle_id, format='xlsx')

        logger.info(f"TTUM XLSX files found for run {target_run}: {ttum_files}")

        if not ttum_files:
            raise HTTPException(status_code=404, detail="No TTUM XLSX files found")

        # If only one file, return it directly
        if len(ttum_files) == 1:
            ttum_file = ttum_files[0]
            filename = os.path.basename(ttum_file)

            # Mark download
            try:
                meta_path = os.path.join(os.path.dirname(ttum_file), 'download_meta.json')
                with open(meta_path, 'w') as mf:
                    json.dump({
                        'is_downloaded': True,
                        'downloaded_at': datetime.utcnow().isoformat(),
                        'downloaded_by': user.get('username', 'unknown'),
                    }, mf, indent=2)
            except Exception:
                pass

            return FileResponse(
                ttum_file,
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                filename=filename,
            )

        # Multiple files - zip them
        zip_path = os.path.join(OUTPUT_DIR, target_run, f"ttum_xlsx_{target_run}.zip")
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in ttum_files:
                zf.write(file_path, arcname=os.path.basename(file_path))

        # Mark download
        try:
            meta_path = os.path.join(OUTPUT_DIR, target_run, 'ttum', 'download_meta.json')
            os.makedirs(os.path.dirname(meta_path), exist_ok=True)
            with open(meta_path, 'w') as mf:
                json.dump({
                    'is_downloaded': True,
                    'downloaded_at': datetime.utcnow().isoformat(),
                    'downloaded_by': user.get('username', 'unknown'),
                }, mf, indent=2)
        except Exception:
            pass

        return FileResponse(zip_path, media_type='application/zip', filename=os.path.basename(zip_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTUM XLSX download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download TTUM XLSX files")


@router.get("/ttum/merged")
async def download_ttum_merged(
    user: dict = Depends(get_current_user),
    run_id: Optional[str] = None,
    format: str = Query('xlsx', regex='^(csv|xlsx)$'),
):
    """Download all TTUM data merged into a single file (CSV or XLSX)"""
    try:
        # Default to latest run
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target_run = run_id if run_id else sorted(runs)[-1]

        from services.reporting import get_ttum_files
        ttum_files = get_ttum_files(target_run, format='all')

        if not ttum_files:
            raise HTTPException(status_code=404, detail="No TTUM files found")

        # Read all JSON/CSV files and merge
        import csv as csv_module
        all_rows = []
        all_headers = set()

        for file_path in ttum_files:
            try:
                if file_path.endswith('.json'):
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            all_rows.extend(data)
                            for row in data:
                                if isinstance(row, dict):
                                    all_headers.update(row.keys())
                elif file_path.endswith('.csv'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        reader = csv_module.DictReader(f)
                        for row in reader:
                            all_rows.append(row)
                            all_headers.update(row.keys())
            except Exception as e:
                logger.warning(f"Error reading TTUM file {file_path}: {e}")
                continue

        if not all_rows:
            raise HTTPException(status_code=404, detail="No TTUM data found")

        # Prepare output
        headers = sorted(list(all_headers))

        if format.lower() == 'xlsx':
            from services.reporting import write_ttum_xlsx
            out_path = write_ttum_xlsx(
                target_run,
                None,
                f"TTUM_MERGED_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                headers,
                all_rows,
            )
            return FileResponse(
                out_path,
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                filename=os.path.basename(out_path),
            )
        # csv
        from services.reporting import write_ttum_csv
        out_path = write_ttum_csv(
            target_run,
            None,
            f"TTUM_MERGED_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            headers,
            all_rows,
        )
        return FileResponse(out_path, media_type='text/csv', filename=os.path.basename(out_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTUM merged download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create merged TTUM file")

@router.get("/unmatched")
async def get_unmatched_report(user: dict = Depends(get_current_user)):
    """Get unmatched transactions report with proper format for frontend"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        latest = sorted(runs)[-1]

        # First check OUTPUT_DIR (UPI results)
        recon_out = os.path.join(OUTPUT_DIR, latest, 'recon_output.json')
        if os.path.exists(recon_out):
            with open(recon_out, 'r') as f:
                data = json.load(f)

            # Extract unmatched from UPI format
            if isinstance(data, dict) and 'exceptions' in data:
                # UPI format - return exceptions as array for easier frontend processing
                exceptions_list = data.get('exceptions', [])

                # Ensure exceptions have direction field for frontend filtering
                for exc in exceptions_list:
                    if 'direction' not in exc and 'debit_credit' in exc:
                        dr_cr = exc.get('debit_credit', '').strip().upper()
                        if dr_cr.startswith('C'):
                            exc['direction'] = 'INWARD'
                        elif dr_cr.startswith('D'):
                            exc['direction'] = 'OUTWARD'
                        else:
                            exc['direction'] = 'UNKNOWN'

                return JSONResponse(content={
                    "run_id": latest,
                    "data": exceptions_list,
                    "format": "upi_array",
                    "summary": data.get('summary', {}),
                    "total_exceptions": len(exceptions_list),
                })

        # Check for legacy format (RRN keyed dict)
        run_root = os.path.join(UPLOAD_DIR, latest)
        recon_out = None
        for root_dir, dirs, files in os.walk(run_root):
            if 'recon_output.json' in files:
                recon_out = os.path.join(root_dir, 'recon_output.json')
                break

        if recon_out and os.path.exists(recon_out):
            with open(recon_out, 'r') as f:
                data = json.load(f)

            # Convert legacy RRN dict to exceptions array
            exceptions_list = []
            if isinstance(data, dict):
                for rrn, record in data.items():
                    if isinstance(record, dict) and record.get('status') in ['HANGING', 'PARTIAL_MATCH', 'MISMATCH', 'PARTIAL_MISMATCH']:
                        # Determine source and get data
                        source_data = None
                        source = 'UNKNOWN'
                        if record.get('cbs'):
                            source_data = record['cbs']
                            source = 'CBS'
                        elif record.get('switch'):
                            source_data = record['switch']
                            source = 'SWITCH'
                        elif record.get('npci'):
                            source_data = record['npci']
                            source = 'NPCI'

                        if source_data:
                            exc = {
                                'rrn': rrn,
                                'amount': source_data.get('amount', 0),
                                'date': source_data.get('date', ''),
                                'reference': source_data.get('reference', ''),
                                'debit_credit': source_data.get('dr_cr', ''),
                                'exception_type': record.get('status', 'UNKNOWN'),
                                'source': source,
                            }
                            exceptions_list.append(exc)

            return JSONResponse(content={
                "run_id": latest,
                "data": exceptions_list,
                "format": "upi_array",
                "summary": {},
                "total_exceptions": len(exceptions_list),
            })

        raise HTTPException(status_code=404, detail="Reconciliation output not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get unmatched report error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve unmatched report")


@router.get("/matched")
async def download_matched_reports(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Package pairwise matched CSVs into a ZIP and return. Supports OUTPUT_DIR-first (UPI) and legacy."""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        # Prefer OUTPUT_DIR/<run>/reports
        out_reports = os.path.join(OUTPUT_DIR, target, 'reports')
        reports_dir = None
        if os.path.exists(out_reports):
            reports_dir = out_reports
        else:
            # legacy UPLOAD_DIR fallback
            run_folder = os.path.join(UPLOAD_DIR, target)
            for root_dir, dirs, files in os.walk(run_folder):
                if 'reports' in dirs:
                    reports_dir = os.path.join(root_dir, 'reports')
                    break

        if not reports_dir or not os.path.exists(reports_dir):
            raise HTTPException(status_code=404, detail="Reports directory not found for run")

        matched_files = [f for f in os.listdir(reports_dir) if any(x in f.lower() for x in ('gl_vs_switch', 'switch_vs_npci', 'gl_vs_npci', 'gl_switch', 'switch_npci', 'gl_npci', 'matched')) and f.endswith('.csv')]
        if not matched_files:
            raise HTTPException(status_code=404, detail="No matched reports found for run")

        zip_path = os.path.join(reports_dir, f"matched_reports_{target}.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fname in matched_files:
                fp = os.path.join(reports_dir, fname)
                if os.path.isfile(fp):
                    zf.write(fp, arcname=fname)

        return FileResponse(zip_path, media_type='application/zip', filename=os.path.basename(zip_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Matched reports download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to prepare matched reports")


@router.get("/available")
async def get_available_reports(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """List all available reports for a run"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        available_reports = {
            "json": [],
            "csv": [],
            "other": [],
        }

        # Check OUTPUT_DIR (UPI format)
        output_dir = os.path.join(OUTPUT_DIR, target, 'reports')
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if f.endswith('.csv'):
                    available_reports["csv"].append(f)
                elif f.endswith('.json'):
                    available_reports["json"].append(f)
                else:
                    available_reports["other"].append(f)

        # Check UPLOAD_DIR
        upload_dir = os.path.join(UPLOAD_DIR, target)
        if os.path.exists(upload_dir):
            for root_dir, dirs, files in os.walk(upload_dir):
                for f in files:
                    if f.endswith('.csv'):
                        available_reports["csv"].append(f)
                    elif f.endswith('.json'):
                        available_reports["json"].append(f)
                    else:
                        available_reports["other"].append(f)

        # Remove duplicates
        available_reports["csv"] = sorted(list(set(available_reports["csv"])) )
        available_reports["json"] = sorted(list(set(available_reports["json"])) )
        available_reports["other"] = sorted(list(set(available_reports["other"])) )

        return JSONResponse(content={
            "run_id": target,
            "available_reports": available_reports,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Available reports error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list available reports")


@router.get("/summary")
async def download_summary(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Return summary for a run. For UPI, derives from OUTPUT_DIR/<run>/recon_output.json."""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        # Try UPI output first
        output_path = os.path.join(OUTPUT_DIR, target, 'recon_output.json')
        if os.path.exists(output_path):
            with open(output_path, 'r') as f:
                data = json.load(f)
            return JSONResponse(content={
                "run_id": target,
                "summary": data.get('summary', {}),
                "exceptions_count": len(data.get('exceptions', [])),
            })

        # Legacy fallback: summary.json
        run_root = os.path.join(UPLOAD_DIR, target)
        summary_path = None
        for root_dir, dirs, files in os.walk(run_root):
            if 'summary.json' in files:
                summary_path = os.path.join(root_dir, 'summary.json')
                break

        if summary_path and os.path.exists(summary_path):
            return FileResponse(summary_path, media_type='application/json', filename=os.path.basename(summary_path))

        raise HTTPException(status_code=404, detail='Summary not found for run')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summary download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve summary")

@router.get("/matched/csv")
async def download_matched_csv(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download matched report in CSV format."""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        reports_dir = os.path.join(OUTPUT_DIR, target, 'reports')
        if not os.path.exists(reports_dir):
            # legacy fallback
            run_folder = os.path.join(UPLOAD_DIR, target)
            for root_dir, dirs, files in os.walk(run_folder):
                if 'reports' in dirs:
                    reports_dir = os.path.join(root_dir, 'reports')
                    break

        if not reports_dir or not os.path.exists(reports_dir):
            raise HTTPException(status_code=404, detail="Reports directory not found for run")

        # Find a matched CSV
        matched_files = [f for f in os.listdir(reports_dir) if 'matched' in f.lower() and f.endswith('.csv')]
        if not matched_files:
            raise HTTPException(status_code=404, detail="No matched CSV found")

        matched_file = os.path.join(reports_dir, matched_files[0])
        return FileResponse(matched_file, media_type='text/csv', filename=os.path.basename(matched_file))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Matched CSV download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download matched CSV")


@router.get("/download/{report_key}")
async def download_report_by_key(
    report_key: str,
    user: dict = Depends(get_current_user),
    run_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    period: Optional[str] = None,
):
    """Download report by a stable report key used by the frontend."""
    try:
        target = resolve_run_id(run_id)
        path = None

        if report_key == "cbs_beneficiary_listing":
            path = generate_listing_report(target, "cbs_inward", direction="INWARD")
        elif report_key == "cbs_remitter_listing":
            path = generate_listing_report(target, "cbs_outward", direction="OUTWARD")
        elif report_key == "switch_listing_inward":
            path = generate_listing_report(target, "switch", direction="INWARD")
        elif report_key == "switch_listing_outward":
            path = generate_listing_report(target, "switch", direction="OUTWARD")
        elif report_key == "npci_beneficiary_listing":
            path = generate_listing_report(target, "npci_inward", direction="INWARD")
        elif report_key == "npci_remitter_listing":
            path = generate_listing_report(target, "npci_outward", direction="OUTWARD")
        elif report_key == "adjustment_report_listing":
            path = generate_adjustment_listing(target)
        elif report_key == "matched_transactions":
            path = generate_matched_transactions_report(target)
        elif report_key == "unmatched_transactions":
            path = generate_unmatched_transactions_report(target)
        elif report_key == "ttum_receivable_inward":
            path = generate_ttum_listing(target, "INWARD")
        elif report_key == "ttum_payable_outward":
            path = generate_ttum_listing(target, "OUTWARD")
        elif report_key == "switch_status_update":
            # Prefer generated switch update file in reports dir
            candidate = os.path.join(OUTPUT_DIR, target, "reports", "Switch_Update_File.csv")
            if os.path.exists(candidate):
                path = candidate
        elif report_key == "annexure_iv_tcc_ret":
            outputs = generate_annexure_iv_split(target)
            path = outputs.get("tcc_ret")
        elif report_key == "annexure_iv_drc_rrc":
            outputs = generate_annexure_iv_split(target)
            path = outputs.get("drc_rrc")
        elif report_key == "adjustment_report":
            candidate = os.path.join(OUTPUT_DIR, target, "reports", "ANNEXURE_III.csv")
            if os.path.exists(candidate):
                path = candidate
        elif report_key == "gl_justification":
            path = find_gl_statement(target)
        elif report_key == "mis_daily":
            path = generate_mis_report(target, "daily", date_from, date_to)
        elif report_key == "mis_weekly":
            path = generate_mis_report(target, "weekly", date_from, date_to)
        elif report_key == "mis_monthly":
            path = generate_mis_report(target, "monthly", date_from, date_to)
        elif report_key == "income_expense_datewise":
            path = generate_datewise_income_expense(target, date_from, date_to)
        elif report_key == "monthly_settlement_ntsl":
            path = generate_monthly_settlement_report(target)
        elif report_key == "ntsl_settlement_ttum_sponsor":
            path = generate_ntsl_settlement_ttum(target, "sponsor")
        elif report_key == "ntsl_settlement_ttum_submember":
            path = generate_ntsl_settlement_ttum(target, "submember")
        elif report_key == "dispute_tracker":
            path = generate_dispute_tracker(target)
        elif report_key == "rbi_reporting":
            path = generate_rbi_reporting(target)

        if not path or not os.path.exists(path):
            raise HTTPException(status_code=404, detail=f"Report '{report_key}' not found")

        media_type = "text/csv"
        if path.endswith(".xlsx"):
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return FileResponse(path, media_type=media_type, filename=os.path.basename(path))
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Download report by key error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download report")


@router.get("/{report_type:path}")
async def download_report_by_type(report_type: str, run_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Download specific report by type (legacy compatibility)."""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        # Search in OUTPUT_DIR and UPLOAD_DIR
        candidates = []
        output_dir = os.path.join(OUTPUT_DIR, target)
        if os.path.exists(output_dir):
            for root_dir, dirs, files in os.walk(output_dir):
                for f in files:
                    if report_type in f:
                        candidates.append(os.path.join(root_dir, f))

        if not candidates:
            upload_dir = os.path.join(UPLOAD_DIR, target)
            if os.path.exists(upload_dir):
                for root_dir, dirs, files in os.walk(upload_dir):
                    for f in files:
                        if report_type in f:
                            candidates.append(os.path.join(root_dir, f))

        if not candidates:
            raise HTTPException(status_code=404, detail=f"Report '{report_type}' not found")

        report_path = candidates[0]
        media_type = 'text/csv' if report_path.endswith('.csv') else 'application/json'
        return FileResponse(report_path, media_type=media_type, filename=os.path.basename(report_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download report error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download report")


@router.get("/unmatched/csv")
async def download_unmatched_csv(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download unmatched report in CSV format."""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        reports_dir = os.path.join(OUTPUT_DIR, target, 'reports')
        if not os.path.exists(reports_dir):
            # legacy fallback
            run_folder = os.path.join(UPLOAD_DIR, target)
            for root_dir, dirs, files in os.walk(run_folder):
                if 'reports' in dirs:
                    reports_dir = os.path.join(root_dir, 'reports')
                    break

        if not reports_dir or not os.path.exists(reports_dir):
            raise HTTPException(status_code=404, detail="Reports directory not found for run")

        # Find an unmatched CSV
        unmatched_files = [f for f in os.listdir(reports_dir) if 'unmatched' in f.lower() and f.endswith('.csv')]
        if not unmatched_files:
            raise HTTPException(status_code=404, detail="No unmatched CSV found")

        unmatched_file = os.path.join(reports_dir, unmatched_files[0])
        return FileResponse(unmatched_file, media_type='text/csv', filename=os.path.basename(unmatched_file))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unmatched CSV download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download unmatched CSV")

@router.get("/ageing")
async def download_ageing_reports(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download ageing reports (Unmatched_Inward_Ageing.csv and Unmatched_Outward_Ageing.csv)"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        # Try OUTPUT_DIR first (UPI format)
        output_dir = os.path.join(OUTPUT_DIR, target, 'reports')
        ageing_files = []
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if 'ageing' in f.lower() and f.endswith('.csv'):
                    ageing_files.append(os.path.join(output_dir, f))

        # Try UPLOAD_DIR if not found
        if not ageing_files:
            run_folder = os.path.join(UPLOAD_DIR, target)
            reports_dir = None
            for root_dir, dirs, files in os.walk(run_folder):
                if 'reports' in dirs:
                    reports_dir = os.path.join(root_dir, 'reports')
                    break

            if reports_dir and os.path.exists(reports_dir):
                for f in os.listdir(reports_dir):
                    if 'ageing' in f.lower() and f.endswith('.csv'):
                        ageing_files.append(os.path.join(reports_dir, f))

        if not ageing_files:
            raise HTTPException(status_code=404, detail="No ageing reports found")

        # If single file, return it directly
        if len(ageing_files) == 1:
            file_path = ageing_files[0]
            filename = os.path.basename(file_path)

            # Read file content
            with open(file_path, 'rb') as f:
                content = f.read()

            # Set appropriate headers
            headers = {}
            if filename.endswith('.xlsx'):
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:
                content_type = 'text/csv; charset=utf-8'

            headers['Content-Type'] = content_type
            headers['Content-Disposition'] = f'attachment; filename="{filename}"'

            return Response(content=content, headers=headers, media_type=content_type)

        # Multiple files - zip them
        zip_path = os.path.join(OUTPUT_DIR, target, f"ageing_reports_{target}.zip")
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in ageing_files:
                zf.write(file_path, arcname=os.path.basename(file_path))

        return FileResponse(zip_path, media_type='application/zip', filename=os.path.basename(zip_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download ageing reports error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download ageing reports")


@router.get("/hanging")
async def download_hanging_reports(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download hanging transaction reports (Hanging_Inward.csv and Hanging_Outward.csv)"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        # Try OUTPUT_DIR first (UPI format)
        output_dir = os.path.join(OUTPUT_DIR, target, 'reports')
        hanging_files = []
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if 'hanging' in f.lower() and f.endswith('.csv'):
                    hanging_files.append(os.path.join(output_dir, f))

        # Try UPLOAD_DIR if not found
        if not hanging_files:
            run_folder = os.path.join(UPLOAD_DIR, target)
            reports_dir = None
            for root_dir, dirs, files in os.walk(run_folder):
                if 'reports' in dirs:
                    reports_dir = os.path.join(root_dir, 'reports')
                    break

            if reports_dir and os.path.exists(reports_dir):
                for f in os.listdir(reports_dir):
                    if 'hanging' in f.lower() and f.endswith('.csv'):
                        hanging_files.append(os.path.join(reports_dir, f))

        if not hanging_files:
            raise HTTPException(status_code=404, detail="No hanging reports found")

        # If single file, return it directly
        if len(hanging_files) == 1:
            file_path = hanging_files[0]
            filename = os.path.basename(file_path)

            # Read file content
            with open(file_path, 'rb') as f:
                content = f.read()

            # Set appropriate headers
            headers = {}
            if filename.endswith('.xlsx'):
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:
                content_type = 'text/csv; charset=utf-8'

            headers['Content-Type'] = content_type
            headers['Content-Disposition'] = f'attachment; filename="{filename}"'

            return Response(content=content, headers=headers, media_type=content_type)

        # Multiple files - zip them
        zip_path = os.path.join(OUTPUT_DIR, target, f"hanging_reports_{target}.zip")
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in hanging_files:
                zf.write(file_path, arcname=os.path.basename(file_path))

        return FileResponse(zip_path, media_type='application/zip', filename=os.path.basename(zip_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download hanging reports error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download hanging reports")


@router.get("/switch-update")
async def download_switch_update_file(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download Switch Update File"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        # Try OUTPUT_DIR first (UPI format)
        output_dir = os.path.join(OUTPUT_DIR, target, 'reports')
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if 'switch_update' in f.lower() and f.endswith('.csv'):
                    file_path = os.path.join(output_dir, f)
                    filename = os.path.basename(file_path)

                    # Read file content
                    with open(file_path, 'rb') as file:
                        content = file.read()

                    # Set appropriate headers
                    headers = {}
                    if filename.endswith('.xlsx'):
                        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    else:
                        content_type = 'text/csv; charset=utf-8'

                    headers['Content-Type'] = content_type
                    headers['Content-Disposition'] = f'attachment; filename="{filename}"'

                    return Response(content=content, headers=headers, media_type=content_type)

        # Try UPLOAD_DIR
        run_folder = os.path.join(UPLOAD_DIR, target)
        reports_dir = None
        for root_dir, dirs, files in os.walk(run_folder):
            if 'reports' in dirs:
                reports_dir = os.path.join(root_dir, 'reports')
                break

        if reports_dir and os.path.exists(reports_dir):
            for f in os.listdir(reports_dir):
                if 'switch_update' in f.lower() and f.endswith('.csv'):
                    file_path = os.path.join(reports_dir, f)
                    filename = os.path.basename(file_path)

                    # Read file content
                    with open(file_path, 'rb') as file:
                        content = file.read()

                    # Set appropriate headers
                    headers = {}
                    if filename.endswith('.xlsx'):
                        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    else:
                        content_type = 'text/csv; charset=utf-8'

                    headers['Content-Type'] = content_type
                    headers['Content-Disposition'] = f'attachment; filename="{filename}"'

                    return Response(content=content, headers=headers, media_type=content_type)

        raise HTTPException(status_code=404, detail="Switch Update File not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download switch update file error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download Switch Update File")

@router.get("/annexure")
async def download_annexure_reports(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download Annexure IV reports"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        annexure_files = []

        # Try OUTPUT_DIR first (UPI format)
        output_dir = os.path.join(OUTPUT_DIR, target)
        if os.path.exists(output_dir):
            for root_dir, dirs, files in os.walk(output_dir):
                for f in files:
                    if 'annexure' in f.lower() and f.endswith('.csv'):
                        annexure_files.append(os.path.join(root_dir, f))

        # Try UPLOAD_DIR if not found
        if not annexure_files:
            run_folder = os.path.join(UPLOAD_DIR, target)
            for root_dir, dirs, files in os.walk(run_folder):
                for f in files:
                    if 'annexure' in f.lower() and f.endswith('.csv'):
                        annexure_files.append(os.path.join(root_dir, f))

        if not annexure_files:
            raise HTTPException(status_code=404, detail="No Annexure reports found")

        # If single file, return it directly
        if len(annexure_files) == 1:
            file_path = annexure_files[0]
            filename = os.path.basename(file_path)

            # Read file content
            with open(file_path, 'rb') as f:
                content = f.read()

            # Set appropriate headers
            headers = {}
            if filename.endswith('.xlsx'):
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:
                content_type = 'text/csv; charset=utf-8'

            headers['Content-Type'] = content_type
            headers['Content-Disposition'] = f'attachment; filename="{filename}"'

            return Response(content=content, headers=headers, media_type=content_type)

        # Multiple files - zip them
        zip_path = os.path.join(OUTPUT_DIR, target, f"annexure_reports_{target}.zip")
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in annexure_files:
                zf.write(file_path, arcname=os.path.basename(file_path))

        return FileResponse(zip_path, media_type='application/zip', filename=os.path.basename(zip_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download annexure reports error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download Annexure reports")


@router.get("/all")
async def download_all_reports(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download all generated reports in a single ZIP file"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        zip_path = os.path.join(OUTPUT_DIR, target, f"all_reports_{target}.zip")
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add reports from OUTPUT_DIR
            output_dir = os.path.join(OUTPUT_DIR, target)
            if os.path.exists(output_dir):
                for root_dir, dirs, files in os.walk(output_dir):
                    for f in files:
                        if f.endswith(('.csv', '.json', '.txt')) and not f.startswith('all_reports_'):
                            rel_path = os.path.relpath(os.path.join(root_dir, f), output_dir)
                            zf.write(os.path.join(root_dir, f), arcname=rel_path)

            # Add reports from UPLOAD_DIR if not already included
            run_folder = os.path.join(UPLOAD_DIR, target)
            if os.path.exists(run_folder):
                for root_dir, dirs, files in os.walk(run_folder):
                    for f in files:
                        if f.endswith(('.csv', '.json', '.txt')):
                            rel_path = os.path.relpath(os.path.join(root_dir, f), run_folder)
                            # Avoid duplicates
                            if rel_path not in zf.namelist():
                                zf.write(os.path.join(root_dir, f), arcname=f"upload_dir/{rel_path}")

        return FileResponse(zip_path, media_type='application/zip', filename=os.path.basename(zip_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download all reports error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download all reports")
