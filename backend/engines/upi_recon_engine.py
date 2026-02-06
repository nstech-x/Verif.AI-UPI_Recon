"""
UPI Reconciliation Engine
Implements UPI-specific matching logic per functional doc.
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from config import (
    UPI_MATCHING_CONFIGS,
    GL_ACCOUNTS,
    TTUM_TYPES,
    EXCEPTION_MATRIX,
    OUTPUT_DIR,
)
from services.logging_config import get_logger

logger = get_logger(__name__)


class UPIReconciliationEngine:
    """UPI-specific reconciliation engine implementing complex matching logic"""

    def __init__(self):
        self.matching_results = {
            'matched': [],
            'unmatched': [],
            'hanging': [],
            'exceptions': []
        }

    def perform_upi_reconciliation(
        self,
        cbs_df: pd.DataFrame,
        switch_df: pd.DataFrame,
        npci_df: pd.DataFrame,
        run_id: str,
        cycle_id: Optional[str] = None,
        adjustment_df: Optional[pd.DataFrame] = None,
    ) -> Dict:
        """
        Perform UPI reconciliation with complex matching logic
        Returns reconciliation results
        """
        logger.info(f"Starting UPI reconciliation for run: {run_id}")

        # Initialize dataframes
        self.cbs_df = cbs_df.copy()
        self.switch_df = switch_df.copy()
        self.npci_df = npci_df.copy()
        self.adjustment_df = adjustment_df.copy() if adjustment_df is not None else pd.DataFrame()
        self.run_id = run_id
        self.current_cycle_id = cycle_id

        # Apply adjustments if provided
        if not self.adjustment_df.empty:
            self._apply_adjustments()

        # Load previous hanging state and apply carry-over with auto-TTUM triggers

        # Load previous hanging state and apply carry-over with auto-TTUM triggers
        import os, json
        state_path = os.path.join(OUTPUT_DIR, run_id, 'hanging_state.json')
        prev_state = {}
        try:
            if os.path.exists(state_path):
                with open(state_path, 'r') as sf:
                    prev_state = json.load(sf) or {}
        except Exception:
            prev_state = {}
        entries = prev_state.get('entries', []) if isinstance(prev_state, dict) else []
        current_npci_rrns = set(self.npci_df['RRN'].dropna().astype(str)) if 'RRN' in self.npci_df.columns else set()
        carried = []
        for entry in entries:
            rrn = str(entry.get('rrn', '')).strip()
            dr_cr = str(entry.get('dr_cr', '')).upper()
            cycles_persisted = int(entry.get('cycles_persisted', 0))
            # If found in current NPCI, resolve and skip carry
            if rrn and rrn in current_npci_rrns:
                continue
            # Increment age and trigger TTUM after 2 cycles
            cycles_persisted += 1
            if cycles_persisted >= 2:
                # Auto TTUM trigger via marking switch side
                # Find switch row by RRN
                if rrn and 'RRN' in self.switch_df.columns:
                    mask = self.switch_df['RRN'].astype(str) == rrn
                    if mask.any():
                        self.switch_df.loc[mask, 'processed'] = True
                        self.switch_df.loc[mask, 'match_status'] = 'UNMATCHED'
                        self.switch_df.loc[mask, 'exception_type'] = 'CARRY_OVER_TTUM'
                        self.switch_df.loc[mask, 'ttum_required'] = True
                        if dr_cr.startswith('D'):
                            self.switch_df.loc[mask, 'ttum_type'] = 'REVERSAL'  # Remitter Refund
                        elif dr_cr.startswith('C'):
                            self.switch_df.loc[mask, 'ttum_type'] = 'BENEFICIARY_CREDIT'  # Beneficiary Recovery
                continue
            # Carry forward for next cycle
            entry['cycles_persisted'] = cycles_persisted
            entry['last_cycle_id'] = cycle_id
            carried.append(entry)
        # Prepare state holder for later save
        self._prev_hanging_state = {'entries': carried, 'last_cycle_id': cycle_id}

        # Add processing flags
        for df_name in ['cbs_df', 'switch_df', 'npci_df']:
            df = getattr(self, df_name)
            df['processed'] = False
            df['match_status'] = 'UNMATCHED'
            df['exception_type'] = None
            df['ttum_required'] = False
            df['ttum_type'] = None
            setattr(self, df_name, df)

        # Execute matching logic in sequence (as per functional document)
        self._step_1_cut_off_transactions()
        # Mark present-in-Switch but missing-in-NPCI transactions as Hanging for this cycle
        try:
            if 'RRN' in self.switch_df.columns:
                sw_rrns = set(self.switch_df['RRN'].dropna().astype(str))
                npci_rrns = set(self.npci_df['RRN'].dropna().astype(str)) if 'RRN' in self.npci_df.columns else set()
                only_switch = sw_rrns - npci_rrns
                if only_switch:
                    mask = self.switch_df['RRN'].astype(str).isin(only_switch)
                    self.switch_df.loc[mask, 'processed'] = True
                    self.switch_df.loc[mask, 'match_status'] = 'HANGING'
                    self.switch_df.loc[mask, 'exception_type'] = 'SWITCH_ONLY'
        except Exception:
            pass
        self._step_2_self_matched_transactions()
        self._step_3_settlement_entries()
        self._step_4_double_debit_credit()
        self._step_5_normal_matching()
        self._step_6_deemed_accepted_matching()
        self._step_7_npci_declined_transactions()
        self._step_8_failed_auto_credit_reversal()

        # Apply exception handling matrix for remaining transactions
        self._apply_exception_handling_matrix()

        # Persist updated hanging state for this cycle before generating results
        try:
            import os, json
            os.makedirs(os.path.join(OUTPUT_DIR, run_id), exist_ok=True)
            state_entries = self._prev_hanging_state.get('entries', []) if hasattr(self, '_prev_hanging_state') else []
            # Append current cycle's hanging for carry-over
            # From NPCI
            try:
                if 'match_status' in self.npci_df.columns:
                    hanging_npci = self.npci_df[self.npci_df['match_status'] == 'HANGING']
                    for _, row in hanging_npci.iterrows():
                        rrn = str(row.get('RRN',''))
                        if rrn:
                            state_entries.append({
                                'rrn': rrn,
                                'amount': row.get('Amount'),
                                'dr_cr': str(row.get('Dr_Cr','')),
                                'reason': row.get('exception_type','HANGING'),
                                'first_seen_cycle': self._prev_hanging_state.get('last_cycle_id') if hasattr(self, '_prev_hanging_state') else cycle_id,
                                'last_cycle_id': cycle_id,
                                'cycles_persisted': 0
                            })
            except Exception:
                pass
            # From Switch-only
            try:
                if 'exception_type' in self.switch_df.columns:
                    sw_hanging = self.switch_df[(self.switch_df['exception_type'] == 'SWITCH_ONLY') & (self.switch_df['match_status'] == 'HANGING')]
                    for _, row in sw_hanging.iterrows():
                        rrn = str(row.get('RRN',''))
                        if rrn:
                            state_entries.append({
                                'rrn': rrn,
                                'amount': row.get('Amount'),
                                'dr_cr': str(row.get('Dr_Cr','')),
                                'reason': 'SWITCH_ONLY',
                                'first_seen_cycle': self._prev_hanging_state.get('last_cycle_id') if hasattr(self, '_prev_hanging_state') else cycle_id,
                                'last_cycle_id': cycle_id,
                                'cycles_persisted': 0
                            })
            except Exception:
                pass
            state_path = os.path.join(OUTPUT_DIR, run_id, 'hanging_state.json')
            with open(state_path, 'w') as sf:
                json.dump({'entries': state_entries, 'last_cycle_id': cycle_id, 'updated_at': datetime.now().isoformat()}, sf, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save hanging state: {e}")

        # Generate final results
        results = self._generate_reconciliation_results(run_id)

        logger.info(f"UPI reconciliation completed for run: {run_id}")
        return results

    def _step_1_cut_off_transactions(self):
        """Step 1: Handle cut-off transactions (Hanging transactions)"""
        logger.info("Step 1: Processing cut-off transactions")

        # Identify transactions where original leg is in current NPCI file
        # but reversal leg might be in next cycle due to cut-off time
        # Mark as hanging for next cycle processing

        # Get unprocessed NPCI transactions
        unprocessed_npci = self.npci_df[~self.npci_df['processed']]

        # Look for transactions that appear to be cut-off scenarios:
        # 1. Transactions with Tran_Date close to cycle end
        # 2. Transactions that have matching RRN in CBS/Switch but different
        #    amounts or dates
        # 3. Transactions that might have reversal legs in future cycles

        hanging_transactions = []

        for _, npci_row in unprocessed_npci.iterrows():
            # rrn = npci_row.get('RRN')  # Not used in this scope
            tran_date = pd.to_datetime(npci_row.get('Tran_Date'))
            amount = npci_row.get('Amount')

            # Check if this might be a cut-off transaction
            # Look for partial matches in CBS and Switch
            cbs_partial_match = self._find_partial_match(
                self.cbs_df, npci_row, ['RRN', 'Tran_Date']
            )
            switch_partial_match = self._find_partial_match(
                self.switch_df, npci_row, ['RRN', 'Tran_Date']
            )

            # If we have partial matches but not exact matches, mark as hanging
            if (
                cbs_partial_match is not None or
                switch_partial_match is not None
            ):
                # Check if amounts differ significantly (indicating possible reversal)
                if cbs_partial_match is not None:
                    cbs_amount = cbs_partial_match.get('Amount', 0)
                    if abs(cbs_amount - amount) > 0.01:  # Amount difference
                        self._mark_as_hanging(npci_row, 'CUT_OFF_TRANSACTION')
                        hanging_transactions.append(npci_row.to_dict())
                        continue

                if switch_partial_match is not None:
                    switch_amount = switch_partial_match.get('Amount', 0)
                    if abs(switch_amount - amount) > 0.01:  # Amount difference
                        self._mark_as_hanging(npci_row, 'CUT_OFF_TRANSACTION')
                        hanging_transactions.append(npci_row.to_dict())
                        continue

            # Check for transactions near cycle cut-off time (assuming 11:30 PM cut-off)
            if (
                tran_date.hour >= 23 or
                (tran_date.hour == 22 and tran_date.minute >= 30)
            ):
                # Transactions near cut-off time are likely hanging
                self._mark_as_hanging(npci_row, 'CUT_OFF_TIME')
                hanging_transactions.append(npci_row.to_dict())

        logger.info(f"Found {len(hanging_transactions)} hanging transactions due to cut-off")

    def _step_2_self_matched_transactions(self):
        """Step 2: Self-matched transactions (Auto-reversed)"""
        logger.info("Step 2: Processing self-matched transactions")

        # Find transactions with same UPI_Tran_ID, RRN, Tran_Date, Tran_Amt
        # but opposite Dr_Cr indicators (auto-reversal)
        self_matched = []

        # Group by key fields
        if 'UPI_Tran_ID' in self.cbs_df.columns and 'RRN' in self.cbs_df.columns:
            cbs_groups = self.cbs_df.groupby(['UPI_Tran_ID', 'RRN', 'Tran_Date', 'Amount'])

            for group_key, group in cbs_groups:
                if len(group) == 2:  # Debit and credit pair
                    dr_cr_values = group['Dr_Cr'].unique()
                    if len(dr_cr_values) == 2 and set(dr_cr_values) <= {'DR', 'CR', 'D', 'C'}:
                        # Mark as matched
                        self.cbs_df.loc[group.index, 'processed'] = True
                        self.cbs_df.loc[group.index, 'match_status'] = 'MATCHED'
                        self.cbs_df.loc[group.index, 'exception_type'] = 'SELF_MATCHED'
                        self_matched.extend(group.to_dict('records'))

        if 'UPI_Tran_ID' in self.switch_df.columns and 'RRN' in self.switch_df.columns:
            switch_groups = self.switch_df.groupby(['UPI_Tran_ID', 'RRN', 'Tran_Date', 'Amount'])

            for group_key, group in switch_groups:
                if len(group) == 2:
                    dr_cr_values = group['Dr_Cr'].unique()
                    if len(dr_cr_values) == 2 and set(dr_cr_values) <= {'DR', 'CR', 'D', 'C'}:
                        self.switch_df.loc[group.index, 'processed'] = True
                        self.switch_df.loc[group.index, 'match_status'] = 'MATCHED'
                        self.switch_df.loc[group.index, 'exception_type'] = 'SELF_MATCHED'

        if 'UPI_Tran_ID' in self.npci_df.columns and 'RRN' in self.npci_df.columns:
            npci_groups = self.npci_df.groupby(['UPI_Tran_ID', 'RRN', 'Tran_Date', 'Amount'])

            for group_key, group in npci_groups:
                if len(group) == 2:
                    # NPCI files typically don't have Dr_Cr, but check for reversal patterns
                    self.npci_df.loc[group.index, 'processed'] = True
                    self.npci_df.loc[group.index, 'match_status'] = 'MATCHED'
                    self.npci_df.loc[group.index, 'exception_type'] = 'SELF_MATCHED'

        logger.info(f"Found {len(self_matched)} self-matched transaction pairs")

    def _step_3_settlement_entries(self):
        """Step 3: Settlement entries identification"""
        logger.info("Step 3: Processing settlement entries")

        # Identify settlement entries in GL (previous batch settlement)
        # Look for entries with equivalent amount to previous NTSL and no RRN

        # Get unprocessed CBS transactions
        unprocessed_cbs = self.cbs_df[~self.cbs_df['processed']]

        # Look for CBS entries that might be settlement entries:
        # 1. No RRN (settlement entries typically don't have RRN)
        # 2. Large amounts that match previous NTSL totals
        # 3. Dr_Cr pattern indicating settlement

        settlement_candidates = []

        # Find CBS entries without RRN (potential settlement entries)
        no_rrn_entries = unprocessed_cbs[unprocessed_cbs['RRN'].isna() | (unprocessed_cbs['RRN'] == '')]

        for _, cbs_row in no_rrn_entries.iterrows():
            amount = cbs_row.get('Amount', 0)
            dr_cr = cbs_row.get('Dr_Cr', '').upper()

            # Check if this could be a settlement entry
            # Look for large amounts or amounts that match previous cycle totals
            if amount > 1000:  # Threshold for settlement amounts
                # Check if there's a corresponding entry in opposite direction
                opposite_entries = unprocessed_cbs[
                    (unprocessed_cbs['Amount'] == amount) &
                    (
                        unprocessed_cbs['Dr_Cr'].isin(['CR', 'C', 'DR', 'D'])
                        if dr_cr in ['DR', 'D']
                        else unprocessed_cbs['Dr_Cr'].isin(['DR', 'D'])
                    ) &
                    (~unprocessed_cbs['processed'])
                ]

                if len(opposite_entries) > 0:
                    # Mark as settlement entry
                    self.cbs_df.loc[cbs_row.name, 'processed'] = True
                    self.cbs_df.loc[cbs_row.name, 'match_status'] = 'MATCHED'
                    self.cbs_df.loc[cbs_row.name, 'exception_type'] = 'SETTLEMENT_ENTRY'

                    # Mark the opposite entry as well
                    self.cbs_df.loc[opposite_entries.index, 'processed'] = True
                    self.cbs_df.loc[opposite_entries.index, 'match_status'] = 'MATCHED'
                    self.cbs_df.loc[opposite_entries.index, 'exception_type'] = 'SETTLEMENT_ENTRY'

                    settlement_candidates.append(cbs_row.to_dict())

        logger.info(f"Found {len(settlement_candidates)} settlement entries")

    def _step_4_double_debit_credit(self):
        """Step 4: Double debit/credit detection with proper TTUM generation
        
        Detects transactions with multiple entries for same RRN in the same source,
        which indicates potential double debit/credit scenarios. Marks them for
        manual review and TTUM generation with REVERSAL type.
        """
        logger.info("Step 4: Detecting double debits/credits with proper TTUM handling")

        for df_name, df in [('CBS', self.cbs_df), ('Switch', self.switch_df)]:
            if 'RRN' in df.columns and not df['processed'].all():
                rrn_groups = df[~df['processed']].groupby('RRN')
                for rrn, group in rrn_groups:
                    if len(group) > 1 and pd.notna(rrn) and rrn != '':
                        # First, check for self-reversal, which should be matched
                        if len(group) == 2:
                            dr_cr_values = group['Dr_Cr'].fillna('').astype(str).str.upper().unique()
                            if len(dr_cr_values) == 2:
                                df.loc[group.index, 'processed'] = True
                                df.loc[group.index, 'match_status'] = 'MATCHED'
                                df.loc[group.index, 'exception_type'] = 'SELF_MATCHED'
                                continue

                        # If not a self-reversal, it is a double debit/credit
                        dr_cr_values = group['Dr_Cr'].fillna('').astype(str).str.upper()
                        has_dr = any(v.startswith('D') for v in dr_cr_values)
                        has_cr = any(v.startswith('C') for v in dr_cr_values)
                        
                        df.loc[group.index, 'processed'] = True
                        df.loc[group.index, 'match_status'] = 'UNMATCHED'
                        df.loc[group.index, 'exception_type'] = 'DOUBLE_DEBIT_CREDIT'
                        df.loc[group.index, 'ttum_required'] = True
                        
                        if has_dr and has_cr:
                            df.loc[group.index, 'ttum_type'] = 'REVERSAL'
                        else:
                            df.loc[group.index, 'ttum_type'] = 'INVESTIGATION'
                        
                        logger.info(f"Detected {len(group)} double debit/credit entries for RRN: {rrn} in {df_name}")

    def _step_5_normal_matching(self):
        """Step 5: Normal matching with configurable parameters"""
        logger.info("Step 5: Performing normal matching")

        matched_count = 0

        # Only match transactions with RC='00' (successful)
        successful_npci = self.npci_df[
            (self.npci_df['RC'] == '00') &
            (~self.npci_df['processed'])
        ]

        # Use configurable matching parameters from config.py
        for config in UPI_MATCHING_CONFIGS:
            if matched_count > 0:  # If best match found some, skip relaxed
                break

            # Validate that required fields are present in NPCI data
            required_fields_present = all(
                field in successful_npci.columns
                for field in config['required_fields']
            )

            if not required_fields_present:
                logger.warning(f"Skipping {config['name']}: required fields {config['required_fields']} not present in NPCI data")
                continue

            matched_count += self._perform_matching_round(
                successful_npci, config['params'], config['name']
            )

        logger.info(f"Normal matching completed: {matched_count} transactions matched")

    def _perform_matching_round(self, npci_candidates: pd.DataFrame,
                               match_params: List[str], match_type: str) -> int:
        """Perform one round of matching with given parameters"""
        matched_count = 0

        # Get unprocessed CBS and Switch transactions
        unprocessed_cbs = self.cbs_df[~self.cbs_df['processed']]
        unprocessed_switch = self.switch_df[~self.switch_df['processed']]

        for _, npci_row in npci_candidates.iterrows():
            # Try to find matching CBS and Switch records
            cbs_match = self._find_matching_record(unprocessed_cbs, npci_row, match_params)
            switch_match = self._find_matching_record(unprocessed_switch, npci_row, match_params)

            if cbs_match is not None and switch_match is not None:
                # Three-way match found
                self._mark_as_matched(cbs_match, switch_match, npci_row, match_type)
                matched_count += 1

        return matched_count

    def _find_matching_record(self, df: pd.DataFrame, npci_row: pd.Series,
                            match_params: List[str]) -> Optional[pd.Series]:
        """Find matching record in dataframe using given parameters"""
        if df.empty:
            return None

        # Build match conditions
        conditions = []
        for param in match_params:
            if param in df.columns and param in npci_row.index:
                npci_value = npci_row[param]
                if pd.notna(npci_value):
                    if param == 'Amount':
                        # Amount matching with tolerance
                        conditions.append(abs(df[param] - npci_value) < 0.01)
                    elif param == 'Tran_Date':
                        # Date matching - exact or within 1 day
                        npci_date = pd.to_datetime(npci_value)
                        conditions.append(
                            (df[param] == npci_value) |
                            (abs(pd.to_datetime(df[param]) - npci_date) <= timedelta(days=1))
                        )
                    else:
                        conditions.append(df[param] == npci_value)

        if not conditions:
            return None

        # Combine all conditions
        combined_condition = conditions[0]
        for condition in conditions[1:]:
            combined_condition &= condition

        matches = df[combined_condition]
        if len(matches) == 1:
            return matches.iloc[0]
        elif len(matches) > 1:
            # Multiple matches - take the first one (could be improved)
            return matches.iloc[0]

        return None

    def _mark_as_matched(self, cbs_row: pd.Series, switch_row: pd.Series,
                        npci_row: pd.Series, match_type: str):
        """Mark records as matched in all three files"""
        # Mark CBS
        cbs_idx = self.cbs_df[
            (self.cbs_df['RRN'] == cbs_row['RRN']) &
            (self.cbs_df['Amount'] == cbs_row['Amount'])
        ].index
        if len(cbs_idx) > 0:
            self.cbs_df.loc[cbs_idx, 'processed'] = True
            self.cbs_df.loc[cbs_idx, 'match_status'] = 'MATCHED'
            self.cbs_df.loc[cbs_idx, 'exception_type'] = match_type

        # Mark Switch
        switch_idx = self.switch_df[
            (self.switch_df['RRN'] == switch_row['RRN']) &
            (self.switch_df['Amount'] == switch_row['Amount'])
        ].index
        if len(switch_idx) > 0:
            self.switch_df.loc[switch_idx, 'processed'] = True
            self.switch_df.loc[switch_idx, 'match_status'] = 'MATCHED'
            self.switch_df.loc[switch_idx, 'exception_type'] = match_type

        # Mark NPCI
        npci_idx = self.npci_df[
            (self.npci_df['RRN'] == npci_row['RRN']) &
            (self.npci_df['Amount'] == npci_row['Amount'])
        ].index
        if len(npci_idx) > 0:
            self.npci_df.loc[npci_idx, 'processed'] = True
            self.npci_df.loc[npci_idx, 'match_status'] = 'MATCHED'
            self.npci_df.loc[npci_idx, 'exception_type'] = match_type

    def _step_6_deemed_accepted_matching(self):
        """Step 6: Deemed accepted matching (RC='RB' → TCC 102/103)"""
        logger.info("Step 6: Processing deemed accepted transactions")

        # Find NPCI transactions with RC='RB' (deemed accepted)
        deemed_accepted = self.npci_df[
            (self.npci_df['RC'] == 'RB') &
            (~self.npci_df['processed'])
        ]

        for _, npci_row in deemed_accepted.iterrows():
            rrn = npci_row['RRN']

            # Check if corresponding debit exists in CBS (remitter account)
            cbs_debit = self.cbs_df[
                (self.cbs_df['RRN'] == rrn) &
                (self.cbs_df['Dr_Cr'].isin(['DR', 'D', 'DEBIT'])) &
                (~self.cbs_df['processed'])
            ]

            if len(cbs_debit) > 0:
                # TCC 102: Deemed accepted with CBS credit found
                self.npci_df.loc[npci_row.name, 'processed'] = True
                self.npci_df.loc[npci_row.name, 'match_status'] = 'MATCHED'
                self.npci_df.loc[npci_row.name, 'exception_type'] = 'TCC_102'

                self.cbs_df.loc[cbs_debit.index, 'processed'] = True
                self.cbs_df.loc[cbs_debit.index, 'match_status'] = 'MATCHED'
                self.cbs_df.loc[cbs_debit.index, 'exception_type'] = 'TCC_102'
            else:
                # TCC 103: Deemed accepted but no CBS credit - needs TTUM
                self.npci_df.loc[npci_row.name, 'processed'] = True
                self.npci_df.loc[npci_row.name, 'match_status'] = 'UNMATCHED'
                self.npci_df.loc[npci_row.name, 'exception_type'] = 'TCC_103'
                self.npci_df.loc[npci_row.name, 'ttum_required'] = True
                self.npci_df.loc[npci_row.name, 'ttum_type'] = 'BENEFICIARY_CREDIT'

    def _step_7_npci_declined_transactions(self):
        """Step 7: Handle NPCI declined transactions"""
        logger.info("Step 7: Processing NPCI declined transactions")

        # Find failed NPCI transactions (RC not 00 or RB)
        failed_npci = self.npci_df[
            (~self.npci_df['RC'].isin(['00', 'RB'])) &
            (~self.npci_df['processed'])
        ]

        for _, npci_row in failed_npci.iterrows():
            rrn = npci_row['RRN']

            # Check CBS - should not have any entry for failed transactions
            cbs_entries = self.cbs_df[
                (self.cbs_df['RRN'] == rrn) &
                (~self.cbs_df['processed'])
            ]

            if len(cbs_entries) > 0:
                # CBS has entries for failed NPCI transaction - needs reversal
                self.cbs_df.loc[cbs_entries.index, 'processed'] = True
                self.cbs_df.loc[cbs_entries.index, 'match_status'] = 'UNMATCHED'
                self.cbs_df.loc[cbs_entries.index, 'exception_type'] = 'NPCI_FAILED'
                self.cbs_df.loc[cbs_entries.index, 'ttum_required'] = True
                self.cbs_df.loc[cbs_entries.index, 'ttum_type'] = 'REVERSAL'

            # Mark NPCI as processed
            self.npci_df.loc[npci_row.name, 'processed'] = True
            self.npci_df.loc[npci_row.name, 'match_status'] = 'UNMATCHED'
            self.npci_df.loc[npci_row.name, 'exception_type'] = 'NPCI_DECLINED'

    def _step_8_failed_auto_credit_reversal(self):
        """Step 8: Handle failed auto-credit reversal"""
        logger.info("Step 8: Processing failed auto-credit reversals")

        # Handle scenarios where NPCI has both Dr and Cr legs but CBS has only one
        # This indicates failed auto-credit reversal scenarios

        failed_reversals = []

        # Get unprocessed NPCI transactions
        unprocessed_npci = self.npci_df[~self.npci_df['processed']]

        # Group NPCI transactions by RRN to find debit/credit pairs
        if 'RRN' in self.npci_df.columns:
            npci_rrn_groups = unprocessed_npci.groupby('RRN')

            for rrn, group in npci_rrn_groups:
                if len(group) == 2:  # Potential debit/credit pair
                    # Check if amounts are the same (indicating reversal)
                    amounts = group['Amount'].unique()
                    if len(amounts) == 1:  # Same amount
                        # Check CBS for this RRN
                        cbs_entries = self.cbs_df[
                            (self.cbs_df['RRN'] == rrn) &
                            (~self.cbs_df['processed'])
                        ]

                        if len(cbs_entries) == 1:  # CBS has only one entry
                            # This is a failed auto-credit reversal scenario
                            # Mark NPCI entries as processed
                            self.npci_df.loc[group.index, 'processed'] = True
                            self.npci_df.loc[group.index, 'match_status'] = 'UNMATCHED'
                            self.npci_df.loc[group.index, 'exception_type'] = 'FAILED_AUTO_REVERSAL'
                            self.npci_df.loc[group.index, 'ttum_required'] = True
                            self.npci_df.loc[group.index, 'ttum_type'] = 'REVERSAL'

                            # Mark CBS entry as processed
                            self.cbs_df.loc[cbs_entries.index, 'processed'] = True
                            self.cbs_df.loc[cbs_entries.index, 'match_status'] = 'UNMATCHED'
                            self.cbs_df.loc[cbs_entries.index, 'exception_type'] = 'FAILED_AUTO_REVERSAL'
                            self.cbs_df.loc[cbs_entries.index, 'ttum_required'] = True
                            self.cbs_df.loc[cbs_entries.index, 'ttum_type'] = 'REVERSAL'

                            failed_reversals.extend(group.to_dict('records'))

        logger.info(f"Found {len(failed_reversals)} failed auto-credit reversal scenarios")

    def _generate_reconciliation_results(self, run_id: str) -> Dict:
        """Generate final reconciliation results"""
        logger.info("Generating reconciliation results")

        # Add transaction categorization
        self._add_transaction_categorization()

        # Calculate inflow/outflow from all transactions
        inflow_count = 0
        inflow_amount = 0.0
        outflow_count = 0
        outflow_amount = 0.0

        for df in [self.cbs_df, self.switch_df, self.npci_df]:
            if 'Dr_Cr' in df.columns:
                # Credit transactions = Inflow
                credit_mask = df['Dr_Cr'].astype(str).str.strip().str.upper().str.startswith('C')
                inflow_count += credit_mask.sum()
                inflow_amount += df.loc[credit_mask, 'Amount'].sum() if 'Amount' in df.columns else 0

                # Debit transactions = Outflow
                debit_mask = df['Dr_Cr'].astype(str).str.strip().str.upper().str.startswith('D')
                outflow_count += debit_mask.sum()
                outflow_amount += df.loc[debit_mask, 'Amount'].sum() if 'Amount' in df.columns else 0

        results = {
            'run_id': run_id,
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_cbs': len(self.cbs_df),
                'total_switch': len(self.switch_df),
                'total_npci': len(self.npci_df),
                'matched_cbs': len(self.cbs_df[self.cbs_df['match_status'] == 'MATCHED']),
                'matched_switch': len(self.switch_df[self.switch_df['match_status'] == 'MATCHED']),
                'matched_npci': len(self.npci_df[self.npci_df['match_status'] == 'MATCHED']),
                'unmatched_cbs': len(self.cbs_df[self.cbs_df['match_status'] == 'UNMATCHED']),
                'unmatched_switch': len(self.switch_df[self.switch_df['match_status'] == 'UNMATCHED']),
                'unmatched_npci': len(self.npci_df[self.npci_df['match_status'] == 'UNMATCHED']),
                'ttum_required': len(self.cbs_df[self.cbs_df['ttum_required']]) + len(self.npci_df[self.npci_df['ttum_required']]),
                'inflow_count': int(inflow_count),
                'inflow_amount': float(inflow_amount),
                'outflow_count': int(outflow_count),
                'outflow_amount': float(outflow_amount)
            },
            'details': {
                'cbs_breakdown': self._get_status_breakdown(self.cbs_df),
                'switch_breakdown': self._get_status_breakdown(self.switch_df),
                'npci_breakdown': self._get_status_breakdown(self.npci_df)
            },
            'categorization': self._get_transaction_categorization(),
            'exceptions': self._get_exception_summary(),
            'ttum_candidates': self._get_ttum_candidates()
        }

        return results

    def _get_status_breakdown(self, df: pd.DataFrame) -> Dict:
        """Get breakdown by match status"""
        return df['match_status'].value_counts().to_dict()

    def _get_exception_summary(self) -> Dict:
        """Get summary of exceptions found with full transaction details and direction info"""
        all_exceptions = []

        for df, source in [(self.cbs_df, 'CBS'), (self.switch_df, 'SWITCH'), (self.npci_df, 'NPCI')]:
            exceptions = df[df['exception_type'].notna()]
            for _, row in exceptions.iterrows():
                # Extract fields with robust RRN and normalized date/time
                rrn = self._extract_rrn(row)
                amount = self._extract_amount(row)
                raw_date = self._extract_field(row, ['Date', 'Tran_Date', 'Transaction_Date', 'Tran_DateTime'])
                raw_time = self._extract_field(row, ['Time', 'Tran_Time', 'Transaction_Time'])
                norm_date, norm_time = self._normalize_date_time(raw_date, raw_time)
                # Separate UPI transaction id for clarity
                upi_tran_id = self._extract_field(row, ['UPI_Tran_ID', 'Transaction_ID'])
                reference = self._extract_field(row, ['Reference_ID', 'Reference'])
                description = self._extract_field(row, ['Description', 'Narration', 'Remarks', 'Notes'])
                debit_credit = self._extract_field(row, ['Debit_Credit', 'Dr_Cr', 'D_C', 'Type'])

                # Determine direction based on Dr_Cr
                direction = self._determine_direction_from_dr_cr(debit_credit)

                exc_record = {
                    'source': source,
                    'rrn': rrn,
                    'amount': amount,
                    'date': norm_date,
                    'time': norm_time,
                    'reference': reference,
                    'upi_tran_id': upi_tran_id,
                    'description': description,
                    'debit_credit': debit_credit,
                    'direction': direction,
                    'exception_type': row.get('exception_type'),
                    'ttum_required': row.get('ttum_required', False),
                    'ttum_type': row.get('ttum_type')
                }
                all_exceptions.append(exc_record)

        return all_exceptions

    def _determine_direction_from_dr_cr(self, debit_credit: str) -> str:
        """Determine transaction direction (INWARD/OUTWARD) from Dr_Cr value"""
        if not debit_credit:
            return 'UNKNOWN'
        
        dr_cr_upper = debit_credit.strip().upper()
        
        # Credit (CR/C) = Inward (money coming in)
        if dr_cr_upper.startswith('C'):
            return 'INWARD'
        # Debit (DR/D) = Outward (money going out)
        elif dr_cr_upper.startswith('D'):
            return 'OUTWARD'
        
        return 'UNKNOWN'

    def _extract_field(self, row: pd.Series, possible_columns: List[str]) -> str:
        """Extract value from row trying multiple possible column names"""
        for col_name in possible_columns:
            if col_name in row.index:
                value = row.get(col_name)
                if value is not None and pd.notna(value):
                    return str(value).strip()
        return ''

    def _extract_amount(self, row: pd.Series) -> float:
        """Extract amount safely from row"""
        try:
            amount = row.get('Amount', 0)
            if pd.notna(amount):
                return float(amount)
        except (ValueError, TypeError):
            pass
        return 0.0

    def _extract_rrn(self, row: pd.Series) -> str:
        """Extract a reliable RRN. Prefer explicit RRN; else find a numeric-like 10-20 digit token; avoid UPI_Tran_ID."""
        # Prefer dedicated RRN field
        for col in ['RRN', 'Reference_Number']:
            if col in row.index:
                val = row.get(col)
                if pd.notna(val):
                    s = str(val).strip()
                    if s:
                        return s
        # Fallback: scan candidate columns for a numeric-looking token
        import re
        candidates = []
        for col in ['Reference', 'Remarks', 'Narration', 'Description']:
            if col in row.index:
                val = row.get(col)
                if pd.notna(val):
                    candidates.append(str(val))
        text = ' '.join(candidates)
        m = re.search(r'(?<!\d)(\d{10,20})(?!\d)', text)
        if m:
            return m.group(1)
        # As last resort, if RRN missing but UPI_Tran_ID exists, do not use it as RRN; return empty
        return ''

    def _normalize_date_time(self, date_val: str, time_val: str) -> (str, str):
        """Split combined datetime into date and time if needed. Return (date, time)."""
        d = (date_val or '').strip()
        t = (time_val or '').strip()
        if not d:
            return '', t
        # If we already have time, try to reduce date to just date
        # Handle common formats
        try:
            # ISO with time
            from datetime import datetime as _dt
            # Try parse with fromisoformat
            parsed = None
            try:
                parsed = _dt.fromisoformat(d.replace('Z','').replace('T',' '))
            except Exception:
                pass
            if parsed:
                if not t:
                    t = parsed.strftime('%H:%M:%S')
                d = parsed.date().isoformat()
                return d, t
        except Exception:
            pass
        # If string contains space, split
        if ' ' in d and not t:
            parts = d.split()
            if len(parts) >= 2:
                # date first then time
                d_only = parts[0]
                t_only = parts[1][:8]
                return d_only, t_only
        # If has 'T'
        if 'T' in d and not t:
            parts = d.split('T', 1)
            d_only = parts[0]
            t_only = parts[1][:8]
            return d_only, t_only
        return d, t

    def _get_ttum_candidates(self) -> List[Dict]:
        """Get all transactions requiring TTUM generation"""
        ttum_candidates = []

        # From CBS
        cbs_ttum = self.cbs_df[self.cbs_df['ttum_required']]
        for _, row in cbs_ttum.iterrows():
            direction = self._determine_transaction_direction(row, 'CBS')
            account_number = self._get_account_number(row, direction)
            gl_accounts = self._get_gl_accounts(row.get('ttum_type'), direction)

            ttum_candidates.append({
                'source': 'CBS',
                'direction': direction,
                'rrn': row.get('RRN'),
                'amount': row.get('Amount'),
                'ttum_type': row.get('ttum_type'),
                'exception_type': row.get('exception_type'),
                'account_number': account_number,
                'gl_accounts': gl_accounts
            })

        # From NPCI
        npci_ttum = self.npci_df[self.npci_df['ttum_required']]
        for _, row in npci_ttum.iterrows():
            direction = 'OUTWARD'  # NPCI failures typically affect outward
            account_number = self._get_account_number(row, direction)
            gl_accounts = self._get_gl_accounts(row.get('ttum_type'), direction)

            ttum_candidates.append({
                'source': 'NPCI',
                'direction': direction,
                'rrn': row.get('RRN'),
                'amount': row.get('Amount'),
                'ttum_type': row.get('ttum_type'),
                'exception_type': row.get('exception_type'),
                'account_number': account_number,
                'gl_accounts': gl_accounts
            })

        # From SWITCH if marked (carry-over triggers)
        if 'ttum_required' in self.switch_df.columns:
            sw_ttum = self.switch_df[self.switch_df['ttum_required']]
            for _, row in sw_ttum.iterrows():
                direction = self._determine_transaction_direction(row, 'SWITCH')
                account_number = self._get_account_number(row, direction)
                gl_accounts = self._get_gl_accounts(row.get('ttum_type'), direction)
                ttum_candidates.append({
                    'source': 'SWITCH',
                    'direction': direction,
                    'rrn': row.get('RRN'),
                    'amount': row.get('Amount'),
                    'ttum_type': row.get('ttum_type'),
                    'exception_type': row.get('exception_type'),
                    'account_number': account_number,
                    'gl_accounts': gl_accounts
                })

        return ttum_candidates

    def _find_partial_match(self, df: pd.DataFrame, npci_row: pd.Series,
                           match_params: List[str]) -> Optional[pd.Series]:
        """Find partial matching record (not exact match)"""
        if df.empty:
            return None

        # Build partial match conditions (more lenient)
        conditions = []
        for param in match_params:
            if param in df.columns and param in npci_row.index:
                npci_value = npci_row[param]
                if pd.notna(npci_value):
                    if param == 'Amount':
                        # Amount matching with larger tolerance for partial matches
                        conditions.append(abs(df[param] - npci_value) < 1.0)  # $1 tolerance
                    elif param == 'Tran_Date':
                        # Date matching - within 2 days for partial matches
                        npci_date = pd.to_datetime(npci_value)
                        conditions.append(
                            abs(pd.to_datetime(df[param]) - npci_date) <= timedelta(days=2)
                        )
                    else:
                        conditions.append(df[param] == npci_value)

        if not conditions:
            return None

        # Combine all conditions
        combined_condition = conditions[0]
        for condition in conditions[1:]:
            combined_condition &= condition

        matches = df[combined_condition]
        if len(matches) > 0:
            return matches.iloc[0]

        return None

    def _mark_as_hanging(self, npci_row: pd.Series, reason: str):
        """Mark a transaction as hanging"""
        npci_idx = self.npci_df[
            (self.npci_df['RRN'] == npci_row['RRN']) &
            (self.npci_df['Amount'] == npci_row['Amount'])
        ].index

        if len(npci_idx) > 0:
            self.npci_df.loc[npci_idx, 'processed'] = True
            self.npci_df.loc[npci_idx, 'match_status'] = 'HANGING'
            self.npci_df.loc[npci_idx, 'exception_type'] = reason

    def _determine_transaction_direction(self, row: pd.Series, source: str) -> str:
        """Determine if transaction is INWARD or OUTWARD based on various factors"""
        if source == 'CBS':
            # For CBS, determine direction based on Dr_Cr and exception type
            dr_cr = str(row.get('Dr_Cr', '')).upper()

            # If it's a debit (DR/D), it's typically an outward transaction (money going out)
            if dr_cr in ['DR', 'D', 'DEBIT']:
                return 'OUTWARD'
            # If it's a credit (CR/C), it's typically an inward transaction (money coming in)
            elif dr_cr in ['CR', 'C', 'CREDIT']:
                return 'INWARD'

            # For specific exception types, we can determine direction
            exception_type = row.get('exception_type')
            if exception_type in ['NPCI_FAILED', 'DOUBLE_DEBIT_CREDIT', 'FAILED_AUTO_REVERSAL']:
                return 'OUTWARD'  # These typically require remitter refunds
            elif exception_type in ['BENEFICIARY_RECOVERY']:
                return 'INWARD'  # These require beneficiary recovery

        # Default fallback
        return 'OUTWARD'

    def _get_account_number(self, row: pd.Series, direction: str) -> str:
        """Get the appropriate account number based on transaction direction"""
        if direction == 'OUTWARD':
            # For outward transactions, use remitter account
            return row.get('Remitter_Number', row.get('Account_Number', ''))
        else:
            # For inward transactions, use beneficiary account
            return row.get('Beneficiary_Number', row.get('Account_Number', ''))

    def _get_gl_accounts(self, ttum_type: str, direction: str) -> Dict[str, str]:
        """Get GL accounts for TTUM based on type and direction"""
        if ttum_type in TTUM_TYPES:
            ttum_config = TTUM_TYPES[ttum_type]
            if ttum_config['type'] == 'BOTH' or ttum_config['type'] == direction:
                return ttum_config['gl_accounts']

        # Default GL accounts based on direction
        if direction == 'OUTWARD':
            return {
                'debit': GL_ACCOUNTS.get('REMITTER_ACCOUNT', 'REMITTER_ACCOUNTS'),
                'credit': GL_ACCOUNTS.get('NPCI_SETTLEMENT_ACCOUNT', 'NPCI_SETTLEMENT')
            }
        else:
            return {
                'debit': GL_ACCOUNTS.get('NPCI_SETTLEMENT_ACCOUNT', 'NPCI_SETTLEMENT'),
                'credit': GL_ACCOUNTS.get('BENEFICIARY_ACCOUNT', 'BENEFICIARY_ACCOUNTS')
            }

    def _add_transaction_categorization(self):
        """Add transaction categorization based on match status and exception types"""
        # Categorize CBS transactions
        for idx, row in self.cbs_df.iterrows():
            category = self._categorize_transaction(row, 'CBS')
            self.cbs_df.loc[idx, 'category'] = category

        # Categorize Switch transactions
        for idx, row in self.switch_df.iterrows():
            category = self._categorize_transaction(row, 'SWITCH')
            self.switch_df.loc[idx, 'category'] = category

        # Categorize NPCI transactions
        for idx, row in self.npci_df.iterrows():
            category = self._categorize_transaction(row, 'NPCI')
            self.npci_df.loc[idx, 'category'] = category

    def _categorize_transaction(self, row: pd.Series, source: str) -> str:
        """Categorize a single transaction based on its properties"""
        match_status = row.get('match_status', 'UNMATCHED')
        exception_type = row.get('exception_type')

        # Matched transactions
        if match_status == 'MATCHED':
            if exception_type == 'SELF_MATCHED':
                return 'SELF_MATCHED'
            elif exception_type == 'SETTLEMENT_ENTRY':
                return 'SETTLEMENT_ENTRY'
            else:
                return 'MATCHED'

        # Hanging transactions
        if match_status == 'HANGING':
            return 'HANGING'

        # TCC categories
        if exception_type in ['TCC_102', 'TCC_103']:
            return exception_type

        # Return transactions
        if exception_type == 'RET':
            return 'RET'

        # Unmatched transactions requiring TTUM
        if row.get('ttum_required', False):
            return 'TTUM_REQUIRED'

        # Default unmatched
        return 'UNMATCHED'

    def _get_transaction_categorization(self) -> Dict:
        """Get summary of transaction categorization"""
        cbs_categories = self.cbs_df['category'].value_counts().to_dict() if 'category' in self.cbs_df.columns else {}
        switch_categories = self.switch_df['category'].value_counts().to_dict() if 'category' in self.switch_df.columns else {}
        npci_categories = self.npci_df['category'].value_counts().to_dict() if 'category' in self.npci_df.columns else {}

        return {
            'cbs': cbs_categories,
            'switch': switch_categories,
            'npci': npci_categories
        }

    def _apply_exception_handling_matrix(self):
        """Apply exception handling matrix for remaining unprocessed transactions
        
        Uses EXCEPTION_MATRIX configuration to determine proper handling for each
        combination of CBS/SWITCH/NPCI transaction statuses. Categorizes exceptions
        and marks TTUM requirements.
        """
        logger.info("Applying exception handling matrix for unprocessed transactions")

        exception_count_by_type = {}
        
        # Get unprocessed transactions
        unprocessed_cbs = self.cbs_df[~self.cbs_df['processed']]
        unprocessed_switch = self.switch_df[~self.switch_df['processed']]
        unprocessed_npci = self.npci_df[~self.npci_df['processed']]

        # Process each unprocessed CBS transaction
        for _, cbs_row in unprocessed_cbs.iterrows():
            rrn = cbs_row.get('RRN')
            if pd.isna(rrn) or rrn == '':
                continue

            # Find matching transactions in Switch and NPCI
            switch_match = self._find_matching_by_rrn(unprocessed_switch, rrn)
            npci_match = self._find_matching_by_rrn(unprocessed_npci, rrn)

            # Determine status for each source
            cbs_status = self._get_source_status(cbs_row, 'CBS')
            switch_status = self._get_source_status(switch_match, 'SWITCH') if switch_match is not None else 'FAILED'
            npci_status = self._get_source_status(npci_match, 'NPCI') if npci_match is not None else 'FAILED'

            # Create combination key
            combination_key = f"{cbs_status}_{switch_status}_{npci_status}"

            # Apply exception handling based on matrix
            if combination_key in EXCEPTION_MATRIX:
                actions = EXCEPTION_MATRIX[combination_key]
                self._apply_exception_actions(cbs_row, switch_match, npci_match, actions, rrn)
                
                # Track exception types for summary
                action_type = actions.get('action', 'UNMATCHED')
                exception_count_by_type[action_type] = exception_count_by_type.get(action_type, 0) + 1
            else:
                # Mark as unmatched if no rule found
                if not cbs_row['processed']:
                    self.cbs_df.loc[cbs_row.name, 'processed'] = True
                    self.cbs_df.loc[cbs_row.name, 'match_status'] = 'UNMATCHED'
                    self.cbs_df.loc[cbs_row.name, 'exception_type'] = 'UNMATCHED_NO_RULE'
                    logger.debug(f"RRN {rrn}: No matching rule in exception matrix for {combination_key}")

        logger.info("Exception handling matrix applied")
        if exception_count_by_type:
            logger.info(f"Exception counts by type: {exception_count_by_type}")

    def _find_matching_by_rrn(self, df: pd.DataFrame, rrn: str) -> Optional[pd.Series]:
        """Find matching record by RRN"""
        if df.empty or pd.isna(rrn):
            return None

        matches = df[df['RRN'] == rrn]
        if len(matches) > 0:
            return matches.iloc[0]
        return None

    def _get_source_status(self, row: Optional[pd.Series], source: str) -> str:
        """Determine status for a source (SUCCESS or FAILED)"""
        if row is None:
            return 'FAILED'

        if source == 'CBS':
            # CBS is considered successful if it exists
            return 'SUCCESS'
        elif source == 'SWITCH':
            # Switch success based on some criteria (e.g., response code)
            rc = row.get('RC', '')
            return 'SUCCESS' if rc == '00' else 'FAILED'
        elif source == 'NPCI':
            # NPCI success based on response code
            rc = row.get('RC', '')
            return 'SUCCESS' if rc in ['00', 'RB'] else 'FAILED'

        return 'FAILED'

    def _apply_exception_actions(self, cbs_row: pd.Series, switch_row: Optional[pd.Series],
                                npci_row: Optional[pd.Series], actions: Dict, rrn: str):
        """Apply exception actions based on matrix configuration with proper TTUM/TCC generation
        
        Handles direction-specific logic for inward vs outward transactions.
        Maps exception matrix actions to transaction marking and TTUM/TCC requirement decisions.
        """
        # Determine transaction direction from CBS Dr_Cr
        direction = 'OUTWARD' if cbs_row.get('Dr_Cr', '').upper() in ['DR', 'D'] else 'INWARD'
        
        # Get the appropriate action based on direction
        action_key = f"{direction.lower()}_action"
        action_type = actions.get(action_key, 'UNMATCHED')
        
        logger.debug(f"Applying {direction} exception action {action_type} for RRN {rrn}")

        # Handle different action types
        if action_type == 'MATCHED':
            # Mark all as matched - successful reconciliation
            self._mark_transaction_status(cbs_row, switch_row, npci_row, 'MATCHED', None, False, None, None)
            
        elif action_type == 'CONDITIONAL_TCC_102':
            # For inward: No action if RC=00, TCC 102 if RC=RB
            rc = npci_row.get('RC', '') if npci_row is not None else ''
            if rc == 'RB':
                # Generate TCC 102
                self._mark_transaction_status(cbs_row, switch_row, npci_row, 'MATCHED', 'TCC_102', False, None, 'TCC_102')
            else:
                # No action - matched
                self._mark_transaction_status(cbs_row, switch_row, npci_row, 'MATCHED', None, False, None, None)
                
        elif action_type == 'REMITTER_REFUND_TTUM':
            # Generate remitter refund TTUM
            self._mark_transaction_status(cbs_row, switch_row, npci_row, 'UNMATCHED', 'REMITTER_REFUND', True, 'REVERSAL', None)
            
        elif action_type == 'BENEFICIARY_RECOVERY_TTUM':
            # Generate beneficiary recovery TTUM
            if npci_row is not None:
                npci_idx = self.npci_df[
                    (self.npci_df['RRN'] == rrn) & 
                    (~self.npci_df['processed'])
                ].index
                if len(npci_idx) > 0:
                    self.npci_df.loc[npci_idx, 'processed'] = True
                    self.npci_df.loc[npci_idx, 'match_status'] = 'UNMATCHED'
                    self.npci_df.loc[npci_idx, 'exception_type'] = 'BENEFICIARY_RECOVERY'
                    self.npci_df.loc[npci_idx, 'ttum_required'] = True
                    self.npci_df.loc[npci_idx, 'ttum_type'] = 'BENEFICIARY_CREDIT'
                    logger.info(f"RRN {rrn}: Marked NPCI for BENEFICIARY_RECOVERY TTUM")
                    
        elif action_type == 'SWITCH_UPDATE':
            # Mark for switch update
            if switch_row is not None:
                switch_idx = self.switch_df[
                    (self.switch_df['RRN'] == rrn) & 
                    (~self.switch_df['processed'])
                ].index
                if len(switch_idx) > 0:
                    self.switch_df.loc[switch_idx, 'processed'] = True
                    self.switch_df.loc[switch_idx, 'match_status'] = 'UNMATCHED'
                    self.switch_df.loc[switch_idx, 'exception_type'] = 'SWITCH_UPDATE'
                    self.switch_df.loc[switch_idx, 'switch_update_required'] = True
                    logger.info(f"RRN {rrn}: Marked SWITCH for update")
                    
        elif action_type == 'CONDITIONAL_TCC_102_SWITCH_UPDATE':
            # For inward: conditional TCC 102 + switch update
            rc = npci_row.get('RC', '') if npci_row is not None else ''
            tcc_type = 'TCC_102' if rc == 'RB' else None
            
            # Mark switch for update
            if switch_row is not None:
                switch_idx = self.switch_df[
                    (self.switch_df['RRN'] == rrn) & 
                    (~self.switch_df['processed'])
                ].index
                if len(switch_idx) > 0:
                    self.switch_df.loc[switch_idx, 'processed'] = True
                    self.switch_df.loc[switch_idx, 'match_status'] = 'UNMATCHED'
                    self.switch_df.loc[switch_idx, 'exception_type'] = 'SWITCH_UPDATE_TCC'
                    self.switch_df.loc[switch_idx, 'switch_update_required'] = True
                    if tcc_type:
                        self.switch_df.loc[switch_idx, 'tcc_type'] = tcc_type
                    logger.info(f"RRN {rrn}: Marked SWITCH for update with TCC {tcc_type}")
                    
        elif action_type == 'REMITTER_RECOVERY_TTUM':
            # Generate remitter recovery TTUM
            self._mark_transaction_status(cbs_row, switch_row, npci_row, 'UNMATCHED', 'REMITTER_RECOVERY', True, 'RECOVERY', None)
            
        elif action_type == 'BENEFICIARY_CREDIT_TTUM_TCC_103':
            # Generate beneficiary credit TTUM + TCC 103
            if npci_row is not None:
                npci_idx = self.npci_df[
                    (self.npci_df['RRN'] == rrn) & 
                    (~self.npci_df['processed'])
                ].index
                if len(npci_idx) > 0:
                    self.npci_df.loc[npci_idx, 'processed'] = True
                    self.npci_df.loc[npci_idx, 'match_status'] = 'UNMATCHED'
                    self.npci_df.loc[npci_idx, 'exception_type'] = 'BENEFICIARY_CREDIT_TCC_103'
                    self.npci_df.loc[npci_idx, 'ttum_required'] = True
                    self.npci_df.loc[npci_idx, 'ttum_type'] = 'BENEFICIARY_CREDIT'
                    self.npci_df.loc[npci_idx, 'tcc_type'] = 'TCC_103'
                    logger.info(f"RRN {rrn}: Marked NPCI for BENEFICIARY_CREDIT TTUM + TCC_103")
                    
        else:
            # Default to unmatched
            self._mark_transaction_status(cbs_row, switch_row, npci_row, 'UNMATCHED', None, False, None, None)
            logger.debug(f"RRN {rrn}: Marked as unmatched (default action)")

    def _mark_transaction_status(self, cbs_row: pd.Series, switch_row: Optional[pd.Series],
                                npci_row: Optional[pd.Series], match_status: str, exception_type: Optional[str],
                                ttum_required: bool, ttum_type: Optional[str], tcc_type: Optional[str] = None):
        """Mark transaction status for all sources with TTUM and TCC support"""
        # Mark CBS
        if cbs_row is not None:
            cbs_idx = self.cbs_df[
                (self.cbs_df['RRN'] == cbs_row['RRN']) &
                (self.cbs_df['Amount'] == cbs_row['Amount'])
            ].index
            if len(cbs_idx) > 0:
                self.cbs_df.loc[cbs_idx, 'processed'] = True
                self.cbs_df.loc[cbs_idx, 'match_status'] = match_status
                if exception_type:
                    self.cbs_df.loc[cbs_idx, 'exception_type'] = exception_type
                self.cbs_df.loc[cbs_idx, 'ttum_required'] = ttum_required
                if ttum_type:
                    self.cbs_df.loc[cbs_idx, 'ttum_type'] = ttum_type
                if tcc_type:
                    self.cbs_df.loc[cbs_idx, 'tcc_type'] = tcc_type

        # Mark Switch
        if switch_row is not None:
            switch_idx = self.switch_df[
                (self.switch_df['RRN'] == switch_row['RRN']) &
                (self.switch_df['Amount'] == switch_row['Amount'])
            ].index
            if len(switch_idx) > 0:
                self.switch_df.loc[switch_idx, 'processed'] = True
                self.switch_df.loc[switch_idx, 'match_status'] = match_status
                if exception_type:
                    self.switch_df.loc[switch_idx, 'exception_type'] = exception_type
                self.switch_df.loc[switch_idx, 'ttum_required'] = ttum_required
                if ttum_type:
                    self.switch_df.loc[switch_idx, 'ttum_type'] = ttum_type
                if tcc_type:
                    self.switch_df.loc[switch_idx, 'tcc_type'] = tcc_type

        # Mark NPCI
        if npci_row is not None:
            npci_idx = self.npci_df[
                (self.npci_df['RRN'] == npci_row['RRN']) &
                (self.npci_df['Amount'] == npci_row['Amount'])
            ].index
            if len(npci_idx) > 0:
                self.npci_df.loc[npci_idx, 'processed'] = True
                self.npci_df.loc[npci_idx, 'match_status'] = match_status
                if exception_type:
                    self.npci_df.loc[npci_idx, 'exception_type'] = exception_type
                self.npci_df.loc[npci_idx, 'ttum_required'] = ttum_required
                if ttum_type:
                    self.npci_df.loc[npci_idx, 'ttum_type'] = ttum_type
                if tcc_type:
                    self.npci_df.loc[npci_idx, 'tcc_type'] = tcc_type

    def _apply_adjustments(self):
        """Apply adjustment.csv entries during reconciliation
        
        Adjustments can override mismatches, compensate for missing entries,
        or force match transactions based on business rules.
        """
        if self.adjustment_df.empty:
            return
            
        logger.info(f"Applying {len(self.adjustment_df)} adjustment entries")
        
        for _, adj_row in self.adjustment_df.iterrows():
            rrn = str(adj_row.get('RRN', '')).strip()
            if not rrn:
                continue
                
            adj_type = str(adj_row.get('Adjtype', '')).upper()
            adj_amount = float(adj_row.get('Adjamount', 0))
            
            # Find matching transactions across all dataframes
            self._apply_single_adjustment(rrn, adj_row, adj_type, adj_amount)
            
        logger.info("Adjustment processing completed")

    def _apply_single_adjustment(self, rrn: str, adj_row: pd.Series, adj_type: str, adj_amount: float):
        """Apply a single adjustment entry"""
        # Find transactions by RRN across all sources
        cbs_matches = self.cbs_df[self.cbs_df['RRN'].astype(str) == rrn] if 'RRN' in self.cbs_df.columns else pd.DataFrame()
        switch_matches = self.switch_df[self.switch_df['RRN'].astype(str) == rrn] if 'RRN' in self.switch_df.columns else pd.DataFrame()
        npci_matches = self.npci_df[self.npci_df['RRN'].astype(str) == rrn] if 'RRN' in self.npci_df.columns else pd.DataFrame()
        
        if adj_type == 'FORCE_MATCH':
            # Force match transactions that would otherwise be unmatched
            self._force_match_adjustment(cbs_matches, switch_matches, npci_matches, rrn)
            
        elif adj_type == 'AMOUNT_CORRECTION':
            # Adjust amounts to match
            self._amount_correction_adjustment(cbs_matches, switch_matches, npci_matches, adj_amount, rrn)
            
        elif adj_type == 'STATUS_OVERRIDE':
            # Override match status
            self._status_override_adjustment(cbs_matches, switch_matches, npci_matches, adj_row, rrn)
            
        # Mark adjustment as applied
        logger.debug(f"Applied {adj_type} adjustment for RRN {rrn}")

    def _force_match_adjustment(self, cbs_matches, switch_matches, npci_matches, rrn):
        """Force match transactions across sources"""
        # Mark all matching transactions as matched
        for df_name, matches in [('cbs_df', cbs_matches), ('switch_df', switch_matches), ('npci_df', npci_matches)]:
            if not matches.empty:
                df = getattr(self, df_name)
                for idx in matches.index:
                    df.loc[idx, 'match_status'] = 'MATCHED'
                    df.loc[idx, 'processed'] = True
                    df.loc[idx, 'exception_type'] = 'ADJUSTMENT_FORCE_MATCH'
                    
    def _amount_correction_adjustment(self, cbs_matches, switch_matches, npci_matches, adj_amount, rrn):
        """Correct amounts to enable matching"""
        # Adjust amounts in all sources to the adjustment amount
        for df_name, matches in [('cbs_df', cbs_matches), ('switch_df', switch_matches), ('npci_df', npci_matches)]:
            if not matches.empty:
                df = getattr(self, df_name)
                for idx in matches.index:
                    df.loc[idx, 'Amount'] = adj_amount
                    df.loc[idx, 'exception_type'] = 'ADJUSTMENT_AMOUNT_CORRECTION'
                    
    def _status_override_adjustment(self, cbs_matches, switch_matches, npci_matches, adj_row, rrn):
        """Override transaction status based on adjustment"""
        new_status = str(adj_row.get('Response', 'MATCHED')).upper()
        
        for df_name, matches in [('cbs_df', cbs_matches), ('switch_df', switch_matches), ('npci_df', npci_matches)]:
            if not matches.empty:
                df = getattr(self, df_name)
                for idx in matches.index:
                    df.loc[idx, 'match_status'] = new_status
                    df.loc[idx, 'processed'] = True
                    df.loc[idx, 'exception_type'] = 'ADJUSTMENT_STATUS_OVERRIDE'
