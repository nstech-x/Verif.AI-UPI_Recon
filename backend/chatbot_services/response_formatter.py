from typing import Dict, Optional, List


def format_transaction_response(transaction: Dict, run_id: str) -> Dict:
    """
    Format transaction data for API response.
    
    Args:
        transaction: Raw transaction dict from lookup.py
        run_id: Current reconciliation run ID
    
    Returns:
        Formatted response dict matching API spec
        
    Example:
        >>> txn = {"rrn": "123456789012", "status": "FULL_MATCH", ...}
        >>> format_transaction_response(txn, "RUN_20251125_001")
        {
            "rrn": "123456789012",
            "cbs": {...},
            "switch": {...},
            "npci": {...},
            "status": "FULL_MATCH",
            "direction": "OUTWARD"
        }
    """
    response = {
        "rrn": transaction.get("rrn"),
        "txn_id": transaction.get("txn_id"),
        "amount": transaction.get("amount"),
        "date": transaction.get("date"),
        "cbs": transaction.get("cbs", {"found": False}),
        "switch": transaction.get("switch", {"found": False}),
        "npci": transaction.get("npci", {"found": False}),
        "status": transaction.get("status"),
        "direction": transaction.get("direction"),
        "recon_run_id": run_id
    }
    
    return response


def format_not_found_response(
    identifier: str, 
    search_type: str, 
    run_id: str
) -> Dict:
    """
    Format error response when transaction not found.
    
    Args:
        identifier: The RRN or TXN_ID that was searched
        search_type: Either "rrn" or "txn_id"
        run_id: Current reconciliation run ID
    
    Returns:
        Error response dict with helpful suggestions
        
    Example:
        >>> format_not_found_response("999999999999", "rrn", "RUN_20251125_001")
        {
            "error": "Transaction not found",
            "query": {"rrn": "999999999999"},
            ...
        }
    """
    query_dict = {search_type: identifier}
    
    message = (
        f"No transaction found with {search_type.upper()} {identifier} "
        f"in reconciliation run {run_id}"
    )
    
    suggestions = [
        f"Check if the {search_type.upper()} is correct",
        "Try searching by RRN instead" if search_type == "txn_id" else "Try searching by transaction ID instead",
        "Verify the transaction was included in the latest reconciliation batch",
        "Contact support if this is a recent transaction"
    ]
    
    return {
        "error": "Transaction not found",
        "query": query_dict,
        "message": message,
        "recon_run_id": run_id,
        "suggestions": suggestions
    }


def format_validation_error(message: str, details: Optional[Dict] = None) -> Dict:
    """
    Format validation error response.
    
    Args:
        message: Error message describing the validation issue
        details: Optional dict with additional error details
    
    Returns:
        Validation error response dict
        
    Example:
        >>> format_validation_error("RRN must be 12 digits", {"provided": "12345"})
        {
            "error": "Validation error",
            "message": "RRN must be 12 digits",
            "details": {"provided": "12345"}
        }
    """
    response = {
        "error": "Validation error",
        "message": message
    }
    
    if details:
        response["details"] = details
    
    return response


def format_human_readable(transaction: Dict) -> str:
    """
    Create CLI-friendly text output for transaction.
    
    Args:
        transaction: Transaction dict
    
    Returns:
        Formatted string for console display
        
    Example:
        >>> print(format_human_readable(txn))
        ═══════════════════════════════════════
        Transaction: TXN001
        RRN: 123456789012
        ═══════════════════════════════════════
        ✅ CBS    : Found | ₹5000.00 | Dr | 2025-11-25
        ...
    """
    lines = []
    
    # Header
    lines.append("═" * 50)
    lines.append(f"Transaction: {transaction.get('txn_id', 'N/A')}")
    lines.append(f"RRN: {transaction.get('rrn', 'N/A')}")
    lines.append(f"Amount: ₹{transaction.get('amount', 0):.2f}")
    lines.append(f"Date: {transaction.get('date', 'N/A')}")
    lines.append("═" * 50)
    
    # CBS
    cbs = transaction.get("cbs", {})
    if cbs.get("found"):
        lines.append(
            f"✅ CBS    : Found | ₹{cbs.get('amount', 0):.2f} | "
            f"{cbs.get('dr_cr', 'N/A')} | {cbs.get('date', 'N/A')} | "
            f"RC: {cbs.get('rc', 'N/A')}"
        )
    else:
        lines.append("❌ CBS    : Not found")
    
    # Switch
    switch = transaction.get("switch", {})
    if switch.get("found"):
        lines.append(
            f"✅ Switch : Found | ₹{switch.get('amount', 0):.2f} | "
            f"{switch.get('tran_type', 'N/A')} | {switch.get('date', 'N/A')}"
        )
    else:
        lines.append("❌ Switch : Not found")
    
    # NPCI
    npci = transaction.get("npci", {})
    if npci.get("found"):
        lines.append(
            f"✅ NPCI   : Found | ₹{npci.get('amount', 0):.2f} | "
            f"{npci.get('date', 'N/A')}"
        )
    else:
        lines.append("❌ NPCI   : Not found")
    
    # Footer
    lines.append("═" * 50)
    lines.append(f"Status    : {transaction.get('status', 'UNKNOWN')}")
    lines.append(f"Direction : {transaction.get('direction', 'N/A')}")
    lines.append("═" * 50)
    
    return "\n".join(lines)


def format_error_response(error: Exception, context: str = "") -> Dict:
    """
    Format generic error response.
    
    Args:
        error: The exception that occurred
        context: Optional context about where error occurred
    
    Returns:
        Generic error response dict
    """
    return {
        "error": "Internal server error",
        "message": str(error),
        "context": context,
        "type": type(error).__name__
    }