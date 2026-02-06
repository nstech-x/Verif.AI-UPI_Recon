import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from config import OUTPUT_DIR, UPLOAD_DIR
from core.security import get_current_user
from dependencies import audit, rollback_manager
from managers.rollback_manager import RollbackLevel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["rollback"])


@router.post("/recon/rollback")
async def api_recon_rollback(request: Request, user: dict = Depends(get_current_user)):
    """API wrapper to trigger rollback operations via `RollbackManager`"""
    try:
        payload = await request.json()
        run_id = payload.get('run_id')
        level = payload.get('level')
        params = payload.get('params', {})

        if not run_id or not level:
            raise HTTPException(status_code=400, detail="run_id and level are required")

        # Map level string to RollbackLevel
        try:
            rl = RollbackLevel(level)
        except Exception:
            # allow value names
            try:
                rl = RollbackLevel[level]
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid rollback level")

        # Call the appropriate rollback
        if rl == RollbackLevel.INGESTION:
            result = rollback_manager.ingestion_rollback(run_id, params.get('failed_filename', ''), params.get('validation_error', ''))
        elif rl == RollbackLevel.MID_RECON:
            result = rollback_manager.mid_recon_rollback(run_id, params.get('error_message', ''), affected_transactions=params.get('affected_transactions'))
        elif rl == RollbackLevel.CYCLE_WISE:
            result = rollback_manager.cycle_wise_rollback(run_id, params.get('cycle_id', ''))
        elif rl == RollbackLevel.ACCOUNTING:
            result = rollback_manager.accounting_rollback(run_id, params.get('reason', ''), voucher_ids=params.get('voucher_ids'))
        elif rl == RollbackLevel.WHOLE_PROCESS:
            result = rollback_manager.whole_process_rollback(run_id, params.get('reason', ''))
        else:
            raise HTTPException(status_code=400, detail="Unsupported rollback level via API")

        # Audit
        try:
            audit.log_rollback_operation(run_id, rl.value, user_id='system', details={'api_call': True})
        except Exception:
            pass

        return JSONResponse(content={"status": "ok", "result": result})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rollback API error: {e}")
        raise HTTPException(status_code=500, detail="Rollback operation failed")


@router.get("/rollback/history")
async def get_rollback_history(run_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Get rollback history for a run or all runs"""
    try:
        # Look for rollback_history.json in OUTPUT_DIR
        history_path = os.path.join(OUTPUT_DIR, "rollback_history.json")

        if not os.path.exists(history_path):
            # Return empty history if file doesn't exist
            return JSONResponse(content={"history": []})

        with open(history_path, 'r') as f:
            history_data = json.load(f)

        # Filter by run_id if provided
        if run_id:
            filtered_history = [item for item in history_data if item.get('run_id') == run_id]
            return JSONResponse(content={"run_id": run_id, "history": filtered_history})

        return JSONResponse(content={"history": history_data})

    except Exception as e:
        logger.error(f"Get rollback history error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve rollback history")


@router.post("/rollback/whole-process")
async def api_rollback_whole_process(run_id: Optional[str] = Query(None), reason: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    try:
        if not run_id or not reason:
            raise HTTPException(status_code=400, detail="run_id and reason are required")
        result = rollback_manager.whole_process_rollback(run_id, reason, confirmation_required=False)
        try:
            audit.log_rollback_operation(run_id, 'whole_process', user_id='system', details={'api_call': True})
        except Exception:
            pass
        return JSONResponse(content={"status": "ok", "result": result})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Whole-process rollback API error: {e}")
        raise HTTPException(status_code=500, detail="Rollback operation failed")


@router.post("/rollback/cycle-wise")
async def api_rollback_cycle_wise(run_id: Optional[str] = Query(None), cycle_id: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    try:
        if not run_id or not cycle_id:
            raise HTTPException(status_code=400, detail="run_id and cycle_id are required")

        # Clean up cycle_id in case it has date prefix (e.g., '20260106_1C' -> '1C')
        clean_cycle_id = cycle_id
        if '_' in cycle_id:
            # Take the last part after splitting by underscore (should be the cycle ID)
            clean_cycle_id = cycle_id.split('_')[-1]

        result = rollback_manager.cycle_wise_rollback(run_id, clean_cycle_id, confirmation_required=False)
        try:
            audit.log_rollback_operation(run_id, 'cycle_wise', user_id='system', details={'api_call': True, 'cycle_id': clean_cycle_id})
        except Exception:
            pass
        return JSONResponse(content={"status": "ok", "result": result})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cycle-wise rollback API error: {e}")
        raise HTTPException(status_code=500, detail="Rollback operation failed")


@router.post("/rollback/ingestion")
async def api_rollback_ingestion(run_id: Optional[str] = Query(None), filename: Optional[str] = Query(None), error: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    try:
        if not run_id or not filename:
            raise HTTPException(status_code=400, detail="run_id and filename are required")
        result = rollback_manager.ingestion_rollback(run_id, filename, validation_error=error or 'ingestion rollback')
        try:
            audit.log_rollback_operation(run_id, 'ingestion', user_id='system', details={'api_call': True, 'filename': filename})
        except Exception:
            pass
        return JSONResponse(content={"status": "ok", "result": result})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion rollback API error: {e}")
        raise HTTPException(status_code=500, detail="Rollback operation failed")


@router.post("/rollback/mid-recon")
async def api_rollback_mid_recon(run_id: Optional[str] = Query(None), error: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    try:
        if not run_id:
            raise HTTPException(status_code=400, detail="run_id is required")
        result = rollback_manager.mid_recon_rollback(run_id, error_message=error or 'mid-recon rollback', affected_transactions=None, confirmation_required=False)
        try:
            audit.log_rollback_operation(run_id, 'mid_recon', user_id='system', details={'api_call': True})
        except Exception:
            pass
        return JSONResponse(content={"status": "ok", "result": result})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mid-recon rollback API error: {e}")
        raise HTTPException(status_code=500, detail="Rollback operation failed")


@router.post("/rollback/accounting")
async def api_rollback_accounting(run_id: Optional[str] = Query(None), reason: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    try:
        if not run_id or not reason:
            raise HTTPException(status_code=400, detail="run_id and reason are required")
        result = rollback_manager.accounting_rollback(run_id, reason, voucher_ids=None, confirmation_required=False)
        try:
            audit.log_rollback_operation(run_id, 'accounting', user_id='system', details={'api_call': True})
        except Exception:
            pass
        return JSONResponse(content={"status": "ok", "result": result})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Accounting rollback API error: {e}")
        raise HTTPException(status_code=500, detail="Rollback operation failed")


@router.get('/rollback/available-cycles')
async def api_get_available_cycles(run_id: Optional[str] = Query(None)):
    try:
        if not run_id:
            raise HTTPException(status_code=400, detail='run_id is required')

        cycles = set()
        valid_cycles = ['1C', '2C', '3C', '4C', '5C', '6C', '7C', '8C', '9C', '10C']

        # Check in UPLOAD_DIR (where files are uploaded and organized by cycle)
        upload_base = os.path.join(UPLOAD_DIR, run_id)
        if os.path.exists(upload_base):
            for entry in os.listdir(upload_base):
                # Look for cycle_<id> folders
                if entry.startswith('cycle_'):
                    cycle_id = entry.split('cycle_', 1)[1]
                    # Remove date prefix if present (format: YYYYMMDD_CYCLE_ID)
                    if '_' in cycle_id:
                        cycle_id = cycle_id.split('_')[-1]
                    # Only add valid cycle IDs
                    if cycle_id in valid_cycles:
                        cycles.add(cycle_id)

        # Also check in OUTPUT_DIR for any additional cycles
        output_base = os.path.join(OUTPUT_DIR, run_id)
        if os.path.exists(output_base):
            for sub in ('reports', 'ttum', 'annexure', ''):
                path = os.path.join(output_base, sub) if sub else output_base
                if os.path.exists(path):
                    try:
                        for entry in os.listdir(path):
                            if entry.startswith('cycle_'):
                                # Extract cycle ID, removing any date prefix
                                cycle_id = entry.split('cycle_', 1)[1]
                                # Remove date prefix if present (format: YYYYMMDD_CYCLE_ID)
                                if '_' in cycle_id:
                                    cycle_id = cycle_id.split('_')[-1]
                                # Only add valid cycle IDs
                                if cycle_id in valid_cycles:
                                    cycles.add(cycle_id)
                    except (OSError, PermissionError):
                        continue

        available_cycles = sorted(list(cycles))
        return JSONResponse(content={
            'run_id': run_id,
            'status': 'success',
            'available_cycles': available_cycles,
            'total_available': len(available_cycles),
            'all_cycles': available_cycles,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get available cycles error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list available cycles")
