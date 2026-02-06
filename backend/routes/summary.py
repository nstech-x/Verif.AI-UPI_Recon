import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from config import OUTPUT_DIR, UPLOAD_DIR
from core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["summary"])


@router.get("/summary")
async def get_summary(user: dict = Depends(get_current_user)):
    """Get latest reconciliation summary (alias for /api/v1/recon/latest/summary)"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            return {
                "total_transactions": 0,
                "matched": 0,
                "unmatched": 0,
                "adjustments": 0,
                "status": "no_data",
                "run_id": None,
            }
        latest = sorted(runs)[-1]

        # First try OUTPUT_DIR for UPI reconciliation results (recon_output.json)
        output_path = os.path.join(OUTPUT_DIR, latest, 'recon_output.json')
        if os.path.exists(output_path):
            with open(output_path, 'r') as f:
                recon_data = json.load(f)

            # Transform UPI recon output to summary format
            summary_data = recon_data.get('summary', {})
            exceptions = recon_data.get('exceptions', [])
            details = recon_data.get('details', {})

            total_count = summary_data.get('total_cbs', 0) + summary_data.get('total_switch', 0) + summary_data.get('total_npci', 0)
            matched_count = summary_data.get('matched_cbs', 0) + summary_data.get('matched_switch', 0) + summary_data.get('matched_npci', 0)

            # Calculate unmatched from summary data, not just exceptions
            unmatched_count = (
                summary_data.get('unmatched_cbs', 0)
                + summary_data.get('unmatched_switch', 0)
                + summary_data.get('unmatched_npci', 0)
            )

            # Extract hanging transactions from switch breakdown
            switch_breakdown = details.get('switch_breakdown', {})
            hanging_count = switch_breakdown.get('HANGING', 0)

            return {
                "run_id": latest,
                "status": "completed",
                "totals": {
                    "count": total_count,
                    "amount": 0,
                },
                "matched": {
                    "count": matched_count,
                    "amount": 0,
                },
                "unmatched": {
                    "count": unmatched_count,
                    "amount": 0,
                },
                "hanging": {
                    "count": hanging_count,
                    "amount": 0,
                },
                "exceptions": {
                    "count": len(exceptions),
                    "amount": 0,
                },
                "inward": {
                    "count": summary_data.get('inflow_count', 0),
                    "amount": summary_data.get('inflow_amount', 0.0),
                },
                "outward": {
                    "count": summary_data.get('outflow_count', 0),
                    "amount": summary_data.get('outflow_amount', 0.0),
                },
                "breakdown": {
                    "cbs": {
                        "total": summary_data.get('total_cbs', 0),
                        "matched": summary_data.get('matched_cbs', 0),
                        "unmatched": summary_data.get('unmatched_cbs', 0),
                    },
                    "switch": {
                        "total": summary_data.get('total_switch', 0),
                        "matched": summary_data.get('matched_switch', 0),
                        "unmatched": summary_data.get('unmatched_switch', 0),
                        "hanging": hanging_count,
                    },
                    "npci": {
                        "total": summary_data.get('total_npci', 0),
                        "matched": summary_data.get('matched_npci', 0),
                        "unmatched": summary_data.get('unmatched_npci', 0),
                    },
                },
                "ttum_required": summary_data.get('ttum_required', 0),
            }

        # Fallback to UPLOAD_DIR for legacy summary.json
        run_root = os.path.join(UPLOAD_DIR, latest)
        summary_path = None
        for root_dir, dirs, files in os.walk(run_root):
            if 'summary.json' in files:
                summary_path = os.path.join(root_dir, 'summary.json')
                break

        if summary_path and os.path.exists(summary_path):
            with open(summary_path, 'r') as f:
                return json.load(f)

        return {
            "total_transactions": 0,
            "matched": 0,
            "unmatched": 0,
            "adjustments": 0,
            "status": "no_reconciliation_run",
            "run_id": latest,
        }

    except Exception as e:
        logger.error(f"Get summary error: {str(e)}")
        return {
            "total_transactions": 0,
            "matched": 0,
            "unmatched": 0,
            "adjustments": 0,
            "status": "error",
            "run_id": None,
        }


@router.get("/summary/historical")
async def get_historical_summary():
    """Get all historical reconciliation summaries"""
    try:
        historical_summaries = []
        # Note: This uses UPLOAD_DIR which might differ from file_handler.base_upload_dir
        for run_id in os.listdir(UPLOAD_DIR):
            if not run_id.startswith('RUN_'):
                continue
            run_folder = os.path.join(UPLOAD_DIR, run_id)
            try:
                # Extract date from run_id (RUN_YYYYMMDD_HHMMSS)
                date_part = run_id.split('_')[1] if len(run_id.split('_')) > 1 else ''
                month = f"{date_part[:4]}-{date_part[4:6]}" if len(date_part) >= 6 else ''

                # Try to read recon output from OUTPUT_DIR first (UPI), then UPLOAD_DIR (legacy)
                recon_output = None
                output_path = os.path.join(OUTPUT_DIR, run_id, 'recon_output.json')
                if os.path.exists(output_path):
                    with open(output_path, 'r') as f:
                        recon_output = json.load(f)
                else:
                    # Try nested in UPLOAD_DIR
                    for root_dir, dirs, files in os.walk(run_folder):
                        if 'recon_output.json' in files:
                            with open(os.path.join(root_dir, 'recon_output.json'), 'r') as f:
                                recon_output = json.load(f)
                            break

                if recon_output:
                    # Handle UPI format with 'summary' key
                    if isinstance(recon_output, dict) and 'summary' in recon_output:
                        summary_data = recon_output['summary']

                        # Calculate totals from individual sources (CBS, Switch, NPCI)
                        total_cbs = summary_data.get('total_cbs', 0)
                        total_switch = summary_data.get('total_switch', 0)
                        total_npci = summary_data.get('total_npci', 0)
                        all_txns = total_cbs + total_switch + total_npci

                        # Calculate matched transactions
                        matched_cbs = summary_data.get('matched_cbs', 0)
                        matched_switch = summary_data.get('matched_switch', 0)
                        matched_npci = summary_data.get('matched_npci', 0)
                        reconciled = matched_cbs + matched_switch + matched_npci

                        # Extract inflow/outflow data if available, otherwise estimate
                        inflow_count = summary_data.get('inflow_count', total_npci + total_cbs)
                        inflow_amount = summary_data.get('inflow_amount', 0.0)
                        outflow_count = summary_data.get('outflow_count', total_switch)
                        outflow_amount = summary_data.get('outflow_amount', 0.0)
                    else:
                        # Legacy format - no inflow/outflow data available
                        all_txns = len(recon_output) if isinstance(recon_output, dict) else 0
                        matched = sum(
                            1
                            for k, v in (
                                recon_output.items() if isinstance(recon_output, dict) else []
                            )
                            if isinstance(v, dict) and v.get('status') == 'MATCHED'
                        )
                        reconciled = matched
                        inflow_count = 0
                        inflow_amount = 0.0
                        outflow_count = 0
                        outflow_amount = 0.0

                    if month:
                        # Calculate match rate
                        match_rate = (reconciled / all_txns * 100) if all_txns > 0 else 0

                        historical_summaries.append({
                            "month": month,
                            "allTxns": all_txns,
                            "reconciled": reconciled,
                            "breaks": all_txns - reconciled,
                            "matchRate": round(match_rate, 1),
                            "inward": inflow_count,
                            "outward": outflow_count,
                        })
            except Exception as ex:
                logger.debug(f"Could not process run {run_id}: {ex}")
                continue

        return historical_summaries
    except Exception as e:
        logger.error(f"Get historical summary error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve historical summaries")
