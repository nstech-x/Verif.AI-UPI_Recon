import re
from datetime import datetime
from typing import Optional, Dict

# Example: ISSRP2PPYBP130725_1C
# Groups: Direction (ISSR/ACQR), TxnType (P2P/P2M), BankCode (4), Date (DDMMYY), Cycle (1C)
FILENAME_RE = re.compile(
    r"^(ISSR|ACQR)(P2P|P2M)([A-Z0-9]{4})(\d{6})(?:[_-]?(\d{1,2})C)?$",
    re.IGNORECASE,
)


def parse_upi_filename(filename: str) -> Optional[Dict[str, str]]:
    name = filename
    # strip extension
    if "." in name:
        name = name.rsplit(".", 1)[0]
    match = FILENAME_RE.match(name)
    if not match:
        return None

    direction_raw, txn_type, bank_code, date_str, cycle = match.groups()
    direction_raw = direction_raw.upper()
    txn_type = txn_type.upper()
    bank_code = bank_code.upper()

    direction = "INWARD" if direction_raw == "ISSR" else "OUTWARD"

    # Parse date DDMMYY
    try:
        dt = datetime.strptime(date_str, "%d%m%y").date()
        file_date = dt.strftime("%Y-%m-%d")
    except Exception:
        file_date = ""

    return {
        "direction": direction,
        "txn_type": txn_type,
        "bank_code": bank_code,
        "date": file_date,
        "cycle": cycle or "",
        "raw_direction": direction_raw,
    }

