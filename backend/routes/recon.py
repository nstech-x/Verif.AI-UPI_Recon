import json
import logging
import os
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from config import OUTPUT_DIR, UPLOAD_DIR
from core.rate_limit import rate_limiter
from core.security import get_current_user
from dependencies import audit, file_handler, recon_engine, upi_recon_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["reconciliation"])


class ReconRunRequest(BaseModel):
    run_id: Optional[str] = None  # Optional; if not provided, uses latest run


def _detect_upi_reconciliation(dataframes: List[pd.DataFrame]) -> bool:
    """Detect if this is a UPI reconciliation run based on file content"""
    upi_indicators = ['UPI_Tran_ID', 'Payer_PSP', 'Payee_PSP', 'Originating_Channel']

    for df in dataframes:
        if any(col in df.columns for col in upi_indicators):
            return True

        # Check for UPI-specific values in Tran_Type
        if 'Tran_Type' in df.columns:
            tran_types = df['Tran_Type'].astype(str).str.strip().str.upper()
            if any(tt in ['U2', 'U3'] for tt in tran_types.unique()):
                return True

    return False


def _extract_upi_dataframes(dataframes: List[pd.DataFrame]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Extract CBS, Switch, NPCI, and Adjustment dataframes for UPI reconciliation"""
    cbs_df = pd.DataFrame()
    switch_df = pd.DataFrame()
    npci_df = pd.DataFrame()
    adjustment_df = pd.DataFrame()

    for df in dataframes:
        # Get source column - handle both Series and string values
        source = ''
        if 'Source' in df.columns:
            source_val = df['Source'].iloc[0] if len(df) > 0 else ''
            source = str(source_val).upper() if source_val else ''

        if source == 'CBS':
            cbs_df = pd.concat([cbs_df, df], ignore_index=True)
        elif source == 'SWITCH':
            switch_df = pd.concat([switch_df, df], ignore_index=True)
        elif source == 'NPCI':
            npci_df = pd.concat([npci_df, df], ignore_index=True)
        elif source == 'ADJUSTMENT' or 'Adjtype' in df.columns:
            adjustment_df = pd.concat([adjustment_df, df], ignore_index=True)
        else:
            # Fallback: place into first empty slot based on order
            if cbs_df.empty:
                cbs_df = df.copy()
            elif switch_df.empty:
                switch_df = df.copy()
            elif npci_df.empty:
                npci_df = df.copy()

    return cbs_df, switch_df, npci_df, adjustment_df

@router.post("/recon/run")
async def run_reconciliation(
    run_request: ReconRunRequest,
    user: dict = Depends(get_current_user),
    _rl=Depends(rate_limiter),
):
    """Runs the reconciliation process for a given run_id or latest if not provided."""
    try:
        run_id = run_request.run_id

        # If run_id not provided, use the latest run
        if not run_id:
            runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
            if not runs:
                raise HTTPException(status_code=404, detail="No runs found")
            run_id = sorted(runs)[-1]  # Get latest run
            logger.info(f"Using latest run: {run_id}")

        run_root = os.path.join(UPLOAD_DIR, run_id)

        if not os.path.isdir(run_root):
            logger.error(f"Run ID not found: {run_id}")
            raise HTTPException(status_code=404, detail=f"Run ID '{run_id}' not found.")

        # locate the folder that actually contains uploaded files (may be nested by cycle/direction)
        run_folder = None
        for root_dir, dirs, files in os.walk(run_root):
            # prefer folder containing file_mapping.json or CSV files
            if 'file_mapping.json' in files or any(f.lower().endswith('.csv') for f in files):
                run_folder = root_dir
                break

        if not run_folder:
            # fallback to run_root
            run_folder = run_root

        # Load dataframes for reconciliation
        dataframes = file_handler.load_files_for_recon(run_folder)

        # Detect if this is a UPI reconciliation run (check for UPI-specific files)
        is_upi_run = _detect_upi_reconciliation(dataframes)

        # Run reconciliation using appropriate engine
        if is_upi_run:
            logger.info(f"Detected UPI files, using UPI reconciliation engine for {run_id}")
            # Extract UPI-specific dataframes
            cbs_df, switch_df, npci_df, adjustment_df = _extract_upi_dataframes(dataframes)
            results = upi_recon_engine.perform_upi_reconciliation(
                cbs_df,
                switch_df,
                npci_df,
                run_id,
                adjustment_df=adjustment_df,
            )

            # UPI engine outputs structured data - save it to OUTPUT_DIR
            try:
                output_run_dir = os.path.join(OUTPUT_DIR, run_id)
                os.makedirs(output_run_dir, exist_ok=True)
                recon_output_path = os.path.join(output_run_dir, "recon_output.json")
                with open(recon_output_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, default=str)
                logger.info(f"UPI reconciliation results saved to {recon_output_path}")

                # Generate CSV/XLSX reports from UPI results
                try:
                    logger.info(f"Generating UPI reports in {output_run_dir}")
                    recon_engine.generate_upi_report(results, output_run_dir, run_id=run_id)
                    logger.info(f"UPI reports generated successfully in {output_run_dir}/reports")
                except Exception as e:
                    logger.error(f"Could not generate UPI CSV reports: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Failed to save UPI results: {e}")
        else:
            logger.info(f"Using standard reconciliation engine for {run_id}")
            results = recon_engine.reconcile(dataframes)

            # Generate reports for legacy format
            recon_engine.generate_report(results, run_folder, run_id=run_id)
            recon_engine.generate_adjustments_csv(results, run_folder)
            recon_engine.generate_unmatched_ageing(results, run_folder)

        # Generate TTUMs and GL statements (only for legacy format for now)
        if not is_upi_run:
            try:
                recon_engine.settlement_engine.generate_vouchers_from_recon(results, run_id)
                # generate TTUM CSVs
                ttum_info = recon_engine.settlement_engine.generate_ttum_files(results, run_folder)
                # generate GL statement CSV
                gl_path = recon_engine.settlement_engine.generate_gl_statement(run_id, run_folder)
            except Exception:
                ttum_info = {}
                gl_path = ''

        # Audit
        audit.log_reconciliation_event(run_id, 'completed', user_id='system', matched_count=0, unmatched_count=0)
        # Log generated TTUM files
        try:
            for k, p in ttum_info.items():
                if isinstance(p, str):
                    audit.log_data_export(run_id, 'csv', 0, user_id='system')
        except Exception:
            pass

        logger.info(f"Reconciliation completed for {run_id}")

        # Prepare detailed summary response
        summary_response = {
            "run_id": run_id,
            "message": "Reconciliation complete and reports generated.",
            "status": "completed",
        }

        # Add UPI-specific details if available
        if is_upi_run:
            output_path = os.path.join(OUTPUT_DIR, run_id, 'recon_output.json')
            if os.path.exists(output_path):
                try:
                    with open(output_path, 'r') as f:
                        results = json.load(f)

                    # Extract comprehensive summary
                    summary = results.get('summary', {})
                    exceptions = results.get('exceptions', [])
                    ttum_candidates = results.get('ttum_candidates', [])

                    summary_response["details"] = summary
                    summary_response["unmatched_count"] = len(exceptions)
                    summary_response["matched_count"] = summary.get('matched_cbs', 0) + summary.get('matched_switch', 0) + summary.get('matched_npci', 0)
                    summary_response["ttum_required_count"] = summary.get('ttum_required', 0)
                    summary_response["ttum_candidates_count"] = len(ttum_candidates)

                    # Add breakdown by source
                    summary_response["breakdown"] = {
                        "cbs": {
                            "total": summary.get('total_cbs', 0),
                            "matched": summary.get('matched_cbs', 0),
                            "unmatched": summary.get('unmatched_cbs', 0),
                        },
                        "switch": {
                            "total": summary.get('total_switch', 0),
                            "matched": summary.get('matched_switch', 0),
                            "unmatched": summary.get('unmatched_switch', 0),
                        },
                        "npci": {
                            "total": summary.get('total_npci', 0),
                            "matched": summary.get('matched_npci', 0),
                            "unmatched": summary.get('unmatched_npci', 0),
                        },
                    }

                    # Add exception types summary
                    exception_types = {}
                    for exc in exceptions:
                        exc_type = exc.get('exception_type', 'UNKNOWN')
                        exception_types[exc_type] = exception_types.get(exc_type, 0) + 1
                    summary_response["exception_types"] = exception_types

                except Exception as e:
                    logger.warning(f"Could not extract details from results: {e}")

        return summary_response

    except Exception as e:
        logger.exception(f"Reconciliation run error for {run_request.run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Reconciliation failed")


@router.post("/recon/run-cycle")
async def run_reconciliation_for_cycle(
    run_id: str = Query(..., description="Run ID"),
    cycle_id: str = Query(..., description="Cycle ID"),
    user: dict = Depends(get_current_user),
):
    """Runs reconciliation for a specific cycle within a run (UPI mode only)"""
    try:
        # locate the cycle folder in UPLOAD_DIR
        run_root = os.path.join(UPLOAD_DIR, run_id)
        if not os.path.isdir(run_root):
            raise HTTPException(status_code=404, detail=f"Run ID '{run_id}' not found.")

        cycle_folder = None
        for root_dir, dirs, files in os.walk(run_root):
            if os.path.basename(root_dir).lower() == f"cycle_{cycle_id}".lower():
                cycle_folder = root_dir
                break

        if not cycle_folder:
            raise HTTPException(status_code=404, detail=f"Cycle {cycle_id} not found under run {run_id}")

        # Load dataframes
        dataframes = file_handler.load_files_for_recon(cycle_folder)

        # Only UPI engine supported here
        cbs_df, switch_df, npci_df, adjustment_df = _extract_upi_dataframes(dataframes)
        results = upi_recon_engine.perform_upi_reconciliation(
            cbs_df,
            switch_df,
            npci_df,
            run_id,
            adjustment_df=adjustment_df,
            cycle_id=cycle_id,
        )

        # Save results under OUTPUT_DIR/<run>/cycle_<id>/recon_output.json
        output_run_dir = os.path.join(OUTPUT_DIR, run_id, f"cycle_{cycle_id}")
        os.makedirs(output_run_dir, exist_ok=True)
        recon_output_path = os.path.join(output_run_dir, "recon_output.json")
        with open(recon_output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)

        return {
            "run_id": run_id,
            "cycle_id": cycle_id,
            "status": "completed",
            "message": f"Reconciliation completed for cycle {cycle_id}",
        }
    except Exception as e:
        logger.error(f"Cycle reconciliation error: {e}")
        raise HTTPException(status_code=500, detail="Cycle reconciliation failed")

@router.get("/recon/latest/summary")
async def get_latest_summary(user: dict = Depends(get_current_user)):
    """Get reconciliation summary for the latest run. Supports UPI (OUTPUT_DIR) and legacy (UPLOAD_DIR)."""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        latest = sorted(runs)[-1]

        # UPI-first: read OUTPUT_DIR/<run>/recon_output.json and return its summary
        upi_output = os.path.join(OUTPUT_DIR, latest, 'recon_output.json')
        if os.path.exists(upi_output):
            with open(upi_output, 'r') as f:
                data = json.load(f)
            return JSONResponse(content={
                "run_id": latest,
                "format": "upi",
                "summary": data.get('summary', {}),
                "exceptions_count": len(data.get('exceptions', [])),
            })

        # Legacy fallback as before
        run_root = os.path.join(UPLOAD_DIR, latest)
        summary_path = None
        report_path = None
        for root_dir, dirs, files in os.walk(run_root):
            if 'summary.json' in files:
                summary_path = os.path.join(root_dir, 'summary.json')
                break
            if 'report.txt' in files:
                report_path = os.path.join(root_dir, 'report.txt')
                break

        if summary_path and os.path.exists(summary_path):
            with open(summary_path, 'r') as f:
                return JSONResponse(content=json.load(f))
        if report_path and os.path.exists(report_path):
            with open(report_path, 'r') as f:
                return PlainTextResponse(content=f.read())
        raise HTTPException(status_code=404, detail="Summary not found for the latest run")

    except Exception as e:
        logger.error(f"Get summary error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve summary")


@router.get("/recon/latest/unmatched")
async def get_latest_unmatched(user: dict = Depends(get_current_user)):
    """Get unmatched transactions for the latest run (UPI format supported)"""
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
                    "format": "upi",
                    "unmatched": exceptions_list,
                    "count": len(exceptions_list),
                })

        # Legacy fallback: attempt to find unmatched report in UPLOAD_DIR
        run_root = os.path.join(UPLOAD_DIR, latest)
        unmatched_path = None
        for root_dir, dirs, files in os.walk(run_root):
            if 'unmatched.json' in files:
                unmatched_path = os.path.join(root_dir, 'unmatched.json')
                break

        if unmatched_path and os.path.exists(unmatched_path):
            with open(unmatched_path, 'r') as f:
                data = json.load(f)
            return JSONResponse(content={
                "run_id": latest,
                "format": "legacy",
                "unmatched": data,
                "count": len(data) if isinstance(data, list) else 0,
            })

        raise HTTPException(status_code=404, detail="Unmatched data not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get unmatched error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve unmatched transactions")


@router.get("/recon/latest/hanging")
async def get_latest_hanging(user: dict = Depends(get_current_user)):
    """Get hanging transactions for the latest run (UPI format supported)"""
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

            if isinstance(data, dict):
                # Extract hanging transactions (switch breakdown)
                details = data.get('details', {})
                switch_breakdown = details.get('switch_breakdown', {})
                hanging_count = switch_breakdown.get('HANGING', 0)

                # Filter exceptions where exception_type indicates hanging
                hanging_exceptions = []
                for exc in data.get('exceptions', []):
                    if isinstance(exc, dict):
                        exc_type = exc.get('exception_type', '')
                        if 'HANGING' in exc_type.upper():
                            hanging_exceptions.append(exc)

                return JSONResponse(content={
                    "run_id": latest,
                    "format": "upi",
                    "hanging_count": hanging_count,
                    "hanging": hanging_exceptions,
                })

        # Legacy fallback: no dedicated hanging data
        raise HTTPException(status_code=404, detail="Hanging data not available for legacy format")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get hanging error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve hanging transactions")


@router.get("/recon/latest/report")
async def get_latest_report(user: dict = Depends(get_current_user)):
    """Get the latest reconciliation report file"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        latest = sorted(runs)[-1]

        # First check OUTPUT_DIR (for UPI results)
        output_run_path = os.path.join(OUTPUT_DIR, latest)
        if os.path.exists(output_run_path):
            recon_output_path = os.path.join(output_run_path, "recon_output.json")
            if os.path.exists(recon_output_path):
                return FileResponse(recon_output_path, media_type='application/json', filename=f"recon_report_{latest}.json")

        # Then check UPLOAD_DIR (for legacy results)
        upload_run_path = os.path.join(UPLOAD_DIR, latest)
        report_path = None
        for root_dir, dirs, files in os.walk(upload_run_path):
            if 'report.txt' in files:
                report_path = os.path.join(root_dir, 'report.txt')
                break

        if report_path and os.path.exists(report_path):
            return FileResponse(report_path, media_type='text/plain', filename=f"recon_report_{latest}.txt")
        if os.path.exists(os.path.join(output_run_path, "recon_output.json")):
            return FileResponse(os.path.join(output_run_path, "recon_output.json"), media_type='application/json', filename=f"recon_report_{latest}.json")
        raise HTTPException(status_code=404, detail="Report not found for the latest run")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get latest report error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve report")


@router.get("/recon/latest/adjustments")
async def get_latest_adjustments(user: dict = Depends(get_current_user)):
    """Get adjustments for the latest run (UPI format supported)"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        latest = sorted(runs)[-1]

        recon_out = os.path.join(OUTPUT_DIR, latest, 'recon_output.json')
        if os.path.exists(recon_out):
            with open(recon_out, 'r') as f:
                data = json.load(f)

            adjustments = data.get('adjustments', [])
            return JSONResponse(content={
                "run_id": latest,
                "format": "upi",
                "adjustments": adjustments,
                "count": len(adjustments),
            })

        # Legacy fallback
        raise HTTPException(status_code=404, detail="Adjustments not available for legacy format")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get adjustments error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve adjustments")

@router.get("/recon/latest/raw")
async def get_latest_raw_data(user: dict = Depends(get_current_user)):
    """Get raw reconciliation data for the latest run"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        latest = sorted(runs)[-1]

        # First check OUTPUT_DIR (UPI results)
        recon_out = os.path.join(OUTPUT_DIR, latest, 'recon_output.json')

        if not os.path.exists(recon_out):
            # Then check UPLOAD_DIR (legacy results)
            run_root = os.path.join(UPLOAD_DIR, latest)
            recon_out = None
            for root_dir, dirs, files in os.walk(run_root):
                if 'recon_output.json' in files:
                    recon_out = os.path.join(root_dir, 'recon_output.json')
                    break

        if not recon_out or not os.path.exists(recon_out):
            raise HTTPException(status_code=404, detail="Reconciliation output not found")

        with open(recon_out, 'r') as f:
            data = json.load(f)

        # Handle UPI format (has 'summary' key)
        if isinstance(data, dict) and 'summary' in data:
            summary = data.get('summary', {})

            # First pass: count sources per RRN to determine PARTIAL_MATCH vs HANGING
            rrn_source_count = {}
            rrn_data = {}

            for exc in data.get('exceptions', []):
                if isinstance(exc, dict):
                    rrn = exc.get('rrn') or exc.get('RRN')
                    if rrn:
                        source = exc.get('source', '').lower()
                        if rrn not in rrn_source_count:
                            rrn_source_count[rrn] = set()
                            rrn_data[rrn] = exc  # Store one representative exception per RRN
                        rrn_source_count[rrn].add(source)

            logger.info(f"DEBUG: RRN source counts: {dict(rrn_source_count)}")

            # Convert exceptions array to RRN-keyed dict with full transaction details for ForceMatch
            exceptions_dict = {}
            for rrn, sources in rrn_source_count.items():
                exc = rrn_data[rrn]  # Use the representative exception data
                source_count = len(sources)

                # Determine status based on number of sources with data
                # PARTIAL_MATCH if exactly 2 sources have data, HANGING if only 1 source
                if source_count >= 2:  # Changed from == 2 to >= 2 to include all partial cases
                    status = 'PARTIAL_MATCH'
                else:
                    status = 'HANGING'

                logger.info(f"DEBUG: RRN {rrn} has {source_count} sources, status: {status}")

                # Build transaction object compatible with ForceMatch
                exception_type = exc.get('exception_type', '')
                main_source = exc.get('source', '').lower()

                transaction = {
                    'rrn': rrn,
                    'status': status,  # Use source-count-based status
                    'amount': exc.get('amount', 0),
                    'date': exc.get('date', ''),
                    'reference': exc.get('reference', ''),
                    'exception_type': exception_type,
                    'ttum_required': exc.get('ttum_required', False),
                    'ttum_type': exc.get('ttum_type', ''),
                    'source': main_source,
                    'sources_available': list(sources),
                }

                # Map all available source data to the transaction
                for src in sources:
                    # Find the exception record for this specific source
                    src_exc = None
                    for e in data.get('exceptions', []):
                        if e.get('rrn') == rrn and e.get('source', '').lower() == src:
                            src_exc = e
                            break

                    if src_exc:
                        if src == 'cbs':
                            transaction['cbs'] = {
                                'amount': src_exc.get('amount', 0),
                                'date': src_exc.get('date', ''),
                                'reference': src_exc.get('reference', ''),
                            }
                        elif src == 'switch':
                            transaction['switch'] = {
                                'amount': src_exc.get('amount', 0),
                                'date': src_exc.get('date', ''),
                                'reference': src_exc.get('reference', ''),
                            }
                        elif src == 'npci':
                            transaction['npci'] = {
                                'amount': src_exc.get('amount', 0),
                                'date': src_exc.get('date', ''),
                                'reference': src_exc.get('reference', ''),
                            }

                exceptions_dict[rrn] = transaction

            # Build response with summary and exceptions dict
            return JSONResponse(content={
                "run_id": latest,
                "format": "upi",
                "summary": summary,
                "exceptions": exceptions_dict,
                "exceptions_count": len(exceptions_dict),
            })

        # Legacy format: return raw data as-is
        return JSONResponse(content=data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get raw data error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve raw data")


@router.get('/recon/cycles/{run_id}')
async def get_run_cycles(run_id: str, user: dict = Depends(get_current_user)):
    """Get all cycles for a specific run"""
    try:
        cycles_info = []

        # Check in UPLOAD_DIR for cycle folders
        upload_base = os.path.join(UPLOAD_DIR, run_id)
        if os.path.exists(upload_base):
            for entry in os.listdir(upload_base):
                if entry.startswith('cycle_'):
                    cycle_id = entry.split('cycle_', 1)[1]
                    cycle_path = os.path.join(upload_base, entry)

                    # Get cycle metadata
                    metadata_path = os.path.join(cycle_path, 'metadata.json')
                    cycle_metadata = {}
                    if os.path.exists(metadata_path):
                        try:
                            with open(metadata_path, 'r') as f:
                                cycle_metadata = json.load(f)
                        except Exception:
                            pass

                    # Check if reconciliation has been run for this cycle
                    output_path = os.path.join(OUTPUT_DIR, run_id, entry, 'recon_output.json')
                    has_results = os.path.exists(output_path)

                    cycles_info.append({
                        'cycle_id': cycle_id,
                        'path': cycle_path,
                        'has_results': has_results,
                        'metadata': cycle_metadata,
                        'files_count': len([f for f in os.listdir(cycle_path) if f.endswith(('.csv', '.xlsx', '.txt'))]),
                    })

        return JSONResponse(content={
            'run_id': run_id,
            'cycles': cycles_info,
            'total_cycles': len(cycles_info),
        })
    except Exception as e:
        logger.error(f"Get run cycles error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get run cycles")


@router.get('/recon/cycle/{run_id}/{cycle_id}/summary')
async def get_cycle_summary(run_id: str, cycle_id: str, user: dict = Depends(get_current_user)):
    """Get summary for a specific cycle"""
    try:
        # Check for cycle-specific results
        output_path = os.path.join(OUTPUT_DIR, run_id, f"cycle_{cycle_id}", 'recon_output.json')

        if not os.path.exists(output_path):
            raise HTTPException(status_code=404, detail=f"No results found for cycle {cycle_id}")

        with open(output_path, 'r') as f:
            results = json.load(f)

        # Format response similar to main summary
        summary = results.get('summary', {})
        exceptions = results.get('exceptions', [])

        return JSONResponse(content={
            "run_id": run_id,
            "cycle_id": cycle_id,
            "status": "completed",
            "totals": {
                "count": summary.get('total_cbs', 0) + summary.get('total_switch', 0) + summary.get('total_npci', 0),
                "amount": 0,
            },
            "matched": {
                "count": summary.get('matched_cbs', 0) + summary.get('matched_switch', 0) + summary.get('matched_npci', 0),
                "amount": 0,
            },
            "unmatched": {
                "count": len(exceptions),
                "amount": 0,
            },
            "breakdown": {
                "cbs": {
                    "total": summary.get('total_cbs', 0),
                    "matched": summary.get('matched_cbs', 0),
                    "unmatched": summary.get('unmatched_cbs', 0),
                },
                "switch": {
                    "total": summary.get('total_switch', 0),
                    "matched": summary.get('matched_switch', 0),
                    "unmatched": summary.get('unmatched_switch', 0),
                },
                "npci": {
                    "total": summary.get('total_npci', 0),
                    "matched": summary.get('matched_npci', 0),
                    "unmatched": summary.get('unmatched_npci', 0),
                },
            },
            "ttum_required": summary.get('ttum_required', 0),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get cycle summary error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cycle summary")


@router.get('/recon/merge-cycles')
async def merge_cycles(run_id: str = Query(...), cycle_ids: str = Query(...), user: dict = Depends(get_current_user)):
    """Merge multiple cycles into a single consolidated view"""
    try:
        if not run_id:
            raise HTTPException(status_code=400, detail="run_id is required")

        if not cycle_ids:
            raise HTTPException(status_code=400, detail="cycle_ids is required (comma-separated)")

        # Parse cycle IDs
        cycles = [cid.strip() for cid in cycle_ids.split(',') if cid.strip()]

        if not cycles:
            raise HTTPException(status_code=400, detail="At least one cycle_id must be provided")

        merged_summary = {
            "run_id": run_id,
            "merged_cycles": cycles,
            "status": "completed",
            "totals": {"count": 0, "amount": 0},
            "matched": {"count": 0, "amount": 0},
            "unmatched": {"count": 0, "amount": 0},
            "breakdown": {
                "cbs": {"total": 0, "matched": 0, "unmatched": 0},
                "switch": {"total": 0, "matched": 0, "unmatched": 0},
                "npci": {"total": 0, "matched": 0, "unmatched": 0},
            },
            "ttum_required": 0,
            "cycle_summaries": [],
        }

        # Aggregate data from each cycle
        for cycle_id in cycles:
            output_path = os.path.join(OUTPUT_DIR, run_id, f"cycle_{cycle_id}", 'recon_output.json')

            if not os.path.exists(output_path):
                logger.warning(f"No results found for cycle {cycle_id}, skipping")
                continue

            try:
                with open(output_path, 'r') as f:
                    results = json.load(f)

                summary = results.get('summary', {})
                exceptions = results.get('exceptions', [])

                # Add to totals
                merged_summary["totals"]["count"] += summary.get('total_cbs', 0) + summary.get('total_switch', 0) + summary.get('total_npci', 0)
                merged_summary["matched"]["count"] += summary.get('matched_cbs', 0) + summary.get('matched_switch', 0) + summary.get('matched_npci', 0)
                merged_summary["unmatched"]["count"] += len(exceptions)

                # Add to breakdown
                for source in ['cbs', 'switch', 'npci']:
                    merged_summary["breakdown"][source]["total"] += summary.get(f'total_{source}', 0)
                    merged_summary["breakdown"][source]["matched"] += summary.get(f'matched_{source}', 0)
                    merged_summary["breakdown"][source]["unmatched"] += summary.get(f'unmatched_{source}', 0)

                merged_summary["ttum_required"] += summary.get('ttum_required', 0)

                # Store individual cycle summary
                merged_summary["cycle_summaries"].append({
                    "cycle_id": cycle_id,
                    "summary": summary,
                    "exception_count": len(exceptions),
                })

            except Exception as e:
                logger.warning(f"Error processing cycle {cycle_id}: {e}")
                continue

        return JSONResponse(content=merged_summary)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Merge cycles error: {e}")
        raise HTTPException(status_code=500, detail="Failed to merge cycles")


@router.get('/recon/compare-cycles')
async def compare_cycles(run_id: str = Query(...), cycle_ids: str = Query(...), user: dict = Depends(get_current_user)):
    """Compare reconciliation results across multiple cycles"""
    try:
        if not run_id:
            raise HTTPException(status_code=400, detail="run_id is required")

        if not cycle_ids:
            raise HTTPException(status_code=400, detail="cycle_ids is required (comma-separated)")

        # Parse cycle IDs
        cycles = [cid.strip() for cid in cycle_ids.split(',') if cid.strip()]

        if len(cycles) < 2:
            raise HTTPException(status_code=400, detail="At least two cycle_ids must be provided for comparison")

        comparison_data = {
            "run_id": run_id,
            "compared_cycles": cycles,
            "cycle_comparison": [],
            "summary_comparison": {
                "totals": {},
                "matched": {},
                "unmatched": {},
                "breakdown": {
                    "cbs": {},
                    "switch": {},
                    "npci": {},
                },
            },
        }

        # Collect data for each cycle
        cycle_data = {}
        for cycle_id in cycles:
            output_path = os.path.join(OUTPUT_DIR, run_id, f"cycle_{cycle_id}", 'recon_output.json')

            if not os.path.exists(output_path):
                logger.warning(f"No results found for cycle {cycle_id}, skipping")
                continue

            try:
                with open(output_path, 'r') as f:
                    results = json.load(f)

                summary = results.get('summary', {})
                exceptions = results.get('exceptions', [])

                cycle_data[cycle_id] = {
                    "summary": summary,
                    "exceptions": exceptions,
                    "metrics": {
                        "total_transactions": summary.get('total_cbs', 0) + summary.get('total_switch', 0) + summary.get('total_npci', 0),
                        "matched_transactions": summary.get('matched_cbs', 0) + summary.get('matched_switch', 0) + summary.get('matched_npci', 0),
                        "unmatched_transactions": len(exceptions),
                        "ttum_required": summary.get('ttum_required', 0),
                    },
                }

            except Exception as e:
                logger.warning(f"Error processing cycle {cycle_id}: {e}")
                continue

        # Build comparison data
        for cycle_id, data in cycle_data.items():
            comparison_data["cycle_comparison"].append({
                "cycle_id": cycle_id,
                "metrics": data["metrics"],
                "summary": data["summary"],
            })

        # Calculate differences and trends
        if len(cycle_data) >= 2:
            sorted_cycles = sorted(cycle_data.keys())
            for i in range(1, len(sorted_cycles)):
                current = sorted_cycles[i]
                previous = sorted_cycles[i - 1]

                curr_metrics = cycle_data[current]["metrics"]
                prev_metrics = cycle_data[previous]["metrics"]

                # Calculate differences
                differences = {
                    "cycle_comparison": f"{current}_vs_{previous}",
                    "total_diff": curr_metrics["total_transactions"] - prev_metrics["total_transactions"],
                    "matched_diff": curr_metrics["matched_transactions"] - prev_metrics["matched_transactions"],
                    "unmatched_diff": curr_metrics["unmatched_transactions"] - prev_metrics["unmatched_transactions"],
                    "ttum_diff": curr_metrics["ttum_required"] - prev_metrics["ttum_required"],
                }

                # Add to comparison data
                comparison_data.setdefault("differences", []).append(differences)

        return JSONResponse(content=comparison_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Compare cycles error: {e}")
        raise HTTPException(status_code=500, detail="Failed to compare cycles")
