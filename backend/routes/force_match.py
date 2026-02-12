import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from config import OUTPUT_DIR, UPLOAD_DIR
from core.rate_limit import rate_limiter
from core.security import get_current_user
from dependencies import audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/force-match", tags=["force-match"])


# =====================
# Maker / Checker Force-Match Flow (file-backed proposals)
# =====================

def _proposal_store_path(run_id: str):
    return os.path.join(OUTPUT_DIR, f"{run_id}_proposals.json")


def _load_proposals(run_id: str):
    ppath = _proposal_store_path(run_id)
    try:
        if os.path.exists(ppath):
            with open(ppath, 'r') as pf:
                return json.load(pf)
    except Exception:
        return []
    return []


def _save_proposals(run_id: str, proposals):
    ppath = _proposal_store_path(run_id)
    try:
        with open(ppath, 'w') as pf:
            json.dump(proposals, pf, indent=2)
        return True
    except Exception:
        return False


def _latest_run_id() -> Optional[str]:
    runs = []
    try:
        runs.extend([d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')])
    except Exception:
        pass
    try:
        runs.extend([d for d in os.listdir(OUTPUT_DIR) if d.startswith('RUN_')])
    except Exception:
        pass
    if not runs:
        return None
    return sorted(set(runs))[-1]


def _find_recon_output_path(run_id: str) -> Optional[str]:
    # Prefer UPI output location
    out_path = os.path.join(OUTPUT_DIR, run_id, "recon_output.json")
    if os.path.exists(out_path):
        return out_path

    # Legacy fallback inside upload directory
    run_root = os.path.join(UPLOAD_DIR, run_id)
    if os.path.isdir(run_root):
        for root_dir, dirs, files in os.walk(run_root):
            if 'recon_output.json' in files:
                return os.path.join(root_dir, 'recon_output.json')
    return None


def _rrn_exists_in_recon(recon_data, rrn: str) -> bool:
    if not rrn:
        return False
    if isinstance(recon_data, dict):
        if 'exceptions' in recon_data:
            for exc in recon_data.get('exceptions', []):
                if exc.get('rrn') == rrn or exc.get('RRN') == rrn:
                    return True
        if rrn in recon_data:
            return True
    elif isinstance(recon_data, list):
        for rec in recon_data:
            if isinstance(rec, dict) and (rec.get('rrn') == rrn or rec.get('RRN') == rrn):
                return True
    return False


def _apply_force_match(recon_data, rrn: str, approved_by: str, proposal_id: Optional[str] = None):
    now = datetime.utcnow().isoformat()
    updated = False

    if isinstance(recon_data, dict) and 'exceptions' in recon_data:
        for exc in recon_data.get('exceptions', []):
            if exc.get('rrn') == rrn or exc.get('RRN') == rrn:
                exc['status'] = 'FORCE_MATCHED'
                exc['force_matched'] = True
                exc['force_match_approved_by'] = approved_by
                exc['force_match_approved_at'] = now
                if proposal_id:
                    exc['force_match_proposal_id'] = proposal_id
                updated = True
                break
    elif isinstance(recon_data, dict) and rrn in recon_data:
        recon_data[rrn]['status'] = 'FORCE_MATCHED'
        recon_data[rrn]['force_matched'] = True
        recon_data[rrn]['force_match_approved_by'] = approved_by
        recon_data[rrn]['force_match_approved_at'] = now
        if proposal_id:
            recon_data[rrn]['force_match_proposal_id'] = proposal_id
        updated = True
    elif isinstance(recon_data, list):
        for rec in recon_data:
            if isinstance(rec, dict) and (rec.get('rrn') == rrn or rec.get('RRN') == rrn):
                rec['status'] = 'FORCE_MATCHED'
                rec['force_matched'] = True
                rec['force_match_approved_by'] = approved_by
                rec['force_match_approved_at'] = now
                if proposal_id:
                    rec['force_match_proposal_id'] = proposal_id
                updated = True
                break

    return recon_data, updated


@router.get("/proposals")
async def get_force_match_proposals(run_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Get all force-match proposals for a run (or latest if not specified)"""
    try:
        if not run_id:
            run_id = _latest_run_id()
            if not run_id:
                raise HTTPException(status_code=404, detail="No runs found")

        proposals = _load_proposals(run_id)

        # Enrich proposals with transaction details from recon output
        for prop in proposals:
            prop_rrn = prop.get('rrn')
            try:
                # Try to get full transaction data
                recon_path = _find_recon_output_path(run_id)
                if recon_path:
                    with open(recon_path, 'r') as f:
                        recon_data = json.load(f)
                    if isinstance(recon_data, dict) and 'exceptions' in recon_data:
                        for exc in recon_data['exceptions']:
                            if exc.get('rrn') == prop_rrn:
                                prop['transaction_details'] = exc
                                break
            except Exception:
                pass  # If lookup fails, just return proposal as-is

        return JSONResponse(content={
            "run_id": run_id,
            "proposals": proposals,
            "total": len(proposals),
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get proposals error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve proposals")


@router.post("")
async def propose_force_match(request: Request, user: dict = Depends(get_current_user), _rl=Depends(rate_limiter)):
    """Maker proposes a force-match for an RRN. Saves proposal with status 'proposed'."""
    try:
        # Support JSON body, form, or query-params for flexibility in clients/tests
        payload = {}
        try:
            payload = await request.json()
            if payload is None:
                payload = {}
        except Exception:
            payload = {}

        if not payload:
            try:
                form = await request.form()
                payload = dict(form) if form else {}
            except Exception:
                payload = {}

        if not payload:
            payload = dict(request.query_params)
        rrn = payload.get('rrn')
        action = payload.get('action')
        direction = payload.get('direction')
        run_id = payload.get('run_id')
        reason = payload.get('reason', '')

        if not rrn or not action:
            raise HTTPException(status_code=400, detail='rrn and action are required')

        if not run_id:
            run_id = _latest_run_id()
            if not run_id:
                raise HTTPException(status_code=404, detail='No runs found')

        # Validate RRN exists in the reconciliation results
        recon_path = _find_recon_output_path(run_id)
        if not recon_path:
            raise HTTPException(status_code=404, detail=f'recon_output.json not found for run {run_id}')

        with open(recon_path, 'r') as f:
            recon_data = json.load(f)

        if not _rrn_exists_in_recon(recon_data, rrn):
            raise HTTPException(status_code=404, detail=f'RRN {rrn} not found in reconciliation results')

        # Legacy direct force-match flow used by frontend panel
        source1 = payload.get('source1')
        source2 = payload.get('source2')
        if source1 and source2:
            user_id = user.get('username', 'system')
            recon_data, updated = _apply_force_match(recon_data, rrn, approved_by=user_id, proposal_id=None)
            if not updated:
                raise HTTPException(status_code=404, detail=f'RRN {rrn} not found for force match update')
            with open(recon_path, 'w') as wf:
                json.dump(recon_data, wf, indent=2)
            try:
                audit.log_force_match(run_id, rrn, action, user_id=user_id, status='approved')
            except Exception:
                pass
            return JSONResponse(content={
                'status': 'success',
                'message': f'RRN {rrn} force matched between {source1} and {source2}',
                'action': action,
                'rrn': rrn
            })

        proposals = _load_proposals(run_id)
        prop_id = f"PROP_{int(time.time())}_{len(proposals)+1}"
        maker = user.get('username', 'unknown')
        proposal = {
            'proposal_id': prop_id,
            'rrn': rrn,
            'action': action,
            'direction': direction,
            'run_id': run_id,
            'reason': reason,
            'maker': maker,
            'status': 'proposed',
            'created_at': datetime.utcnow().isoformat(),
        }
        proposals.append(proposal)
        _save_proposals(run_id, proposals)

        # audit
        try:
            audit.log_force_match(run_id, rrn, action, user_id=maker, status='proposed')
        except Exception:
            pass

        return JSONResponse(content={'status': 'proposed', 'proposal_id': prop_id, 'rrn': rrn})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Force-match proposal error: {e}")
        raise HTTPException(status_code=500, detail='Failed to create proposal')


@router.post("/approve")
async def approve_force_match(request: Request, user: dict = Depends(get_current_user), _rl=Depends(rate_limiter)):
    """Checker approves a pending proposal. Enforces maker != checker."""
    try:
        payload = await request.json()
        proposal_id = payload.get('proposal_id')
        comments = payload.get('comments', '')

        if not proposal_id:
            raise HTTPException(status_code=400, detail='proposal_id is required')

        # find proposal across runs (scan OUTPUT_DIR)
        found = None
        for fname in os.listdir(OUTPUT_DIR):
            if fname.endswith('_proposals.json'):
                path = os.path.join(OUTPUT_DIR, fname)
                try:
                    with open(path, 'r') as pf:
                        proposals = json.load(pf)
                    for p in proposals:
                        if p.get('proposal_id') == proposal_id:
                            found = p
                            break
                except Exception:
                    continue
            if found:
                break

        if not found:
            raise HTTPException(status_code=404, detail='Proposal not found')

        checker = user.get('username', 'unknown')
        if checker == found.get('maker'):
            raise HTTPException(status_code=400, detail='Maker and checker must be different')

        # update proposal
        found['status'] = 'approved'
        found['checker'] = checker
        found['checker_comments'] = comments
        found['approved_at'] = datetime.utcnow().isoformat()

        # persist back
        proposals = _load_proposals(found.get('run_id'))
        for i, p in enumerate(proposals):
            if p.get('proposal_id') == proposal_id:
                proposals[i] = found
                break
        _save_proposals(found.get('run_id'), proposals)

        # apply change to recon_output.json (mark rrn FORCE_MATCHED)
        try:
            recon_path = _find_recon_output_path(found.get('run_id'))
            if recon_path and os.path.exists(recon_path):
                with open(recon_path, 'r') as rf:
                    ro = json.load(rf)
                ro, _ = _apply_force_match(ro, found.get('rrn'), approved_by=checker, proposal_id=found.get('proposal_id'))

                with open(recon_path, 'w') as wf:
                    json.dump(ro, wf, indent=2)
        except Exception as e:
            logger.warning(f"Failed to update recon_output.json: {e}")

        # audit
        try:
            audit.log_force_match(found.get('run_id'), found.get('rrn'), found.get('action'), user_id=checker, status='approved')
        except Exception:
            pass

        return JSONResponse(content={'status': 'approved', 'ttum_generated': True})

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Force-match approval error: {e}")
        raise HTTPException(status_code=500, detail='Failed to approve proposal')
