import pandas as pd
import os
from typing import Dict, List, Tuple
import json
from datetime import datetime
from loguru import logger
from settlement_engine import SettlementEngine
from config import UPLOAD_DIR as CFG_UPLOAD_DIR
from reporting import write_report

# Constants
CBS = 'cbs'
SWITCH = 'switch'
NPCI = 'npci'
NTSL = 'ntsl'
SOURCES = [CBS, SWITCH, NPCI, NTSL]

RRN = 'RRN'
AMOUNT = 'Amount'
TRAN_DATE = 'Tran_Date'
SOURCE = 'Source'
DR_CR = 'Dr_Cr'
RC = 'RC'
TRAN_TYPE = 'Tran_Type'
UPI_ID = 'UPI_Tran_ID'

MATCHED = 'MATCHED'
MISMATCH = 'MISMATCH'
PARTIAL_MATCH = 'PARTIAL_MATCH'
PARTIAL_MISMATCH = 'PARTIAL_MISMATCH'
ORPHAN = 'HANGING'
UNKNOWN = 'UNKNOWN'
FORCE_MATCHED = 'FORCE_MATCHED'
PROCESSING_ERROR = 'PROCESSING_ERROR'
HANGING = 'HANGING'
DUPLICATE = 'DUPLICATE'

class ReconciliationEngine:
    def __init__(self, output_dir: str = "./data/output"):
        self.output_dir = output_dir
        self.matched_records = []
        self.partial_match_records = []
        self.hanging_records = []
        self.exceptions = []
        self.unmatched_records = []
        self.settlement_engine = SettlementEngine(output_dir)
    
    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values in the dataframe based on a configuration."""
        
        # Configuration for handling missing values
        missing_value_config = {
            RRN: {'fillna': '', 'astype': str, 'strip': True},
            AMOUNT: {'to_numeric': True, 'fillna': 0},
            TRAN_DATE: {'fillna': '1970-01-01', 'astype': str},
            DR_CR: {'fillna': '', 'astype': str},
            RC: {'fillna': '', 'astype': str},
            TRAN_TYPE: {'fillna': '', 'astype': str}
        }

        for col, config in missing_value_config.items():
            if col in df.columns:
                if config.get('to_numeric'):
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(config['fillna'])
                else:
                    df[col] = df[col].fillna(config['fillna'])
                
                if 'astype' in config:
                    df[col] = df[col].astype(config['astype'])
                
                if config.get('strip'):
                    df[col] = df[col].str.strip()
        
        return df

    def reconcile(self, dataframes: List[pd.DataFrame]) -> Dict:
        """Main reconciliation logic - RRN + Amount + Date matching with comprehensive error handling"""
        logger.info(f"Starting reconciliation with {len(dataframes)} dataframes")

        self._clear_previous_run_data()

        try:
            processed_dataframes = self._preprocess_dataframes(dataframes)
            combined_df = self._combine_dataframes(processed_dataframes)
            results = self._perform_reconciliation_logic(combined_df)
            self._generate_summary(results)
            
            return results

        except Exception as e:
            logger.error(f"Reconciliation failed with error: {str(e)}")
            raise ValueError(f"Reconciliation process failed: {str(e)}")

    def _clear_previous_run_data(self):
        """Clears data from previous reconciliation runs."""
        self.matched_records = []
        self.partial_match_records = []
        self.hanging_records = []
        self.exceptions = []
        self.unmatched_records = []

    def _preprocess_dataframes(self, dataframes: List[pd.DataFrame]) -> List[pd.DataFrame]:
        """Preprocessing and validation of the input dataframes."""
        processed_dataframes = []
        for i, df in enumerate(dataframes):
            try:
                required_cols = [RRN, AMOUNT, TRAN_DATE, SOURCE]
                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    raise ValueError(f"Dataframe {i} missing required columns: {missing_cols}")

                df = self._handle_missing_values(df)

                original_count = len(df)
                df = df[df[RRN] != ''].reset_index(drop=True)
                removed_count = original_count - len(df)

                if removed_count > 0:
                    logger.warning(f"Removed {removed_count} rows with empty RRN from dataframe {i}")

                if not df.empty:
                    processed_dataframes.append(df)
                    logger.info(f"Processed dataframe {i}: {len(df)} valid records")
                else:
                    logger.warning(f"Dataframe {i} became empty after preprocessing")

            except Exception as df_error:
                logger.error(f"Error preprocessing dataframe {i}: {str(df_error)}")
                raise ValueError(f"Data preprocessing failed for dataframe {i}: {str(df_error)}")
        
        if not processed_dataframes:
            logger.error("No valid dataframes after preprocessing")
            raise ValueError("No valid data found after preprocessing all dataframes")
            
        return processed_dataframes

    def _combine_dataframes(self, dataframes: List[pd.DataFrame]) -> pd.DataFrame:
        """Combine the processed dataframes into a single dataframe."""
        try:
            combined_df = pd.concat(dataframes, ignore_index=True)
            logger.info(f"Combined dataframe has {len(combined_df)} total records")

            original_count = len(combined_df)
            combined_df = combined_df[combined_df[RRN] != ''].reset_index(drop=True)
            removed_count = original_count - len(combined_df)

            if removed_count > 0:
                logger.warning(f"Removed {removed_count} additional rows with empty RRN during combination")

            if combined_df.empty:
                logger.error("Combined dataframe is empty after final cleanup")
                raise ValueError("No valid transaction records found after data combination")
                
            return combined_df

        except Exception as combine_error:
            logger.error(f"Error combining dataframes: {str(combine_error)}")
            raise ValueError(f"Data combination failed: {str(combine_error)}")

    def _perform_reconciliation_logic(self, combined_df: pd.DataFrame) -> Dict:
        """Enhanced reconciliation logic with improved matching, duplicate detection, and missing RRN handling."""
        results = {}
        try:
            # First: attempt matching by UPI_Tran_ID when RRN missing
            if UPI_ID in combined_df.columns:
                upi_df = combined_df[combined_df[UPI_ID].notnull() & (combined_df[RRN].isnull() | (combined_df[RRN] == ''))]
                if not upi_df.empty:
                    upi_grouped = upi_df.groupby(UPI_ID)
                    for upi, ugroup in upi_grouped:
                        try:
                            key = f"UPI_{upi}"
                            record = self._create_record_structure()
                            self._populate_record_by_source(record, ugroup)
                            # Enhanced matching check with tolerance for small amount differences
                            amounts = [record[s]['amount'] for s in SOURCES if record[s]]
                            dates = [record[s]['date'] for s in SOURCES if record[s]]
                            if self._enhanced_amount_match(amounts) and len(set(dates)) == 1 and len([s for s in SOURCES if record[s]]) >= 2:
                                record['status'] = MATCHED
                                self.matched_records.append(key)
                            else:
                                record['status'] = PARTIAL_MATCH
                                self.partial_match_records.append(key)
                            results[key] = record
                        except Exception as e:
                            logger.warning(f"UPI grouping failed for {upi}: {e}")

            # Enhanced duplicate detection: identify RRNs that appear multiple times within or across sources
            duplicate_info = self._detect_comprehensive_duplicates(combined_df)

            grouped = combined_df.groupby(RRN)
            total_groups = len(grouped)
            logger.info(f"Processing {total_groups} unique RRN groups")

            for rrn, group in grouped:
                try:
                    sources = set(group[SOURCE].tolist())
                    record = self._create_record_structure()

                    self._populate_record_by_source(record, group)

                    # Check for comprehensive duplicates
                    if rrn in duplicate_info:
                        dup_type = duplicate_info[rrn]['type']
                        record['status'] = DUPLICATE
                        record['duplicate_info'] = duplicate_info[rrn]
                        self.exceptions.append(rrn)
                        results[rrn] = record
                        logger.warning(f"Duplicate detected for RRN {rrn}: {dup_type}")
                        continue

                    # Cut-off handling: if a declined txn has a reversal present (RC startswith 'RB'),
                    # mark as HANGING (declined with reversal in next/other cycle)
                    try:
                        if self._detect_cutoff_reversal(group, record):
                            record['status'] = HANGING
                            record['hanging_reason'] = 'declined_with_reversal'
                            if 'hanging_list' not in results:
                                results['hanging_list'] = []
                            results['hanging_list'].append(rrn)
                            results[rrn] = record
                            continue
                    except Exception:
                        pass

                    # Enhanced self-reversal detection: debit + credit same amount and date within any source
                    if self._detect_self_reversal(group):
                        record['status'] = MATCHED
                        record['reversal_detected'] = True
                        self.matched_records.append(rrn)
                        results[rrn] = record
                        continue

                    # Enhanced record classification with better partial matching
                    self._enhanced_classify_record(rrn, record, sources, group)

                    # Enhanced hanging detection with more scenarios
                    self._enhanced_hanging_detection(rrn, record, results)

                    results[rrn] = record

                except Exception as rrn_error:
                    logger.error(f"Error processing RRN {rrn}: {str(rrn_error)}")
                    self.exceptions.append(rrn)
                    results[rrn] = self._create_error_record(rrn_error)

        except Exception as logic_error:
            logger.error(f"Critical error in reconciliation logic: {str(logic_error)}")
            raise ValueError(f"Reconciliation logic failed: {str(logic_error)}")

        return results

    def _enhanced_amount_match(self, amounts: List) -> bool:
        """Check if amounts match with tolerance for small differences."""
        if len(amounts) < 2:
            return False
        amounts = [float(a) for a in amounts if a is not None and str(a).strip()]
        if not amounts:
            return False
        # Check if all amounts are within 0.01 tolerance of each other
        min_amt = min(amounts)
        max_amt = max(amounts)
        return abs(max_amt - min_amt) < 0.01

    def _detect_comprehensive_duplicates(self, combined_df: pd.DataFrame) -> Dict:
        """Detect RRNs that appear multiple times within or across sources."""
        duplicate_info = {}

        # Check for duplicates within each source
        for src in [CBS, SWITCH, NPCI]:
            src_df = combined_df[combined_df[SOURCE].str.lower() == src]
            if not src_df.empty:
                counts = src_df[RRN].value_counts()
                for rrn, count in counts[counts > 1].items():
                    if rrn not in duplicate_info:
                        duplicate_info[rrn] = {'type': f'Multiple in {src.upper()} ({count} times)', 'sources': [src]}
                    else:
                        duplicate_info[rrn]['sources'].append(src)

        # Check for cross-source duplicates (same RRN in multiple sources with different data)
        rrn_groups = combined_df.groupby(RRN)
        for rrn, group in rrn_groups:
            if len(group) > 1:  # Multiple records for same RRN
                sources = group[SOURCE].unique()
                if len(sources) > 1:
                    # Check if amounts or dates differ across sources
                    amounts = group[AMOUNT].unique()
                    dates = group[TRAN_DATE].unique()
                    if len(amounts) > 1 or len(dates) > 1:
                        duplicate_info[rrn] = {
                            'type': 'Cross-source data mismatch',
                            'sources': sources.tolist(),
                            'amounts': amounts.tolist(),
                            'dates': dates.tolist()
                        }

        return duplicate_info

    def _detect_self_reversal(self, group: pd.DataFrame) -> bool:
        """Enhanced self-reversal detection: debit + credit same amount and date within any source."""
        if DR_CR not in group.columns:
            return False

        try:
            grp = group.copy()
            grp['amount_num'] = pd.to_numeric(grp[AMOUNT], errors='coerce').fillna(0)
            grp['drcr'] = grp[DR_CR].astype(str).str.upper().str.strip()

            # Group by source to check within each source
            for source, src_group in grp.groupby(SOURCE):
                if len(src_group) < 2:
                    continue

                # Find debit-credit pairs with same amount and date
                debits = src_group[src_group['drcr'].isin(['D', 'DEBIT'])]
                credits = src_group[src_group['drcr'].isin(['C', 'CREDIT'])]

                for _, debit_row in debits.iterrows():
                    for _, credit_row in credits.iterrows():
                        if (debit_row['amount_num'] == credit_row['amount_num'] and
                            debit_row[TRAN_DATE] == credit_row[TRAN_DATE]):
                            return True
        except Exception:
            pass
        return False

    def _enhanced_classify_record(self, rrn: str, record: Dict, sources: set, group: pd.DataFrame):
        """Enhanced record classification with better partial matching."""
        amounts = [record[s]['amount'] for s in SOURCES if record[s]]
        dates = [record[s]['date'] for s in SOURCES if record[s]]

        num_sources = len(sources)
        amounts_match = self._enhanced_amount_match(amounts)
        dates_match = len(set(dates)) == 1

        if num_sources == 3:
            if amounts_match and dates_match:
                record['status'] = MATCHED
                self.matched_records.append(rrn)
            else:
                record['status'] = MISMATCH
                self.exceptions.append(rrn)
        elif num_sources == 2:
            if amounts_match and dates_match:
                record['status'] = PARTIAL_MATCH
                self.partial_match_records.append(rrn)
            else:
                record['status'] = PARTIAL_MISMATCH
                self.exceptions.append(rrn)
        elif num_sources == 1:
            record['status'] = ORPHAN
            self.orphan_records.append(rrn)
        else:
            record['status'] = UNKNOWN
            self.exceptions.append(rrn)

        # Enhanced TCC rules with better logic
        try:
            npc = record.get(NPCI)
            cbs = record.get(CBS)
            if npc and str(npc.get('rc','')).upper().startswith('RB'):
                if cbs and str(cbs.get('dr_cr','')).upper().startswith('C'):
                    record['tcc'] = 'TCC_102'
                else:
                    record['tcc'] = 'TCC_103'
                    record['needs_ttum'] = True
        except Exception:
            pass

        # Enhanced NTSL Settlement matching
        try:
            ntsl_rec = record.get(NTSL)
            if ntsl_rec:
                ntsl_amt = float(str(ntsl_rec.get('amount') or 0) or 0)
                gl_amt = None
                if cbs and cbs.get('amount') is not None:
                    gl_amt = float(cbs.get('amount') or 0)
                elif record.get(SWITCH) and record.get(SWITCH).get('amount') is not None:
                    gl_amt = float(record.get(SWITCH).get('amount') or 0)
                elif record.get(NPCI) and record.get(NPCI).get('amount') is not None:
                    gl_amt = float(record.get(NPCI).get('amount') or 0)

                if gl_amt is not None and abs(ntsl_amt - gl_amt) < 0.01:
                    record['status'] = MATCHED
                    record['settlement_matched'] = True
                    if rrn not in self.matched_records:
                        self.matched_records.append(rrn)
        except Exception:
            pass

        # Enhanced failed transaction handling
        try:
            if npc:
                rc_val = str(npc.get('rc','')).upper()
                success_codes = ['00', '0', 'SUCCESS', 'S', 'APPROVED', 'A']
                if rc_val not in success_codes and rc_val:
                    if cbs and str(cbs.get('rc','')).upper() in success_codes:
                        record['status'] = 'EXCEPTION'
                        record['exception_reason'] = 'NPCI failed but CBS successful'
                        self.exceptions.append(rrn)
        except Exception:
            pass

    def _enhanced_hanging_detection(self, rrn: str, record: Dict, results: Dict):
        """Enhanced hanging detection with more scenarios."""
        # Basic hanging: CBS + SWITCH present, NPCI missing
        if record.get(CBS) and record.get(SWITCH) and not record.get(NPCI):
            if record['status'] == ORPHAN:
                record['status'] = HANGING
                record['hanging_reason'] = 'CBS and SWITCH present, NPCI missing'
                if 'hanging_list' not in results:
                    results['hanging_list'] = []
                results['hanging_list'].append(rrn)

        # Advanced hanging: Amount mismatch between CBS and SWITCH
        elif record.get(CBS) and record.get(SWITCH):
            try:
                cbs_amt = float(record[CBS].get('amount') or 0)
                switch_amt = float(record[SWITCH].get('amount') or 0)
                if abs(cbs_amt - switch_amt) > 0.01:  # Significant difference
                    record['status'] = HANGING
                    record['hanging_reason'] = f'Amount mismatch: CBS={cbs_amt}, SWITCH={switch_amt}'
                    if 'hanging_list' not in results:
                        results['hanging_list'] = []
                    results['hanging_list'].append(rrn)
            except Exception:
                pass

        # Date mismatch hanging
        elif record.get(CBS) and record.get(SWITCH):
            try:
                cbs_date = str(record[CBS].get('date') or '').strip()
                switch_date = str(record[SWITCH].get('date') or '').strip()
                if cbs_date and switch_date and cbs_date != switch_date:
                    record['status'] = HANGING
                    record['hanging_reason'] = f'Date mismatch: CBS={cbs_date}, SWITCH={switch_date}'
                    if 'hanging_list' not in results:
                        results['hanging_list'] = []
                    results['hanging_list'].append(rrn)
            except Exception:
                pass

    def _create_record_structure(self) -> Dict:
        """Creates a new, empty record structure."""
        return {
            CBS: None,
            SWITCH: None,
            NPCI: None,
            NTSL: None,
            'status': UNKNOWN
        }

    def _populate_record_by_source(self, record: Dict, group: pd.DataFrame):
        """Populates a record with data from a grouped DataFrame."""
        for _, row in group.iterrows():
            source = row[SOURCE].lower()
            if source in SOURCES:
                record[source] = {
                    'amount': row[AMOUNT],
                    'date': row[TRAN_DATE],
                    'dr_cr': row.get(DR_CR, ''),
                    'rc': row.get(RC, ''),
                    'tran_type': row.get(TRAN_TYPE, '')
                }

    def _detect_cutoff_reversal(self, group: pd.DataFrame, record: Dict) -> bool:
        """Detect declined transactions that have a reversal present (RC starting with 'RB').
        If found, returns True to indicate hanging/cutoff condition.
        Operates on the grouped DataFrame for a single RRN."""
        try:
            # Normalize RC values
            rc_vals = group[RC].astype(str).str.strip().str.upper().fillna('') if RC in group.columns else []
            # Any reversal markers
            has_reversal = any(str(r).upper().startswith('RB') for r in rc_vals)
            # Any declined (non-success) markers
            success_markers = {'00', '0', 'SUCCESS', 'S'}
            has_decline = any((str(r) not in success_markers and str(r) != '') for r in rc_vals)

            # If both decline and reversal present, treat as cut-off hanging
            return has_decline and has_reversal
        except Exception:
            return False

    def _classify_record(self, rrn: str, record: Dict, sources: set):
        """Classifies a record based on its status (e.g., MATCHED, MISMATCH)."""
        amounts = [record[s]['amount'] for s in SOURCES if record[s]]
        dates = [record[s]['date'] for s in SOURCES if record[s]]

        amount_set = set(amounts)
        date_set = set(dates)

        num_sources = len(sources)
        amounts_match = len(amount_set) == 1
        dates_match = len(date_set) == 1

        if num_sources == 3:
            if amounts_match and dates_match:
                record['status'] = MATCHED
                self.matched_records.append(rrn)
            else:
                record['status'] = MISMATCH
                self.exceptions.append(rrn)
        elif num_sources == 2:
            if amounts_match and dates_match:
                record['status'] = PARTIAL_MATCH
                self.partial_match_records.append(rrn)
            else:
                record['status'] = PARTIAL_MISMATCH
                self.exceptions.append(rrn)
        elif num_sources == 1:
            record['status'] = ORPHAN
            self.hanging_records.append(rrn)
        else:
            record['status'] = UNKNOWN
            self.exceptions.append(rrn)

        # TCC rules: if NPCI RC startswith 'RB'
        try:
            npc = record.get(NPCI)
            cbs = record.get(CBS)
            if npc and str(npc.get('rc','')).upper().startswith('RB'):
                if cbs and cbs.get('dr_cr','').upper().startswith('C'):
                    record['tcc'] = 'TCC_102'
                else:
                    record['tcc'] = 'TCC_103'
                    # mark as needs TTUM
                    record['needs_ttum'] = True
        except Exception:
            pass

        # NTSL Settlement: if NTSL exists and amount equals CBS/GL amount, mark as settlement matched
        try:
            ntsl_rec = record.get(NTSL)
            if ntsl_rec:
                ntsl_amt = float(str(ntsl_rec.get('amount') or 0) or 0)
                # Prefer CBS as GL-equivalent; fallback to switch or npci
                gl_amt = None
                if cbs and cbs.get('amount') is not None:
                    gl_amt = float(cbs.get('amount') or 0)
                elif record.get(SWITCH) and record.get(SWITCH).get('amount') is not None:
                    gl_amt = float(record.get(SWITCH).get('amount') or 0)
                elif record.get(NPCI) and record.get(NPCI).get('amount') is not None:
                    gl_amt = float(record.get(NPCI).get('amount') or 0)

                if gl_amt is not None and abs(ntsl_amt - gl_amt) < 0.01:
                    # Treat as matched settlement
                    record['status'] = MATCHED
                    record['settlement_matched'] = True
                    if rrn not in self.matched_records:
                        self.matched_records.append(rrn)
        except Exception:
            pass

        # Failed txn handling: NPCI failed + CBS success -> Exception
        try:
            if npc:
                rc_val = str(npc.get('rc','')).upper()
                # treat non-success as failure (simple heuristics)
                if rc_val not in ['00','0','SUCCESS','S']:
                    if cbs and str(cbs.get('rc','')).upper() in ['00','0','SUCCESS','S']:
                        record['status'] = 'EXCEPTION'
                        self.exceptions.append(rrn)
        except Exception:
            pass
            
    def _create_error_record(self, error: Exception) -> Dict:
        """Creates a new record that represents a processing error."""
        return {
            CBS: None, SWITCH: None, NPCI: None,
            'status': PROCESSING_ERROR,
            'error': str(error)
        }

    def _generate_summary(self, results: Dict):
        """Generates a summary of the reconciliation results."""
        logger.info(f"Reconciliation completed: {len(results)} total RRNs processed")
        logger.info(f"Results: {len(self.matched_records)} matched, {len(self.partial_match_records)} partial, {len(self.hanging_records)} orphan, {len(self.exceptions)} exceptions")

    # -------------------------
    # Reporting / Export helpers
    # -------------------------
    def _ensure_reports_dir(self, run_folder: str):
        import os
        reports_dir = os.path.join(run_folder, 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        return reports_dir

    def _parse_date(self, date_str: str):
        """Attempt to parse a date string into a date object. Returns None on failure."""
        from datetime import datetime
        if not date_str:
            return None
        try:
            # try ISO first
            return datetime.fromisoformat(str(date_str)).date()
        except Exception:
            try:
                return datetime.strptime(str(date_str), '%Y-%m-%d').date()
            except Exception:
                try:
                    return datetime.strptime(str(date_str), '%d-%m-%Y').date()
                except Exception:
                    return None

    def generate_report(self, results: Dict, run_folder: str, run_id: str = None, cycle_id: str = None):
        """Generate matched reports (GL vs Switch / Switch vs NPCI / GL vs NPCI)

        Produces six CSVs (inward/outward for each pair). Does not change
        reconciliation logic — uses existing `results` classification.
        Also writes `recon_output.json` for traceability.
        """
        import os
        import pandas as pd
        from datetime import datetime

        reports_dir = self._ensure_reports_dir(run_folder)

        # Save raw recon output for audit/consumers
        try:
            import json
            outp = os.path.join(reports_dir, 'recon_output.json')
            with open(outp, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str)
        except Exception:
            pass

        # Prepare rows for each required report
        report_rows = {
            'GL_vs_Switch_Inward': [],
            'GL_vs_Switch_Outward': [],
            'Switch_vs_NPCI_Inward': [],
            'Switch_vs_NPCI_Outward': [],
            'GL_vs_NPCI_Inward': [],
            'GL_vs_NPCI_Outward': []
        }

        # Helper to determine direction (inward/outward) using available fields
        def infer_direction(rec):
            # prefer explicit tran_type if it contains keywords
            for s in ['cbs', 'switch', 'npci']:
                src = rec.get(s)
                if src:
                    tt = str(src.get('tran_type') or '').upper()
                    if 'INWARD' in tt or 'IN' in tt:
                        return 'Inward'
                    if 'OUTWARD' in tt or 'OUT' in tt:
                        return 'Outward'
                    drcr = str(src.get('dr_cr') or '').upper()
                    if drcr.startswith('C'):
                        return 'Inward'
                    if drcr.startswith('D'):
                        return 'Outward'
            return 'Inward'

        # Iterate over results and populate rows
        for key, rec in results.items():
            # skip non-record entries (like hanging_list index)
            if not isinstance(rec, dict):
                continue
            status = rec.get('status')
            # Matched transactions
            if status == MATCHED or rec.get('settlement_matched'):
                # Get normalized values
                for pair, systems in [('GL_vs_Switch', (CBS, SWITCH)), ('Switch_vs_NPCI', (SWITCH, NPCI)), ('GL_vs_NPCI', (CBS, NPCI))]:
                    s1, s2 = systems
                    r1 = rec.get(s1)
                    r2 = rec.get(s2)
                    if r1 and r2:
                        # ensure amount & date match (strict equality as per rules)
                        try:
                            amt1 = float(r1.get('amount') or 0)
                            amt2 = float(r2.get('amount') or 0)
                        except Exception:
                            continue
                        date1 = r1.get('date')
                        date2 = r2.get('date')
                        if amt1 == amt2 and str(date1) == str(date2):
                            direction = infer_direction(rec)
                            # Build row following required schema
                            row = {
                                'run_id': run_id,
                                'cycle_id': cycle_id or '',
                                'RRN': key,
                                'UPI_Transaction_ID': (rec.get('UPI_Tran_ID') or ''),
                                'Amount': amt1,
                                'Transaction_Date': self._parse_date(date1).strftime('%Y-%m-%d') if self._parse_date(date1) else (str(date1) if date1 else ''),
                                'RC': (r1.get('rc') or r2.get('rc') or ''),
                                'Source_System_1': s1.upper(),
                                'Source_System_2': s2.upper(),
                                'Direction': infer_direction(rec),
                                'Matched_On': 'RRN'
                            }
                            report_key = f"{pair}_{direction}"
                            if report_key in report_rows:
                                report_rows[report_key].append(row)

        # Write reports using pandas with both CSV and XLSX formats
        matched_headers = [
            'run_id','cycle_id','RRN','UPI_Transaction_ID','Amount','Transaction_Date',
            'RC','Source_System_1','Source_System_2','Direction','Matched_On'
        ]
        import pandas as pd
        for name, rows in report_rows.items():
            try:
                df = pd.DataFrame(rows, columns=matched_headers) if rows else pd.DataFrame(columns=matched_headers)
                # Generate CSV
                csv_path = os.path.join(reports_dir, f"{name}.csv")
                df.to_csv(csv_path, index=False, encoding='utf-8')
                # Generate XLSX
                xlsx_path = os.path.join(reports_dir, f"{name}.xlsx")
                df.to_excel(xlsx_path, index=False, engine='openpyxl')
                logger.info(f"Generated {name}.csv and {name}.xlsx with {len(rows)} records")
            except Exception as e:
                logger.error(f"Failed to write report {name}: {e}")

        # Generate all comprehensive reports
        try:
            self.generate_all_comprehensive_reports(results, run_folder, run_id, cycle_id)
        except Exception as e:
            logger.warning(f"Failed to generate comprehensive reports: {e}")

        # Also generate switch update file (best-effort from results)
        try:
            self.generate_switch_update_file(results, reports_dir, run_id=run_id)
        except Exception:
            pass

    def generate_all_comprehensive_reports(self, results: Dict, run_folder: str, run_id: str = None, cycle_id: str = None):
        """Generate all comprehensive reports required by the system.
        
        Generates:
        - GL vs Switch - Matched Transactions (Inward/Outward)
        - GL vs Switch - Unmatched Transactions with ageing (Inward/Outward)
        - Switch vs Network - Matched Transactions (Inward/Outward)
        - Switch vs Network - Unmatched Transactions with ageing (Inward/Outward)
        - GL vs Network - Matched Transactions (Inward/Outward)
        - GL vs Network - Unmatched Transactions with ageing (Inward/Outward)
        - Hanging Transactions (Inward/Outward)
        """
        try:
            # Generate unmatched ageing reports
            self._generate_unmatched_ageing_reports(results, run_folder, run_id, cycle_id)
            logger.info("Generated unmatched ageing reports")
        except Exception as e:
            logger.warning(f"Failed to generate unmatched ageing reports: {e}")
        
        try:
            # Generate hanging transaction reports
            self.generate_hanging_reports(results, run_folder, run_id, cycle_id)
            logger.info("Generated hanging transaction reports")
        except Exception as e:
            logger.warning(f"Failed to generate hanging transaction reports: {e}")
        
        try:
            # Generate annexure reports (I, II, III, IV)
            self._generate_annexure_reports_from_regular_results(results, run_folder, run_id, cycle_id)
            logger.info("Generated annexure reports")
        except Exception as e:
            logger.warning(f"Failed to generate annexure reports: {e}")

        try:
            # Generate adjustments/annexure reports
            self._generate_adjustments_reports(results, run_folder, run_id, cycle_id)
            logger.info("Generated adjustments/annexure reports")
        except Exception as e:
            logger.warning(f"Failed to generate adjustments reports: {e}")

    def generate_upi_report(self, upi_results: Dict, run_folder: str, run_id: str = None, cycle_id: str = None):
        """Generate CSV reports from UPI reconciliation results
        
        Generates:
        - matched_transactions.csv: All matched transactions
        - unmatched_exceptions.csv: All exceptions that need attention
        - ttum_candidates.csv: Transactions requiring TTUM generation
        - GL_vs_Switch_Inward/Outward.csv: Matched transactions between GL and Switch
        - Switch_vs_NPCI_Inward/Outward.csv: Matched transactions between Switch and NPCI
        - GL_vs_NPCI_Inward/Outward.csv: Matched transactions between GL and NPCI
        - Unmatched_Inward/Outward_Ageing.csv: Unmatched transactions with ageing
        - Hanging_Inward/Outward.csv: Hanging transactions
        """
        import os
        import pandas as pd
        from datetime import datetime
        
        # Ensure reports directory exists
        reports_dir = self._ensure_reports_dir(run_folder)
        logger.info(f"Generating UPI reports in {reports_dir} for run {run_id}")
        
        try:
            # Verify directory is writable
            if not os.access(reports_dir, os.W_OK):
                logger.warning(f"Reports directory not writable: {reports_dir}, attempting to create...")
                os.makedirs(reports_dir, exist_ok=True)
            
            # Extract data from results
            summary = upi_results.get('summary', {})
            exceptions = upi_results.get('exceptions', [])
            ttum_candidates = upi_results.get('ttum_candidates', [])
            
            # Generate matched transactions report
            matched_rows = []
            for status_key in ['cbs_breakdown', 'switch_breakdown', 'npci_breakdown']:
                if status_key in summary.get('status_breakdown', {}):
                    breakdown = summary['status_breakdown'][status_key]
                    if isinstance(breakdown, dict) and 'MATCHED' in breakdown:
                        matched_rows.append({
                            'run_id': run_id,
                            'cycle_id': cycle_id or '',
                            'source': status_key.split('_')[0].upper(),
                            'matched_count': breakdown['MATCHED'],
                            'unmatched_count': breakdown.get('UNMATCHED', 0),
                            'hanging_count': breakdown.get('HANGING', 0)
                        })
            
            if matched_rows:
                df_matched = pd.DataFrame(matched_rows)
                matched_path_csv = os.path.join(reports_dir, 'matched_transactions.csv')
                matched_path_xlsx = os.path.join(reports_dir, 'matched_transactions.xlsx')
                df_matched.to_csv(matched_path_csv, index=False, encoding='utf-8')
                df_matched.to_excel(matched_path_xlsx, index=False, engine='openpyxl')
                logger.info(f"✅ Generated matched transactions reports: {matched_path_csv} and {matched_path_xlsx}")
            
            # Generate pairwise matched reports (GL vs Switch, Switch vs NPCI, GL vs NPCI)
            # These are required by frontend for reconciliation reports
            self._generate_pairwise_reports(exceptions, reports_dir, run_id, cycle_id)
            
            # Generate annexure reports
            self._generate_annexure_reports(upi_results, reports_dir, run_id, cycle_id)
            
            # Generate exceptions report
            if exceptions:
                df_exceptions = pd.DataFrame(exceptions)
                # Ensure required columns
                for col in ['source', 'rrn', 'amount', 'date', 'exception_type']:
                    if col not in df_exceptions.columns:
                        df_exceptions[col] = ''
                
                # Reorder columns for readability - include direction if available
                cols_to_keep = ['source', 'rrn', 'amount', 'date', 'time', 'reference', 
                               'description', 'debit_credit', 'direction', 'exception_type', 'ttum_required']
                cols_present = [c for c in cols_to_keep if c in df_exceptions.columns]
                df_exceptions = df_exceptions[cols_present]
                
                exceptions_path_csv = os.path.join(reports_dir, 'unmatched_exceptions.csv')
                exceptions_path_xlsx = os.path.join(reports_dir, 'unmatched_exceptions.xlsx')
                df_exceptions.to_csv(exceptions_path_csv, index=False, encoding='utf-8')
                df_exceptions.to_excel(exceptions_path_xlsx, index=False, engine='openpyxl')
                logger.info(f"✅ Generated exceptions reports: {exceptions_path_csv} and {exceptions_path_xlsx} ({len(exceptions)} records)")
                
                # Generate ageing reports from exceptions
                self._generate_ageing_reports_from_exceptions(exceptions, reports_dir, run_id, cycle_id)
                
                # Generate hanging reports from exceptions
                self._generate_hanging_reports_from_exceptions(exceptions, reports_dir, run_id, cycle_id)
            
            # Generate TTUM candidates report
            if ttum_candidates:
                df_ttum = pd.DataFrame(ttum_candidates)
                # Ensure required columns
                for col in ['source', 'rrn', 'amount', 'ttum_type', 'exception_type']:
                    if col not in df_ttum.columns:
                        df_ttum[col] = ''
                
                ttum_path_csv = os.path.join(reports_dir, 'ttum_candidates.csv')
                ttum_path_xlsx = os.path.join(reports_dir, 'ttum_candidates.xlsx')
                df_ttum.to_csv(ttum_path_csv, index=False, encoding='utf-8-sig')
                df_ttum.to_excel(ttum_path_xlsx, index=False, engine='openpyxl')
                logger.info(f"✅ Generated TTUM candidates reports: {ttum_path_csv} and {ttum_path_xlsx} ({len(ttum_candidates)} records)")
            
            # List all generated files
            generated_files = os.listdir(reports_dir) if os.path.exists(reports_dir) else []
            logger.info(f"✅ UPI reports generation completed. Files in {reports_dir}: {generated_files}")
            
        except Exception as e:
            logger.error(f"Error generating UPI reports: {str(e)}", exc_info=True)
            raise
    
    def _generate_pairwise_reports(self, exceptions: List[Dict], reports_dir: str, run_id: str, cycle_id: str):
        """Generate pairwise matched reports (GL vs Switch, Switch vs NPCI, GL vs NPCI)"""
        import pandas as pd

        # Initialize report data structures
        gl_switch_inward = []
        gl_switch_outward = []
        switch_npci_inward = []
        switch_npci_outward = []
        gl_npci_inward = []
        gl_npci_outward = []

        # Process exceptions to extract matched pairs
        # Note: In UPI format, we need to infer matches from exception data
        # For now, create empty reports with proper structure

        # Define headers
        headers = ['run_id', 'cycle_id', 'RRN', 'Amount', 'Transaction_Date', 'Direction', 'Status']

        # Write reports with both CSV and XLSX formats
        for name, data in [
            ('GL_vs_Switch_Inward', gl_switch_inward),
            ('GL_vs_Switch_Outward', gl_switch_outward),
            ('Switch_vs_NPCI_Inward', switch_npci_inward),
            ('Switch_vs_NPCI_Outward', switch_npci_outward),
            ('GL_vs_NPCI_Inward', gl_npci_inward),
            ('GL_vs_NPCI_Outward', gl_npci_outward)
        ]:
            df = pd.DataFrame(data, columns=headers) if data else pd.DataFrame(columns=headers)
            # Generate CSV
            csv_path = os.path.join(reports_dir, f"{name}.csv")
            df.to_csv(csv_path, index=False, encoding='utf-8')
            # Generate XLSX
            xlsx_path = os.path.join(reports_dir, f"{name}.xlsx")
            df.to_excel(xlsx_path, index=False, engine='openpyxl')
            logger.info(f"Generated {name}.csv and {name}.xlsx")
    
    def _generate_ageing_reports_from_exceptions(self, exceptions: List[Dict], reports_dir: str, run_id: str, cycle_id: str):
        """Generate ageing reports from exceptions"""
        import pandas as pd
        from datetime import datetime
        
        inward_rows = []
        outward_rows = []
        today = datetime.now().date()
        
        for exc in exceptions:
            direction = exc.get('direction', 'UNKNOWN')
            if direction not in ['INWARD', 'OUTWARD']:
                continue
            
            # Calculate ageing
            try:
                tran_date = pd.to_datetime(exc.get('date')).date()
                ageing_days = (today - tran_date).days
            except:
                ageing_days = 0
            
            # Determine bucket
            if ageing_days <= 1:
                bucket = '0-1 days'
            elif ageing_days <= 3:
                bucket = '2-3 days'
            else:
                bucket = '>3 days'
            
            row = {
                'run_id': run_id,
                'cycle_id': cycle_id or '',
                'RRN': exc.get('rrn', ''),
                'Amount': exc.get('amount', 0),
                'Transaction_Date': exc.get('date', ''),
                'Source': exc.get('source', ''),
                'Exception_Type': exc.get('exception_type', ''),
                'Ageing_Days': ageing_days,
                'Ageing_Bucket': bucket
            }
            
            if direction == 'INWARD':
                inward_rows.append(row)
            else:
                outward_rows.append(row)
        
        # Write reports
        if inward_rows:
            df_inward = pd.DataFrame(inward_rows)
            inward_path_csv = os.path.join(reports_dir, 'Unmatched_Inward_Ageing.csv')
            inward_path_xlsx = os.path.join(reports_dir, 'Unmatched_Inward_Ageing.xlsx')
            df_inward.to_csv(inward_path_csv, index=False, encoding='utf-8')
            df_inward.to_excel(inward_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated Unmatched_Inward_Ageing.csv and .xlsx with {len(inward_rows)} records")

        if outward_rows:
            df_outward = pd.DataFrame(outward_rows)
            outward_path_csv = os.path.join(reports_dir, 'Unmatched_Outward_Ageing.csv')
            outward_path_xlsx = os.path.join(reports_dir, 'Unmatched_Outward_Ageing.xlsx')
            df_outward.to_csv(outward_path_csv, index=False, encoding='utf-8')
            df_outward.to_excel(outward_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated Unmatched_Outward_Ageing.csv and .xlsx with {len(outward_rows)} records")
    
    def _generate_hanging_reports_from_exceptions(self, exceptions: List[Dict], reports_dir: str, run_id: str, cycle_id: str):
        """Generate hanging transaction reports from exceptions"""
        import pandas as pd
        
        inward_rows = []
        outward_rows = []
        
        for exc in exceptions:
            if exc.get('exception_type') == 'HANGING' or 'HANGING' in str(exc.get('exception_type', '')):
                direction = exc.get('direction', 'UNKNOWN')
                if direction not in ['INWARD', 'OUTWARD']:
                    continue
                
                row = {
                    'run_id': run_id,
                    'cycle_id': cycle_id or '',
                    'RRN': exc.get('rrn', ''),
                    'Amount': exc.get('amount', 0),
                    'Transaction_Date': exc.get('date', ''),
                    'Source': exc.get('source', ''),
                    'Reason': exc.get('exception_type', '')
                }
                
                if direction == 'INWARD':
                    inward_rows.append(row)
                else:
                    outward_rows.append(row)
        
        # Write reports
        if inward_rows:
            df_inward = pd.DataFrame(inward_rows)
            inward_path_csv = os.path.join(reports_dir, 'Hanging_Inward.csv')
            inward_path_xlsx = os.path.join(reports_dir, 'Hanging_Inward.xlsx')
            df_inward.to_csv(inward_path_csv, index=False, encoding='utf-8')
            df_inward.to_excel(inward_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated Hanging_Inward.csv and .xlsx with {len(inward_rows)} records")

        if outward_rows:
            df_outward = pd.DataFrame(outward_rows)
            outward_path_csv = os.path.join(reports_dir, 'Hanging_Outward.csv')
            outward_path_xlsx = os.path.join(reports_dir, 'Hanging_Outward.xlsx')
            df_outward.to_csv(outward_path_csv, index=False, encoding='utf-8')
            df_outward.to_excel(outward_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated Hanging_Outward.csv and .xlsx with {len(outward_rows)} records")
    
    def _generate_annexure_reports_from_regular_results(self, results: Dict, run_folder: str, run_id: str, cycle_id: str):
        """Generate ANNEXURE I, II, III, IV reports from regular reconciliation results"""
        reports_dir = self._ensure_reports_dir(run_folder)
        import pandas as pd

        # Extract data for annexure reports
        exceptions = []
        ttum_candidates = []

        # Process results to extract exceptions and TTUM candidates
        for rrn, record in results.items():
            if not isinstance(record, dict):
                continue

            status = record.get('status', '')
            direction = 'INWARD'  # Default, will be inferred

            # Infer direction from available data
            for source in ['cbs', 'switch', 'npci']:
                src_data = record.get(source)
                if src_data and isinstance(src_data, dict):
                    dr_cr = str(src_data.get('dr_cr', '')).upper()
                    if dr_cr.startswith('C'):
                        direction = 'INWARD'
                        break
                    elif dr_cr.startswith('D'):
                        direction = 'OUTWARD'
                        break

            # Create exception entry for problematic records
            if status in ['MISMATCH', 'PARTIAL_MISMATCH', 'ORPHAN', 'EXCEPTION']:
                # Determine source and amount
                source = 'UNKNOWN'
                amount = 0
                date = ''

                for src_name in ['cbs', 'switch', 'npci']:
                    src_data = record.get(src_name)
                    if src_data and isinstance(src_data, dict):
                        source = src_name.upper()
                        amount = src_data.get('amount', 0)
                        date = src_data.get('date', '')
                        break

                exceptions.append({
                    'rrn': rrn,
                    'amount': float(amount) if amount else 0,
                    'date': str(date) if date else '',
                    'source': source,
                    'direction': direction,
                    'exception_type': status,
                    'ttum_required': record.get('needs_ttum', False) or record.get('tcc') is not None,
                    'ttum_type': 'REVERSAL' if record.get('tcc') == 'TCC_103' else 'ADJUSTMENT'
                })

            # TTUM candidates
            if record.get('needs_ttum') or record.get('tcc'):
                ttum_candidates.append({
                    'rrn': rrn,
                    'amount': float(record.get('cbs', {}).get('amount', 0)) if isinstance(record.get('cbs'), dict) else 0,
                    'ttum_type': 'REVERSAL' if record.get('tcc') == 'TCC_103' else 'ADJUSTMENT',
                    'source': 'CBS',
                    'direction': direction,
                    'gl_accounts': '',
                    'exception_type': record.get('tcc') or status
                })

        # Generate ANNEXURE I: Raw Unmatched Transactions (CBS side)
        annexure_i_rows = []
        for exc in exceptions:
            if exc.get('source', '').upper() == 'CBS':
                annexure_i_rows.append({
                    'RRN': exc.get('rrn', ''),
                    'Amount': exc.get('amount', 0),
                    'Date': exc.get('date', ''),
                    'Direction': exc.get('direction', ''),
                    'Exception_Type': exc.get('exception_type', '')
                })

        if annexure_i_rows:
            df_i = pd.DataFrame(annexure_i_rows)
            ttum_annex_dir = os.path.join(reports_dir, 'ttum & annex')
            os.makedirs(ttum_annex_dir, exist_ok=True)
            annexure_i_path_csv = os.path.join(ttum_annex_dir, 'ANNEXURE_I.csv')
            annexure_i_path_xlsx = os.path.join(ttum_annex_dir, 'ANNEXURE_I.xlsx')
            df_i.to_csv(annexure_i_path_csv, index=False, encoding='utf-8')
            df_i.to_excel(annexure_i_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated ANNEXURE_I.csv and .xlsx with {len(annexure_i_rows)} records")

        # ANNEXURE II: Raw Unmatched Transactions (NPCI side)
        annexure_ii_rows = []
        for exc in exceptions:
            if exc.get('source', '').upper() == 'NPCI':
                annexure_ii_rows.append({
                    'RRN': exc.get('rrn', ''),
                    'Amount': exc.get('amount', 0),
                    'Date': exc.get('date', ''),
                    'Direction': exc.get('direction', ''),
                    'Exception_Type': exc.get('exception_type', '')
                })

        if annexure_ii_rows:
            df_ii = pd.DataFrame(annexure_ii_rows)
            ttum_annex_dir = os.path.join(reports_dir, 'ttum & annex')
            os.makedirs(ttum_annex_dir, exist_ok=True)
            annexure_ii_path_csv = os.path.join(ttum_annex_dir, 'ANNEXURE_II.csv')
            annexure_ii_path_xlsx = os.path.join(ttum_annex_dir, 'ANNEXURE_II.xlsx')
            df_ii.to_csv(annexure_ii_path_csv, index=False, encoding='utf-8')
            df_ii.to_excel(annexure_ii_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated ANNEXURE_II.csv and .xlsx with {len(annexure_ii_rows)} records")

        # ANNEXURE III: Adjustment Entries (TTUM candidates)
        annexure_iii_rows = []
        for ttum in ttum_candidates:
            annexure_iii_rows.append({
                'RRN': ttum.get('rrn', ''),
                'Amount': ttum.get('amount', 0),
                'TTUM_Type': ttum.get('ttum_type', ''),
                'Direction': ttum.get('direction', ''),
                'GL_Accounts': ttum.get('gl_accounts', ''),
                'Exception_Type': ttum.get('exception_type', '')
            })

        if annexure_iii_rows:
            df_iii = pd.DataFrame(annexure_iii_rows)
            annexure_iii_path_csv = os.path.join(reports_dir, 'ANNEXURE_III.csv')
            annexure_iii_path_xlsx = os.path.join(reports_dir, 'ANNEXURE_III.xlsx')
            df_iii.to_csv(annexure_iii_path_csv, index=False, encoding='utf-8')
            df_iii.to_excel(annexure_iii_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated ANNEXURE_III.csv and .xlsx with {len(annexure_iii_rows)} records")

        # ANNEXURE IV: Bulk Adjustments (all TTUM candidates grouped)
        if ttum_candidates:
            df_iv = pd.DataFrame(ttum_candidates)
            annexure_iv_path_csv = os.path.join(reports_dir, 'ANNEXURE_IV.csv')
            annexure_iv_path_xlsx = os.path.join(reports_dir, 'ANNEXURE_IV.xlsx')
            df_iv.to_csv(annexure_iv_path_csv, index=False, encoding='utf-8')
            df_iv.to_excel(annexure_iv_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated ANNEXURE_IV.csv and .xlsx with {len(ttum_candidates)} records")

    def _generate_annexure_reports(self, upi_results: Dict, reports_dir: str, run_id: str, cycle_id: str):
        """Generate ANNEXURE I, II, III, IV reports from UPI reconciliation results"""
        import pandas as pd
        from datetime import datetime
        
        exceptions = upi_results.get('exceptions', [])
        ttum_candidates = upi_results.get('ttum_candidates', [])
        
        # ANNEXURE I: Raw Unmatched Transactions (CBS side)
        annexure_i_rows = []
        for exc in exceptions:
            if exc.get('source', '').upper() == 'CBS':
                annexure_i_rows.append({
                    'RRN': exc.get('rrn', ''),
                    'Amount': exc.get('amount', 0),
                    'Date': exc.get('date', ''),
                    'Direction': exc.get('direction', ''),
                    'Exception_Type': exc.get('exception_type', '')
                })
        
        if annexure_i_rows:
            df_i = pd.DataFrame(annexure_i_rows)
            annexure_i_path_csv = os.path.join(reports_dir, 'ANNEXURE_I.csv')
            annexure_i_path_xlsx = os.path.join(reports_dir, 'ANNEXURE_I.xlsx')
            df_i.to_csv(annexure_i_path_csv, index=False, encoding='utf-8')
            df_i.to_excel(annexure_i_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated ANNEXURE_I.csv and .xlsx with {len(annexure_i_rows)} records")
        
        # ANNEXURE II: Raw Unmatched Transactions (NPCI side)
        annexure_ii_rows = []
        for exc in exceptions:
            if exc.get('source', '').upper() == 'NPCI':
                annexure_ii_rows.append({
                    'RRN': exc.get('rrn', ''),
                    'Amount': exc.get('amount', 0),
                    'Date': exc.get('date', ''),
                    'Direction': exc.get('direction', ''),
                    'Exception_Type': exc.get('exception_type', '')
                })
        
        if annexure_ii_rows:
            df_ii = pd.DataFrame(annexure_ii_rows)
            annexure_ii_path_csv = os.path.join(reports_dir, 'ANNEXURE_II.csv')
            annexure_ii_path_xlsx = os.path.join(reports_dir, 'ANNEXURE_II.xlsx')
            df_ii.to_csv(annexure_ii_path_csv, index=False, encoding='utf-8')
            df_ii.to_excel(annexure_ii_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated ANNEXURE_II.csv and .xlsx with {len(annexure_ii_rows)} records")
        
        # ANNEXURE III: Adjustment Entries (TTUM candidates)
        annexure_iii_rows = []
        for ttum in ttum_candidates:
            annexure_iii_rows.append({
                'RRN': ttum.get('rrn', ''),
                'Amount': ttum.get('amount', 0),
                'TTUM_Type': ttum.get('ttum_type', ''),
                'Direction': ttum.get('direction', ''),
                'GL_Accounts': ttum.get('gl_accounts', ''),
                'Exception_Type': ttum.get('exception_type', '')
            })
        
        if annexure_iii_rows:
            df_iii = pd.DataFrame(annexure_iii_rows)
            annexure_iii_path_csv = os.path.join(reports_dir, 'ANNEXURE_III.csv')
            annexure_iii_path_xlsx = os.path.join(reports_dir, 'ANNEXURE_III.xlsx')
            df_iii.to_csv(annexure_iii_path_csv, index=False, encoding='utf-8')
            df_iii.to_excel(annexure_iii_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated ANNEXURE_III.csv and .xlsx with {len(annexure_iii_rows)} records")
        
        # ANNEXURE IV: Bulk Adjustments (all TTUM candidates grouped)
        if ttum_candidates:
            df_iv = pd.DataFrame(ttum_candidates)
            annexure_iv_path_csv = os.path.join(reports_dir, 'ANNEXURE_IV.csv')
            annexure_iv_path_xlsx = os.path.join(reports_dir, 'ANNEXURE_IV.xlsx')
            df_iv.to_csv(annexure_iv_path_csv, index=False, encoding='utf-8')
            df_iv.to_excel(annexure_iv_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated ANNEXURE_IV.csv and .xlsx with {len(ttum_candidates)} records")

    def generate_unmatched_ageing(self, results: Dict, run_folder: str, run_id: str = None, cycle_id: str = None):
        """Generate unmatched inward/outward CSVs with ageing buckets."""
        import os
        import pandas as pd
        from datetime import datetime

        reports_dir = self._ensure_reports_dir(run_folder)
        generated_at = datetime.now().isoformat()
        today = datetime.now().date()

        rows_inward = []
        rows_outward = []

        for key, rec in results.items():
            if not isinstance(rec, dict):
                continue
            status = rec.get('status')
            if status in [ORPHAN, PARTIAL_MATCH, PARTIAL_MISMATCH, MISMATCH]:
                # determine present and missing systems
                present = [s.upper() for s in [CBS, SWITCH, NPCI] if rec.get(s)]
                missing = [s.upper() for s in [CBS, SWITCH, NPCI] if not rec.get(s)]

                # pick a date from available sources (prefer CBS then switch then npci)
                date_candidate = None
                amt_candidate = 0
                for s in [CBS, SWITCH, NPCI]:
                    src = rec.get(s)
                    if src:
                        date_candidate = src.get('date') or date_candidate
                        amt_candidate = src.get('amount') or amt_candidate

                parsed = self._parse_date(date_candidate)
                ageing_days = None
                if parsed:
                    ageing_days = (today - parsed).days
                # bucket
                if ageing_days is None:
                    bucket = '>3 days'
                elif ageing_days <= 1:
                    bucket = '0-1 days'
                elif 2 <= ageing_days <= 3:
                    bucket = '2-3 days'
                else:
                    bucket = '>3 days'

                # infer direction
                direction = 'Inward'
                # simple inference using available dr_cr
                for s in [CBS, SWITCH, NPCI]:
                    src = rec.get(s)
                    if src:
                        drcr = str(src.get('dr_cr') or '').upper()
                        if drcr.startswith('C'):
                            direction = 'Inward'
                            break
                        if drcr.startswith('D'):
                            direction = 'Outward'
                            break

                row = {
                    'run_id': run_id,
                    'cycle_id': cycle_id or '',
                    'RRN': key,
                    'Present_In': '/'.join(present),
                    'Missing_In': '/'.join(missing),
                    'Amount': amt_candidate,
                    'Transaction_Date': self._parse_date(date_candidate).strftime('%Y-%m-%d') if self._parse_date(date_candidate) else (str(date_candidate) if date_candidate else ''),
                    'Ageing_Days': ageing_days if ageing_days is not None else '',
                    'Ageing_Bucket': bucket,
                    'Unmatched_Reason': ','.join(present)
                }

                if direction == 'Inward':
                    rows_inward.append(row)
                else:
                    rows_outward.append(row)

        # Write reports with both CSV and XLSX formats
        ageing_headers = ['run_id','cycle_id','RRN','Present_In','Missing_In','Amount','Transaction_Date','Ageing_Days','Ageing_Bucket','Unmatched_Reason']
        import pandas as pd

        # Write inward ageing reports
        try:
            df_inward = pd.DataFrame(rows_inward, columns=ageing_headers) if rows_inward else pd.DataFrame(columns=ageing_headers)
            inward_path_csv = os.path.join(reports_dir, 'Unmatched_Inward_Ageing.csv')
            inward_path_xlsx = os.path.join(reports_dir, 'Unmatched_Inward_Ageing.xlsx')
            df_inward.to_csv(inward_path_csv, index=False, encoding='utf-8')
            df_inward.to_excel(inward_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated Unmatched_Inward_Ageing.csv and .xlsx with {len(rows_inward)} records")
        except Exception as e:
            logger.error(f"Failed to write Unmatched_Inward_Ageing reports: {e}")

        # Write outward ageing reports
        try:
            df_outward = pd.DataFrame(rows_outward, columns=ageing_headers) if rows_outward else pd.DataFrame(columns=ageing_headers)
            outward_path_csv = os.path.join(reports_dir, 'Unmatched_Outward_Ageing.csv')
            outward_path_xlsx = os.path.join(reports_dir, 'Unmatched_Outward_Ageing.xlsx')
            df_outward.to_csv(outward_path_csv, index=False, encoding='utf-8')
            df_outward.to_excel(outward_path_xlsx, index=False, engine='openpyxl')
            logger.info(f"Generated Unmatched_Outward_Ageing.csv and .xlsx with {len(rows_outward)} records")
        except Exception as e:
            logger.error(f"Failed to write Unmatched_Outward_Ageing reports: {e}")

        # Return the inward ageing report path (primary report)
        return inward_path_csv if 'inward_path_csv' in locals() else None

    def generate_hanging_reports(self, results: Dict, run_folder: str, run_id: str = None, cycle_id: str = None):
        """Generate Hanging Transactions reports (Inward / Outward)."""
        import os
        import pandas as pd
        from datetime import datetime

        reports_dir = self._ensure_reports_dir(run_folder)
        generated_at = datetime.now().isoformat()

        rows_in = []
        rows_out = []

        for key, rec in results.items():
            if not isinstance(rec, dict):
                continue
            if rec.get('status') == HANGING:
                # pick source info
                present = [s.upper() for s in [CBS, SWITCH, NPCI] if rec.get(s)]
                missing = [s.upper() for s in [CBS, SWITCH, NPCI] if not rec.get(s)]
                # amount/date
                amt = ''
                date = ''
                for s in [CBS, SWITCH, NPCI]:
                    src = rec.get(s)
                    if src:
                        amt = src.get('amount') or amt
                        date = src.get('date') or date

                reason = rec.get('hanging_reason') or ''

                # infer direction
                direction = 'Inward'
                for s in [CBS, SWITCH, NPCI]:
                    src = rec.get(s)
                    if src:
                        drcr = str(src.get('dr_cr') or '').upper()
                        if drcr.startswith('D'):
                            direction = 'Outward'
                            break
                        if drcr.startswith('C'):
                            direction = 'Inward'
                            break

                row = {
                    'run_id': run_id,
                    'cycle_id': cycle_id or '',
                    'RRN': key,
                    'Amount': amt,
                    'Transaction_Date': self._parse_date(date).strftime('%Y-%m-%d') if self._parse_date(date) else (str(date) if date else ''),
                    'Expected_Next_Cycle': '',
                    'Reason': reason
                }

                if direction == 'Inward':
                    rows_in.append(row)
                else:
                    rows_out.append(row)

        # Write CSVs
        hanging_headers = ['run_id','cycle_id','RRN','Amount','Transaction_Date','Expected_Next_Cycle','Reason']
        try:
            inward_path = write_report(run_id, cycle_id, 'reports', 'Hanging_Inward.csv', hanging_headers, rows_in)
        except Exception:
            inward_path = write_report(run_id, cycle_id, 'reports', 'Hanging_Inward.csv', hanging_headers, [])
        try:
            outward_path = write_report(run_id, cycle_id, 'reports', 'Hanging_Outward.csv', hanging_headers, rows_out)
        except Exception:
            outward_path = write_report(run_id, cycle_id, 'reports', 'Hanging_Outward.csv', hanging_headers, [])

        # Return the inward hanging report path (primary report)
        return inward_path

    def _generate_unmatched_ageing_reports(self, results: Dict, run_folder: str, run_id: str = None, cycle_id: str = None):
        """Generate unmatched inward/outward CSVs with ageing buckets."""
        self.generate_unmatched_ageing(results, run_folder, run_id, cycle_id)

    def _generate_adjustments_reports(self, results: Dict, run_folder: str, run_id: str = None, cycle_id: str = None):
        """Generate ANNEXURE-IV style adjustments CSV using annexure_iv helper."""
        self.generate_adjustments_csv(results, run_folder, run_id, cycle_id)

    def generate_adjustments_csv(self, results: Dict, run_folder: str, run_id: str = None, cycle_id: str = None):
        """Generate ANNEXURE-IV style adjustments CSV using annexure_iv helper.

        This collects candidate adjustment records from reconciliation results
        (TCC/RET/DRC/RRC/REFUND/RECOVERY candidates) and writes an Annexure file
        named ANNEXURE_IV_<run_id>.csv under reports/.
        """
        try:
            reports_dir = self._ensure_reports_dir(run_folder)
            annex_recs = []
            from datetime import datetime

            for key, rec in results.items():
                if not isinstance(rec, dict):
                    continue
                # candidate conditions: tcc present or needs_ttum or status in certain set
                if rec.get('tcc') or rec.get('needs_ttum') or rec.get('status') in [MISMATCH, PARTIAL_MISMATCH, ORPHAN]:
                    # pick best source
                    src = None
                    for s in [CBS, SWITCH, NPCI]:
                        if rec.get(s):
                            src = rec.get(s)
                            break
                    amt = src.get('amount') if src else ''
                    date = src.get('date') if src else ''
                    # Normalize date to YYYY-MM-DD when possible
                    try:
                        if date:
                            dnorm = datetime.fromisoformat(str(date)).strftime('%Y-%m-%d')
                        else:
                            dnorm = ''
                    except Exception:
                        try:
                            from datetime import datetime as _dt
                            dnorm = _dt.strptime(str(date), '%Y-%m-%d').strftime('%Y-%m-%d')
                        except Exception:
                            dnorm = ''

                    flag = 'DRC'
                    if rec.get('tcc'):
                        flag = 'TCC'
                    elif rec.get('needs_ttum'):
                        flag = 'RET'

                    annex_recs.append({
                        'Bankadjref': f"BR_{key}_{int(datetime.now().timestamp())}",
                        'Flag': flag,
                        'shtdat': dnorm,
                        'adjsmt': amt,
                        'Shser': str(key),
                        'Shcrd': f"NBIN{key}",
                        'FileName': f"ANNEXURE_{run_id}.csv",
                        'reason': (rec.get('cbs') or {}).get('rc','') or (rec.get('npci') or {}).get('rc',''),
                        'specifyother': rec.get('tcc') or ''
                    })

            if annex_recs:
                try:
                    from annexure_iv import generate_annexure_iv_csv
                    # write using run_id and cycle scoping
                    generate_annexure_iv_csv(annex_recs, run_id=run_id, cycle_id=cycle_id)
                except Exception as e:
                    logger.error(f"Failed to write ANNEXURE_IV: {e}")
        except Exception:
            pass

    def generate_switch_update_file(self, results: Dict, run_folder: str, run_id: str = None):
        """Generate a best-effort switch update file containing old/new statuses.

        Old Status is taken from any source RC present; New Status is the
        reconciliation `status`. This file is informational and intended for
        downstream operational ingestion — do not assume any automatic action.
        """
        import os
        import pandas as pd
        from datetime import datetime

        reports_dir = self._ensure_reports_dir(run_folder)
        generated_at = datetime.now().isoformat()
        rows = []

        for key, rec in results.items():
            if not isinstance(rec, dict):
                continue
            # collect old status from available source RC fields
            old_status = ''
            for s in [NPCI, SWITCH, CBS]:
                src = rec.get(s)
                if src and src.get('rc'):
                    old_status = src.get('rc')
                    break

            new_status = rec.get('status') or ''
            if not old_status and not new_status:
                continue

            rows.append({
                'run_id': run_id,
                'generated_at': generated_at,
                'RRN': key,
                'Old_Status': old_status,
                'New_Status': new_status,
                'Reason': rec.get('tcc') or rec.get('hanging_reason') or '',
                'Date': (rec.get('cbs') or rec.get('switch') or rec.get('npci') or {}).get('date',''),
                'Source_Systems': ','.join([s.upper() for s in [CBS, SWITCH, NPCI] if rec.get(s)])
            })

        try:
            df = pd.DataFrame(rows)
            if df.empty:
                df = pd.DataFrame(columns=['run_id','generated_at','RRN','Old_Status','New_Status','Reason','Date','Source_Systems'])
            df.to_csv(os.path.join(reports_dir, 'Switch_Update_File.csv'), index=False, encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to write Switch update file: {e}")

        # Populate unmatched_records as combination of partial_match_records and orphan_records
        self.unmatched_records = self.partial_match_records + self.hanging_records

        if not results:
            logger.warning("Reconciliation completed but no results generated")
            raise ValueError("Reconciliation completed but no transaction records were processed")
    
    def force_match_rrn(self, rrn: str, source1: str, source2: str, results: Dict):
        """Force match a specific RRN between two sources"""
        if rrn in results:
            record = results[rrn]
            
            # Check if both sources exist in the record
            if record.get(source1) and record.get(source2):
                # Update status to force matched
                record['status'] = FORCE_MATCHED
                
                # Sync amount and date from source1 to source2
                record[source2]['amount'] = record[source1]['amount']
                record[source2]['date'] = record[source1]['date']
                
                logger.info(f"Successfully force-matched RRN {rrn} between {source1} and {source2}")
            else:
                logger.warning(f"Could not force-match RRN {rrn}: one or both sources not found.")
        else:
            logger.warning(f"Could not force-match RRN {rrn}: RRN not found in results.")
        
        return results
    
    def generate_summary_json(self, results: Dict, run_folder: str) -> str:
        """Generate a summary.json file with key reconciliation metrics."""
        summary_data = {
            'run_id': os.path.basename(run_folder),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'totals': {
                'count': len([r for r in results.values() if isinstance(r, dict)]),
                'amount': sum((rec.get(CBS, {}).get('amount') if isinstance(rec, dict) and rec.get(CBS) else (rec.get(SWITCH, {}) or {}).get('amount', 0)) for rec in results.values() if isinstance(rec, dict))
            },
            'matched': {
                'count': len(self.matched_records),
                'amount': sum(results[rrn][CBS]['amount'] for rrn in self.matched_records if rrn in results and isinstance(results[rrn], dict) and results[rrn].get(CBS))
            },
            'unmatched': {
                'count': len(self.unmatched_records),
                'amount': sum((results[rrn][CBS]['amount'] if rrn in self.unmatched_records and rrn in results and isinstance(results[rrn], dict) and results[rrn].get(CBS) else (results[rrn].get(SWITCH, {}) or {}).get('amount', 0)) for rrn in self.unmatched_records if rrn in results and isinstance(results[rrn], dict))
            },
            'hanging': { # Placeholder for future logic
                'count': 0,
                'amount': 0.0
            },
            'exceptions': {
                'count': len(self.exceptions),
                'amount': sum((results[rrn][CBS]['amount'] if rrn in self.exceptions and rrn in results and isinstance(results[rrn], dict) and results[rrn].get(CBS) else (results[rrn].get(SWITCH, {}) or {}).get('amount', 0)) for rrn in self.exceptions if rrn in results and isinstance(results[rrn], dict))
            }
        }
        
        output_path = os.path.join(run_folder, "summary.json")
        with open(output_path, 'w') as f:
            json.dump(summary_data, f, indent=4)
        
        logger.info(f"Generated summary.json at {output_path}")
        return output_path

    def generate_human_report(self, results: Dict, run_folder: str, run_id: str = None) -> str:
        """Generate human-readable report.txt and summary.json"""
        # Also generate the JSON summary
        self.generate_summary_json(results, run_folder)
        
        unmatched_records = self.partial_match_records + self.hanging_records
        report_content = f"""BANK RECONCILIATION REPORT
Run ID: {os.path.basename(run_folder)}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY:
Total RRNs processed: {len(results)}
Matched records: {len(self.matched_records)} (All 3 systems agree)
Partial Match records: {len(self.partial_match_records)} (2 systems match, 1 missing)
Orphan records: {len(self.hanging_records)} (Only in 1 system)
Exceptions: {len(self.exceptions)} (Data mismatches or inconsistencies)

Unmatched records: {len(unmatched_records)} (Partial + Orphan)

VALIDATION:
Total = Matched + Partial Match + Orphan + Exceptions = {len(self.matched_records) + len(self.partial_match_records) + len(self.hanging_records) + len(self.exceptions)}

MATCHED RECORDS ({len(self.matched_records)}):
{', '.join(self.matched_records[:20])}{'...' if len(self.matched_records) > 20 else ''}

PARTIAL MATCH RECORDS ({len(self.partial_match_records)}):
{', '.join(self.partial_match_records[:20])}{'...' if len(self.partial_match_records) > 20 else ''}

ORPHAN RECORDS ({len(self.hanging_records)}):
{', '.join(self.hanging_records[:20])}{'...' if len(self.hanging_records) > 20 else ''}

EXCEPTIONS ({len(self.exceptions)}):
{', '.join(self.exceptions[:20])}{'...' if len(self.exceptions) > 20 else ''}

DETAILED ANALYSIS:
- Matched: RRNs found in all 3 systems (CBS + Switch + NPCI) with SAME Amount + Date
- Partial Match: RRNs found in exactly 2 systems with matching data (missing in 1 system)
- Orphan: RRNs found in only 1 system (missing in 2 systems)
- Exceptions: RRNs with data inconsistencies
  * MISMATCH: Found in all 3 systems but amounts/dates don't match
  * PARTIAL_MISMATCH: Found in 2 systems but amounts/dates don't match
"""
        
        report_path = os.path.join(run_folder, "report.txt")
        with open(report_path, 'w') as f:
            f.write(report_content)
        # Save full recon output for enquiries and rollback
        try:
            recon_out_path = os.path.join(run_folder, 'recon_output.json')
            with open(recon_out_path, 'w') as rf:
                json.dump(results, rf, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write recon_output.json: {e}")

        # Pairwise matched reports (GL-Switch, Switch-NPCI, GL-NPCI)
        try:
            reports_dir = os.path.join(run_folder, 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            import csv

            # prepare rows for each pair
            rows_gl_switch = []
            rows_switch_npci = []
            rows_gl_npci = []

            for rrn, rec in results.items():
                if not isinstance(rec, dict):
                    continue
                cbs = rec.get(CBS)
                switch = rec.get(SWITCH)
                npci = rec.get(NPCI)
                ntsl = rec.get(NTSL)

                rows_gl_switch.append([rrn, cbs.get('amount') if cbs else '', switch.get('amount') if switch else '', rec.get('status', '')])
                rows_switch_npci.append([rrn, switch.get('amount') if switch else '', npci.get('amount') if npci else '', rec.get('status', '')])
                rows_gl_npci.append([rrn, cbs.get('amount') if cbs else '', npci.get('amount') if npci else '', rec.get('status', '')])

            # write CSVs
            with open(os.path.join(reports_dir, 'gl_switch.csv'), 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['RRN', 'CBS_Amount', 'SWITCH_Amount', 'Status'])
                w.writerows(rows_gl_switch)

            with open(os.path.join(reports_dir, 'switch_npci.csv'), 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['RRN', 'SWITCH_Amount', 'NPCI_Amount', 'Status'])
                w.writerows(rows_switch_npci)

            with open(os.path.join(reports_dir, 'gl_npci.csv'), 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['RRN', 'CBS_Amount', 'NPCI_Amount', 'Status'])
                w.writerows(rows_gl_npci)
        except Exception as e:
            logger.warning(f"Failed to generate pairwise reports: {e}")

        # Generate source-wise listings and per-upload-file listings
        try:
            # Aggregate source-wise from results
            for source in [CBS.upper(), SWITCH.upper(), NPCI.upper()]:
                rows = []
                for rrn, rec in results.items():
                    if not isinstance(rec, dict):
                        continue
                    src_rec = rec.get(source.lower())
                    if src_rec:
                        rows.append([
                            rrn,
                            src_rec.get('amount',''),
                            src_rec.get('date',''),
                            src_rec.get('dr_cr',''),
                            src_rec.get('rc',''),
                            src_rec.get('tran_type',''),
                            rec.get('status','')
                        ])
                if rows:
                    with open(os.path.join(reports_dir, f"{source.lower()}_listing.csv"), 'w', newline='') as sf:
                        sw = csv.writer(sf)
                        sw.writerow(['RRN','Amount','Tran_Date','Dr_Cr','RC','Tran_Type','Status'])
                        sw.writerows(rows)

            # Per-file listing: read uploaded CSV/XLSX files found under run_folder
            for root, dirs, files in os.walk(run_folder):
                for fname in files:
                    if not fname.lower().endswith(('.csv', '.xlsx', '.xls')):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        df = pd.read_csv(fpath) if fname.lower().endswith('.csv') else pd.read_excel(fpath)
                        df = self._handle_missing_values(self._smart_map_columns(df))
                        # add source from filename
                        src = 'OTHER'
                        fname_l = fname.lower()
                        if 'cbs' in fname_l:
                            src = 'CBS'
                        elif 'switch' in fname_l:
                            src = 'SWITCH'
                        elif 'npci' in fname_l or 'npc' in fname_l:
                            src = 'NPCI'
                        # direction inference
                        direction = ''
                        if 'inward' in fname_l:
                            direction = 'INWARD'
                        elif 'outward' in fname_l:
                            direction = 'OUTWARD'

                        out_rows = []
                        for _, r in df.iterrows():
                            out_rows.append([
                                r.get(RRN,''), r.get(AMOUNT,''), r.get(TRAN_DATE,''), r.get(DR_CR,''), r.get(RC,''), r.get(TRAN_TYPE,''), src, direction
                            ])
                        if out_rows:
                            out_fn = os.path.join(reports_dir, f"file_listing_{os.path.splitext(fname)[0]}.csv")
                            with open(out_fn, 'w', newline='') as of:
                                w = csv.writer(of)
                                w.writerow(['RRN','Amount','Tran_Date','Dr_Cr','RC','Tran_Type','Source','Direction'])
                                w.writerows(out_rows)
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Failed to generate source/file listings: {e}")

        # Cross-run cut-off detection: if this run has declines for an RRN and the next chronological run
        # contains a reversal (RC starts with 'RB'), flag the current RRN as HANGING.
        try:
            if run_id:
                runs = [d for d in os.listdir(CFG_UPLOAD_DIR) if d.startswith('RUN_')]
                runs = sorted(runs)
                if run_id in runs:
                    idx = runs.index(run_id)
                    next_idx = idx + 1
                    if next_idx < len(runs):
                        next_run = runs[next_idx]
                        next_run_folder = os.path.join(CFG_UPLOAD_DIR, next_run)
                        next_recon = os.path.join(next_run_folder, 'recon_output.json')
                        if os.path.exists(next_recon):
                            try:
                                with open(next_recon, 'r') as nf:
                                    next_data = json.load(nf)
                                # determine reversal RRNs in next run
                                rev_rrns = set()
                                if isinstance(next_data, dict) and not next_data.get('matched') and not next_data.get('unmatched'):
                                    for k, v in next_data.items():
                                        if isinstance(v, dict):
                                            npci = v.get(NPCI)
                                            if npci and str(npci.get('rc','')).upper().startswith('RB'):
                                                rev_rrns.add(k)
                                else:
                                    for rec in next_data.get('matched', []) + next_data.get('unmatched', []):
                                        if isinstance(rec, dict) and rec.get('NPCI') and str(rec.get('NPCI').get('rc','')).upper().startswith('RB'):
                                            rev_rrns.add(rec.get('rrn') or rec.get('RRN'))

                                # flag current results
                                for rrn in list(results.keys()):
                                    if rrn in rev_rrns:
                                        rec = results.get(rrn)
                                        if rec:
                                            rec['status'] = HANGING
                                            rec['hanging_reason'] = 'declined_then_reversed_next_cycle'
                                            if 'hanging_list' not in results:
                                                results['hanging_list'] = []
                                            if rrn not in results['hanging_list']:
                                                results['hanging_list'].append(rrn)
                            except Exception:
                                pass
        except Exception:
            pass
        # Hanging CSV logic: write current pending hanging state, and if present in previous two runs, mark as final hanging
        hanging_rrns = results.get('hanging_list', [])
        try:
            import csv
            # write hanging_state.json in current run folder for future runs to reference
            state_path = os.path.join(run_folder, 'hanging_state.json')
            try:
                with open(state_path, 'w') as sf:
                    json.dump({'hanging': hanging_rrns, 'generated_at': datetime.now().isoformat()}, sf, indent=2)
            except Exception:
                pass

            # If run_id provided, check previous two runs for hanging_state occurrences
            final_hangings = []
            if run_id:
                # locate runs sorted
                root_upload = os.path.dirname(os.path.dirname(run_folder)) if os.path.basename(run_folder).startswith('cycle_') else os.path.join(os.path.dirname(run_folder))
                # Better: list runs from UPLOAD_DIR
                from config import UPLOAD_DIR as CFG_UPLOAD
                runs = [d for d in os.listdir(CFG_UPLOAD) if d.startswith('RUN_')]
                runs = sorted(runs)
                if run_id in runs:
                    idx = runs.index(run_id)
                    prev_runs = []
                    # get previous two runs indices
                    if idx-1 >= 0:
                        prev_runs.append(runs[idx-1])
                    if idx-2 >= 0:
                        prev_runs.append(runs[idx-2])

                    # count how many previous runs had the rrn in hanging_state
                    for rrn in hanging_rrns:
                        count = 0
                        for pr in prev_runs:
                            pr_state = os.path.join(CFG_UPLOAD, pr, 'hanging_state.json')
                            if os.path.exists(pr_state):
                                try:
                                    with open(pr_state, 'r') as pf:
                                        data = json.load(pf)
                                    if rrn in data.get('hanging', []):
                                        count += 1
                                except Exception:
                                    pass
                        # if found in both previous runs (count==2) then mark as final hanging
                        if count >= 2:
                            final_hangings.append(rrn)

            # write final hanging.csv for those meeting the wait condition
            if final_hangings:
                try:
                    hanging_path = os.path.join(run_folder, 'hanging.csv')
                    with open(hanging_path, 'w', newline='') as hf:
                        writer = csv.writer(hf)
                        writer.writerow(['RRN', 'Reason'])
                        for r in final_hangings:
                            writer.writerow([r, 'CBS+Switch present, NPCI missing (waited 2 cycles)'])
                except Exception as e:
                    logger.warning(f"Failed to write hanging.csv: {e}")
        except Exception as e:
            logger.warning(f"Hanging processing failed: {e}")

        return report_path


    
    def generate_adjustments_csv(self, results: Dict, run_folder: str, run_id: str = None, cycle_id: str = None) -> str:
        """Generate adjustments.csv for Force Match UI - handles both legacy and UPI format"""
        adjustments_data = []
        
        # Check if this is UPI engine output (has 'summary' and 'details' keys)
        if 'summary' in results and 'details' in results:
            # UPI engine format - extract exceptions and TTUM candidates
            exceptions = results.get('exceptions', [])
            ttum_candidates = results.get('ttum_candidates', [])
            
            # Process exceptions
            for exc in exceptions:
                row = {
                    RRN: exc.get('rrn', ''),
                    'Status': 'EXCEPTION',
                    f'{CBS.upper()}_Amount': exc.get('amount', '') if exc.get('source') == 'CBS' else '',
                    f'{SWITCH.upper()}_Amount': exc.get('amount', '') if exc.get('source') == 'SWITCH' else '',
                    f'{NPCI.upper()}_Amount': exc.get('amount', '') if exc.get('source') == 'NPCI' else '',
                    f'{CBS.upper()}_Date': '',
                    f'{SWITCH.upper()}_Date': '',
                    f'{NPCI.upper()}_Date': '',
                    f'{CBS.upper()}_Source': 'X' if exc.get('source') == 'CBS' else '',
                    f'{SWITCH.upper()}_Source': 'X' if exc.get('source') == 'SWITCH' else '',
                    f'{NPCI.upper()}_Source': 'X' if exc.get('source') == 'NPCI' else '',
                    'Exception_Type': exc.get('exception_type', ''),
                    'TTUM_Required': 'Yes' if exc.get('ttum_required') else 'No',
                    'Suggested_Action': f"Generate {exc.get('ttum_type', 'MANUAL')} TTUM"
                }
                adjustments_data.append(row)
            
            # Process TTUM candidates
            for ttum in ttum_candidates:
                row = {
                    RRN: ttum.get('rrn', ''),
                    'Status': 'TTUM_REQUIRED',
                    f'{CBS.upper()}_Amount': ttum.get('amount', '') if ttum.get('source') == 'CBS' else '',
                    f'{SWITCH.upper()}_Amount': '',
                    f'{NPCI.upper()}_Amount': ttum.get('amount', '') if ttum.get('source') == 'NPCI' else '',
                    f'{CBS.upper()}_Date': '',
                    f'{SWITCH.upper()}_Date': '',
                    f'{NPCI.upper()}_Date': '',
                    f'{CBS.upper()}_Source': 'X' if ttum.get('source') == 'CBS' else '',
                    f'{SWITCH.upper()}_Source': '',
                    f'{NPCI.upper()}_Source': 'X' if ttum.get('source') == 'NPCI' else '',
                    'TTUM_Type': ttum.get('ttum_type', ''),
                    'Direction': ttum.get('direction', ''),
                    'Suggested_Action': f"Generate {ttum.get('ttum_type', 'UNKNOWN')} TTUM"
                }
                adjustments_data.append(row)
        else:
            # Legacy format - RRN keyed records
            for rrn, record in results.items():
                if not isinstance(record, dict):
                    continue
                row = {
                    RRN: rrn,
                    'Status': record.get('status', 'UNKNOWN'),
                    f'{CBS.upper()}_Amount': record.get(CBS, {}).get('amount', '') if isinstance(record.get(CBS), dict) else '',
                    f'{SWITCH.upper()}_Amount': record.get(SWITCH, {}).get('amount', '') if isinstance(record.get(SWITCH), dict) else '',
                    f'{NPCI.upper()}_Amount': record.get(NPCI, {}).get('amount', '') if isinstance(record.get(NPCI), dict) else '',
                    f'{CBS.upper()}_Date': record.get(CBS, {}).get('date', '') if isinstance(record.get(CBS), dict) else '',
                    f'{SWITCH.upper()}_Date': record.get(SWITCH, {}).get('date', '') if isinstance(record.get(SWITCH), dict) else '',
                    f'{NPCI.upper()}_Date': record.get(NPCI, {}).get('date', '') if isinstance(record.get(NPCI), dict) else '',
                    f'{CBS.upper()}_Source': 'X' if record.get(CBS) else '',
                    f'{SWITCH.upper()}_Source': 'X' if record.get(SWITCH) else '',
                    f'{NPCI.upper()}_Source': 'X' if record.get(NPCI) else '',
                    'Suggested_Action': self._get_suggested_action(record)
                }
                adjustments_data.append(row)
        
        if adjustments_data:
            df = pd.DataFrame(adjustments_data)
        else:
            # Create empty dataframe with expected columns
            df = pd.DataFrame(columns=[RRN, 'Status', f'{CBS.upper()}_Amount', f'{SWITCH.upper()}_Amount', 
                                      f'{NPCI.upper()}_Amount', 'Suggested_Action'])
        
        csv_path = os.path.join(run_folder, "adjustments.csv")
        df.to_csv(csv_path, index=False)
        
        return csv_path
    
    def _get_suggested_action(self, record: Dict) -> str:
        """Determine suggested action based on status"""
        status = record.get('status')
        if status == ORPHAN:
            missing_systems = []
            if not record.get(CBS): missing_systems.append(CBS.upper())
            if not record.get(SWITCH): missing_systems.append(SWITCH.upper())
            if not record.get(NPCI): missing_systems.append(NPCI.upper())
            return f'Investigate missing in {", ".join(missing_systems)}'
        elif status == PARTIAL_MATCH:
            missing_systems = []
            if not record.get(CBS): missing_systems.append(CBS.upper())
            if not record.get(SWITCH): missing_systems.append(SWITCH.upper())
            if not record.get(NPCI): missing_systems.append(NPCI.upper())
            return f'Check missing system data in {", ".join(missing_systems)}'
        elif status == MISMATCH:
            return 'CRITICAL: All systems have record but amounts/dates differ - investigate discrepancy'
        elif status == PARTIAL_MISMATCH:
            return 'WARNING: 2 systems have record but amounts/dates differ - investigate discrepancy'
        elif status == FORCE_MATCHED:
            return 'Manual intervention completed - forced match'
        elif status == MATCHED:
            return 'No action needed - perfect match'
        else:
            return 'Unknown status - manual review required'
