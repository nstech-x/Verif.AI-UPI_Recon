import io
import logging
import os
import pandas as pd

logger = logging.getLogger(__name__)


async def validate_file_columns(content: bytes, filename: str, file_type: str) -> dict:
    """Validate that required columns exist in uploaded files with flexible column name matching"""
    try:
        # Read file content into DataFrame - handle both CSV and Excel files
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
