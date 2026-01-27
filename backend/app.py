print("DEBUG: App.py loaded successfully")

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Request, Depends
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from fastapi import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from audit_trail import create_audit_trail
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from jose import JWTError, jwt
import os
import json
import time
import logging
import warnings
import hashlib
import pandas as pd
import zipfile
import io
from file_handler import FileHandler
from recon_engine import ReconciliationEngine
from upi_recon_engine import UPIReconciliationEngine
from rollback_manager import RollbackManager, RollbackLevel
from exception_handler import ExceptionHandler
from config import UPLOAD_DIR, OUTPUT_DIR
from pydantic import BaseModel

# Suppress warnings
warnings.filterwarnings("ignore")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# AUTHENTICATION CONFIGURATION
# ============================================================================

SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password"""
    return hashlib.sha256(plain_password.encode('utf-8')).hexdigest() == hashed_password

# Hardcoded user database (for now)
USERS_DB = {
    "admin": {
        "username": "admin",
        "full_name": "Administrator",
        "email": "admin@verif.ai",
        "hashed_password": hash_password("admin123"),
        "disabled": False,
        "roles": ["admin"]
    },
    "Verif.AI": {
        "username": "Verif.AI",
        "full_name": "UPI Reconciliation System",
        "email": "system@verif.ai",
        "hashed_password": hash_password("Recon"),
        "disabled": False,
        "roles": ["Verif.AI"]
    }
}

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def authenticate_user(username: str, password: str):
    """Authenticate user"""
    user = USERS_DB.get(username)
    if not user:
        return False
    if not verify_password(password, user["hashed_password"]):
        return False
    return user

bearer_scheme = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Get current user from JWT token"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        user = USERS_DB.get(username)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============================================================================
# CONFIGURATION (from config.py)
# ============================================================================
# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# RATE LIMITING SETUP
# ============================================================================

RATE_LIMIT = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = int(os.getenv('RATE_LIMIT_MAX', '10'))


def _cleanup_timestamps(timestamps):
    cutoff = time.time() - RATE_LIMIT_WINDOW
    return [t for t in timestamps if t >= cutoff]


async def rate_limiter(request: Request):
    """Rate limiter using IP address"""
    key = request.client.host if request.client else 'anonymous'
    timestamps = RATE_LIMIT.get(key, [])
    timestamps = _cleanup_timestamps(timestamps)
    if len(timestamps) >= RATE_LIMIT_MAX:
        msg = f"Rate limit exceeded ({RATE_LIMIT_MAX} req/{RATE_LIMIT_WINDOW}s)"
        raise HTTPException(status_code=429, detail=msg)
    timestamps.append(time.time())
    RATE_LIMIT[key] = timestamps
    return True

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ReconRunRequest(BaseModel):
    run_id: Optional[str] = None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def validate_file_columns(content: bytes, filename: str, file_type: str) -> dict:
    """Validate that required columns exist in uploaded files with flexible column name matching"""
    try:
        # Read file content into DataFrame - handle both CSV and Excel files
        import os
        _, ext = os.path.splitext(filename)
        if ext.lower() in ('.xlsx', '.xls'):
            df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
        else:
            df = pd.read_csv(io.BytesIO(content))

        # Log actual columns present in the file for debugging
        logger.info(f"File: {filename}, Type: {file_type}, Columns found: {list(df.columns)}")

        # Define required columns with possible name variations for flexible matching
        required_columns_flexible = {
            'cbs_inward': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
                'Date': ['Date', 'date', 'tran date', 'transaction date', 'tran_date', 'transaction_date', 'dt'],
                'Debit_Credit': ['Debit_Credit', 'debit_credit', 'd/c', 'dr/cr', 'dr_cr', 'type', 'transaction_type']
            },
            'cbs_outward': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
                'Date': ['Date', 'date', 'tran date', 'transaction date', 'tran_date', 'transaction_date', 'dt'],
                'Debit_Credit': ['Debit_Credit', 'debit_credit', 'd/c', 'dr/cr', 'dr_cr', 'type', 'transaction_type']
            },
            'switch': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
                'Date': ['Date', 'date', 'tran date', 'transaction date', 'tran_date', 'transaction_date', 'dt']
            },
            'npci_inward': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
                'Date': ['Date', 'date', 'tran date', 'transaction date', 'tran_date', 'transaction_date', 'dt']
            },
            'npci_outward': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
                'Date': ['Date', 'date', 'tran date', 'transaction date', 'tran_date', 'transaction_date', 'dt']
            },
            'ntsl': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value']
            },
            'adjustment': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
                'Reason': ['Reason', 'reason', 'description', 'desc', 'remarks', 'adjustment_type', 'type']
            }
        }

        # Get required columns for this file type
        req_cols_dict = required_columns_flexible.get(file_type, {})

        # Define which columns are critical (must be present) vs optional (warnings only)
        critical_columns = ['RRN', 'Amount']  # Always required
        optional_columns = ['Date', 'Debit_Credit', 'Reason']  # Warnings only if missing

        # Check for missing columns using flexible matching
        missing_critical = []
        missing_optional = []
        for req_col, possible_names in req_cols_dict.items():
            found = any(name in df.columns for name in possible_names)
            if not found:
                if req_col in critical_columns:
                    missing_critical.append(req_col)
                elif req_col in optional_columns:
                    missing_optional.append(req_col)

        # If critical columns are missing, fail validation
        if missing_critical:
            suggestions = []
            for missing in missing_critical:
                possible = req_cols_dict[missing]
                suggestions.append(f"{missing} (possible names: {', '.join(possible)})")
            return {
                "valid": False,
                "error": f"Missing required columns: {', '.join(missing_critical)}",
                "missing_columns": missing_critical,
                "suggestion": f"Please ensure the file contains columns for: {'; '.join(suggestions)}"
            }

        # For optional columns, add warnings but allow upload
        warnings = []
        if missing_optional:
            for missing in missing_optional:
                possible = req_cols_dict[missing]
                warnings.append(f"Missing optional column: {missing} (possible names: {', '.join(possible)})")

        # Check for empty DataFrame
        if len(df) == 0:
            return {
                "valid": False,
                "error": "File contains no data rows",
                "suggestion": "Please ensure the file contains transaction data"
            }

        # Warnings (don't block upload)
        if df.isnull().values.any():
            warnings.append(f"File contains {df.isnull().sum().sum()} null values")

        return {
            "valid": True,
            "warnings": warnings
        }

        # Check for empty DataFrame
        if len(df) == 0:
            return {
                "valid": False,
                "error": "File contains no data rows",
                "suggestion": "Please ensure the file contains transaction data"
            }

        # Warnings (don't block upload)
        warnings = []
        if df.isnull().values.any():
            warnings.append(f"File contains {df.isnull().sum().sum()} null values")

        return {
            "valid": True,
            "warnings": warnings
        }

    except pd.errors.EmptyDataError:
        return {
            "valid": False,
            "error": "File is empty or contains no valid data"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Error reading file: {str(e)}"
        }

def get_ttum_files(run_id: str, cycle_id: Optional[str] = None, format: str = 'all') -> List[str]:
    """Get TTUM files for a run"""
    ttum_files = []

    # Check OUTPUT_DIR
    output_ttum = os.path.join(OUTPUT_DIR, run_id, 'ttum')
    if cycle_id:
        output_ttum = os.path.join(OUTPUT_DIR, run_id, f'cycle_{cycle_id}', 'ttum')

    if os.path.exists(output_ttum):
        for f in os.listdir(output_ttum):
            if format == 'all':
                if f.endswith(('.csv', '.xlsx', '.json')):
                    ttum_files.append(os.path.join(output_ttum, f))
            elif format == 'csv' and f.endswith('.csv'):
                ttum_files.append(os.path.join(output_ttum, f))
            elif format == 'xlsx' and f.endswith('.xlsx'):
                ttum_files.append(os.path.join(output_ttum, f))

    # Check UPLOAD_DIR as fallback
    if not ttum_files:
        upload_ttum = os.path.join(UPLOAD_DIR, run_id, 'ttum')
        if cycle_id:
            upload_ttum = os.path.join(UPLOAD_DIR, run_id, f'cycle_{cycle_id}', 'ttum')

        if os.path.exists(upload_ttum):
            for f in os.listdir(upload_ttum):
                if format == 'all':
                    if f.endswith(('.csv', '.xlsx', '.json')):
                        ttum_files.append(os.path.join(upload_ttum, f))
                elif format == 'csv' and f.endswith('.csv'):
                    ttum_files.append(os.path.join(upload_ttum, f))
                elif format == 'xlsx' and f.endswith('.xlsx'):
                    ttum_files.append(os.path.join(upload_ttum, f))

    return ttum_files

def write_ttum_csv(run_id: str, cycle_id: Optional[str], filename: str, headers: List[str], data: List[dict]) -> str:
    """Write TTUM data to CSV"""
    output_dir = os.path.join(OUTPUT_DIR, run_id, 'ttum')
    if cycle_id:
        output_dir = os.path.join(OUTPUT_DIR, run_id, f'cycle_{cycle_id}', 'ttum')

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{filename}.csv")

    df = pd.DataFrame(data, columns=headers)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    return output_path

def write_ttum_xlsx(run_id: str, cycle_id: Optional[str], filename: str, headers: List[str], data: List[dict]) -> str:
    """Write TTUM data to XLSX"""
    output_dir = os.path.join(OUTPUT_DIR, run_id, 'ttum')
    if cycle_id:
        output_dir = os.path.join(OUTPUT_DIR, run_id, f'cycle_{cycle_id}', 'ttum')

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{filename}.xlsx")

    df = pd.DataFrame(data, columns=headers)
    df.to_excel(output_path, index=False, engine='openpyxl')

    return output_path

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class ReconRunRequest(BaseModel):
    run_id: Optional[str] = None  # Optional; if not provided, uses latest run

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
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Request validation error for {request.url}: {exc.errors()}")
    # Return the same structure FastAPI would return but ensure it's logged
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# Mount chatbot service
# app.mount("/", chatbot_app)  # Commented out - conflicts with main app routes

# ============================================================================
# INITIALIZE COMPONENTS
# ============================================================================

file_handler = FileHandler()
recon_engine = ReconciliationEngine(output_dir=OUTPUT_DIR)
upi_recon_engine = UPIReconciliationEngine()
rollback_manager = RollbackManager(upload_dir=UPLOAD_DIR, output_dir=OUTPUT_DIR)
exception_handler = ExceptionHandler(upload_dir=UPLOAD_DIR, output_dir=OUTPUT_DIR)
audit = create_audit_trail(OUTPUT_DIR)

# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "UPI Reconciliation API",
        "version": "1.v1.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/api/v1/auth/login")
async def login(request: Request):
    """Login endpoint - returns JWT token"""
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")

        user = authenticate_user(username, password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"]}, expires_delta=access_token_expires
        )

        logger.info(f"User {username} logged in successfully")
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "username": user["username"],
                "full_name": user["full_name"],
                "email": user["email"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")


@app.get("/api/v1/auth/me")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    """Get current user information"""
    return {
        "username": user["username"],
        "full_name": user["full_name"],
        "email": user["email"],
        "roles": user.get("roles", [])
    }


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/api/v1/auth/login")
async def login(request: Request):
    """Login endpoint - returns JWT token"""
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")

        user = authenticate_user(username, password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"]}, expires_delta=access_token_expires
        )

        logger.info(f"User {username} logged in successfully")
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "username": user["username"],
                "full_name": user["full_name"],
                "email": user["email"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")


@app.get("/api/v1/auth/me")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    """Get current user information"""
    return {
        "username": user["username"],
        "full_name": user["full_name"],
        "email": user["email"],
        "roles": user.get("roles", [])
    }

# ============================================================================
# SUMMARY ENDPOINTS
# ============================================================================

@app.get("/api/v1/summary")
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
                "run_id": None
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
            unmatched_count = (summary_data.get('unmatched_cbs', 0) + 
                             summary_data.get('unmatched_switch', 0) + 
                             summary_data.get('unmatched_npci', 0))

            # Extract hanging transactions from switch breakdown
            switch_breakdown = details.get('switch_breakdown', {})
            hanging_count = switch_breakdown.get('HANGING', 0)

            return {
                "run_id": latest,
                "status": "completed",
                "totals": {
                    "count": total_count,
                    "amount": 0  # Total amount not available in summary
                },
                "matched": {
                    "count": matched_count,
                    "amount": 0  # Matched amount not available in summary
                },
                "unmatched": {
                    "count": unmatched_count,
                    "amount": 0  # Unmatched amount not available in summary
                },
                "hanging": {
                    "count": hanging_count,
                    "amount": 0  # Hanging amount not available in summary
                },
                "exceptions": {
                    "count": len(exceptions),
                    "amount": 0  # Exception amount not available in summary
                },
                "inward": {
                    "count": summary_data.get('inflow_count', 0),
                    "amount": summary_data.get('inflow_amount', 0.0)
                },
                "outward": {
                    "count": summary_data.get('outflow_count', 0),
                    "amount": summary_data.get('outflow_amount', 0.0)
                },
                "breakdown": {
                    "cbs": {
                        "total": summary_data.get('total_cbs', 0),
                        "matched": summary_data.get('matched_cbs', 0),
                        "unmatched": summary_data.get('unmatched_cbs', 0)
                    },
                    "switch": {
                        "total": summary_data.get('total_switch', 0),
                        "matched": summary_data.get('matched_switch', 0),
                        "unmatched": summary_data.get('unmatched_switch', 0),
                        "hanging": hanging_count
                    },
                    "npci": {
                        "total": summary_data.get('total_npci', 0),
                        "matched": summary_data.get('matched_npci', 0),
                        "unmatched": summary_data.get('unmatched_npci', 0)
                    }
                },
                "ttum_required": summary_data.get('ttum_required', 0)
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
        else:
            return {
                "total_transactions": 0,
                "matched": 0,
                "unmatched": 0,
                "adjustments": 0,
                "status": "no_reconciliation_run",
                "run_id": latest
            }
    except Exception as e:
        logger.error(f"Get summary error: {str(e)}")
        return {
            "total_transactions": 0,
            "matched": 0,
            "unmatched": 0,
            "adjustments": 0,
            "status": "error",
            "run_id": None
        }

# ============================================================================
# RECONCILIATION ENDPOINTS
# ============================================================================

@app.post("/api/v1/upload", status_code=201)
async def upload_files(
    cycle: str = Query("1C", description="Cycle e.g., 1C..10C"),
    run_date: str = Query(None, description="Run date YYYY-MM-DD"),
    direction: str = Query("INWARD", description="INWARD or OUTWARD"),
    cbs_inward: UploadFile = File(None),
    cbs_outward: UploadFile = File(None),
    switch: UploadFile = File(None),
    npci_inward: UploadFile = File(None),
    npci_outward: UploadFile = File(None),
    ntsl: UploadFile = File(None),
    adjustment: UploadFile = File(None),
    files: List[UploadFile] = File(None),
    user: dict = Depends(get_current_user)
):
    """Uploads the required files for a reconciliation run"""
    try:
        run_id = f"RUN_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Validate cycle format
        valid_cycles = [f"{i}C" for i in range(1, 11)]
        if cycle not in valid_cycles:
            raise HTTPException(status_code=400, detail=f"Invalid cycle. Valid cycles: {', '.join(valid_cycles)}")

        # Required file mapping
        required_files = {
            'cbs_inward': cbs_inward,
            'cbs_outward': cbs_outward,
            'switch': switch,
            'npci_inward': npci_inward,
            'npci_outward': npci_outward,
            'ntsl': ntsl,
            'adjustment': adjustment,
        }

        # Map generic files list
        if files:
            for upfile in files:
                fname = upfile.filename.lower()
                assigned = False
                if 'cbs' in fname and 'in' in fname:
                    required_files['cbs_inward'] = upfile
                    assigned = True
                elif 'cbs' in fname and 'out' in fname:
                    required_files['cbs_outward'] = upfile
                    assigned = True
                elif 'switch' in fname:
                    required_files['switch'] = upfile
                    assigned = True
                elif 'npci' in fname and 'in' in fname:
                    required_files['npci_inward'] = upfile
                    assigned = True
                elif 'npci' in fname and 'out' in fname:
                    required_files['npci_outward'] = upfile
                    assigned = True
                elif 'ntsl' in fname or 'national' in fname:
                    required_files['ntsl'] = upfile
                    assigned = True
                elif 'adjust' in fname or 'adj' in fname:
                    required_files['adjustment'] = upfile
                    assigned = True

                if not assigned:
                    for k, v in required_files.items():
                        if v is None:
                            required_files[k] = upfile
                            break

        uploaded_files_content = {}
        invalid_files = []
        validation_warnings = []
        MAX_BYTES = 100 * 1024 * 1024

        for key, upfile in required_files.items():
            if upfile is None:
                invalid_files.append({
                    "field": key,
                    "error": "required file is missing",
                    "suggestion": f"Please upload a {key.replace('_', ' ')} file"
                })
                continue

            try:
                content = await upfile.read()
            except Exception as e:
                invalid_files.append({
                    "filename": upfile.filename,
                    "error": f"failed to read file content: {str(e)}"
                })
                continue

            if not content or len(content) == 0:
                invalid_files.append({
                    "filename": upfile.filename,
                    "error": "file is empty",
                    "suggestion": "Please ensure the file contains data"
                })
                continue

            if len(content) > MAX_BYTES:
                invalid_files.append({
                    "filename": upfile.filename,
                    "error": f"file size ({len(content)/1024/1024:.1f} MB) exceeds limit (100 MB)"
                })
                continue

            # Validate file
            is_valid, err = file_handler.validate_file_bytes(content, upfile.filename)
            if not is_valid:
                invalid_files.append({
                    "filename": upfile.filename,
                    "error": err,
                    "suggestion": "Please check file format and ensure it contains valid financial transaction data"
                })
                continue

            # Validate columns
            validation_result = await validate_file_columns(content, upfile.filename, key)
            if not validation_result["valid"]:
                invalid_files.append({
                    "filename": upfile.filename,
                    "error": validation_result["error"],
                    "missing_columns": validation_result.get("missing_columns", []),
                    "suggestion": validation_result.get("suggestion", "Please check column headers in your file")
                })
                continue

            if validation_result.get("warnings"):
                validation_warnings.extend(validation_result["warnings"])

            uploaded_files_content[upfile.filename] = content

        if invalid_files:
            for bad in invalid_files:
                try:
                    rollback_manager.ingestion_rollback(run_id, bad.get('filename', bad.get('field','')), bad.get('error',''))
                except Exception:
                    pass

            if validation_warnings:
                logger.info(f"Upload validation warnings: {validation_warnings}")

            logger.warning(f"Upload contained invalid files: {invalid_files}")
            error_response = {"invalid_files": invalid_files}
            if validation_warnings:
                error_response["warnings"] = validation_warnings
            raise HTTPException(status_code=400, detail=error_response)

        # Save files
        run_folder = file_handler.save_uploaded_files(uploaded_files_content, run_id, cycle=cycle, direction=direction, run_date=run_date)

        # Audit
        for fname, content in uploaded_files_content.items():
            audit.log_file_upload(run_id, fname, len(content), user_id='system', status='success')

        logger.info(f"Files for {run_id} uploaded successfully to {run_folder}")

        return JSONResponse(content={"status": "success", "run_id": run_id}, status_code=201)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="File upload process failed")

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


@app.post("/api/v1/recon/run")
async def run_reconciliation(run_request: ReconRunRequest, user: dict = Depends(get_current_user), _rl=Depends(rate_limiter)):
    """Runs the reconciliation process for a given run_id or latest if not provided."""
    try:
        # require ops role to run reconciliation
        # try:
        #     require_role(user, 'Verif.AI')
        # except HTTPException:
        #     raise

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
            results = upi_recon_engine.perform_upi_reconciliation(cbs_df, switch_df, npci_df, run_id, adjustment_df=adjustment_df)

            # UPI engine outputs structured data - save it to OUTPUT_DIR
            try:
                import json
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
            "status": "completed"
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
                            "unmatched": summary.get('unmatched_cbs', 0)
                        },
                        "switch": {
                            "total": summary.get('total_switch', 0),
                            "matched": summary.get('matched_switch', 0),
                            "unmatched": summary.get('unmatched_switch', 0)
                        },
                        "npci": {
                            "total": summary.get('total_npci', 0),
                            "matched": summary.get('matched_npci', 0),
                            "unmatched": summary.get('unmatched_npci', 0)
                        }
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
        raise HTTPException(status_code=500, detail="Reconciliation process failed")


@app.post("/api/v1/recon/run-cycle")
async def run_reconciliation_cycle(
    run_id: str = Query(...),
    cycle_id: str = Query(...),
    user: dict = Depends(get_current_user)
):
    """Run reconciliation for a specific cycle"""
    try:
        run_root = os.path.join(UPLOAD_DIR, run_id, f"cycle_{cycle_id}")

        if not os.path.exists(run_root):
            raise HTTPException(status_code=404, detail=f"Cycle {cycle_id} not found for run {run_id}")

        # Load and process only this cycle's data
        dataframes = file_handler.load_files_for_recon(run_root)

        # Detect if this is a UPI reconciliation run
        is_upi_run = _detect_upi_reconciliation(dataframes)

        if is_upi_run:
            cbs_df, switch_df, npci_df, adjustment_df = _extract_upi_dataframes(dataframes)
            results = upi_recon_engine.perform_upi_reconciliation(cbs_df, switch_df, npci_df, run_id, cycle_id, adjustment_df=adjustment_df)
        else:
            results = recon_engine.reconcile(dataframes)

        # Save cycle-specific results
        output_run_dir = os.path.join(OUTPUT_DIR, run_id, f"cycle_{cycle_id}")
        os.makedirs(output_run_dir, exist_ok=True)

        recon_output_path = os.path.join(output_run_dir, "recon_output.json")
        with open(recon_output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)

        return {
            "run_id": run_id,
            "cycle_id": cycle_id,
            "status": "completed",
            "message": f"Reconciliation completed for cycle {cycle_id}"
        }
    except Exception as e:
        logger.error(f"Cycle reconciliation error: {e}")
        raise HTTPException(status_code=500, detail="Cycle reconciliation failed")



@app.get("/api/v1/recon/latest/summary")
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
        elif report_path and os.path.exists(report_path):
            with open(report_path, 'r') as f:
                return PlainTextResponse(content=f.read())
        else:
            raise HTTPException(status_code=404, detail="Summary not found for the latest run")

    except Exception as e:
        logger.error(f"Get summary error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve summary")

@app.get("/api/v1/summary/historical")
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
                        inflow_count = summary_data.get('inflow_count', total_npci + total_cbs)  # Estimate inward as NPCI + CBS
                        inflow_amount = summary_data.get('inflow_amount', 0.0)
                        outflow_count = summary_data.get('outflow_count', total_switch)  # Estimate outward as Switch
                        outflow_amount = summary_data.get('outflow_amount', 0.0)
                    else:
                        # Legacy format - no inflow/outflow data available
                        all_txns = len(recon_output) if isinstance(recon_output, dict) else 0
                        matched = sum(1 for k, v in (recon_output.items() if isinstance(recon_output, dict) else []) if isinstance(v, dict) and v.get('status') == 'MATCHED')
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
                            "breaks": all_txns - reconciled,  # Frontend expects 'breaks' not 'unmatched'
                            "matchRate": round(match_rate, 1),
                            "inward": inflow_count,
                            "outward": outflow_count
                        })
            except Exception as ex:
                logger.debug(f"Could not process run {run_id}: {ex}")
                continue
        
        return historical_summaries
    except Exception as e:
        logger.error(f"Get historical summary error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve historical summaries")


@app.post("/api/v1/reports/listing")
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
        logger.error(f"Listing report generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate listing reports")

@app.get("/api/v1/recon/latest/unmatched")
async def get_latest_unmatched(user: dict = Depends(get_current_user)):
    """Return unmatched transactions for the latest run"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        latest = sorted(runs)[-1]

        # First check OUTPUT_DIR (UPI format with summary and exceptions)
        recon_out = os.path.join(OUTPUT_DIR, latest, 'recon_output.json')
        if os.path.exists(recon_out):
            with open(recon_out, 'r') as f:
                data = json.load(f)
            
            # UPI format - extract unmatched/exception transactions
            unmatched = []
            if isinstance(data, dict) and 'exceptions' in data:
                # All exceptions are unmatched transactions
                for exc in data['exceptions']:
                    if isinstance(exc, dict):
                        unmatched.append({
                            "RRN": exc.get('rrn', 'N/A'),
                            "UPI_Tran_ID": exc.get('reference', 'N/A'),
                            "source": exc.get('source', 'UNKNOWN'),
                            "amount": exc.get('amount', 0),
                            "date": exc.get('date', ''),
                            "time": exc.get('time', ''),
                            "exception_type": exc.get('exception_type', ''),
                            "description": exc.get('description', ''),
                            "ttum_required": exc.get('ttum_required', False),
                            "ttum_type": exc.get('ttum_type', None),
                            "debit_credit": exc.get('debit_credit', ''),
                            "status": "UNMATCHED"
                        })
            
            # Sort by amount descending for better visibility
            unmatched = sorted(unmatched, key=lambda x: x.get('amount', 0), reverse=True)
            
            return JSONResponse(content={
                "run_id": latest, 
                "unmatched": unmatched, 
                "total_unmatched": len(unmatched),
                "format": "upi"
            })

        # Then check UPLOAD_DIR (legacy format)
        run_root = os.path.join(UPLOAD_DIR, latest)
        recon_out = None
        for root_dir, dirs, files in os.walk(run_root):
            if 'recon_output.json' in files:
                recon_out = os.path.join(root_dir, 'recon_output.json')
                break
        if not recon_out or not os.path.exists(recon_out):
            raise HTTPException(status_code=404, detail="Reconciliation output not found for latest run")
        with open(recon_out, 'r') as f:
            data = json.load(f)

        # If format is dict keyed by RRN
        unmatched = []
        if isinstance(data, dict) and not data.get('matched') and not data.get('unmatched'):
            for rrn, rec in data.items():
                if isinstance(rec, dict) and rec.get('status') in ['HANGING', 'PARTIAL_MATCH', 'PARTIAL_MISMATCH']:
                    unmatched.append({"RRN": rrn, "status": rec.get('status'), "record": rec})
        else:
            # legacy format
            for rec in data.get('unmatched', []):
                unmatched.append(rec)

        return JSONResponse(content={"run_id": latest, "unmatched": unmatched, "format": "legacy"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get unmatched error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve unmatched list")


@app.get("/api/v1/recon/latest/hanging")
async def get_latest_hanging(user: dict = Depends(get_current_user)):
    """Return hanging transactions for the latest run"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        latest = sorted(runs)[-1]
        run_root = os.path.join(UPLOAD_DIR, latest)

        hanging_path = None
        hanging_state = None
        for root_dir, dirs, files in os.walk(run_root):
            if 'hanging.csv' in files:
                hanging_path = os.path.join(root_dir, 'hanging.csv')
                break
            if 'hanging_state.json' in files:
                hanging_state = os.path.join(root_dir, 'hanging_state.json')
                break

        hanging = []
        if hanging_path and os.path.exists(hanging_path):
            with open(hanging_path, 'r') as f:
                hanging = f.read()
            return PlainTextResponse(content=hanging)
        elif hanging_state and os.path.exists(hanging_state):
            with open(hanging_state, 'r') as f:
                return JSONResponse(content=json.load(f))
        else:
            return JSONResponse(content={"run_id": latest, "hanging": []})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get hanging error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve hanging list")


@app.get("/api/v1/reports/gl-statement")
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

        return FileResponse(gl_file, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if gl_file.endswith('.xlsx') else 'text/csv', filename=os.path.basename(gl_file))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GL statement download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download GL statement")


@app.get("/api/v1/reports/ttum")
async def download_ttum(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Package TTUM CSVs/XLSX for a run into a ZIP and return."""
    import zipfile
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
                    'downloaded_by': user.get('username', 'unknown')
                }, mf, indent=2)
        except Exception:
            pass

        return FileResponse(zip_path, media_type='application/zip', filename=os.path.basename(zip_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTUM download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to prepare TTUM files")


@app.get("/api/v1/reports/ttum/csv")
async def download_ttum_csv(user: dict = Depends(get_current_user), run_id: Optional[str] = None, cycle_id: Optional[str] = None):
    """Download TTUM data in CSV format (all files zipped if multiple cycles).
    Sets a persistent is_downloaded flag.
    """
    import zipfile
    try:
        # Default to latest run
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target_run = run_id if run_id else sorted(runs)[-1]

        # Get TTUM files from output directory
        from reporting import get_ttum_files
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

        # If single file, return it directly
        if len(ttum_files) == 1:
            file_path = ttum_files[0]
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="TTUM CSV file not found")
            file_size = os.path.getsize(file_path)
            logger.info(f"Returning single TTUM CSV file: {file_path}, size: {file_size} bytes")
            # Set download flag
            try:
                out_ttum = os.path.join(OUTPUT_DIR, target_run, 'ttum')
                os.makedirs(out_ttum, exist_ok=True)
                with open(os.path.join(out_ttum, 'download_meta.json'), 'w') as mf:
                    json.dump({'is_downloaded': True, 'downloaded_at': datetime.utcnow().isoformat(), 'downloaded_by': user.get('username','unknown')}, mf, indent=2)
            except Exception:
                pass
            return FileResponse(file_path, media_type='text/csv', filename=os.path.basename(file_path))

        # Multiple files - zip them
        zip_path = os.path.join(OUTPUT_DIR, target_run, f"ttum_csv_{target_run}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in ttum_files:
                if os.path.exists(file_path):
                    zf.write(file_path, arcname=os.path.basename(file_path))
                else:
                    logger.warning(f"Skipping missing file: {file_path}")

        zip_size = os.path.getsize(zip_path) if os.path.exists(zip_path) else 0
        logger.info(f"Created TTUM ZIP: {zip_path}, size: {zip_size} bytes")

        # Set download flag
        try:
            out_ttum = os.path.join(OUTPUT_DIR, target_run, 'ttum')
            os.makedirs(out_ttum, exist_ok=True)
            with open(os.path.join(out_ttum, 'download_meta.json'), 'w') as mf:
                json.dump({'is_downloaded': True, 'downloaded_at': datetime.utcnow().isoformat(), 'downloaded_by': user.get('username','unknown')}, mf, indent=2)
        except Exception:
            pass

        return FileResponse(zip_path, media_type='application/zip', filename=os.path.basename(zip_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTUM CSV download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download TTUM CSV files")




@app.get("/api/v1/reports/ttum/xlsx")
async def download_ttum_xlsx(user: dict = Depends(get_current_user), run_id: Optional[str] = None, cycle_id: Optional[str] = None):
    """Download TTUM data in XLSX format (all files zipped if multiple cycles).
    Sets a persistent is_downloaded flag.
    """
    import zipfile
    try:
        # Default to latest run
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target_run = run_id if run_id else sorted(runs)[-1]
        
        # Get TTUM files from output directory
        from reporting import get_ttum_files
        ttum_files = get_ttum_files(target_run, cycle_id, format='xlsx')
        
        if not ttum_files:
            raise HTTPException(status_code=404, detail="No TTUM XLSX files found")
        
        # If single file, return it directly
        if len(ttum_files) == 1:
            # Set download flag
            try:
                out_ttum = os.path.join(OUTPUT_DIR, target_run, 'ttum')
                os.makedirs(out_ttum, exist_ok=True)
                with open(os.path.join(out_ttum, 'download_meta.json'), 'w') as mf:
                    json.dump({'is_downloaded': True, 'downloaded_at': datetime.utcnow().isoformat(), 'downloaded_by': user.get('username','unknown')}, mf, indent=2)
            except Exception:
                pass
            return FileResponse(ttum_files[0], media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=os.path.basename(ttum_files[0]))
        
        # Multiple files - zip them
        zip_path = os.path.join(OUTPUT_DIR, target_run, f"ttum_xlsx_{target_run}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in ttum_files:
                zf.write(file_path, arcname=os.path.basename(file_path))
        
        # Set download flag
        try:
            out_ttum = os.path.join(OUTPUT_DIR, target_run, 'ttum')
            os.makedirs(out_ttum, exist_ok=True)
            with open(os.path.join(out_ttum, 'download_meta.json'), 'w') as mf:
                json.dump({'is_downloaded': True, 'downloaded_at': datetime.utcnow().isoformat(), 'downloaded_by': user.get('username','unknown')}, mf, indent=2)
        except Exception:
            pass

        return FileResponse(zip_path, media_type='application/zip', filename=os.path.basename(zip_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTUM XLSX download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download TTUM XLSX files")


@app.get("/api/v1/reports/ttum/merged")
async def download_ttum_merged(user: dict = Depends(get_current_user), run_id: Optional[str] = None, format: str = Query('xlsx', regex='^(csv|xlsx)$')):
    """Download all TTUM data merged into a single file (CSV or XLSX)"""
    try:
        # Default to latest run
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target_run = run_id if run_id else sorted(runs)[-1]
        
        from reporting import get_ttum_files
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
            from reporting import write_ttum_xlsx
            out_path = write_ttum_xlsx(target_run, None, f"TTUM_MERGED_{datetime.now().strftime('%Y%m%d_%H%M%S')}", headers, all_rows)
            return FileResponse(out_path, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=os.path.basename(out_path))
        else:  # csv
            from reporting import write_ttum_csv
            out_path = write_ttum_csv(target_run, None, f"TTUM_MERGED_{datetime.now().strftime('%Y%m%d_%H%M%S')}", headers, all_rows)
            return FileResponse(out_path, media_type='text/csv', filename=os.path.basename(out_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTUM merged download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create merged TTUM file")


@app.get("/api/v1/enquiry")
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


@app.get("/api/v1/chatbot")
async def chatbot_lookup(
    rrn: Optional[str] = Query(None, description="12-digit Retrieval Reference Number"),
    txn_id: Optional[str] = Query(None, description="Transaction ID (e.g., TXN001)"),
    txd_id: Optional[str] = Query(None, description="Transaction ID (alias for txn_id)")
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
                    "required": "At least one of: rrn, txn_id"
                }
            })

        # Find the latest run
        runs = [d for d in os.listdir(OUTPUT_DIR) if d.startswith('RUN_') and os.path.isdir(os.path.join(OUTPUT_DIR, d))]
        if not runs:
            return JSONResponse(status_code=404, content={
                "error": "No reconciliation data available",
                "message": "Please run reconciliation first"
            })

        runs.sort(reverse=True)
        latest_run = runs[0]
        run_path = os.path.join(OUTPUT_DIR, latest_run, 'recon_output.json')

        if not os.path.exists(run_path):
            return JSONResponse(status_code=404, content={
                "error": "Reconciliation output not found",
                "message": f"File not found: {run_path}"
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
                    "sources_checked": ["exceptions", "ttum_candidates"]
                }
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
                "direction": transaction.get('direction')
            }
        }

        return JSONResponse(content=formatted_response)

    except Exception as e:
        logger.error(f"Chatbot lookup error: {e}")
        return JSONResponse(status_code=500, content={
            "error": "Failed to lookup transaction",
            "details": str(e)
        })


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


@app.get('/api/v1/force-match/proposals')
async def get_force_match_proposals(run_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Get all force-match proposals for a run (or latest if not specified)"""
    try:
        if not run_id:
            # Get latest run
            runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
            if not runs:
                raise HTTPException(status_code=404, detail="No runs found")
            run_id = sorted(runs)[-1]
        
        proposals = _load_proposals(run_id)
        
        # Enrich proposals with transaction details from recon output
        for prop in proposals:
            prop_rrn = prop.get('rrn')
            try:
                # Try to get full transaction data
                run_root = os.path.join(UPLOAD_DIR, run_id)
                for root_dir, dirs, files in os.walk(run_root):
                    if 'recon_output.json' in files:
                        with open(os.path.join(root_dir, 'recon_output.json'), 'r') as f:
                            recon_data = json.load(f)
                        
                        # Find transaction with matching RRN
                        if isinstance(recon_data, dict) and 'exceptions' in recon_data:
                            for exc in recon_data['exceptions']:
                                if exc.get('rrn') == prop_rrn:
                                    prop['transaction_details'] = exc
                                    break
                        break
            except Exception:
                pass  # If lookup fails, just return proposal as-is
        
        return JSONResponse(content={
            "run_id": run_id,
            "proposals": proposals,
            "total": len(proposals)
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get proposals error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve proposals")


@app.post('/api/v1/force-match')
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
            try:
                form = await request.form()
                payload = dict(form)
            except Exception:
                # fallback to query params
                payload = dict(request.query_params)
        rrn = payload.get('rrn')
        action = payload.get('action')
        direction = payload.get('direction')
        run_id = payload.get('run_id')
        reason = payload.get('reason', '')

        if not rrn or not action:
            raise HTTPException(status_code=400, detail='rrn and action are required')

        if not run_id:
            raise HTTPException(status_code=400, detail='run_id is required')

        # Validate RRN exists in the reconciliation results
        rrn_found = False
        run_root = os.path.join(UPLOAD_DIR, run_id)
        for root_dir, dirs, files in os.walk(run_root):
            if 'recon_output.json' in files:
                with open(os.path.join(root_dir, 'recon_output.json'), 'r') as f:
                    recon_data = json.load(f)
                    if isinstance(recon_data, dict):
                        if 'exceptions' in recon_data:
                            # UPI format - check exceptions array
                            for exc in recon_data['exceptions']:
                                if exc.get('rrn') == rrn or exc.get('RRN') == rrn:
                                    rrn_found = True
                                    break
                        else:
                            # Legacy format - check if RRN key exists
                            if rrn in recon_data:
                                rrn_found = True
                                break
                if rrn_found:
                    break

        if not rrn_found:
            raise HTTPException(status_code=404, detail=f'RRN {rrn} not found in reconciliation results')

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
            'created_at': datetime.utcnow().isoformat()
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


@app.post('/api/v1/force-match/approve')
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
        found_run = None
        for fname in os.listdir(OUTPUT_DIR):
            if fname.endswith('_proposals.json'):
                path = os.path.join(OUTPUT_DIR, fname)
                try:
                    with open(path, 'r') as pf:
                        proposals = json.load(pf)
                    for p in proposals:
                        if p.get('proposal_id') == proposal_id:
                            found = p
                            found_run = fname.replace('_proposals.json', '')
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
            run_root = os.path.join(UPLOAD_DIR, found.get('run_id'))
            # find nested recon_output.json
            recon_path = None
            for root_dir, dirs, files in os.walk(run_root):
                if 'recon_output.json' in files:
                    recon_path = os.path.join(root_dir, 'recon_output.json')
                    break
            if recon_path and os.path.exists(recon_path):
                with open(recon_path, 'r') as rf:
                    ro = json.load(rf)

                # Handle UPI format (exceptions array)
                if isinstance(ro, dict) and 'exceptions' in ro:
                    exceptions = ro.get('exceptions', [])
                    for i, exc in enumerate(exceptions):
                        if exc.get('rrn') == found.get('rrn') or exc.get('RRN') == found.get('rrn'):
                            # Mark as force matched by updating status and adding force_match flag
                            exc['status'] = 'FORCE_MATCHED'
                            exc['force_matched'] = True
                            exc['force_match_proposal_id'] = found.get('proposal_id')
                            exc['force_match_approved_by'] = checker
                            exc['force_match_approved_at'] = datetime.utcnow().isoformat()
                            break
                    ro['exceptions'] = exceptions
                # Handle legacy format (RRN keyed dict)
                elif isinstance(ro, dict) and found.get('rrn') in ro:
                    ro[found.get('rrn')]['status'] = 'FORCE_MATCHED'
                    ro[found.get('rrn')]['force_matched'] = True
                    ro[found.get('rrn')]['force_match_proposal_id'] = found.get('proposal_id')
                    ro[found.get('rrn')]['force_match_approved_by'] = checker
                    ro[found.get('rrn')]['force_match_approved_at'] = datetime.utcnow().isoformat()
                else:
                    # try list format
                    for rec in ro:
                        if isinstance(rec, dict) and (rec.get('rrn') == found.get('rrn') or rec.get('RRN') == found.get('rrn')):
                            rec['status'] = 'FORCE_MATCHED'
                            rec['force_matched'] = True
                            rec['force_match_proposal_id'] = found.get('proposal_id')
                            rec['force_match_approved_by'] = checker
                            rec['force_match_approved_at'] = datetime.utcnow().isoformat()
                            break

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


@app.post("/api/v1/recon/rollback")
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
            result = rollback_manager.ingestion_rollback(run_id, params.get('failed_filename',''), params.get('validation_error',''))
        elif rl == RollbackLevel.MID_RECON:
            result = rollback_manager.mid_recon_rollback(run_id, params.get('error_message',''), affected_transactions=params.get('affected_transactions'))
        elif rl == RollbackLevel.CYCLE_WISE:
            result = rollback_manager.cycle_wise_rollback(run_id, params.get('cycle_id',''))
        elif rl == RollbackLevel.ACCOUNTING:
            result = rollback_manager.accounting_rollback(run_id, params.get('reason',''), voucher_ids=params.get('voucher_ids'))
        elif rl == RollbackLevel.WHOLE_PROCESS:
            result = rollback_manager.whole_process_rollback(run_id, params.get('reason',''))
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

@app.get("/api/v1/upload/metadata")
async def get_upload_metadata(run_id: Optional[str] = None):
    """Get metadata for a specific run or latest run if not specified"""
    try:
        # If no run_id provided, use the latest run
        if not run_id:
            runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
            if not runs:
                return {
                    "run_id": None,
                    "uploaded_files": [],
                    "status": "no_runs_found"
                }
            run_id = sorted(runs)[-1]

        # Search for metadata in nested directories
        run_folder = os.path.join(UPLOAD_DIR, run_id)
        metadata_path = None

        for root_dir, dirs, files in os.walk(run_folder):
            if 'metadata.json' in files:
                metadata_path = os.path.join(root_dir, 'metadata.json')
                break

        if not metadata_path or not os.path.exists(metadata_path):
            logger.warning(f"Metadata not found for run {run_id}")
            return {
                "run_id": run_id,
                "uploaded_files": [],
                "status": "metadata_not_found"
            }

        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        # Extract uploaded file types from saved_files dict
        uploaded_files = []
        if isinstance(metadata.get('saved_files'), dict):
            uploaded_files = list(metadata['saved_files'].keys())

        logger.info(f"Retrieved metadata for {run_id}: {uploaded_files}")

        return {
            "run_id": run_id,
            "uploaded_files": uploaded_files,
            "saved_files": metadata.get('saved_files', {}),
            "cycle_id": metadata.get('cycle_id'),
            "direction": metadata.get('direction'),
            "run_date": metadata.get('run_date'),
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Get metadata error: {str(e)}")
        return {
            "run_id": None,
            "uploaded_files": [],
            "status": "error",
            "error": str(e)
        }

@app.get("/api/v1/recon/latest/report")
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
        elif os.path.exists(os.path.join(output_run_path, "recon_output.json")):
            return FileResponse(os.path.join(output_run_path, "recon_output.json"), media_type='application/json', filename=f"recon_report_{latest}.json")
        else:
            raise HTTPException(status_code=404, detail="Report not found for the latest run")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get latest report error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve report")

@app.get("/api/v1/reports/unmatched")
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
                    "total_exceptions": len(exceptions_list)
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
                                'source': source
                            }
                            exceptions_list.append(exc)

            return JSONResponse(content={
                "run_id": latest,
                "data": exceptions_list,
                "format": "upi_array",
                "summary": {},
                "total_exceptions": len(exceptions_list)
            })

        raise HTTPException(status_code=404, detail="Reconciliation output not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get unmatched report error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve unmatched report")


@app.get("/api/v1/reports/matched")
async def download_matched_reports(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Package pairwise matched CSVs into a ZIP and return. Supports OUTPUT_DIR-first (UPI) and legacy."""
    import zipfile
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


@app.get("/api/v1/reports/available")
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
            "other": []
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
        run_folder = os.path.join(UPLOAD_DIR, target)
        reports_dir = None
        for root_dir, dirs, files in os.walk(run_folder):
            if 'reports' in dirs:
                reports_dir = os.path.join(root_dir, 'reports')
                break
        
        if reports_dir and os.path.exists(reports_dir):
            for f in os.listdir(reports_dir):
                if f.endswith('.csv') and f not in available_reports["csv"]:
                    available_reports["csv"].append(f)
                elif f.endswith('.json') and f not in available_reports["json"]:
                    available_reports["json"].append(f)
                elif f not in available_reports["other"]:
                    available_reports["other"].append(f)
        
        # Check for recon_output.json
        output_json = os.path.join(OUTPUT_DIR, target, 'recon_output.json')
        if os.path.exists(output_json):
            available_reports["json"].append('recon_output.json')
        
        return JSONResponse(content={
            "run_id": target,
            "available_reports": available_reports,
            "total_csv": len(available_reports["csv"]),
            "total_json": len(available_reports["json"]),
            "total_other": len(available_reports["other"])
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List available reports error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list available reports")

@app.get("/api/v1/reports/summary")
async def download_summary(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Return summary for a run. For UPI, derives from OUTPUT_DIR/<run>/recon_output.json."""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        # UPI-first
        upi_output = os.path.join(OUTPUT_DIR, target, 'recon_output.json')
        if os.path.exists(upi_output):
            with open(upi_output, 'r') as f:
                data = json.load(f)
            return JSONResponse(content={
                "run_id": target,
                "format": "upi",
                "summary": data.get('summary', {}),
                "exceptions_count": len(data.get('exceptions', []))
            })

        # Legacy
        run_root = os.path.join(UPLOAD_DIR, target)
        summary_path = None
        for root_dir, dirs, files in os.walk(run_root):
            if 'summary.json' in files:
                summary_path = os.path.join(root_dir, 'summary.json')
                break

        if summary_path and os.path.exists(summary_path):
            return FileResponse(summary_path, media_type='application/json', filename=os.path.basename(summary_path))
        else:
            raise HTTPException(status_code=404, detail='Summary not found for run')
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summary download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve summary")


@app.get("/api/v1/recon/latest/adjustments")
async def download_adjustments(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Return ANNEXURE IV adjustment CSV for latest run if present."""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]
        run_root = os.path.join(UPLOAD_DIR, target)

        annex_path = None
        for root_dir, dirs, files in os.walk(run_root):
            for f in files:
                if f.lower().startswith('annexure_iv') and f.lower().endswith('.csv'):
                    annex_path = os.path.join(root_dir, f)
                    break
            if annex_path:
                break

        if annex_path and os.path.exists(annex_path):
            filename = os.path.basename(annex_path)

            # Read file content
            with open(annex_path, 'rb') as f:
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
        else:
            raise HTTPException(status_code=404, detail='Annexure file not found for run')
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Adjustment download error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve adjustments file")

@app.get("/api/v1/reports/matched/csv")
async def download_matched_csv(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download matched transactions CSV report"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]
        
        # Try OUTPUT_DIR first (UPI format)
        output_dir = os.path.join(OUTPUT_DIR, target, 'reports')
        if os.path.exists(output_dir):
            csv_file = None
            for f in os.listdir(output_dir):
                if 'matched' in f.lower() and f.endswith('.csv'):
                    csv_file = os.path.join(output_dir, f)
                    break

            if csv_file and os.path.exists(csv_file):
                filename = os.path.basename(csv_file)

                # Read file content
                with open(csv_file, 'rb') as f:
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
        
        # Try UPLOAD_DIR
        run_folder = os.path.join(UPLOAD_DIR, target)
        reports_dir = None
        for root_dir, dirs, files in os.walk(run_folder):
            if 'reports' in dirs:
                reports_dir = os.path.join(root_dir, 'reports')
                break
        
        if reports_dir:
            for f in os.listdir(reports_dir):
                if 'matched' in f.lower() and f.endswith('.csv'):
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
        
        raise HTTPException(status_code=404, detail="Matched CSV report not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download matched CSV error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download matched CSV")


# New endpoints for specific report types requested by frontend
@app.get("/api/v1/reports/{report_type:path}")
async def download_specific_report(report_type: str, user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download specific report type - handles all frontend report requests with nested paths"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]
        
        # Map frontend report types to backend file patterns
        report_mapping = {
            # Listing reports
            'cbs_beneficiary': ['cbs_beneficiary', 'cbs_inward', 'listing_1'],
            'cbs_remitter': ['cbs_remitter', 'cbs_outward', 'listing_2'],
            'switch_inward': ['switch_inward', 'listing_3'],
            'switch_outward': ['switch_outward', 'listing_4'],
            'npci_inward': ['npci_inward', 'listing_5'],
            'npci_outward': ['npci_outward', 'listing_6'],
            # Reconciliation reports
            'recon/gl_vs_switch/matched/inward': ['GL_vs_Switch_Inward', 'gl_vs_switch_inward'],
            'recon/gl_vs_switch/matched/outward': ['GL_vs_Switch_Outward', 'gl_vs_switch_outward'],
            'recon/gl_vs_switch/unmatched/inward': ['Unmatched_Inward_Ageing', 'unmatched_inward'],
            'recon/gl_vs_switch/unmatched/outward': ['Unmatched_Outward_Ageing', 'unmatched_outward'],
            'recon/switch_vs_network/matched/inward': ['Switch_vs_NPCI_Inward', 'switch_vs_npci_inward'],
            'recon/switch_vs_network/matched/outward': ['Switch_vs_NPCI_Outward', 'switch_vs_npci_outward'],
            'recon/switch_vs_network/unmatched/inward': ['Unmatched_Inward_Ageing', 'unmatched_inward'],
            'recon/switch_vs_network/unmatched/outward': ['Unmatched_Outward_Ageing', 'unmatched_outward'],
            'recon/gl_vs_network/matched/inward': ['GL_vs_NPCI_Inward', 'gl_vs_npci_inward'],
            'recon/gl_vs_network/matched/outward': ['GL_vs_NPCI_Outward', 'gl_vs_npci_outward'],
            'recon/gl_vs_network/unmatched/inward': ['Unmatched_Inward_Ageing', 'unmatched_inward'],
            'recon/gl_vs_network/unmatched/outward': ['Unmatched_Outward_Ageing', 'unmatched_outward'],
            'recon/hanging_transactions/inward': ['Hanging_Inward', 'hanging_inward'],
            'recon/hanging_transactions/outward': ['Hanging_Outward', 'hanging_outward'],
            # TTUM and Annexure
            'ttum': ['ttum_candidates'],
            'annexure/i/raw': ['annexure_i', 'ANNEXURE_I'],
            'annexure/ii/raw': ['annexure_ii', 'ANNEXURE_II'],
            'annexure/iii/adjustment': ['annexure_iii', 'ANNEXURE_III', 'annexure_iv'],
            'annexure/iv/bulk': ['annexure_iv', 'ANNEXURE_IV'],
        }
        
        patterns = report_mapping.get(report_type, [report_type.replace('/', '_')])
        
        # Search in OUTPUT_DIR first
        output_dir = os.path.join(OUTPUT_DIR, target, 'reports')
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                for pattern in patterns:
                    if pattern.lower() in f.lower() and f.endswith(('.csv', '.xlsx')):
                        file_path = os.path.join(output_dir, f)
                        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                        logger.info(f"Returning specific report from OUTPUT_DIR: {file_path}, size: {file_size} bytes, filename: {f}")
                        media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if f.endswith('.xlsx') else 'text/csv'
                        return FileResponse(file_path, media_type=media_type, filename=f)

        # Search in UPLOAD_DIR
        run_folder = os.path.join(UPLOAD_DIR, target)
        for root_dir, dirs, files in os.walk(run_folder):
            for f in files:
                for pattern in patterns:
                    if pattern.lower() in f.lower() and f.endswith(('.csv', '.xlsx')):
                        file_path = os.path.join(root_dir, f)
                        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                        logger.info(f"Returning specific report from UPLOAD_DIR: {file_path}, size: {file_size} bytes, filename: {f}")
                        media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if f.endswith('.xlsx') else 'text/csv'
                        return FileResponse(file_path, media_type=media_type, filename=f)
        
        raise HTTPException(status_code=404, detail=f"Report '{report_type}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download specific report error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download report")

@app.get("/api/v1/reports/unmatched/csv")
async def download_unmatched_csv(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download unmatched exceptions CSV report"""
    try:
        runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith('RUN_')]
        if not runs:
            raise HTTPException(status_code=404, detail="No runs found")
        target = run_id if run_id else sorted(runs)[-1]

        # Try OUTPUT_DIR first (UPI format)
        output_dir = os.path.join(OUTPUT_DIR, target, 'reports')
        if os.path.exists(output_dir):
            csv_file = None
            for f in os.listdir(output_dir):
                if 'unmatched' in f.lower() and f.endswith('.csv'):
                    csv_file = os.path.join(output_dir, f)
                    break

            if csv_file and os.path.exists(csv_file):
                filename = os.path.basename(csv_file)

                # Read file content
                with open(csv_file, 'rb') as f:
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

        # Try UPLOAD_DIR
        run_folder = os.path.join(UPLOAD_DIR, target)
        reports_dir = None
        for root_dir, dirs, files in os.walk(run_folder):
            if 'reports' in dirs:
                reports_dir = os.path.join(root_dir, 'reports')
                break

        if reports_dir:
            for f in os.listdir(reports_dir):
                if 'unmatched' in f.lower() and f.endswith('.csv'):
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

        raise HTTPException(status_code=404, detail="Unmatched CSV report not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download unmatched CSV error: {e}")
        raise HTTPException(status_code=500, detail="Failed to download unmatched CSV")


@app.get("/api/v1/reports/ageing")
async def download_ageing_reports(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download ageing reports (Unmatched_Inward_Ageing.csv and Unmatched_Outward_Ageing.csv)"""
    import zipfile
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


@app.get("/api/v1/reports/hanging")
async def download_hanging_reports(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download hanging transaction reports (Hanging_Inward.csv and Hanging_Outward.csv)"""
    import zipfile
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


@app.get("/api/v1/reports/switch-update")
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


@app.get("/api/v1/reports/annexure")
async def download_annexure_reports(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download Annexure IV reports"""
    import zipfile
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


@app.get("/api/v1/reports/all")
async def download_all_reports(user: dict = Depends(get_current_user), run_id: Optional[str] = None):
    """Download all generated reports in a single ZIP file"""
    import zipfile
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

@app.get("/api/v1/recon/latest/raw")
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
                    'sources_available': list(sources)  # Track which sources have data
                }

                # Map all available source data to the transaction
                # We need to find data from all sources that have exceptions for this RRN
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
                                'rrn': rrn,
                                'amount': src_exc.get('amount', 0),
                                'date': src_exc.get('date', ''),
                                'reference': src_exc.get('reference', ''),
                                'debit_credit': src_exc.get('debit_credit', ''),
                                'status': src_exc.get('status', '')
                            }
                        elif src == 'switch':
                            transaction['switch'] = {
                                'rrn': rrn,
                                'amount': src_exc.get('amount', 0),
                                'date': src_exc.get('date', ''),
                                'reference': src_exc.get('reference', ''),
                                'debit_credit': src_exc.get('debit_credit', ''),
                                'status': src_exc.get('status', '')
                            }
                        elif src == 'npci':
                            transaction['npci'] = {
                                'rrn': rrn,
                                'amount': src_exc.get('amount', 0),
                                'date': src_exc.get('date', ''),
                                'reference': src_exc.get('reference', ''),
                                'debit_credit': src_exc.get('debit_credit', ''),
                                'status': src_exc.get('status', '')
                            }

                exceptions_dict[rrn] = transaction
            
            # If we have exceptions, return them in the expected format
            return JSONResponse(content={
                "run_id": latest,
                "data": exceptions_dict if exceptions_dict else data.get('details', {}),
                "format": "upi",
                "summary": {
                    "total_cbs": summary.get('total_cbs', 0),
                    "total_switch": summary.get('total_switch', 0),
                    "total_npci": summary.get('total_npci', 0),
                    "matched_cbs": summary.get('matched_cbs', 0),
                    "matched_switch": summary.get('matched_switch', 0),
                    "matched_npci": summary.get('matched_npci', 0),
                    "unmatched_cbs": summary.get('unmatched_cbs', 0),
                    "unmatched_switch": summary.get('unmatched_switch', 0),
                    "unmatched_npci": summary.get('unmatched_npci', 0),
                    "ttum_required": summary.get('ttum_required', 0),
                    "file_path": recon_out
                }
            })

        # Handle legacy format
        total_rrns = len(data) if isinstance(data, dict) else len(data.get('matched', [])) + len(data.get('unmatched', []))
        matched_count = 0
        unmatched_count = 0

        if isinstance(data, dict):
            for rec in data.values():
                if isinstance(rec, dict):
                    status = rec.get('status', '')
                    if status in ['MATCHED', 'EXACT_MATCH']:
                        matched_count += 1
                    elif status in ['HANGING', 'PARTIAL_MATCH', 'PARTIAL_MISMATCH', 'EXCEPTION']:
                        unmatched_count += 1
        else:
            matched_count = len(data.get('matched', []))
            unmatched_count = len(data.get('unmatched', []))

        exception_count = unmatched_count  # For now, treat all unmatched as exceptions

        return JSONResponse(content={
            "run_id": latest,
            "data": data,
            "format": "legacy",
            "summary": {
                "total_rrns": total_rrns,
                "matched_count": matched_count,
                "unmatched_count": unmatched_count,
                "exception_count": exception_count,
                "file_path": recon_out
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get raw data error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve raw data")

@app.get("/api/v1/rollback/history")
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
        else:
            return JSONResponse(content={"history": history_data})

    except Exception as e:
        logger.error(f"Get rollback history error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve rollback history")


@app.post("/api/v1/rollback/whole-process")
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


@app.post("/api/v1/rollback/cycle-wise")
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


@app.post("/api/v1/rollback/ingestion")
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


@app.post("/api/v1/rollback/mid-recon")
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


@app.post("/api/v1/rollback/accounting")
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


@app.get('/api/v1/rollback/available-cycles')
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
            'all_cycles': available_cycles
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get available cycles error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list available cycles")


@app.get('/api/v1/recon/cycles/{run_id}')
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
                        'files_count': len([f for f in os.listdir(cycle_path) if f.endswith(('.csv', '.xlsx', '.txt'))])
                    })

        return JSONResponse(content={
            'run_id': run_id,
            'cycles': cycles_info,
            'total_cycles': len(cycles_info)
        })
    except Exception as e:
        logger.error(f"Get run cycles error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get run cycles")


@app.get('/api/v1/recon/cycle/{run_id}/{cycle_id}/summary')
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
                "amount": 0
            },
            "matched": {
                "count": summary.get('matched_cbs', 0) + summary.get('matched_switch', 0) + summary.get('matched_npci', 0),
                "amount": 0
            },
            "unmatched": {
                "count": len(exceptions),
                "amount": 0
            },
            "breakdown": {
                "cbs": {
                    "total": summary.get('total_cbs', 0),
                    "matched": summary.get('matched_cbs', 0),
                    "unmatched": summary.get('unmatched_cbs', 0)
                },
                "switch": {
                    "total": summary.get('total_switch', 0),
                    "matched": summary.get('matched_switch', 0),
                    "unmatched": summary.get('unmatched_switch', 0)
                },
                "npci": {
                    "total": summary.get('total_npci', 0),
                    "matched": summary.get('matched_npci', 0),
                    "unmatched": summary.get('unmatched_npci', 0)
                }
            },
            "ttum_required": summary.get('ttum_required', 0)
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get cycle summary error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cycle summary")


@app.get('/api/v1/recon/merge-cycles')
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
                "npci": {"total": 0, "matched": 0, "unmatched": 0}
            },
            "ttum_required": 0,
            "cycle_summaries": []
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
                    "exception_count": len(exceptions)
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


@app.get('/api/v1/recon/compare-cycles')
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
                    "npci": {}
                }
            }
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
                        "ttum_required": summary.get('ttum_required', 0)
                    }
                }

            except Exception as e:
                logger.warning(f"Error processing cycle {cycle_id}: {e}")
                continue

        # Build comparison data
        for cycle_id, data in cycle_data.items():
            comparison_data["cycle_comparison"].append({
                "cycle_id": cycle_id,
                "metrics": data["metrics"],
                "summary": data["summary"]
            })

        # Calculate differences and trends
        if len(cycle_data) >= 2:
            sorted_cycles = sorted(cycle_data.keys())
            for i in range(1, len(sorted_cycles)):
                current = sorted_cycles[i]
                previous = sorted_cycles[i-1]

                curr_metrics = cycle_data[current]["metrics"]
                prev_metrics = cycle_data[previous]["metrics"]

                # Calculate differences
                differences = {
                    "cycle_comparison": f"{current}_vs_{previous}",
                    "total_diff": curr_metrics["total_transactions"] - prev_metrics["total_transactions"],
                    "matched_diff": curr_metrics["matched_transactions"] - prev_metrics["matched_transactions"],
                    "unmatched_diff": curr_metrics["unmatched_transactions"] - prev_metrics["unmatched_transactions"],
                    "ttum_diff": curr_metrics["ttum_required"] - prev_metrics["ttum_required"]
                }

                # Add to comparison data
                comparison_data.setdefault("differences", []).append(differences)

        return JSONResponse(content=comparison_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Compare cycles error: {e}")
        raise HTTPException(status_code=500, detail="Failed to compare cycles")

# ============================================================================
# INCOME & EXPENSE DASHBOARD APIs
# ============================================================================

@app.get("/api/v1/income-expense/data")
async def get_income_expense_data(
    date_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    date_to: str = Query(..., description="End date in YYYY-MM-DD format")
):
    """
    Get Income & Expense data from NTSL settlement files
    """
    try:
        # Load NTSL settlement data
        ntsl_file = os.path.join("demo_data", "ntsl_settlement.json")
        
        if not os.path.exists(ntsl_file):
            raise HTTPException(status_code=404, detail="NTSL settlement data not found")
        
        with open(ntsl_file, 'r') as f:
            ntsl_data = json.load(f)
        
        # Filter data by date range
        from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
        to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
        
        filtered_data = []
        for record in ntsl_data['settlement_data']:
            record_date = datetime.strptime(record['date'], "%Y-%m-%d").date()
            if from_date <= record_date <= to_date:
                filtered_data.append(record)
        
        if not filtered_data:
            return JSONResponse(content={
                "status": "success",
                "data": [],
                "summary": {
                    "total_income": 0,
                    "total_expense": 0,
                    "net_position": 0
                }
            })
        
        # Calculate aggregated income and expense
        income_breakdown = {
            "interchange_income": {
                "u2_payer_psp_fees": 0,
                "u3_payer_psp_fees": 0,
                "beneficiary_u3_fee": 0
            },
            "gst_income": {
                "beneficiary_u3_fee_gst": 0
            }
        }
        
        expense_breakdown = {
            "interchange_expense": {
                "remitter_u2_fee": 0,
                "remitter_u3_fee": 0,
                "remitter_p2a_declined": 0
            },
            "npci_switching_fees": {
                "remitter_u2_npci": 0,
                "remitter_u3_npci": 0
            },
            "gst_expense": {
                "remitter_u2_fee_gst": 0,
                "remitter_u3_fee_gst": 0,
                "remitter_u2_npci_gst": 0,
                "remitter_u3_npci_gst": 0
            }
        }
        
        date_wise_data = []
        
        for record in filtered_data:
            # Income
            u2_payer = record['u2_payer_psp_fees_received']
            u3_payer = record['u3_payer_psp_fees_received']
            beneficiary_u3 = record['beneficiary_u3_approved_fee']
            beneficiary_u3_gst = record['beneficiary_u3_approved_fee_gst']
            
            income_breakdown['interchange_income']['u2_payer_psp_fees'] += u2_payer
            income_breakdown['interchange_income']['u3_payer_psp_fees'] += u3_payer
            income_breakdown['interchange_income']['beneficiary_u3_fee'] += beneficiary_u3
            income_breakdown['gst_income']['beneficiary_u3_fee_gst'] += beneficiary_u3_gst
            
            total_income = u2_payer + u3_payer + beneficiary_u3 + beneficiary_u3_gst
            
            # Expense
            rem_u2_fee = record['remitter_u2_approved_fee']
            rem_u3_fee = record['remitter_u3_approved_fee']
            rem_p2a = record['remitter_p2a_declined']
            rem_u2_npci = record['remitter_u2_npci_switching_fee']
            rem_u3_npci = record['remitter_u3_npci_switching_fee']
            rem_u2_fee_gst = record['remitter_u2_approved_fee_gst']
            rem_u3_fee_gst = record['remitter_u3_approved_fee_gst']
            rem_u2_npci_gst = record['remitter_u2_npci_switching_fee_gst']
            rem_u3_npci_gst = record['remitter_u3_npci_switching_fee_gst']
            
            expense_breakdown['interchange_expense']['remitter_u2_fee'] += rem_u2_fee
            expense_breakdown['interchange_expense']['remitter_u3_fee'] += rem_u3_fee
            expense_breakdown['interchange_expense']['remitter_p2a_declined'] += rem_p2a
            expense_breakdown['npci_switching_fees']['remitter_u2_npci'] += rem_u2_npci
            expense_breakdown['npci_switching_fees']['remitter_u3_npci'] += rem_u3_npci
            expense_breakdown['gst_expense']['remitter_u2_fee_gst'] += rem_u2_fee_gst
            expense_breakdown['gst_expense']['remitter_u3_fee_gst'] += rem_u3_fee_gst
            expense_breakdown['gst_expense']['remitter_u2_npci_gst'] += rem_u2_npci_gst
            expense_breakdown['gst_expense']['remitter_u3_npci_gst'] += rem_u3_npci_gst
            
            total_expense = (rem_u2_fee + rem_u3_fee + rem_p2a + rem_u2_npci + rem_u3_npci + 
                           rem_u2_fee_gst + rem_u3_fee_gst + rem_u2_npci_gst + rem_u3_npci_gst)
            
            date_wise_data.append({
                "date": record['date'],
                "income": round(total_income, 2),
                "expense": round(total_expense, 2),
                "net": round(total_income - total_expense, 2),
                "transaction_count": record['transaction_count']
            })
        
        # Calculate totals
        total_income = (
            sum(income_breakdown['interchange_income'].values()) +
            sum(income_breakdown['gst_income'].values())
        )
        
        total_expense = (
            sum(expense_breakdown['interchange_expense'].values()) +
            sum(expense_breakdown['npci_switching_fees'].values()) +
            sum(expense_breakdown['gst_expense'].values())
        )
        
        # Round all values for clean output
        for category in income_breakdown:
            for key in income_breakdown[category]:
                income_breakdown[category][key] = round(income_breakdown[category][key], 2)
        
        for category in expense_breakdown:
            for key in expense_breakdown[category]:
                expense_breakdown[category][key] = round(expense_breakdown[category][key], 2)
        
        return JSONResponse(content={
            "status": "success",
            "date_from": date_from,
            "date_to": date_to,
            "summary": {
                "total_income": round(total_income, 2),
                "total_expense": round(total_expense, 2),
                "net_position": round(total_income - total_expense, 2)
            },
            "income_breakdown": income_breakdown,
            "expense_breakdown": expense_breakdown,
            "date_wise_data": date_wise_data
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Income/Expense data error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get income/expense data: {str(e)}")


@app.get("/api/v1/income-expense/download-excel")
async def download_income_expense_excel(
    date_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    date_to: str = Query(..., description="End date in YYYY-MM-DD format")
):
    """
    Download Income & Expense MIS Report as Excel
    """
    try:
        # Load NTSL settlement data
        ntsl_file = os.path.join("demo_data", "ntsl_settlement.json")
        
        if not os.path.exists(ntsl_file):
            raise HTTPException(status_code=404, detail="NTSL settlement data not found")
        
        with open(ntsl_file, 'r') as f:
            ntsl_data = json.load(f)
        
        # Filter data by date range
        from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
        to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
        
        filtered_data = []
        for record in ntsl_data['settlement_data']:
            record_date = datetime.strptime(record['date'], "%Y-%m-%d").date()
            if from_date <= record_date <= to_date:
                filtered_data.append(record)
        
        if not filtered_data:
            raise HTTPException(status_code=404, detail="No data found for the selected date range")
        
        # Prepare data for Excel in the exact format specified
        excel_data = []
        for record in filtered_data:
            excel_data.append({
                "Date": record['date'],
                "Remitter U2 Approved Fee": record['remitter_u2_approved_fee'],
                "Remitter U2 Approved Fee GST": record['remitter_u2_approved_fee_gst'],
                "Remitter U2 NPCI Switching Fee": record['remitter_u2_npci_switching_fee'],
                "Remitter U2 NPCI Switching Fee GST": record['remitter_u2_npci_switching_fee_gst'],
                "Remitter U3 Approved Fee": record['remitter_u3_approved_fee'],
                "Remitter U3 Approved Fee GST": record['remitter_u3_approved_fee_gst'],
                "Remitter U3 NPCI Switching Fee": record['remitter_u3_npci_switching_fee'],
                "Remitter U3 NPCI Switching Fee GST": record['remitter_u3_npci_switching_fee_gst'],
                "Remitter P2A Declined": record['remitter_p2a_declined'],
                "U2 Payer PSP Fees Received": record['u2_payer_psp_fees_received'],
                "U3 Payer PSP Fees Received": record['u3_payer_psp_fees_received'],
                "Beneficiary U3 Approved Fee": record['beneficiary_u3_approved_fee'],
                "Beneficiary U3 Approved Fee GST": record['beneficiary_u3_approved_fee_gst']
            })
        
        # Create DataFrame
        df = pd.DataFrame(excel_data)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Income_Expense_MIS', index=False)
        
        output.seek(0)
        
        # Generate filename with date range
        filename = f"Income_Expense_MIS_Report_{date_from}_to_{date_to}.xlsx"
        
        # Return as file download
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Excel download error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel report: {str(e)}")


# ============================================================================

# MAIN

# ============================================================================



if __name__ == '__main__':

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
