"""
Annexure-IV CSV generator (best-effort implementation)

This module implements a strict, index-based CSV writer for NPCI Annexure-IV
(Adjustment File - Bulk Upload). The CSV format is sensitive to column order
and data formats; NPCI typically validates by column position rather than
header names. The implementation below enforces field formats and lengths
and writes a UTF-8 (no BOM), comma-separated CSV with the exact required
column order.

Usage:
    from annexure_iv import generate_annexure_iv_csv
    generate_annexure_iv_csv(records, 'output.csv')

Important constraints (implemented):
 - Strict column order (Bankadjref,Flag,shtdat,adjsmt,Shser,Shcrd,FileName,reason,specifyother)
 - UTF-8 (no BOM), comma-separated, no trailing commas
 - Field validations (lengths, formats)

Note: This is a best-effort implementation. For production compliance, validate
the produced CSV against NPCI acceptance tests and adjust any field-level
formatting required by the official Annexure-IV spec.
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import re
import pandas as pd
from typing import List, Dict, Optional
from reporting import write_report
from config import OUTPUT_DIR

# Exact, fixed column order required by NPCI (do not change)
COLUMN_ORDER = [
    'Bankadjref',
    'Flag',
    'shtdat',
    'adjsmt',
    'Shser',
    'Shcrd',
    'FileName',
    'reason',
    'specifyother'
]

# Allowed Flags
ALLOWED_FLAGS = {'DRC', 'RRC', 'Cr Adj', 'TCC', 'RET'}

# Regex for Bankadjref: allow alphanumeric and common separators (- _ / .)
BANKREF_RE = re.compile(r'^[A-Za-z0-9\-_.\\/]{1,100}$')


def _validate_and_normalize(record: Dict) -> Dict:
    """Validate one record and return normalized values.

    Raises ValueError on invalid input. Does not mutate the input dict.
    """
    out = {}

    # Bankadjref: mandatory, alphanumeric-ish, max 100 chars
    bankref = record.get('Bankadjref')
    if not bankref or not str(bankref).strip():
        raise ValueError('Bankadjref is mandatory and must be non-empty')
    bankref = str(bankref).strip()
    if len(bankref) > 100 or not BANKREF_RE.match(bankref):
        raise ValueError(f'Invalid Bankadjref "{bankref}"; max 100 chars, alphanumeric and -_/. allowed')
    out['Bankadjref'] = bankref

    # Flag: mandatory, must be one of allowed (preserve 'Cr Adj' case)
    flag = record.get('Flag')
    if not flag or not str(flag).strip():
        raise ValueError('Flag is mandatory')
    raw_flag = str(flag).strip()
    upper_flag = raw_flag.upper()
    if upper_flag == 'CR ADJ':
        norm_flag = 'Cr Adj'
    elif upper_flag in {'DRC', 'RRC', 'TCC', 'RET'}:
        norm_flag = upper_flag
    else:
        raise ValueError(f'Flag must be one of {ALLOWED_FLAGS}, got "{flag}"')
    out['Flag'] = norm_flag

    # shtdat: mandatory, date YYYY-MM-DD
    shtdat = record.get('shtdat')
    if not shtdat or not str(shtdat).strip():
        raise ValueError('shtdat (date) is mandatory')
    shtdat_str = str(shtdat).strip()
    try:
        # Strict parse
        dt = datetime.strptime(shtdat_str, '%Y-%m-%d')
        out['shtdat'] = dt.strftime('%Y-%m-%d')
    except Exception:
        raise ValueError('shtdat must be a date in YYYY-MM-DD format')

    # adjsmt: mandatory numeric with exactly 2 decimals, no commas
    adjsmt = record.get('adjsmt')
    if adjsmt is None or str(adjsmt).strip() == '':
        raise ValueError('adjsmt (amount) is mandatory')
    # Accept strings or numbers; normalize using Decimal
    try:
        dec = Decimal(str(adjsmt)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        raise ValueError('adjsmt must be a numeric value')
    # Ensure formatting with exactly two decimals and no commas
    if dec.as_tuple().exponent != -2:
        # Convert to two-decimal string
        dec = dec.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    out['adjsmt'] = format(dec, 'f')

    # Shser: RRN, mandatory, max 50 chars
    shser = record.get('Shser')
    if not shser or not str(shser).strip():
        raise ValueError('Shser (RRN) is mandatory')
    shser = str(shser).strip()
    if len(shser) > 50:
        raise ValueError('Shser (RRN) exceeds max length 50')
    out['Shser'] = shser

    # Shcrd: NBIN + identifier (Mobile/Account/Aadhaar), mandatory, max 53 chars
    shcrd = record.get('Shcrd')
    if not shcrd or not str(shcrd).strip():
        raise ValueError('Shcrd is mandatory')
    shcrd = str(shcrd).strip()
    if len(shcrd) > 53:
        raise ValueError('Shcrd exceeds max length 53')
    out['Shcrd'] = shcrd

    # FileName: mandatory, max 50 chars
    fname = record.get('FileName')
    if not fname or not str(fname).strip():
        raise ValueError('FileName is mandatory')
    fname = str(fname).strip()
    if len(fname) > 50:
        raise ValueError('FileName exceeds max length 50')
    out['FileName'] = fname

    # reason: optional (NPCI reason code), if present max 5 chars
    reason = record.get('reason') or ''
    reason = str(reason).strip()
    if len(reason) > 5:
        reason = reason[:5]  # Truncate to prevent NPCI upload rejection
    out['reason'] = reason

    # specifyother: optional bank remarks, max 400 chars
    spec = record.get('specifyother') or ''
    spec = str(spec).strip()
    if len(spec) > 400:
        spec = spec[:400]  # Truncate to prevent NPCI upload rejection
    out['specifyother'] = spec

    # Flag-specific additional validations (conservative)
    # - RET: ensure reason present (NPCI return code)
    if flag == 'RET' and not reason:
        raise ValueError('RET flag requires a reason code')

    return out


def generate_annexure_iv_csv(records: List[Dict], output_path: Optional[str] = None, run_id: Optional[str] = None, cycle_id: Optional[str] = None):
    """Generate Annexure-IV CSV.

    Preferred usage is to provide `run_id` (and optional `cycle_id`) so the
    file is written to the standardized output folder structured as:

        <OUTPUT_DIR>/<run_id>/annexure/[cycle_<cycle_id>/]ANNEXURE_IV_<run_id>.csv

    Backwards-compatible: if `output_path` provided and `run_id` is None,
    writes directly to `output_path` (legacy behaviour).
    """
    if not isinstance(records, list):
        raise ValueError('records must be a list of dictionaries')

    normalized = []
    seen_bankrefs = set()
    for i, rec in enumerate(records):
        try:
            row = _validate_and_normalize(rec)
        except Exception as e:
            raise ValueError(f'Record index {i} invalid: {e}')

        # Uniqueness check for Bankadjref
        br = row['Bankadjref']
        if br in seen_bankrefs:
            raise ValueError(f'Duplicate Bankadjref detected: {br}')
        seen_bankrefs.add(br)
        normalized.append(row)

    # If run_id provided, use standardized reporting write
    if run_id:
        filename = f"ANNEXURE_IV_{run_id}.csv"
        # Use write_report which enforces UTF-8 and header ordering
        out = write_report(run_id, cycle_id, 'annexure', filename, COLUMN_ORDER, normalized)
        return out

    # Fallback legacy write to provided output_path
    if not output_path:
        raise ValueError('Either run_id or output_path must be provided')

    # Build DataFrame using exact column order
    df = pd.DataFrame(normalized, columns=COLUMN_ORDER)

    # Ensure file directory exists
    import os
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    # Write CSV: UTF-8 (no BOM), comma-separated, no index
    df.to_csv(output_path, index=False, encoding='utf-8')


if __name__ == '__main__':
    # Small sample dataset and write to sample file when executed directly
    sample = [
        {
            'Bankadjref': 'BR00120260104',
            'Flag': 'DRC',
            'shtdat': '2026-01-04',
            'adjsmt': '150.00',
            'Shser': '518221608885',
            'Shcrd': 'NBIN1234567890',
            'FileName': 'cbs_inward_20260104.csv',
            'reason': '100',
            'specifyother': 'Auto-reversal detected'
        },
        {
            'Bankadjref': 'BR00220260104',
            'Flag': 'CR',
            'shtdat': '2026-01-04',
            'adjsmt': '200.50',
            'Shser': '518221608884',
            'Shcrd': 'NBIN0987654321',
            'FileName': 'cbs_outward_20260104.csv',
            'reason': '',
            'specifyother': 'Remitter refund'
        }
    ]
    outp = os.path.join(os.path.dirname(__file__), 'data', 'output', 'annexure_iv_sample.csv')
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    try:
        generate_annexure_iv_csv(sample, outp)
        print('Sample Annexure-IV written to', outp)
    except Exception as e:
        print('Failed to write sample:', e)
