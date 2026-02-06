print("DEBUG: App.py loaded successfully")

import logging
import os
import warnings

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import OUTPUT_DIR, UPLOAD_DIR
from routes import auth as auth_routes
from routes import enquiry as enquiry_routes
from routes import force_match as force_match_routes
from routes import health as health_routes
from routes import income_expense as income_expense_routes
from routes import recon as recon_routes
from routes import reports as reports_routes
from routes import rollback as rollback_routes
from routes import summary as summary_routes
from routes import upload as upload_routes

# Suppress warnings
warnings.filterwarnings("ignore")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION (from config.py)
# ============================================================================
# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# FASTAPI APP SETUP
# ============================================================================

app = FastAPI(title="UPI Reconciliation API", version="1.0.0")

# Add CORS middleware (fine-grained)
ALLOWED_ORIGINS = [
    "https://main.d26a5egrgsbb19.amplifyapp.com",
    "https://verif-ai.onrender.com",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# Validation error handler to surface Pydantic errors clearly in logs
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Request validation error for {request.url}: {exc.errors()}")
    # Return the same structure FastAPI would return but ensure it's logged
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


# Register modular routers
app.include_router(health_routes.router)
app.include_router(auth_routes.router)
app.include_router(summary_routes.router)
app.include_router(upload_routes.router)
app.include_router(recon_routes.router)
app.include_router(reports_routes.router)
app.include_router(force_match_routes.router)
app.include_router(rollback_routes.router)
app.include_router(enquiry_routes.router)
app.include_router(income_expense_routes.router)
