import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from config import OUTPUT_DIR, UPLOAD_DIR
from core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["enquiry"])


@router.get("/enquiry")
async def enquiry(user: dict = Depends(get_current_user), rrn: str = Query(None), cycle: Optional[str] = Query(None), direction: Optional[str] = Query(None)):
    """Simple RRN enquiry across runs. Returns the first matching record."""
    try:
        if not rrn:
            raise HTTPException(status_code=400, detail="rrn query param required")

        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        runs = sorted(runs, reverse=True)
        for r in runs:
            run_folder = os.path.join(UPLOAD_DIR, r)
            recon_out = os.path.join(run_folder, 'recon_output.json')
            if not os.path.exists(recon_out):
                continue
            try:
                with open(recon_out, 'r') as f:
                    data = json.load(f)
            except Exception:
                continue

            if isinstance(data, dict) and not data.get('matched') and not data.get('unmatched'):
                if rrn in data:
                    return JSONResponse(content={"run_id": r, "record": data.get(rrn)})
            else:
                for rec in data.get('matched', []) + data.get('unmatched', []):
                    if isinstance(rec, dict) and (rec.get('rrn') == rrn or rec.get('RRN') == rrn):
                        return JSONResponse(content={"run_id": r, "record": rec})

        raise HTTPException(status_code=404, detail="RRN not found in recent runs")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enquiry error: {e}")
        raise HTTPException(status_code=500, detail="Failed to perform enquiry")


@router.get("/chatbot")
async def chatbot_lookup(
    rrn: Optional[str] = Query(None, description="12-digit Retrieval Reference Number"),
    txn_id: Optional[str] = Query(None, description="Transaction ID (e.g., TXN001)"),
    txd_id: Optional[str] = Query(None, description="Transaction ID (alias for txn_id)"),
):
    """Main chatbot endpoint - lookup transaction by RRN or Transaction ID."""
    try:
        # Handle txd_id alias
        if txd_id and not txn_id:
            txn_id = txd_id

        # Auto-detect: if txn_id is exactly 12 digits, treat as RRN
        if txn_id and len(txn_id) == 12 and txn_id.isdigit():
            rrn = txn_id
            txn_id = None

        # Step 1: Validate input - at least one parameter required
        if not rrn and not txn_id:
            return JSONResponse(status_code=400, content={
                "error": "Missing required parameter. Provide either 'rrn' or 'txn_id'",
                "details": {
                    "provided": {"rrn": None, "txn_id": None},
                    "required": "At least one of: rrn, txn_id",
                },
            })

        # Find the latest run
        runs = [d for d in os.listdir(OUTPUT_DIR) if d.startswith('RUN_') and os.path.isdir(os.path.join(OUTPUT_DIR, d))]
        if not runs:
            return JSONResponse(status_code=404, content={
                "error": "No reconciliation data available",
                "message": "Please run reconciliation first",
            })

        runs.sort(reverse=True)
        latest_run = runs[0]
        run_path = os.path.join(OUTPUT_DIR, latest_run, 'recon_output.json')

        if not os.path.exists(run_path):
            return JSONResponse(status_code=404, content={
                "error": "Reconciliation output not found",
                "message": f"File not found: {run_path}",
            })

        # Load the reconciliation data
        with open(run_path, 'r', encoding='utf-8') as f:
            recon_data = json.load(f)

        # Search through exceptions and ttum_candidates
        transaction = None
        search_source = None

        # Search in exceptions first
        if 'exceptions' in recon_data and isinstance(recon_data['exceptions'], list):
            for txn in recon_data['exceptions']:
                if isinstance(txn, dict):
                    txn_rrn = str(txn.get('rrn', ''))
                    txn_upi_id = str(txn.get('upi_tran_id', ''))

                    if rrn and txn_rrn == rrn:
                        transaction = txn
                        search_source = 'exceptions'
                        break
                    elif txn_id and txn_upi_id == txn_id:
                        transaction = txn
                        search_source = 'exceptions'
                        break

        # If not found in exceptions, search in ttum_candidates
        if not transaction and 'ttum_candidates' in recon_data and isinstance(recon_data['ttum_candidates'], list):
            for txn in recon_data['ttum_candidates']:
                if isinstance(txn, dict):
                    txn_rrn = str(txn.get('rrn', ''))
                    txn_upi_id = str(txn.get('upi_tran_id', ''))

                    if rrn and txn_rrn == rrn:
                        transaction = txn
                        search_source = 'ttum_candidates'
                        break
                    elif txn_id and txn_upi_id == txn_id:
                        transaction = txn
                        search_source = 'ttum_candidates'
                        break

        if not transaction:
            return JSONResponse(status_code=404, content={
                "error": "Transaction not found",
                "message": f"No transaction found with the specified {'RRN' if rrn else 'Transaction ID'}",
                "searched": {
                    "rrn": rrn,
                    "txn_id": txn_id,
                    "run_id": latest_run,
                    "sources_checked": ["exceptions", "ttum_candidates"],
                },
            })

        # Format and return the response
        formatted_response = {
            "rrn": transaction.get('rrn', rrn or txn_id),
            "run_id": latest_run,
            "search_source": search_source,
            "transaction_details": transaction,
            "summary": {
                "source": transaction.get('source'),
                "amount": transaction.get('amount'),
                "date": transaction.get('date'),
                "exception_type": transaction.get('exception_type'),
                "ttum_required": transaction.get('ttum_required'),
                "direction": transaction.get('direction'),
            },
        }

        return JSONResponse(content=formatted_response)

    except Exception as e:
        logger.error(f"Chatbot lookup error: {e}")
        return JSONResponse(status_code=500, content={
            "error": "Failed to lookup transaction",
            "details": str(e),
        })
