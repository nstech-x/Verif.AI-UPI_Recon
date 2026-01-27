import os
import re
import json
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

# Resolve a sensible default data directory: the project's `backend/data/output`.
# Allow overriding via `RECON_DATA_PATH` environment variable for flexibility.
BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = BASE_DIR / "data" / "output"
DATA_DIR = Path(os.getenv("RECON_DATA_PATH", str(DEFAULT_DATA_DIR)))
RUN_FOLDER_PATTERN = re.compile(r'^RUN_\d{8}_\d+$')

RECON_DATA: List[Dict] = []
RRN_INDEX: Dict[str, Dict] = {}
TXN_INDEX: Dict[str, Dict] = {}
CURRENT_RUN_ID: Optional[str] = None
LOADED_AT: Optional[datetime] = None

def get_latest_run_id() -> str:
    """
    Find the most recent RUN_* folder.
    
    Returns:
        str: Latest RUN folder name (e.g., "RUN_20251127_003")
        
    Raises:
        FileNotFoundError: If no valid RUN folders exist
        
    Example:
        >>> get_latest_run_id()
        'RUN_20251127_003'
    """
    if not DATA_DIR.exists() or not DATA_DIR.is_dir():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        raise FileNotFoundError(
            f"Data directory created at {DATA_DIR}."
            f" Please add RUN_* folders and try again."
        )
        
    all_folders = [f for f in DATA_DIR.iterdir() if f.is_dir()]
    valid_runs = [
        f.name for f in all_folders if RUN_FOLDER_PATTERN.match(f.name)
    ]
    
    if not valid_runs:
        raise FileNotFoundError(
            f"No valid RUN folders found in {DATA_DIR}."
            f"Expected format: RUN_YYYYMMDD_NNN"
        )
    valid_runs.sort()
    return valid_runs[-1]

def load_recon_data(run_id: Optional[str] = None) -> Dict:
    """
    Load reconciliation data from specified or latest run.
    
    Args:
        run_id: Specific RUN folder name, or None for latest
        
    Returns:
        Dictionary of transaction data keyed by RRN
        
    Raises:
        FileNotFoundError: If run folder or JSON file doesn't exist
        json.JSONDecodeError: If JSON is invalid
        
    Example:
        >>> data = load_recon_data("RUN_20251127_003")
        >>> len(data)
        150
    """
    
    if run_id is None:
        run_id = get_latest_run_id()
    
    json_path = DATA_DIR / run_id / "recon_output.json"
    
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found at {json_path}")
    
    with open(json_path, 'r', encoding="utf-8") as f:
        data = json.load(f)
        
    if isinstance(data, list):
        # Convert list to dict format if needed
        data_dict = {}
        for i, item in enumerate(data):
            rrn = item.get('rrn') or item.get('RRN') or str(i)
            data_dict[rrn] = item
        data = data_dict
    
    if not isinstance(data, dict):
        raise json.JSONDecodeError(
            f"Expected a dict or list of transactions in {json_path}", 
            doc=str(data), 
            pos=0
        )
    print(f"Loaded {len(data)} transactions from {json_path} & run_id: {run_id}")
    return data

def build_indexes(transactions: Dict) -> Dict[str, Dict]:
    """
    Build fast lookup indexes for RRN and TXN_ID.
    
    Creates O(1) lookup dictionaries for instant search.
    
    Args:
        transactions: Dict of transaction dictionaries keyed by RRN
        
    Returns:
        Dict with 'rrn_index' and 'txn_index'
        
    Example:
        >>> txns = {"123456789012": {"rrn": "123456789012", "txn_id": "TXN001"}}
        >>> indexes = build_indexes(txns)
        >>> indexes['rrn_index']['123456789012']
        {'rrn': '123456789012', 'txn_id': 'TXN001'}
    """
    rrn_index = {}
    txn_index = {}
    
    def _normalize_rrn_value(val):
        """Return a stable string representation for RRN keys.

        Handles numeric values (int/float) that may have been parsed from JSON
        and strips trailing `.0` when present so keys like `518221608814.0`
        become `518221608814`.
        """
        if val is None:
            return None
        # If already a string, just strip whitespace
        if isinstance(val, str):
            s = val.strip()
            # If a string looks like an integer or a float with trailing .0, normalize to integer string
            m = re.match(r'^(\d+)(?:\.0+)?$', s)
            if m:
                return m.group(1)
            return s
        # If float that is integer-valued, cast to int first
        if isinstance(val, float):
            if val.is_integer():
                return str(int(val))
            return str(val)
        # For ints and other types
        try:
            return str(int(val))
        except Exception:
            return str(val)

    # Handle dict format (keyed by RRN)
    if isinstance(transactions, dict):
        for rrn, txn in transactions.items():
            rrn_key = _normalize_rrn_value(rrn)
            rrn_index[rrn_key] = txn
            txn_id = txn.get("txn_id") or txn.get("TXN_ID")
            if txn_id:
                txn_index[str(txn_id)] = txn
    else:
        # Fallback for list format
        for txn in transactions:
            rrn = txn.get("rrn") or txn.get("RRN")
            rrn_key = _normalize_rrn_value(rrn)
            if rrn_key:
                rrn_index[rrn_key] = txn
            txn_id = txn.get("txn_id") or txn.get("TXN_ID")
            if txn_id:
                txn_index[str(txn_id)] = txn
            
    print(f"Built RRN index with {len(rrn_index)} entries.")
    print(f"Built TXN_ID index with {len(txn_index)} entries.")
    return {
        "rrn_index": rrn_index,
        "txn_index": txn_index
    }
    
def search_by_rrn(rrn: str) -> Optional[Dict]:
    """
    Find transaction by RRN (O(1) lookup).
    
    Args:
        rrn: 12-digit RRN string
        
    Returns:
        Transaction dict or None if not found
        
    Example:
        >>> txn = search_by_rrn("123456789012")
        >>> txn['status']
        'FULL_MATCH'
    """
    # Normalize input so numeric/format differences don't prevent matches
    if rrn is None:
        return None
    rrn_key = str(rrn).strip()
    # Handle cases where input may be provided as numeric with .0
    if rrn_key.endswith('.0'):
        try:
            rrn_key = str(int(float(rrn_key)))
        except Exception:
            rrn_key = rrn_key.rstrip('.0')
    return RRN_INDEX.get(rrn_key)
    
def search_by_txn_id(txn_id: str) -> Optional[Dict]:
    """
    Find transaction by Transaction ID (O(1) lookup).
    
    Args:
        txn_id: Transaction ID string
        
    Returns:
        Transaction dict or None if not found
        
    Example:
        >>> txn = search_by_txn_id("TXN001")
        >>> txn['rrn']
        '123456789012'
    """
    return TXN_INDEX.get(txn_id)

def reload_data() -> bool:
    """
    Reload data from latest run (useful when new data arrives).
    
    Call this endpoint to refresh in-memory cache without restarting server.
    
    Returns:
        bool: True if reload successful, False if already latest
        
    Example:
        >>> reload_data()
        ✅ Reloaded data from RUN_20251127_004
        True
    """
    global RECON_DATA, RRN_INDEX, TXN_INDEX, CURRENT_RUN_ID, LOADED_AT
    try:
        run_id = get_latest_run_id()
        
        if run_id == CURRENT_RUN_ID:
            print(f"Already using latest run: {run_id}")
            return False
        
        data = load_recon_data(run_id)
        indexes = build_indexes(data)
        
        RECON_DATA = data
        RRN_INDEX = indexes['rrn_index']
        TXN_INDEX = indexes['txn_index']
        CURRENT_RUN_ID = run_id
        LOADED_AT = datetime.now()

        print(f"✅ Reloaded data from {run_id} at {LOADED_AT}")
        return True
    except Exception as e:
        print(f"Error reloading data: {e}")
        return False
    
def get_statistics() -> Dict[str, int]:
    """
    Get summary statistics about loaded data.
    
    Returns:
        Dict with statistics about current state
        
    Example:
        >>> stats = get_statistics()
        >>> stats['total_transactions']
        150
    """
    if not RECON_DATA:
        return {
            "status" : "not_loaded",
            "message": "No data loaded yet."
        }
    
    status_counts = {}
    for txn in RECON_DATA:
        status = txn.get("status", "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "status": "loaded",
        "total_transactions": len(RECON_DATA),
        "rrn_indexed": len(RRN_INDEX),
        "txn_indexed": len(TXN_INDEX),
        "status_breakdown": status_counts,
        "current_run_id": CURRENT_RUN_ID,
        "loaded_at": LOADED_AT.isoformat() if LOADED_AT else None,
        "data_path": str(DATA_DIR)
    }
    
def validate_run_id(run_id: str) -> bool:
    """
    Validate RUN folder name format.
    
    Args:
        run_id: Folder name to validate
        
    Returns:
        bool: True if valid format
        
    Example:
        >>> validate_run_id("RUN_20251127_003")
        True
        >>> validate_run_id("RUN_LATEST")
        False
    """
    return bool(RUN_FOLDER_PATTERN.match(run_id))

def initialize() -> None:
    """
    Load data on module import.
    
    Called automatically when this module is imported.
    Sets up in-memory indexes for fast lookups.
    This is now non-fatal - chatbot will work once data is available.
    """
    global RECON_DATA, RRN_INDEX, TXN_INDEX, CURRENT_RUN_ID, LOADED_AT
    
    try:
        print("Initializing chatbot lookup service...")
        print(f"Using data directory: {DATA_DIR}")
        
        CURRENT_RUN_ID = get_latest_run_id()
        RECON_DATA = load_recon_data(CURRENT_RUN_ID)
        indexes = build_indexes(RECON_DATA)
        RRN_INDEX = indexes['rrn_index']
        TXN_INDEX = indexes['txn_index']
        LOADED_AT = datetime.now()
        
        print(f"✅ Chatbot ready! Loaded {len(RECON_DATA)} transactions from {CURRENT_RUN_ID}")
        
    except FileNotFoundError as e:
        print(f"⚠️  {e}")
        print("Chatbot will start once reconciliation data is available")
    except Exception as e:
        print(f"⚠️  Initialization warning: {e}")


# Auto-initialize when module is imported (non-fatal)
initialize()