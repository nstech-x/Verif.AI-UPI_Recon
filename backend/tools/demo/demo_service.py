"""
Demo Service for UPI Reconciliation Platform
Provides simulated data responses for demo mode
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Get demo data directory
DEMO_DATA_DIR = Path(__file__).parent / "demo_data"

def load_json(filename: str) -> Dict[str, Any]:
    """Load JSON data from demo_data directory"""
    filepath = DEMO_DATA_DIR / filename
    if not filepath.exists():
        return {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_dashboard_summary() -> Dict[str, Any]:
    """Get dashboard summary data"""
    return load_json("dashboard.json")

def get_transactions(filter_type: Optional[str] = None) -> Dict[str, Any]:
    """Get transaction data with optional filtering"""
    data = load_json("transactions.json")
    
    if filter_type:
        # Apply simple filtering
        if filter_type == "today":
            return data.get("today_breakup", {})
        elif filter_type == "unmatched":
            return {"transactions": data.get("unmatched_transactions", [])}
    
    return data

def get_disputes() -> Dict[str, Any]:
    """Get disputes data"""
    return load_json("disputes.json")

def get_watchlist() -> Dict[str, Any]:
    """Get watchlist data"""
    return load_json("watchlist.json")

def get_analytics() -> Dict[str, Any]:
    """Get analytics data"""
    return load_json("analytics.json")

def get_ai_insights() -> Dict[str, Any]:
    """Get AI insights data"""
    return load_json("ai_insights.json")

def get_blockchain_audit() -> Dict[str, Any]:
    """Get blockchain audit trail"""
    return load_json("blockchain_audit.json")

def get_maker_checker_data() -> Dict[str, Any]:
    """Get maker-checker workflow data"""
    return load_json("maker_checker.json")

def get_reports_catalog() -> Dict[str, Any]:
    """Get reports catalog"""
    return load_json("reports.json")

def update_maker_checker_status(approval_id: str, status: str, checker_user: str) -> Dict[str, Any]:
    """
    Simulate approval/rejection of pending items
    In real implementation, this would update database
    For demo, we just return success
    """
    return {
        "status": "success",
        "approval_id": approval_id,
        "new_status": status,
        "approved_by": checker_user,
        "message": f"Action {status} completed successfully (Demo Mode)"
    }

def add_to_watchlist(rrn: str, reason: str, priority: str = "medium") -> Dict[str, Any]:
    """
    Simulate adding transaction to watchlist
    For demo, we just return success
    """
    return {
        "status": "success",
        "rrn": rrn,
        "reason": reason,
        "priority": priority,
        "message": f"RRN {rrn} added to watchlist (Demo Mode)"
    }

def create_dispute(rrn: str, reason: str, amount: float) -> Dict[str, Any]:
    """
    Simulate creating a dispute
    For demo, we just return success
    """
    return {
        "status": "success",
        "dispute_id": f"DSP{len(load_json('disputes.json').get('disputes', [])) + 1:06d}",
        "rrn": rrn,
        "reason": reason,
        "amount": amount,
        "message": f"Dispute created for RRN {rrn} (Demo Mode)"
    }
