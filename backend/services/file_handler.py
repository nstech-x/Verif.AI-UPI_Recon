import os
import pandas as pd
from typing import Dict, List
from config import UPLOAD_DIR, OUTPUT_DIR, RUN_ID_FORMAT
from services.logging_config import get_logger
from services.file_naming import parse_upi_filename

logger = get_logger(__name__)

class FileHandler:
    def __init__(self):
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    def save_uploaded_files(self, files: Dict, run_id: str, cycle: str = None, direction: str = None, run_date: str = None, per_file_cycles: Dict[str, str] = None, uploaded_by: str = "AUTO") -> str:
        """Save uploaded files to timestamped folder with standardized naming - Windows compatible
        Supports cycle subfolders and direction metadata. Returns run_folder path.
        """
        # Prepare run folder (kept for backward compatibility)
        run_folder = os.path.join(UPLOAD_DIR, run_id)
        os.makedirs(run_folder, exist_ok=True)

        # Normalize run-level cycle
        cycle_id = None
        if cycle:
            safe_cycle = str(cycle).strip().replace(' ', '_')
            cycle_id = safe_cycle

        # Normalize direction (used as fallback per-file)
        direction_global = None
        if direction:
            direction_global = 'Inward' if direction.upper() == 'INWARD' else 'Outward'

        # Enhanced file type mapping with better pattern recognition
        file_type_mapping = {
            'cbs_inward': ['cbs_inward', 'cbs inward', 'cbs-inward', 'cbsinward'],
            'cbs_outward': ['cbs_outward', 'cbs outward', 'cbs-outward', 'cbsoutward'],
            'switch': ['switch', 'switch_file', 'switch data', 'switch-data'],
            'npci_inward': ['npci_inward', 'npci inward', 'npci-inward', 'npciinward', 'npci inward remittance'],
            'npci_outward': ['npci_outward', 'npci outward', 'npci-outward', 'npcioutward', 'npci outward remittance'],
            'drc': ['drc', 'drc_report', 'drc report'],
            'ntsl': ['ntsl', 'ntsl_file', 'ntsl data', 'national', 'national_switch'],
            'adjustment': ['adjustment', 'adjustments', 'adj', 'adjustment_file']
        }

        saved_files = {}
        file_metadata = {}

        for filename, file_content in files.items():
            # Determine file type using enhanced pattern matching
            file_type = self._determine_file_type(filename, file_type_mapping)

            # Generate standardized filename with timestamp and validation
            standardized_name = self._generate_standardized_filename(file_type, filename)

            # place file inside run folder (legacy location)
            file_path = os.path.join(run_folder, standardized_name)

            try:
                # Validate file content before saving
                if self._validate_file_content(file_content, filename):
                    # Ensure write-once: do not overwrite existing files
                    final_path = file_path
                    suffix = 1
                    while os.path.exists(final_path):
                        name, ext = os.path.splitext(standardized_name)
                        final_path = os.path.join(run_folder, f"{name}_{suffix}{ext}")
                        suffix += 1
                    with open(final_path, 'wb') as f:
                        f.write(file_content)
                    # Make saved file read-only where possible (write-once)
                    try:
                        os.chmod(final_path, 0o444)
                    except Exception:
                        pass
                    file_path = final_path

                    existing = saved_files.get(file_type)
                    if existing is None:
                        saved_files[file_type] = os.path.basename(file_path)
                    elif isinstance(existing, list):
                        existing.append(os.path.basename(file_path))
                        saved_files[file_type] = existing
                    else:
                        saved_files[file_type] = [existing, os.path.basename(file_path)]
                    parsed = parse_upi_filename(filename) or {}
                    row_count = self._count_rows(file_path)
                    file_metadata[filename] = {
                        'standardized_name': os.path.basename(file_path),
                        'file_type': file_type,
                        'original_name': filename,
                        'file_size': len(file_content),
                        'saved_at': os.path.getctime(file_path),
                        'legacy_path': file_path,
                        'uploaded_by': uploaded_by or 'AUTO',
                        'row_count': row_count,
                        'parsed': parsed,
                    }
                    logger.info(f"✅ Saved file: {standardized_name} (original: {filename}, type: {file_type})")
                else:
                    logger.warning(f"⚠️  Skipped invalid/empty file: {filename}")
                    continue

            except Exception as e:
                logger.error(f"❌ Error saving file {filename}: {e}")
                continue

        # Save enhanced file mapping and metadata
        # add run-level metadata (persist canonical cycle_id when available)
        meta = {
            'run_id': run_id,
            'cycle_id': cycle_id if cycle_id else cycle,
            'direction': direction,
            'run_date': run_date,
            'saved_files': saved_files,
            'files_detail': file_metadata,
            'uploaded_by': uploaded_by or 'AUTO',
        }
        self._save_file_metadata(run_folder, saved_files, file_metadata)
        # also write top-level metadata.json in the run root (not cycle subfolder)
        try:
            top_meta_path = os.path.join(UPLOAD_DIR, run_id, 'metadata.json')
            import json
            with open(top_meta_path, 'w') as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass

        # ALSO store files in structured layout inside run_id folder
        for filename, file_content in files.items():
            try:
                info = file_metadata.get(filename, {})
                file_type = info.get('file_type') or self._determine_file_type(filename, file_type_mapping)
                parsed = info.get('parsed') or parse_upi_filename(filename) or {}

                subdir = file_type
                if file_type.startswith('npci_'):
                    direction = (parsed.get('direction') or '').lower()
                    txn_type = (parsed.get('txn_type') or '').lower()
                    subdir = os.path.join('npci', direction or 'unknown', txn_type or 'unknown')
                elif file_type == 'cbs_inward' or file_type == 'cbs_outward' or file_type == 'cbs_general':
                    subdir = 'cbs'
                elif file_type == 'switch':
                    subdir = 'switch'
                elif file_type == 'ntsl':
                    subdir = 'ntsl'
                elif file_type == 'adjustment':
                    subdir = 'adjustment'
                elif filename.lower().startswith('drc'):
                    subdir = 'drc'
                else:
                    subdir = 'other'

                dest_dir = os.path.join(run_folder, subdir)
                os.makedirs(dest_dir, exist_ok=True)
                dest_path = os.path.join(dest_dir, file_metadata[filename]['standardized_name'])

                legacy = file_metadata[filename].get('legacy_path')
                if legacy and os.path.exists(legacy):
                    try:
                        import shutil
                        shutil.copy2(legacy, dest_path)
                    except Exception:
                        with open(dest_path, 'wb') as f:
                            f.write(file_content)
                else:
                    with open(dest_path, 'wb') as f:
                        f.write(file_content)

                file_metadata[filename]['structured_path'] = dest_path
            except Exception as e:
                try:
                    logger.warning(f"Could not copy file {filename} to structured path: {e}")
                except Exception:
                    pass

        return run_folder

    def validate_file_bytes(self, file_content: bytes, filename: str) -> (bool, str):
        """Validate bytes of uploaded file to enforce required fields and formats.
        Enhanced with UPI-specific validation rules.
        Returns (True, "") if valid or (False, error_message).
        """
        from io import BytesIO
        import pandas as pd

        try:
            # File format validation
            ext = filename.lower()
            if ext.endswith('.csv'):
                df = pd.read_csv(BytesIO(file_content))
            elif ext.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(BytesIO(file_content))
            elif ext.endswith('.txt'):
                # Handle pipe/tab delimited text files
                df = pd.read_csv(BytesIO(file_content), sep='\t', engine='python')
            else:
                return False, 'Unsupported file extension; only CSV/Excel/TXT allowed'

            # Enhanced column mapping for UPI files
            df_mapped = self._smart_map_columns_upi(df)

            # Determine file type for specific validation rules
            file_type = self._determine_file_type(filename, self._get_upi_file_mapping())

            # UPI-specific validation based on file type
            validation_result = self._validate_upi_file_content(df_mapped, filename, file_type)
            if not validation_result[0]:
                return validation_result

            return True, ''
        except Exception as e:
            return False, f'Validation error: {str(e)}'

    def _get_upi_file_mapping(self):
        """Get enhanced file type mapping for UPI files"""
        return {
            'cbs_inward': ['cbs_inward', 'cbs inward', 'cbs-inward', 'cbsinward', 'cbs inward gl'],
            'cbs_outward': ['cbs_outward', 'cbs outward', 'cbs-outward', 'cbsoutward', 'cbs outward gl'],
            'switch': ['switch', 'switch_file', 'switch data', 'switch-data', 'switch log'],
            'npci_inward': ['npci_inward', 'npci inward', 'npci-inward', 'npciinward', 'npci inward remittance', 'npci raw inward'],
            'npci_outward': ['npci_outward', 'npci outward', 'npci-outward', 'npcioutward', 'npci outward remittance', 'npci raw outward'],
            'npci_merchant_inward': ['npci merchant inward', 'merchant inward', 'npci_merchant_inward'],
            'npci_merchant_outward': ['npci merchant outward', 'merchant outward', 'npci_merchant_outward'],
            'drc': ['drc', 'drc_report', 'drc report'],
            'ntsl': ['ntsl', 'ntsl_file', 'ntsl data', 'national', 'national_switch', 'ntsl settlement'],
            'adjustment': ['adjustment', 'adjustments', 'adj', 'adjustment_file', 'credit adjustment', 'debit adjustment']
        }

    def _smart_map_columns_upi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Enhanced column mapping for UPI files with additional fields"""
        renamed_df = df.copy()

        # Extended column definitions for UPI files - prioritized by likelihood
        upi_column_definitions = {
            'UPI_Tran_ID': ['upi_tran_id', 'upi id', 'upi_transaction_id', 'upi_txn_id', 'upi_txn',
                           'transaction_ref', 'transaction_ref_no', 'customer reference number', 'transaction_id', 'transaction id'],
            'RRN': ['rrn', 'reference number', 'ref number', 'reference', 'ref',
                   'unique id', 'unique_id', 'reference_no', 'ref_no', 'system trace audit number'],
            'Amount': ['amount', 'amt', 'tran amount', 'transaction amount',
                      'tran_amt', 'transaction_amt', 'value', 'amount_inr',
                      'tran_value', 'transaction_value', 'principal', 'principal_amount',
                      'actual transaction amount'],
            'Tran_Date': ['date', 'tran date', 'transaction date', 'tran_date',
                         'transaction_date', 'trn date', 'trn_date', 'dt',
                         'trans_date', 'transaction_dt', 'date_time', 'datetime',
                         'tran_datetime', 'transaction_datetime', 'card acceptor settl date'],
            'Time': ['time', 'tran time', 'transaction time', 'tran_time', 'transaction_time',
                    'trn time', 'trn_time', 'transaction_time', 'tran_datetime'],
            'Dr_Cr': ['dr_cr', 'd/c', 'dr/cr', 'debit_credit', 'debit/credit',
                     'type', 'transaction_type', 'tran_type', 'txn_type', 'mode',
                     'credit_debit', 'c/d', 'cd'],
            'RC': ['rc', 'rcode', 'response code', 'response_code', 'status',
                  'status_code', 'response', 'rcode_val', 'response_val', 'error_code'],
            'Tran_Type': ['type', 'tran type', 'transaction type', 'tran_type',
                         'transaction_type', 'mode', 'payment type', 'payment_type',
                         'transaction_mode', 'payment_mode', 'service', 'service_type'],
            'Reference_ID': ['reference_id', 'reference id', 'ref_id', 'upi_tran_id', 'transaction_ref'],
            'Description': ['description', 'narration', 'remarks', 'notes', 'comments', 'reference_text'],
            'Beneficiary_Number': ['beneficiary number', 'beneficiary', 'bene_number', 'bene num', 'benef_acc'],
            'Remitter_Number': ['remitter number', 'remitter', 'remit_number', 'remit num', 'remit_acc'],
            'Payer_PSP': ['payer psp', 'payer_psp', 'payer psp code', 'remitter psp', 'payer_code'],
            'Payee_PSP': ['payee psp', 'payee_psp', 'payee psp code', 'beneficiary psp', 'payee_code'],
            'MCC': ['mcc', 'merchant category code'],
            'Originating_Channel': ['originating channel', 'channel', 'otp indicator', 'originating_channel']
        }

        # Create standard columns
        for standard_col, possible_names in upi_column_definitions.items():
            found_col = self._find_best_matching_column(df.columns, possible_names)

            if found_col:
                renamed_df[standard_col] = df[found_col]
            else:
                # Create empty column if not found - will be populated or remain empty
                renamed_df[standard_col] = pd.NA

        # Preserve original columns for reference
        # Keep the original columns alongside mapped ones
        original_cols = set(df.columns)
        mapped_cols = set(upi_column_definitions.keys())
        for col in original_cols - mapped_cols:
            if col not in renamed_df.columns:
                renamed_df[col] = df[col]

        return renamed_df

    def _validate_upi_file_content(self, df_mapped: pd.DataFrame, filename: str, file_type: str) -> (bool, str):
        """UPI-specific file content validation with enhanced RRN validation"""

        # Basic required fields validation
        base_required = ['RRN', 'Amount', 'Tran_Date']
        missing = []
        for col in base_required:
            if col not in df_mapped.columns or df_mapped[col].isnull().all():
                missing.append(col)

        if missing:
            return False, f'Missing required columns: {missing}'

        # RRN validation - ensure RRN is distinct and not just UPI_Tran_ID
        # RRN should be a numeric or alphanumeric code, typically different from UPI_Tran_ID
        rrn_col = df_mapped['RRN']
        if rrn_col.dtype == 'object':
            rrn_values = rrn_col.astype(str).str.strip()
            # Check if RRN values are non-empty
            if (rrn_values == '').any():
                logger.warning('Some RRN values are empty; these transactions may be unmatched')
            # Check for duplicate RRN patterns across too many rows (indicator of mapping error)
            rrn_counts = rrn_values.value_counts()
            if len(rrn_counts) > 0:
                # If one value appears in more than 50% of rows, likely mapping error
                max_count_pct = (rrn_counts.iloc[0] / len(rrn_values)) * 100
                if max_count_pct > 50:
                    logger.warning(f'RRN "{rrn_counts.index[0]}" appears in {max_count_pct:.1f}% of rows; may indicate column mapping issue')

        # Amount validation - must be > 0 for financial transactions
        try:
            df_mapped['Amount'] = pd.to_numeric(df_mapped['Amount'], errors='coerce').fillna(0)
            if (df_mapped['Amount'] <= 0).any():
                return False, 'Amount must be > 0 for all financial transactions'
        except Exception:
            return False, 'Amount column not numeric'

        # File type specific validations
        if 'npci' in file_type:
            return self._validate_npci_file(df_mapped, file_type)
        elif 'cbs' in file_type:
            return self._validate_cbs_file(df_mapped, file_type)
        elif 'switch' in file_type:
            return self._validate_switch_file(df_mapped, file_type)
        elif 'ntsl' in file_type:
            return self._validate_ntsl_file(df_mapped, file_type)
        elif 'adjustment' in file_type:
            return self._validate_adjustment_file(df_mapped, file_type)
        elif 'drc' in file_type:
            return self._validate_drc_file(df_mapped)

        return True, ''

    def _validate_npci_file(self, df: pd.DataFrame, file_type: str) -> (bool, str):
        """Validate NPCI file content"""

        # Tran_Type validation for NPCI files
        if 'Tran_Type' in df.columns:
            import re
            tt = df['Tran_Type'].astype(str).str.strip().str.upper()
            # Accept common NPCI Tran_Type patterns: U followed by digits (U2, U3, etc.)
            non_empty = tt[tt.notna() & (tt != '')]
            if not non_empty.empty:
                invalid = [v for v in non_empty.unique() if not re.match(r'^U\d+$', str(v))]
                if invalid:
                    # Allow certain benign placeholders (export artifacts) like NONE/NA and do not block upload.
                    benign = [v for v in invalid if str(v).upper() in ('NONE', 'NA', 'NAN', '') or 'NONE' in str(v).upper()]
                    other = [v for v in invalid if v not in benign]
                    if other:
                        return False, f'Tran_Type contains unexpected values: {other}; expected pattern U<digit> (e.g., U2, U3)'
                    else:
                        # only benign values present — log a warning and accept
                        try:
                            logger.warning(f"Tran_Type contains benign placeholder values {invalid}; accepting upload")
                        except Exception:
                            pass

        # RC (Response Code) validation
        if 'RC' in df.columns:
            rc_values = df['RC'].astype(str).str.strip().fillna('')
            # Accept numeric codes (00, 01..99), RB, and common textual statuses produced by exports
            import re
            def is_valid_rc(v: str) -> bool:
                if v == '':
                    return True
                if re.match(r'^RB', v, flags=re.IGNORECASE):
                    return True
                if re.match(r'^0?\d{1,2}$', v):
                    return True
                if re.match(r'^U?\d+$', v):
                    return True
                # common textual statuses
                if v.upper() in ('00', '0', 'SUCCESS', 'S', 'RB', 'FAILED', 'FAIL', 'F', 'PENDING', 'P'):
                    return True
                return False

            invalid_mask = ~rc_values.apply(is_valid_rc)
            invalid_vals = rc_values[invalid_mask].unique().tolist()
            if invalid_vals:
                # If invalid values look like benign placeholders (e.g., column headers, export markers), allow but warn
                benign = [v for v in invalid_vals if any(x in str(v).upper() for x in ('NONE', 'N/A', 'NA', 'PENDING', 'SUCCESS', 'FAILED'))]
                other = [v for v in invalid_vals if v not in benign]
                if other:
                    return False, f'Invalid Response Codes found: {other}'
                else:
                    try:
                        logger = get_logger(__name__)
                        logger.warning(f"RC column contains textual/status markers {invalid_vals}; accepting upload")
                    except Exception:
                        pass

        # UPI_Tran_ID validation for NPCI files
        if 'UPI_Tran_ID' in df.columns:
            upi_ids = df['UPI_Tran_ID'].astype(str).str.strip()
            if upi_ids.isnull().any() or (upi_ids == '').any():
                return False, 'UPI_Tran_ID cannot be empty in NPCI files'

        return True, ''

    def _validate_cbs_file(self, df: pd.DataFrame, file_type: str) -> (bool, str):
        """Validate CBS file content"""

        # Dr_Cr validation for CBS files
        if 'Dr_Cr' in df.columns:
            # Normalize values conservatively and accept common variants
            dr_cr_values = df['Dr_Cr'].astype(str).fillna('').str.strip().str.upper()
            # Normalize textual forms to DR/CR
            norm = dr_cr_values.str.replace(r'[^A-Z]', '', regex=True)
            norm = norm.replace({'DEBIT': 'DR', 'DEBITS': 'DR', 'CREDIT': 'CR', 'CREDITS': 'CR'})
            # Accept single-letter and full forms after normalization
            valid_norms = {'DR', 'CR', 'D', 'C', ''}
            invalids = [v for v in norm.unique() if v not in valid_norms]
            if invalids:
                # If invalids look like file-type markers (e.g., 'CBSINWARD', 'CBSOUTWARD') or placeholders,
                # treat them as benign export artifacts and accept the file with a warning.
                benign_markers = [v for v in invalids if any(x in str(v) for x in ('CBS', 'INWARD', 'OUTWARD', 'CBSINWARD', 'CBSOUTWARD', 'CBS_IN', 'CBS_OUT')) or str(v).upper() in ('NONE','NA','NAN','')]
                other_invalids = [v for v in invalids if v not in benign_markers]
                if other_invalids:
                    return False, f"Dr_Cr contains unexpected values: {other_invalids}; expected DR/CR or equivalent"
                else:
                    try:
                        logger.warning(f"Dr_Cr column contains benign markers {invalids}; accepting upload")
                    except Exception:
                        pass

        return True, ''

    def _validate_switch_file(self, df: pd.DataFrame, file_type: str) -> (bool, str):
        """Validate Switch file content"""

        # Switch files should have both financial and non-financial transactions
        # Basic validation - ensure we have transaction data
        if len(df) == 0:
            return False, 'Switch file cannot be empty'

        return True, ''

    def _validate_ntsl_file(self, df: pd.DataFrame, file_type: str) -> (bool, str):
        """Validate NTSL file content"""

        # NTSL files should have settlement amount summaries
        required_ntsl_cols = ['Amount']
        for col in required_ntsl_cols:
            if col not in df.columns:
                return False, f'NTSL file missing required column: {col}'

        return True, ''

    def _validate_adjustment_file(self, df: pd.DataFrame, file_type: str) -> (bool, str):
        """Validate Adjustment file content"""

        # Adjustment files should have adjustment details
        adj_required = ['Amount', 'RRN']
        for col in adj_required:
            if col not in df.columns:
                return False, f'Adjustment file missing required column: {col}'

        # Validate adjustment types
        if 'Adj_Type' in df.columns or 'Adjustment_Type' in df.columns:
            adj_col = 'Adj_Type' if 'Adj_Type' in df.columns else 'Adjustment_Type'
            adj_types = df[adj_col].astype(str).str.strip().str.upper()
            valid_adj_types = ['CREDIT ADJUSTMENT', 'DEBIT ADJUSTMENT', 'DRC', 'RRC', 'TCC', 'RET']
            if not adj_types.isin(valid_adj_types).all():
                return False, f'Invalid adjustment types found. Valid types: {valid_adj_types}'

        return True, ''

    def _validate_drc_file(self, df: pd.DataFrame) -> (bool, str):
        """Validate DRC file content in expected NPCI DRC format."""
        required = ['RRN', 'Amount', 'Tran_Date']
        for col in required:
            if col not in df.columns or df[col].isnull().all():
                return False, f'DRC file missing required column: {col}'
        return True, ''

    def _determine_file_type(self, filename: str, file_type_mapping: Dict) -> str:
        """Determine file type using enhanced pattern matching"""
        filename_lower = filename.lower().strip()

        # Recognize new NPCI filename format (ISSR/ACQR...)
        parsed = parse_upi_filename(filename)
        if parsed:
            if parsed.get("direction") == "INWARD":
                return "npci_inward"
            return "npci_outward"

        # Check for exact matches first
        for file_type, patterns in file_type_mapping.items():
            for pattern in patterns:
                if pattern.lower() in filename_lower:
                    return file_type

        # Fallback: extract type from filename components
        if 'cbs' in filename_lower:
            if 'inward' in filename_lower or 'inw' in filename_lower:
                return 'cbs_inward'
            elif 'outward' in filename_lower or 'out' in filename_lower:
                return 'cbs_outward'
            else:
                return 'cbs_general'
        elif 'switch' in filename_lower:
            return 'switch'
        elif 'npci' in filename_lower:
            if 'inward' in filename_lower or 'inw' in filename_lower:
                return 'npci_inward'
            elif 'outward' in filename_lower or 'out' in filename_lower:
                return 'npci_outward'
            else:
                return 'npci_general'
        elif 'drc' in filename_lower:
            return 'drc'
        elif 'ntsl' in filename_lower or 'national' in filename_lower:
            return 'ntsl'
        elif 'adjust' in filename_lower:
            return 'adjustment'

        # Final fallback: clean filename for type
        return filename_lower.replace(' ', '_').replace('-', '_').split('_')[0]

    def _generate_standardized_filename(self, file_type: str, original_filename: str) -> str:
        """Generate standardized filename with timestamp and proper extension"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Determine file extension
        extension = self._get_file_extension(original_filename)

        # Create standardized name based on file type
        if file_type == 'cbs_inward':
            return f"cbs_inward_{timestamp}{extension}"
        elif file_type == 'cbs_outward':
            return f"cbs_outward_{timestamp}{extension}"
        elif file_type == 'switch':
            return f"switch_{timestamp}{extension}"
        elif file_type == 'npci_inward':
            return f"npci_inward_{timestamp}{extension}"
        elif file_type == 'npci_outward':
            return f"npci_outward_{timestamp}{extension}"
        elif file_type == 'drc':
            return f"drc_{timestamp}{extension}"
        elif file_type == 'ntsl':
            return f"ntsl_{timestamp}{extension}"
        elif file_type == 'adjustment':
            return f"adjustment_{timestamp}{extension}"
        else:
            # Generic naming for unknown types
            return f"{file_type}_{timestamp}{extension}"

    def _get_file_extension(self, filename: str) -> str:
        """Determine appropriate file extension"""
        filename_lower = filename.lower()
        if filename_lower.endswith('.csv'):
            return '.csv'
        elif filename_lower.endswith(('.xlsx', '.xls')):
            return '.xlsx'
        elif filename_lower.endswith('.txt'):
            return '.txt'
        elif filename_lower.endswith('.json'):
            return '.json'
        else:
            # Default to CSV for financial data files
            return '.csv'

    def _validate_file_content(self, file_content: bytes, filename: str) -> bool:
        """Validate file content before saving"""
        if not file_content or len(file_content) == 0:
            logger.warning(f"File '{filename}' is empty.")
            return False

        # Check for minimum file size (at least 10 bytes for valid data)
        if len(file_content) < 10:
            logger.warning(f"File '{filename}' is too small to be a valid data file.")
            return False

        # Validate file content based on extension
        if filename.lower().endswith('.xlsx'):
            if not self._is_xlsx(file_content):
                logger.error(f"File '{filename}' has an .xlsx extension but is not a valid XLSX file.")
                return False
        
        return True

    def _count_rows(self, filepath: str) -> int:
        """Count data rows (excluding header) for CSV/XLSX files."""
        try:
            if filepath.lower().endswith('.csv'):
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    # subtract header
                    return max(sum(1 for _ in f) - 1, 0)
            if filepath.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(filepath)
                return int(len(df.index))
        except Exception:
            return 0
        return 0

    def _is_xlsx(self, file_content: bytes) -> bool:
        """Check if the file content has the XLSX magic number."""
        # XLSX files (which are zip files) start with 'PK\x03\x04'
        return file_content.startswith(b'PK\x03\x04')

    def _save_file_metadata(self, run_folder: str, saved_files: Dict, file_metadata: Dict):
        """Save comprehensive file metadata and mapping"""
        try:
            # Save file mapping
            mapping_file = os.path.join(run_folder, "file_mapping.json")
            with open(mapping_file, 'w') as f:
                import json
                json.dump(saved_files, f, indent=2)

            # Save detailed metadata
            metadata_file = os.path.join(run_folder, "file_metadata.json")
            with open(metadata_file, 'w') as f:
                json.dump(file_metadata, f, indent=2, default=str)

            logger.info(f"✅ File metadata saved for {len(saved_files)} files")

        except Exception as e:
            logger.warning(f"⚠️  Could not save file metadata: {e}")
    
    def load_files_for_recon(self, run_folder: str) -> List[pd.DataFrame]:
        """Load all files and add source column with smart column detection"""
        dataframes = []
        
        if not os.path.exists(run_folder):
            print(f"Folder does not exist: {run_folder}")
            return dataframes
        
        for filename in os.listdir(run_folder):
            filepath = os.path.join(run_folder, filename)
            
            # Skip empty files (placeholder files)
            if os.path.getsize(filepath) == 0:
                print(f"Skipping empty file: {filename}")
                continue
            
            if filename.endswith('.csv'):
                try:
                    df = pd.read_csv(filepath)
                except Exception as e:
                    print(f"Error reading CSV file {filepath}: {e}")
                    continue
            elif filename.endswith(('.xlsx', '.xls')):
                try:
                    df = pd.read_excel(filepath)
                except Exception as e:
                    print(f"Error reading Excel file {filepath}: {e}")
                    continue
            else:
                continue
            
            if 'cbs' in filename.lower():
                source = 'CBS'
            elif 'switch' in filename.lower():
                source = 'SWITCH'
            elif 'npci' in filename.lower():
                source = 'NPCI'
            else:
                source = 'OTHER'
            
            # Smart auto-map columns
            df = self._smart_map_columns(df)
            df['Source'] = source
            dataframes.append(df)
        return dataframes
    
    def _smart_map_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Smartly map columns using multiple detection methods"""
        renamed_df = df.copy()
        
        # Standard column definitions with multiple possible names
        column_definitions = {
            'UPI_Tran_ID': ['upi_tran_id', 'upi id', 'upi_transaction_id', 'upi_txn_id', 'upi_txn', 'transaction_ref', 'transaction_ref_no', 'transaction_id', 'transaction id'],
            'RRN': ['rrn', 'reference number', 'ref number', 'reference', 'ref', 
                   'transaction id', 'txn id', 'transaction_id', 'txn_id', 'id', 
                   'unique id', 'unique_id', 'reference_no', 'ref_no'],
            'Amount': ['amount', 'amt', 'tran amount', 'transaction amount', 
                      'tran_amt', 'transaction_amt', 'value', 'amt', 'amount_inr', 
                      'tran_value', 'transaction_value', 'principal', 'principal_amount'],
            'Tran_Date': ['date', 'tran date', 'transaction date', 'tran_date', 
                         'transaction_date', 'trn date', 'trn_date', 'dt', 
                         'trans_date', 'transaction_dt', 'date_time', 'datetime',
                         'tran_datetime', 'transaction_datetime'],
            'Dr_Cr': ['dr_cr', 'd/c', 'dr/cr', 'debit_credit', 'debit/credit', 
                     'type', 'transaction_type', 'tran_type', 'txn_type', 'mode',
                     'credit_debit', 'c/d', 'cd'],
            'RC': ['rc', 'rcode', 'response code', 'response_code', 'status', 
                  'status_code', 'response', 'rcode_val', 'response_val', 'error_code'],
            'Tran_Type': ['type', 'tran type', 'transaction type', 'tran_type', 
                         'transaction_type', 'mode', 'payment type', 'payment_type', 
                         'transaction_mode', 'payment_mode', 'service', 'service_type']
        }
        
        # Create standard columns
        for standard_col, possible_names in column_definitions.items():
            found_col = self._find_best_matching_column(df.columns, possible_names)
            
            if found_col:
                renamed_df[standard_col] = df[found_col]
            else:
                renamed_df[standard_col] = None
        
        # Keep UPI-specific columns + required columns + Source
        required_cols = ['UPI_Tran_ID', 'RRN', 'Amount', 'Tran_Date', 'Dr_Cr', 'RC', 'Tran_Type', 'Source']
        available_cols = [col for col in required_cols if col in renamed_df.columns]
        
        return renamed_df[available_cols]
    
    def _find_best_matching_column(self, df_columns, possible_names):
        """Find the best matching column using multiple strategies"""
        # Strategy 1: Exact match (case-insensitive)
        for col in df_columns:
            if col.lower().strip() in [name.lower() for name in possible_names]:
                return col
        
        # Strategy 2: Partial match (contains keywords)
        for col in df_columns:
            col_lower = col.lower().strip()
            for name in possible_names:
                if name.lower() in col_lower or col_lower in name.lower():
                    return col
        
        # Strategy 3: Return first column if no matches found (for debugging)
        # This is fallback - in production you might want to return None
        return None
