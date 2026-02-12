import io
import logging
import os
import re
import pandas as pd

logger = logging.getLogger(__name__)


async def validate_file_columns(content: bytes, filename: str, file_type: str) -> dict:
    """Validate that required columns exist in uploaded files with flexible column name matching"""
    try:
        # Read file content into DataFrame - handle both CSV and Excel files
        _, ext = os.path.splitext(filename)
        if ext.lower() in ('.xlsx', '.xls'):
            df = pd.read_excel(io.BytesIO(content), engine='openpyxl', dtype=str)
        else:
            df = pd.read_csv(io.BytesIO(content), dtype=str)

        # Log actual columns present in the file for debugging
        logger.info(f"File: {filename}, Type: {file_type}, Columns found: {list(df.columns)}")

        # Define required columns with possible name variations for flexible matching
        required_columns_flexible = {
            'cbs_inward': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
                'Date': ['Date', 'date', 'tran date', 'transaction date', 'tran_date', 'transaction_date', 'dt'],
                'Debit_Credit': ['Debit_Credit', 'debit_credit', 'd/c', 'dr/cr', 'dr_cr', 'type', 'transaction_type'],
            },
            'cbs_outward': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
                'Date': ['Date', 'date', 'tran date', 'transaction date', 'tran_date', 'transaction_date', 'dt'],
                'Debit_Credit': ['Debit_Credit', 'debit_credit', 'd/c', 'dr/cr', 'dr_cr', 'type', 'transaction_type'],
            },
            'switch': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
                'Date': ['Date', 'date', 'tran date', 'transaction date', 'tran_date', 'transaction_date', 'dt'],
            },
            'npci_inward': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
                'Date': ['Date', 'date', 'tran date', 'transaction date', 'tran_date', 'transaction_date', 'dt'],
            },
            'npci_outward': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
                'Date': ['Date', 'date', 'tran date', 'transaction date', 'tran_date', 'transaction_date', 'dt'],
            },
            'ntsl': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
            },
            'adjustment': {
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Amount': ['Amount', 'amount', 'amt', 'tran amount', 'transaction amount', 'tran_amt', 'transaction_amt', 'value'],
                'Reason': ['Reason', 'reason', 'description', 'desc', 'remarks', 'adjustment_type', 'type'],
            },
            'drc': {
                'Tran Date': ['Tran Date', 'tran date', 'tran_date', 'date', 'transaction date'],
                'Tran ID': ['Tran ID', 'tran id', 'tran_id', 'transaction id', 'transaction_id'],
                'RRN': ['RRN', 'rrn', 'reference number', 'ref number', 'reference', 'ref'],
                'Tran_Amt': ['Tran_Amt', 'tran_amt', 'tran amount', 'transaction amount', 'amount', 'amt'],
                'Remit Bank Name': ['Remit Bank Name', 'remit bank name'],
                'Remit Bank IFSC': ['Remit Bank IFSC', 'remit bank ifsc'],
                'Bene Bank Name': ['Bene Bank Name', 'bene bank name'],
                'Bene Bank IFSC': ['Bene Bank IFSC', 'bene bank ifsc'],
                'Res Code': ['Res Code', 'res code', 'response code', 'rc'],
                'Tran Type': ['Tran Type', 'tran type', 'tran_type', 'transaction type'],
            },
        }

        # Get required columns for this file type
        req_cols_dict = required_columns_flexible.get(file_type, {})

        # Define which columns are critical (must be present) vs optional (warnings only)
        critical_columns = [
            'RRN', 'Amount', 'Tran_Amt', 'Tran Date', 'Tran ID', 'Res Code', 'Tran Type',
            'Remit Bank Name', 'Remit Bank IFSC', 'Bene Bank Name', 'Bene Bank IFSC'
        ]  # Always required
        optional_columns = ['Date', 'Debit_Credit', 'Reason']  # Warnings only if missing

        # Case-insensitive column matching
        normalized_map = {str(col).strip().lower(): col for col in df.columns}
        normalized_cols = set(normalized_map.keys())

        def find_column(possible_names):
            for name in possible_names:
                hit = normalized_map.get(str(name).strip().lower())
                if hit is not None:
                    return hit
            return None

        # DRC supports two accepted layouts:
        # 1) strict NPCI layout (Tran ID, bank details, Res Code, Tran Type...)
        # 2) legacy compact layout (RRN, Reason, Amount, Date)
        active_required_keys = set(req_cols_dict.keys())
        if file_type == "drc":
            strict_required = [
                "Tran Date", "Tran ID", "RRN", "Tran_Amt",
                "Remit Bank Name", "Remit Bank IFSC", "Bene Bank Name", "Bene Bank IFSC",
                "Res Code", "Tran Type",
            ]
            legacy_required = ["RRN", "Amount", "Date"]

            def has_col(req_key: str) -> bool:
                possible = req_cols_dict.get(req_key, [req_key])
                return any(str(name).strip().lower() in normalized_cols for name in possible)

            strict_ok = all(has_col(c) for c in strict_required)
            legacy_ok = all(has_col(c) for c in legacy_required)

            if not strict_ok and not legacy_ok:
                missing = [c for c in strict_required if not has_col(c)]
                return {
                    "valid": False,
                    "error": f"Missing required columns: {', '.join(missing)}",
                    "missing_columns": missing,
                    "suggestion": "Provide strict DRC format or legacy format with RRN, Amount, Date.",
                }
            # Limit required-column checks to the selected schema.
            if legacy_ok and not strict_ok:
                active_required_keys = set(legacy_required)
            else:
                active_required_keys = set(strict_required)

        # Check for missing columns using flexible matching
        missing_critical = []
        missing_optional = []
        for req_col, possible_names in req_cols_dict.items():
            if req_col not in active_required_keys and req_col in critical_columns:
                continue
            found = any(str(name).strip().lower() in normalized_cols for name in possible_names)
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
                "suggestion": f"Please ensure the file contains columns for: {'; '.join(suggestions)}",
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
                "suggestion": "Please ensure the file contains transaction data",
            }

        # Warnings (don't block upload)
        if df.isnull().values.any():
            warnings.append(f"File contains {df.isnull().sum().sum()} null values")

        # Row-level strict checks: reject files with malformed core values.
        row_errors = []
        rrn_col = None
        amount_col = None

        if "RRN" in req_cols_dict:
            rrn_col = find_column(req_cols_dict["RRN"])
        # Prefer Tran_Amt when that is the required amount field (e.g., DRC), else Amount.
        if "Tran_Amt" in req_cols_dict:
            amount_col = find_column(req_cols_dict["Tran_Amt"])
        if not amount_col and "Amount" in req_cols_dict:
            amount_col = find_column(req_cols_dict["Amount"])

        def normalize_rrn(value) -> str:
            if value is None:
                return ""
            s = str(value).strip()
            if s.lower() in ("", "nan", "none"):
                return ""
            # Handle numeric-looking strings commonly parsed/exported as float text (e.g., 369419548116.0)
            if re.fullmatch(r"\d+\.0", s):
                s = s[:-2]
            return s

        if rrn_col:
            for idx, value in df[rrn_col].items():
                rrn = normalize_rrn(value)
                if rrn == "":
                    row_errors.append({
                        "row": int(idx) + 2,  # +2 for header + 1-based index
                        "column": rrn_col,
                        "error": "RRN is empty",
                    })
                    continue
                if not re.fullmatch(r"\d{12}", rrn):
                    row_errors.append({
                        "row": int(idx) + 2,
                        "column": rrn_col,
                        "error": f"RRN must be exactly 12 digits, got '{rrn}'",
                    })

        if amount_col:
            for idx, value in df[amount_col].items():
                raw = "" if value is None else str(value).strip()
                if raw.lower() in ("", "nan", "none"):
                    row_errors.append({
                        "row": int(idx) + 2,
                        "column": amount_col,
                        "error": "Amount is empty",
                    })
                    continue
                try:
                    amt = float(raw.replace(",", ""))
                except Exception:
                    row_errors.append({
                        "row": int(idx) + 2,
                        "column": amount_col,
                        "error": f"Amount must be numeric, got '{raw}'",
                    })
                    continue
                if amt <= 0:
                    row_errors.append({
                        "row": int(idx) + 2,
                        "column": amount_col,
                        "error": f"Amount must be > 0, got '{raw}'",
                    })

        if row_errors:
            # Keep switch upload non-blocking, but surface row-level issues in status screens.
            if file_type == "switch":
                warnings.append(f"Row-level issues found in {len(row_errors)} row(s)")
                return {
                    "valid": True,
                    "warnings": warnings,
                    "row_errors": row_errors[:200],
                    "row_error_count": len(row_errors),
                }
            return {
                "valid": False,
                "error": f"Row-level validation failed in {len(row_errors)} row(s)",
                "row_errors": row_errors[:200],
                "suggestion": "Correct invalid row values (e.g., RRN must be 12 digits and amount must be numeric > 0)",
            }

        return {
            "valid": True,
            "warnings": warnings,
        }

    except pd.errors.EmptyDataError:
        return {
            "valid": False,
            "error": "File is empty or contains no valid data",
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Error reading file: {str(e)}",
        }
