from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
from . import lookup
from . import nlp
from . import response_formatter
from . import reports_api

# Create FastAPI app
app = FastAPI(
    title="Transaction Chatbot API",
    description="Reconciliation lookup service for transaction queries by RRN or Transaction ID",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include the reports router
app.include_router(reports_api.router)


@app.on_event("startup")
async def startup_event():
    """
    Run on application startup.
    Check if data is loaded and print status.
    """
    if lookup.RECON_DATA:
        print(f"✅ Chatbot API ready!")
        print(f"   Loaded: {len(lookup.RECON_DATA)} transactions")
        print(f"   Run ID: {lookup.CURRENT_RUN_ID}")
        print(f"   Loaded at: {lookup.LOADED_AT}")
    else:
        print("⚠️  Warning: No reconciliation data loaded")
        print("   API will return errors until data is available")


@app.get("/")
async def root():
    """
    Root endpoint - API information.
    """
    return {
        "service": "Transaction Chatbot API",
        "version": "1.0.0",
        "status": "running",
        "data_loaded": len(lookup.RECON_DATA) > 0,
        "endpoints": {
            "chatbot": "/api/v1/chatbot?rrn=636397811101708",
            "health": "/health",
            "stats": "/api/v1/stats",
            "reload": "/api/v1/reload (POST)",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns service status and data availability.
    """
    data_loaded = len(lookup.RECON_DATA) > 0
    
    return {
        "status": "healthy" if data_loaded else "degraded",
        "service": "chatbot-service",
        "version": "1.0.0",
        "data_loaded": data_loaded,
        "transaction_count": len(lookup.RECON_DATA),
        "current_run_id": lookup.CURRENT_RUN_ID,
        "loaded_at": lookup.LOADED_AT.isoformat() if lookup.LOADED_AT else None
    }


@app.get("/api/v1/chatbot")
async def chatbot_lookup(
    rrn: Optional[str] = Query(None, description="12-digit Retrieval Reference Number"),
    txn_id: Optional[str] = Query(None, description="Transaction ID (e.g., TXN001)"),
    txd_id: Optional[str] = Query(None, description="Transaction ID (alias for txn_id)")
):
    """
    Main chatbot endpoint - lookup transaction by RRN or Transaction ID.

    Query Parameters:
        - rrn: 12-digit RRN (optional)
        - txn_id: Transaction ID (optional)
        - txd_id: Transaction ID alias (optional)

    Note: At least one parameter must be provided.
    If txn_id/txd_id is 12 digits, it will be treated as RRN.

    Returns:
        Transaction details with reconciliation status across CBS, Switch, and NPCI systems.
    """
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
            error_response = response_formatter.format_validation_error(
                "Missing required parameter. Provide either 'rrn' or 'txn_id'",
                details={
                    "provided": {"rrn": None, "txn_id": None},
                    "required": "At least one of: rrn, txn_id"
                }
            )
            return JSONResponse(status_code=400, content=error_response)
        # Enforce cycle/run scoping: require run_id or cycle_id or explicit allow_latest
        import os
        run_id = os.getenv('CHATBOT_QUERY_RUN_ID') or None
        cycle_id = os.getenv('CHATBOT_QUERY_CYCLE_ID') or None
        allow_latest = os.getenv('CHATBOT_ALLOW_LATEST', 'false').lower() in ('1','true','yes')

        if not run_id and not cycle_id and not allow_latest:
            return JSONResponse(status_code=400, content=response_formatter.format_validation_error(
                "Chatbot queries must include 'run_id' or 'cycle_id' or set allow_latest=true",
                details={'provided': {'run_id': run_id, 'cycle_id': cycle_id, 'allow_latest': allow_latest}}
            ))

        # Resolve run_id when only cycle_id provided by searching runs for matching cycle
        if not run_id and cycle_id:
            from pathlib import Path
            DATA_DIR = Path(__file__).resolve().parents[1] / 'data' / 'output'
            candidates = [p for p in DATA_DIR.iterdir() if p.is_dir() and p.name.startswith('RUN_')]
            candidates.sort(reverse=True)
            found_run = None
            for cand in candidates:
                try:
                    recon_path = cand / 'recon_output.json'
                    if not recon_path.exists():
                        continue
                    import json
                    with open(recon_path, 'r', encoding='utf-8') as f:
                        rd = json.load(f)
                    def has_cycle(d):
                        if isinstance(d, dict):
                            for v in d.values():
                                if isinstance(v, dict) and v.get('cycle_id') == cycle_id:
                                    return True
                        else:
                            for v in d:
                                if isinstance(v, dict) and v.get('cycle_id') == cycle_id:
                                    return True
                        return False
                    if has_cycle(rd):
                        found_run = cand.name
                        break
                except Exception:
                    continue
            if not found_run:
                return JSONResponse(status_code=404, content=response_formatter.format_not_found_response(cycle_id, 'cycle_id', 'UNKNOWN'))
            run_id = found_run

        if not run_id and allow_latest:
            run_id = lookup.get_latest_run_id()

        # Load recon data for resolved run_id
        try:
            data = lookup.load_recon_data(run_id)
            indexes = lookup.build_indexes(data)
        except Exception as e:
            return JSONResponse(status_code=500, content=response_formatter.format_error_response(e, context='load_recon_data'))
        
        # Step 2: Validate and search by RRN if provided
        if rrn:
            # Validate RRN format
            if not nlp.validate_rrn(rrn):
                error_response = response_formatter.format_validation_error(
                    "Invalid RRN format. RRN must be exactly 12 digits",
                    details={
                        "provided": rrn,
                        "expected_format": "12 digits (e.g., 123456789012)",
                        "length": len(rrn)
                    }
                )
                return JSONResponse(status_code=400, content=error_response)
            
            # Search by RRN
            transaction = indexes['rrn_index'].get(rrn)
            search_type = "rrn"
            identifier = rrn
        
        # Step 3: Validate and search by TXN_ID if RRN not provided
        else:
            # Validate TXN_ID format
            if not nlp.validate_txn_id(txn_id):
                error_response = response_formatter.format_validation_error(
                    "Invalid transaction ID format. Must contain only digits",
                    details={
                        "provided": txn_id,
                        "expected_format": "Digits only (e.g., 001, 123)"
                    }
                )
                return JSONResponse(status_code=400, content=error_response)
            
            # Search by TXN_ID
            tkey = f"TXN{txn_id}" if not txn_id.startswith("TXN") else txn_id
            transaction = indexes['txn_index'].get(tkey)
            search_type = "txn_id"
            identifier = txn_id
        
        # Step 4: Handle not found
        if transaction is None:
            run_id_resp = run_id or lookup.CURRENT_RUN_ID or "UNKNOWN"
            error_response = response_formatter.format_not_found_response(
                identifier,
                search_type,
                run_id_resp
            )
            return JSONResponse(status_code=404, content=error_response)
        
        # Step 5: Format and return successful response
        run_id_resp = run_id or lookup.CURRENT_RUN_ID or "UNKNOWN"
        response = response_formatter.format_transaction_response(transaction, run_id_resp)
        # Add cycle and source metadata to chatbot response
        response["cycle_id"] = cycle_id or transaction.get('cycle_id')
        response["report_source"] = f"run:{run_id_resp}, cycle:{response.get('cycle_id', 'UNKNOWN')}"
        return JSONResponse(status_code=200, content=response)
    
    except Exception as e:
        # Handle unexpected errors
        print(f"❌ Error in chatbot_lookup: {e}")
        error_response = response_formatter.format_error_response(
            e, 
            context="chatbot_lookup"
        )
        return JSONResponse(status_code=500, content=error_response)


@app.get("/api/v1/stats")
async def get_statistics():
    """
    Get reconciliation data statistics.
    
    Returns summary of loaded data including:
    - Total transaction count
    - Status breakdown (FULL_MATCH, PARTIAL_MATCH, NO_MATCH)
    - Current run ID
    - Load timestamp
    """
    try:
        stats = lookup.get_statistics()
        return JSONResponse(status_code=200, content=stats)
    except Exception as e:
        error_response = response_formatter.format_error_response(
            e,
            context="get_statistics"
        )
        return JSONResponse(status_code=500, content=error_response)


@app.post("/api/v1/reload")
async def reload_reconciliation_data():
    """
    Reload reconciliation data from latest run.
    
    Useful when new reconciliation batch is available.
    Forces refresh of in-memory cache without restarting server.
    
    Returns:
        Success/failure message with details
    """
    try:
        success = lookup.reload_data()
        
        if success:
            return {
                "status": "success",
                "message": f"Data reloaded from {lookup.CURRENT_RUN_ID}",
                "transaction_count": len(lookup.RECON_DATA),
                "loaded_at": lookup.LOADED_AT.isoformat() if lookup.LOADED_AT else None
            }
        else:
            return {
                "status": "no_change",
                "message": f"Already using latest run: {lookup.CURRENT_RUN_ID}",
                "transaction_count": len(lookup.RECON_DATA)
            }
    except Exception as e:
        error_response = response_formatter.format_error_response(
            e,
            context="reload_data"
        )
        return JSONResponse(status_code=500, content=error_response)


# Run with: uvicorn app:app --host 0.0.0.0 --port 8000 --reload
if __name__ == "__main__":
    import uvicorn
    import os
    # Chatbot runs on port 5001 for local development
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv('CHATBOT_PORT', '5001')))