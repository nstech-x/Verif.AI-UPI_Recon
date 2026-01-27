"""
Settlement Accounting Engine - Phase 3 Task 4
Generates vouchers and GL entries from reconciled transactions
Integrates with GL Proofing for variance analysis and bridging
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
from logging_config import get_logger

logger = get_logger(__name__)
from annexure_iv import generate_annexure_iv_csv
from reporting import write_report, write_ttum_xlsx


class VoucherType(Enum):
    """Types of accounting vouchers"""
    PAYMENT = "PAYMENT"          # Customer payments
    REVERSAL = "REVERSAL"        # Transaction reversals
    ADJUSTMENT = "ADJUSTMENT"    # Manual adjustments
    SETTLEMENT = "SETTLEMENT"    # Settlement entries


class VoucherStatus(Enum):
    """Status of voucher processing"""
    GENERATED = "generated"      # Voucher created
    POSTED = "posted"           # Posted to GL
    FAILED = "failed"           # Posting failed
    REVERSED = "reversed"       # Voucher reversed


class GLEntry:
    """Represents a General Ledger entry"""

    def __init__(
        self,
        account_code: str,
        account_name: str,
        debit_amount: float = 0.0,
        credit_amount: float = 0.0,
        description: str = "",
        reference: str = ""
    ):
        self.account_code = account_code
        self.account_name = account_name
        self.debit_amount = debit_amount
        self.credit_amount = credit_amount
        self.description = description
        self.reference = reference
        self.entry_id = f"GL_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "entry_id": self.entry_id,
            "account_code": self.account_code,
            "account_name": self.account_name,
            "debit_amount": self.debit_amount,
            "credit_amount": self.credit_amount,
            "description": self.description,
            "reference": self.reference,
            "timestamp": self.timestamp
        }


class Voucher:
    """Represents an accounting voucher"""

    def __init__(
        self,
        voucher_id: str,
        voucher_type: VoucherType,
        transaction_date: str,
        amount: float,
        description: str,
        gl_entries: List[GLEntry]
    ):
        self.voucher_id = voucher_id
        self.voucher_type = voucher_type
        self.transaction_date = transaction_date
        self.amount = amount
        self.description = description
        self.gl_entries = gl_entries
        self.status = VoucherStatus.GENERATED
        self.created_at = datetime.now().isoformat()
        self.posted_at = None
        self.rrn = None  # Link to original transaction

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "voucher_id": self.voucher_id,
            "voucher_type": self.voucher_type.value,
            "transaction_date": self.transaction_date,
            "amount": self.amount,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at,
            "posted_at": self.posted_at,
            "rrn": self.rrn,
            "gl_entries": [entry.to_dict() for entry in self.gl_entries]
        }


class SettlementEngine:
    """Engine for generating vouchers and GL entries from reconciled transactions"""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.settlement_dir = os.path.join(output_dir, "settlement")
        os.makedirs(self.settlement_dir, exist_ok=True)

        # GL Account mappings (configurable)
        self.gl_accounts = {
            "cash_account": {"code": "100100", "name": "Cash in Hand"},
            "bank_account": {"code": "100200", "name": "Bank Account"},
            "suspense_account": {"code": "200100", "name": "Suspense Account"},
            "fee_income": {"code": "400100", "name": "Transaction Fee Income"},
            "fee_expense": {"code": "500100", "name": "Transaction Fee Expense"},
            "settlement_payable": {"code": "200200", "name": "Settlement Payable"},
            "settlement_receivable": {"code": "100300", "name": "Settlement Receivable"}
        }

        self.vouchers: List[Voucher] = []
        self.voucher_counter = 1
        # Load optional TTUM mapping and issuer action file
        self.ttum_mapping = self._load_ttum_mapping()
        self.issuer_actions = self._load_issuer_actions()

    def _load_ttum_mapping(self) -> Dict:
        """Load optional TTUM mapping JSON from config/ttum_mapping.json if present."""
        try:
            cfg_dir = os.path.join(os.path.dirname(__file__), 'config')
            cfg_path = os.path.join(cfg_dir, 'ttum_mapping.json')
            if os.path.exists(cfg_path):
                with open(cfg_path, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _load_issuer_actions(self) -> Dict:
        """Attempt to read issuer action mapping from bank_recon_files/Issuer_Raw_20260103.xlsx
        Returns a mapping of RRN string -> { 'action_point': str, 'outward_payable': str (optional) }
        Handles spreadsheets where the outward GL may be in a top header row and the data header is on a later row.
        """
        try:
            import pandas as pd
            issuer_path = os.path.join(os.path.dirname(__file__), 'bank_recon_files', 'Issuer_Raw_20260103.xlsx')
            if not os.path.exists(issuer_path):
                return {}

            df = pd.read_excel(issuer_path, sheet_name=0, header=None, dtype=str)

            # Find outward GL: search first 5 rows/cols for a cell that looks like A<digits>
            outward_gl = None
            import re
            pattern = re.compile(r"\bA\d{6,}\b")
            for i in range(min(5, len(df.index))):
                for j in range(min(8, len(df.columns))):
                    cell = str(df.iat[i, j]) if pd.notna(df.iat[i, j]) else ''
                    if pattern.search(cell):
                        outward_gl = pattern.search(cell).group(0)
                        break
                if outward_gl:
                    break

            # Find header row which contains 'RRN' or 'Txn Category' or 'Action'
            header_row_idx = None
            rrn_idx = None
            action_idx = None
            desc_idx = None
            for i in range(min(10, len(df.index))):
                row_text = ' '.join([str(x).lower() if pd.notna(x) else '' for x in df.iloc[i].tolist()])
                if 'rrn' in row_text or 'txn category' in row_text or 'action point' in row_text or 'description' in row_text:
                    header_row_idx = i
                    # identify column indices
                    for j, val in enumerate(df.iloc[i].tolist()):
                        v = str(val).strip().lower() if pd.notna(val) else ''
                        if 'rrn' in v or 'reference' in v:
                            rrn_idx = j
                        if 'action' in v or 'action point' in v:
                            action_idx = j
                        if 'description' in v or 'desc' in v:
                            desc_idx = j
                    break

            issuer_map = {}
            current_category = None
            start_row = header_row_idx + 1 if header_row_idx is not None else 0
            for i in range(start_row, len(df.index)):
                row = df.iloc[i].tolist()
                # category may appear in first column when RRN blank
                first = str(row[0]).strip() if pd.notna(row[0]) else ''
                if first and not any(ch.isdigit() for ch in first):
                    current_category = first
                # get rrn from identified column or by searching numeric-like cell
                rrn = None
                if rrn_idx is not None:
                    val = row[rrn_idx] if rrn_idx < len(row) else None
                    if pd.notna(val) and str(val).strip():
                        rrn = str(val).strip()
                if not rrn:
                    # try find a numeric-looking string in row
                    for v in row:
                        if pd.notna(v):
                            s = str(v).strip()
                            if s.isdigit():
                                rrn = s
                                break
                if not rrn:
                    continue
                action = ''
                if action_idx is not None and action_idx < len(row) and pd.notna(row[action_idx]):
                    action = str(row[action_idx]).strip()
                # fallback to derive action from current category
                if not action and current_category:
                    action = current_category

                issuer_map[str(rrn)] = {
                    'action_point': action,
                    'outward_payable': outward_gl
                }

            return issuer_map
        except Exception:
            return {}

    def _build_npci_rrn_map(self, run_folder: str) -> Dict[str, Dict[str, str]]:
        """Build a lookup map from RRN -> {payer_psp, payee_psp} by scanning NPCI raw files under run_folder.
        Supports CSV/XLS/XLSX with columns like 'RRN', 'Payer_PSP', 'Payee_PSP'.
        """
        mapping: Dict[str, Dict[str, str]] = {}
        try:
            import pandas as pd
        except Exception:
            return mapping

        # search for NPCI files recursively
        for root, dirs, files in os.walk(run_folder):
            for fname in files:
                fpath = os.path.join(root, fname)
                fl = fname.lower()
                if not any(x in fl for x in ['npci']):
                    continue
                if not fl.endswith(('.csv', '.xlsx', '.xls')):
                    continue
                try:
                    if fl.endswith('.csv'):
                        df = pd.read_csv(fpath)
                    else:
                        df = pd.read_excel(fpath)
                    cols = {c: str(c).strip() for c in df.columns}
                    # normalize column access
                    def col(name_opts: List[str]) -> Optional[str]:
                        for n in name_opts:
                            if n in df.columns:
                                return n
                            # case-insensitive match
                            for c in df.columns:
                                if str(c).strip().lower() == n.lower():
                                    return c
                        return None
                    rrn_col = col(['RRN', 'Reference_Number', 'Ref', 'Shser'])
                    payer_col = col(['Payer_PSP', 'Payer', 'PayerPSP'])
                    payee_col = col(['Payee_PSP', 'Payee', 'PayeePSP'])
                    if not rrn_col:
                        continue
                    for _, row in df.iterrows():
                        rrn_val = row.get(rrn_col)
                        if rrn_val is None:
                            continue
                        rrn_str = str(rrn_val).strip()
                        if not rrn_str:
                            continue
                        payer = row.get(payer_col) if payer_col else ''
                        payee = row.get(payee_col) if payee_col else ''
                        mapping[rrn_str] = {
                            'payer_psp': '' if payer is None else str(payer).strip(),
                            'payee_psp': '' if payee is None else str(payee).strip()
                        }
                except Exception:
                    continue
        return mapping

    def generate_vouchers_from_recon(self, recon_results: Dict, run_id: str) -> Dict:
        """
        Generate vouchers and GL entries from reconciliation results

        Args:
            recon_results: Reconciliation results dictionary
            run_id: Current run identifier

        Returns:
            Dict with settlement details
        """
        logger.info(f"Generating vouchers for run {run_id}")

        vouchers = []
        total_amount = 0.0
        matched_count = 0
        settlement_count = 0

        # Process matched transactions
        for rrn, record in recon_results.items():
            if record.get('status') == 'MATCHED':
                try:
                    voucher = self._create_payment_voucher(rrn, record)
                    if voucher:
                        vouchers.append(voucher)
                        total_amount += voucher.amount
                        matched_count += 1

                except Exception as e:
                    logger.error(f"Failed to create voucher for RRN {rrn}: {str(e)}")

            elif record.get('status') in ['PARTIAL_MATCH', 'ORPHAN']:
                try:
                    voucher = self._create_settlement_voucher(rrn, record)
                    if voucher:
                        vouchers.append(voucher)
                        settlement_count += 1

                except Exception as e:
                    logger.error(f"Failed to create settlement voucher for RRN {rrn}: {str(e)}")

        # Save vouchers to file
        settlement_data = {
            "run_id": run_id,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_vouchers": len(vouchers),
                "matched_transactions": matched_count,
                "settlement_transactions": settlement_count,
                "total_amount": total_amount
            },
            "vouchers": [v.to_dict() for v in vouchers]
        }

        settlement_path = os.path.join(self.settlement_dir, f"settlement_{run_id}.json")
        with open(settlement_path, 'w') as f:
            json.dump(settlement_data, f, indent=2)

        self.vouchers.extend(vouchers)

        logger.info(f"Generated {len(vouchers)} vouchers totaling ₹{total_amount:,.2f}")

        return {
            "status": "success",
            "run_id": run_id,
            "vouchers_generated": len(vouchers),
            "total_amount": total_amount,
            "matched_count": matched_count,
            "settlement_count": settlement_count,
            "settlement_file": settlement_path
        }

    def generate_gl_statement(self, run_id: str, run_folder: str) -> str:
        """Generate a GL statement CSV from generated vouchers for the run."""
        import csv
        try:
            settlement_file = os.path.join(self.settlement_dir, f"settlement_{run_id}.json")
            if not os.path.exists(settlement_file):
                return ''
            with open(settlement_file, 'r') as f:
                data = json.load(f)

            reports_dir = os.path.join(run_folder, 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            gl_path = os.path.join(reports_dir, 'gl_statement.csv')
            with open(gl_path, 'w', newline='') as gf:
                writer = csv.writer(gf)
                writer.writerow(['Voucher_ID', 'RRN', 'Voucher_Type', 'Amount', 'Status', 'Created_At'])
                for v in data.get('vouchers', []):
                    writer.writerow([v.get('voucher_id'), v.get('rrn'), v.get('voucher_type'), v.get('amount'), v.get('status'), v.get('created_at')])

            return gl_path
        except Exception as e:
            logger.error(f"Failed to generate GL statement: {e}")
            return ''

    def _create_payment_voucher(self, rrn: str, record: Dict) -> Optional[Voucher]:
        """Create payment voucher for matched transactions"""
        # Get transaction amount (assume CBS amount as primary)
        amount = 0.0
        transaction_date = ""

        if record.get('cbs'):
            amount = record['cbs'].get('amount', 0)
            transaction_date = record['cbs'].get('date', '')

        if amount <= 0:
            return None

        voucher_id = f"VOUCHER_{self.voucher_counter:06d}"
        self.voucher_counter += 1

        # Create GL entries for payment voucher
        gl_entries = []

        # Debit bank account (money received)
        gl_entries.append(GLEntry(
            account_code=self.gl_accounts["bank_account"]["code"],
            account_name=self.gl_accounts["bank_account"]["name"],
            debit_amount=amount,
            description=f"Payment received - RRN {rrn}",
            reference=f"RRN:{rrn}"
        ))

        # Credit settlement receivable (liability to customer)
        gl_entries.append(GLEntry(
            account_code=self.gl_accounts["settlement_receivable"]["code"],
            account_name=self.gl_accounts["settlement_receivable"]["name"],
            credit_amount=amount,
            description=f"Settlement receivable - RRN {rrn}",
            reference=f"RRN:{rrn}"
        ))

        voucher = Voucher(
            voucher_id=voucher_id,
            voucher_type=VoucherType.PAYMENT,
            transaction_date=transaction_date,
            amount=amount,
            description=f"Payment voucher for matched transaction RRN {rrn}",
            gl_entries=gl_entries
        )
        voucher.rrn = rrn

        return voucher

    def _create_settlement_voucher(self, rrn: str, record: Dict) -> Optional[Voucher]:
        """Create settlement voucher for unmatched transactions"""
        # Get available amount
        amount = 0.0
        transaction_date = ""
        source = ""

        # Prefer CBS amount, then Switch, then NPCI
        if record.get('cbs'):
            amount = record['cbs'].get('amount', 0)
            transaction_date = record['cbs'].get('date', '')
            source = "CBS"
        elif record.get('switch'):
            amount = record['switch'].get('amount', 0)
            transaction_date = record['switch'].get('date', '')
            source = "Switch"
        elif record.get('npci'):
            amount = record['npci'].get('amount', 0)
            transaction_date = record['npci'].get('date', '')
            source = "NPCI"

        if amount <= 0:
            return None

        voucher_id = f"SETTLE_{self.voucher_counter:06d}"
        self.voucher_counter += 1

        # Create GL entries for settlement voucher
        gl_entries = []

        # Debit suspense account (unmatched transaction)
        gl_entries.append(GLEntry(
            account_code=self.gl_accounts["suspense_account"]["code"],
            account_name=self.gl_accounts["suspense_account"]["name"],
            debit_amount=amount,
            description=f"Unmatched transaction - RRN {rrn} ({source})",
            reference=f"RRN:{rrn}"
        ))

        # Credit settlement payable (amount to be settled)
        gl_entries.append(GLEntry(
            account_code=self.gl_accounts["settlement_payable"]["code"],
            account_name=self.gl_accounts["settlement_payable"]["name"],
            credit_amount=amount,
            description=f"Settlement payable - RRN {rrn}",
            reference=f"RRN:{rrn}"
        ))

        voucher = Voucher(
            voucher_id=voucher_id,
            voucher_type=VoucherType.SETTLEMENT,
            transaction_date=transaction_date,
            amount=amount,
            description=f"Settlement voucher for unmatched transaction RRN {rrn} ({source})",
            gl_entries=gl_entries
        )
        voucher.rrn = rrn

        return voucher

    def post_vouchers_to_gl(self, voucher_ids: Optional[List[str]] = None) -> Dict:
        """
        Post vouchers to General Ledger

        Args:
            voucher_ids: Specific voucher IDs to post (None for all)

        Returns:
            Dict with posting results
        """
        target_vouchers = []
        if voucher_ids:
            target_vouchers = [v for v in self.vouchers if v.voucher_id in voucher_ids]
        else:
            target_vouchers = [v for v in self.vouchers if v.status == VoucherStatus.GENERATED]

        posted_count = 0
        failed_count = 0

        for voucher in target_vouchers:
            try:
                # Validate GL entries balance
                total_debit = sum(entry.debit_amount for entry in voucher.gl_entries)
                total_credit = sum(entry.credit_amount for entry in voucher.gl_entries)

                if abs(total_debit - total_credit) > 0.01:  # Allow small rounding differences
                    raise ValueError(f"Voucher {voucher.voucher_id} is not balanced: Debit ₹{total_debit}, Credit ₹{total_credit}")

                # Mark as posted
                voucher.status = VoucherStatus.POSTED
                voucher.posted_at = datetime.now().isoformat()
                posted_count += 1

                logger.info(f"Posted voucher {voucher.voucher_id} to GL")

            except Exception as e:
                voucher.status = VoucherStatus.FAILED
                failed_count += 1
                logger.error(f"Failed to post voucher {voucher.voucher_id}: {str(e)}")

        return {
            "status": "completed",
            "posted_count": posted_count,
            "failed_count": failed_count,
            "total_attempted": len(target_vouchers)
        }

    def get_voucher_summary(self, run_id: Optional[str] = None) -> Dict:
        """Get voucher summary statistics"""
        if run_id:
            # Load from file
            settlement_file = os.path.join(self.settlement_dir, f"settlement_{run_id}.json")
            if os.path.exists(settlement_file):
                with open(settlement_file, 'r') as f:
                    data = json.load(f)
                return data.get("summary", {})

        # Calculate from current vouchers
        total_vouchers = len(self.vouchers)
        posted_vouchers = len([v for v in self.vouchers if v.status == VoucherStatus.POSTED])
        total_amount = sum(v.amount for v in self.vouchers)

        return {
            "total_vouchers": total_vouchers,
            "posted_vouchers": posted_vouchers,
            "total_amount": total_amount,
            "pending_posting": total_vouchers - posted_vouchers
        }

    def get_gl_entries_for_voucher(self, voucher_id: str) -> List[Dict]:
        """Get GL entries for a specific voucher"""
        for voucher in self.vouchers:
            if voucher.voucher_id == voucher_id:
                return [entry.to_dict() for entry in voucher.gl_entries]
        return []

    def generate_ttum_files(self, recon_results: Dict, run_folder: str) -> Dict:
        """Generate NPCI-compliant outputs with Annexure IV prioritized.

        - Prioritize Annexure IV (strict 9-column schema) and generate it first.
        - Also generate internal TTUM CSVs (InstructionType format) for backward compatibility.
        - Extract Payer_PSP and Payee_PSP from NPCI raw files instead of placeholders.
        - Ensure flags limited to {DRC, RRC, Cr Adj, TCC, RET}.
        """
        import csv
        import json as _json
        ttum_dir = os.path.join(run_folder, 'ttum')
        os.makedirs(ttum_dir, exist_ok=True)

        # attempt to infer run_id and cycle_id from the provided run_folder path
        run_id = None
        cycle_id = None
        try:
            parts = os.path.normpath(run_folder).split(os.path.sep)
            for p in parts[::-1]:
                if p.startswith('RUN_'):
                    run_id = p
                    break
            for p in parts:
                if p.startswith('cycle_'):
                    cycle_id = p.split('cycle_', 1)[1]
                    break
        except Exception:
            run_id = None
            cycle_id = None

        # Build NPCI metadata map (RRN -> payer/payee PSP)
        npci_meta = self._build_npci_rrn_map(run_folder)

        # Mandatory Annexure flags (exactly 5 as per NPCI spec)
        ANNEX_FLAGS = {'DRC', 'RRC', 'Cr Adj', 'TCC', 'RET'}
        # Updated flag mapping based on reconciliation status
        flag_map = {
            'MATCHED': None,  # No flag for matched transactions
            'PARTIAL_MATCH': 'RRC',  # Manual reconciliation needed
            'ORPHAN': 'DRC',  # Debit reversal
            'MISMATCH': 'RRC',  # Manual review
            'EXCEPTION': 'RET',  # Return/exception
            'TCC_102': 'TCC',  # Technical credit
            'TCC_103': 'TCC',  # Technical credit
            'RB_SUCCESS': 'TCC'  # Deemed success
        }

        # Helper to pick a representative source record
        def pick_source(rec):
            for s in ['cbs', 'switch', 'npci']:
                if rec.get(s):
                    return rec[s]
            return {}

        # Derive Annexure flag based on reconciliation status and transaction characteristics
        def derive_flag(rec: Dict, src: Dict) -> Optional[str]:
            status = rec.get('status')
            rc = (src.get('rc') or '').strip().upper()
            drcr = (src.get('dr_cr') or '').strip().upper()

            # Priority 1: TCC for RB responses (Deemed Success)
            if rc.startswith('RB'):
                return 'TCC'

            # Priority 2: TCC for technical credits
            if rec.get('tcc') in ['TCC_102', 'TCC_103']:
                return 'TCC'

            # Priority 3: RET for exceptions and returns
            if status == 'EXCEPTION' or rec.get('needs_ttum'):
                return 'RET'

            # Priority 4: Status-based flags for unmatched transactions
            if status == 'PARTIAL_MATCH':
                return 'RRC'  # Manual reconciliation needed
            elif status == 'ORPHAN':
                return 'DRC'  # Debit reversal
            elif status == 'MISMATCH':
                return 'RRC'  # Manual review required

            # Priority 5: Dr/Cr based adjustments for other cases
            if status in ['UNMATCHED', 'HANGING']:
                if drcr.startswith('C'):
                    return 'Cr Adj'  # Credit adjustment
                elif drcr.startswith('D'):
                    return 'DRC'  # Debit reversal

            # No flag for matched transactions
            if status == 'MATCHED':
                return None

            # Default fallback for undefined cases
            return 'RRC'

        # First generate Annexure-IV records (priority)
        annexure_records: List[Dict] = []
        for rrn, rec in recon_results.items():
            if not isinstance(rec, dict):
                continue
            src = pick_source(rec)
            if not src:
                continue
            amount = src.get('amount', '')
            tran_date = src.get('date', '')
            rc = src.get('rc', '')
            rrn_str = str(src.get('RRN', rrn))
            narration = f"RRN {rrn_str}"

            # Normalize date to YYYY-MM-DD
            shtdat = ''
            try:
                if tran_date:
                    try:
                        shtdat = datetime.fromisoformat(str(tran_date)).strftime('%Y-%m-%d')
                    except Exception:
                        try:
                            shtdat = datetime.strptime(str(tran_date), '%Y-%m-%d').strftime('%Y-%m-%d')
                        except Exception:
                            shtdat = ''
            except Exception:
                shtdat = ''

            # derive flag limited to the required set
            flg = derive_flag(rec, src)
            if not flg or flg not in ANNEX_FLAGS:
                continue

            payer = npci_meta.get(rrn_str, {}).get('payer_psp', '')
            payee = npci_meta.get(rrn_str, {}).get('payee_psp', '')

            # Build Annexure record with strict field set; FileName semantic as ANNEXURE for this run
            annexure_records.append({
                'Bankadjref': f"BR_{flg}_{rrn_str}_{int(datetime.now().timestamp())}",
                'Flag': flg,
                'shtdat': shtdat or datetime.now().strftime('%Y-%m-%d'),
                'adjsmt': amount or '',
                'Shser': payer or rrn_str,   # use Payer_PSP when present
                'Shcrd': payee or f"NBIN{rrn_str}",  # use Payee_PSP when present
                'FileName': f"ANNEXURE_{run_id or 'CURRENT'}.csv",
                'reason': (rc or '')[:5],
                'specifyother': narration[:400]
            })

        created: Dict[str, str] = {}
        # Write Annexure-IV first (priority)
        try:
            if annexure_records:
                # Prefer standardized writer with run scoping
                if run_id:
                    annex_path = generate_annexure_iv_csv(annexure_records, run_id=run_id, cycle_id=cycle_id)
                else:
                    # fallback path
                    annex_path = os.path.join(ttum_dir, 'annexure_iv.csv')
                    generate_annexure_iv_csv(annexure_records, annex_path)
                created['ANNEXURE_IV'] = annex_path
        except Exception as e:
            logger.error(f"Failed to generate Annexure-IV CSV: {e}")

        # Backward-compatible internal TTUM CSVs (InstructionType format)
        categories = ['DRC', 'RRC', 'TCC', 'RET', 'RECOVERY', 'REFUND']
        for cat in categories:
            headers = [
                'InstructionType', 'InstructionRefNo', 'RRN', 'Amount', 'ValueDate', 'DrCr', 'RC', 'Tran_Type',
                'AccountNo', 'IFSC', 'Narration', 'TTUM_Code', 'GL_Debit_Account', 'GL_Credit_Account'
            ]
            rows_for_cat: List[Dict] = []

            for rrn, rec in recon_results.items():
                if not isinstance(rec, dict):
                    continue
                src = pick_source(rec)
                if not src:
                    continue
                status = rec.get('status')
                amount = src.get('amount', '')
                tran_date = src.get('date', '')
                drcr = src.get('dr_cr', '')
                rc = src.get('rc', '')
                ttype = src.get('tran_type', '')
                rrn_str = str(src.get('RRN', rrn))

                # Normalize value date to YYYYMMDD when possible
                value_date = ''
                try:
                    if tran_date:
                        try:
                            value_date = datetime.fromisoformat(str(tran_date)).strftime('%Y%m%d')
                        except Exception:
                            try:
                                value_date = datetime.strptime(str(tran_date), '%Y-%m-%d').strftime('%Y%m%d')
                            except Exception:
                                value_date = ''
                except Exception:
                    value_date = ''

                # Default GL mapping
                gl_debit = self.gl_accounts.get('suspense_account', {}).get('code', '')
                gl_credit = self.gl_accounts.get('settlement_payable', {}).get('code', '')

                # issuer overrides
                issuer_action = {}
                try:
                    if self.issuer_actions and rrn_str in self.issuer_actions:
                        issuer_action = self.issuer_actions.get(rrn_str, {}) or {}
                except Exception:
                    issuer_action = {}

                if cat == 'REFUND' and status in ['ORPHAN', 'PARTIAL_MATCH', 'MISMATCH']:
                    gl_debit = self.gl_accounts.get('settlement_payable', {}).get('code', '')
                    gl_credit = self.gl_accounts.get('bank_account', {}).get('code', '')
                    if issuer_action:
                        action = (issuer_action.get('action_point') or '').lower()
                        if 'refund' in action:
                            out_gl = issuer_action.get('outward_payable')
                            if out_gl and str(out_gl).strip():
                                gl_credit = str(out_gl).strip()

                if cat == 'RECOVERY' and status in ['ORPHAN', 'PARTIAL_MATCH', 'MISMATCH']:
                    gl_debit = self.gl_accounts.get('bank_account', {}).get('code', '')
                    gl_credit = self.gl_accounts.get('settlement_receivable', {}).get('code', '')
                    if issuer_action:
                        action = (issuer_action.get('action_point') or '').lower()
                        if 'recovery' in action:
                            out_gl = issuer_action.get('outward_payable')
                            if out_gl and str(out_gl).strip():
                                gl_credit = str(out_gl).strip()

                if cat == 'TCC' and (rec.get('tcc') == 'TCC_103' or str(rc).upper().startswith('RB')):
                    gl_debit = self.gl_accounts.get('suspense_account', {}).get('code', '')
                    gl_credit = self.gl_accounts.get('settlement_payable', {}).get('code', '')

                if cat in ['DRC', 'RRC']:
                    if str(drcr).upper().startswith('D'):
                        gl_debit = self.gl_accounts.get('settlement_payable', {}).get('code', '')
                        gl_credit = self.gl_accounts.get('suspense_account', {}).get('code', '')
                    else:
                        gl_debit = self.gl_accounts.get('suspense_account', {}).get('code', '')
                        gl_credit = self.gl_accounts.get('settlement_payable', {}).get('code', '')

                # Decide if record belongs to this TTUM category
                include = False
                if cat == 'TCC' and (rec.get('tcc') in ['TCC_102', 'TCC_103'] or str(rc).upper().startswith('RB')):
                    include = True
                elif cat in ['DRC', 'RRC'] and status in ['PARTIAL_MATCH', 'ORPHAN', 'MISMATCH']:
                    include = True
                elif cat in ['REFUND', 'RECOVERY'] and status in ['ORPHAN', 'PARTIAL_MATCH', 'MISMATCH'] and not (rec.get('tcc')):
                    include = True
                elif cat == 'RET' and (rec.get('needs_ttum') or status == 'EXCEPTION'):
                    include = True

                if not include:
                    continue

                payer = npci_meta.get(rrn_str, {}).get('payer_psp', '')
                payee = npci_meta.get(rrn_str, {}).get('payee_psp', '')
                # For internal file, put payer/payee PSPs into AccountNo/IFSC placeholders
                account_no = payee or payer or ''
                ifsc = payer or ''
                instr_type = cat
                instr_ref = f"TTUM_{cat}_{rrn_str}"
                narration = f"{cat} for {rrn_str}"

                row = [instr_type, instr_ref, rrn_str, amount, value_date, drcr, rc, ttype,
                       account_no, ifsc, narration, cat, gl_debit, gl_credit]
                rows_for_cat.append(dict(zip(headers, row)))

            # Write out this TTUM category
            if run_id:
                try:
                    outp = write_report(run_id, cycle_id, 'ttum', f"{cat.lower()}.csv", headers, rows_for_cat)
                    created[cat] = outp
                    # Also provide XLSX
                    write_ttum_xlsx(run_id, cycle_id, f"{cat.lower()}", headers, rows_for_cat)
                except Exception:
                    # Fallback: create cycle subdirectory if cycle_id provided
                    if cycle_id:
                        cycle_dir = os.path.join(ttum_dir, f"cycle_{cycle_id}")
                        os.makedirs(cycle_dir, exist_ok=True)
                        path = os.path.join(cycle_dir, f"{cat.lower()}.csv")
                        xlsx_path = os.path.join(cycle_dir, f"{cat.lower()}.xlsx")
                    else:
                        path = os.path.join(ttum_dir, f"{cat.lower()}.csv")
                        xlsx_path = os.path.join(ttum_dir, f"{cat.lower()}.xlsx")
                    with open(path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(headers)
                        for r in rows_for_cat:
                            writer.writerow([r.get(h, '') for h in headers])
                    created[cat] = path
                    # Also write XLSX in fallback
                    try:
                        import pandas as pd
                        df = pd.DataFrame(rows_for_cat)
                        df.to_excel(xlsx_path, index=False, engine='openpyxl')
                    except Exception:
                        pass
            else:
                # Fallback: create cycle subdirectory if cycle_id provided
                if cycle_id:
                    cycle_dir = os.path.join(ttum_dir, f"cycle_{cycle_id}")
                    os.makedirs(cycle_dir, exist_ok=True)
                    path = os.path.join(cycle_dir, f"{cat.lower()}.csv")
                else:
                    path = os.path.join(ttum_dir, f"{cat.lower()}.csv")
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for r in rows_for_cat:
                        writer.writerow([r.get(h, '') for h in headers])
                created[cat] = path

        # write index file of created artifacts
        try:
            idx = os.path.join(ttum_dir, 'index.json')
            with open(idx, 'w') as jf:
                _json.dump({'generated': datetime.now().isoformat(), 'files': list(created.values())}, jf, indent=2)
        except Exception:
            pass

        return created


# Helper function for API integration
def create_settlement_engine(output_dir: str) -> SettlementEngine:
    """Factory function to create settlement engine"""
    return SettlementEngine(output_dir)
