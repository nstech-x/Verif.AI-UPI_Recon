
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
from logging_config import get_logger

logger = get_logger(__name__)


class VarianceCategory(Enum):
    """Categories of variances in GL reconciliation"""
    TIMING_DIFFERENCE = "timing_difference"  # T+1, T+2, T+3 delays
    ROUNDING_DIFFERENCE = "rounding_difference"  # Due to currency conversion
    PENDING_CLEARANCES = "pending_clearances"  # Cheques, transfers in clearing
    REJECTED_TRANSACTIONS = "rejected_transactions"  # Failed reversals, rejections
    MANUAL_ADJUSTMENTS = "manual_adjustments"  # Manual GL entries
    SYSTEM_ADJUSTMENTS = "system_adjustments"  # Auto corrections
    UNKNOWN_VARIANCE = "unknown_variance"  # Unexplained differences


class GLAccount:
    """Represents a GL account with opening, closing, and reconciling balance"""
    
    def __init__(
        self,
        account_code: str,
        account_name: str,
        opening_balance: float,
        closing_balance: float,
        book_balance: float
    ):
        self.account_code = account_code
        self.account_name = account_name
        self.opening_balance = opening_balance
        self.closing_balance = closing_balance
        self.book_balance = book_balance  # Reconciliation book/ledger balance
        self.variance = closing_balance - book_balance
        self.variance_abs = abs(self.variance)
        self.reconciled = self.variance == 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "opening_balance": self.opening_balance,
            "closing_balance": self.closing_balance,
            "book_balance": self.book_balance,
            "variance": self.variance,
            "variance_abs": self.variance_abs,
            "reconciled": self.reconciled
        }


class VarianceBridge:
    """Represents a bridge item that explains part of the variance"""
    
    def __init__(
        self,
        bridge_id: str,
        category: VarianceCategory,
        description: str,
        amount: float,
        justification: str,
        aging_days: int,
        priority: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    ):
        self.bridge_id = bridge_id
        self.category = category
        self.description = description
        self.amount = amount
        self.justification = justification
        self.aging_days = aging_days
        self.priority = priority
        self.timestamp = datetime.now().isoformat()
        self.resolved = False
        self.resolved_by = None
        self.resolution_date = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "bridge_id": self.bridge_id,
            "category": self.category.value,
            "description": self.description,
            "amount": self.amount,
            "justification": self.justification,
            "aging_days": self.aging_days,
            "priority": self.priority,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "resolved_by": self.resolved_by,
            "resolution_date": self.resolution_date
        }


class GLProofingReport:
    """GL proofing report with bridging schedule and reconciliation details"""
    
    def __init__(
        self,
        run_id: str,
        report_date: str,
        gl_accounts: List[GLAccount],
        variance_bridges: List[VarianceBridge]
    ):
        self.report_id = f"GL_PROOF_{run_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.run_id = run_id
        self.report_date = report_date
        self.gl_accounts = gl_accounts
        self.variance_bridges = variance_bridges
        self.timestamp = datetime.now().isoformat()
        
        # Calculate metrics
        self.total_accounts = len(gl_accounts)
        self.reconciled_accounts = sum(1 for acc in gl_accounts if acc.reconciled)
        self.unreconciled_accounts = self.total_accounts - self.reconciled_accounts
        self.total_variance = sum(acc.variance for acc in gl_accounts)
        self.total_variance_abs = sum(acc.variance_abs for acc in gl_accounts)
        self.total_bridged = sum(bridge.amount for bridge in variance_bridges)
        self.bridging_coverage = (
            (self.total_bridged / self.total_variance_abs * 100) 
            if self.total_variance_abs > 0 else 100
        )
        self.remaining_variance = self.total_variance_abs - self.total_bridged
        self.fully_reconciled = self.total_variance == 0
        
        # Categorize bridges
        self.bridges_by_category = self._categorize_bridges()
    
    def _categorize_bridges(self) -> Dict[str, List[VarianceBridge]]:
        """Categorize bridges by variance type"""
        categorized = {}
        for bridge in self.variance_bridges:
            category = bridge.category.value
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(bridge)
        return categorized
    
    def to_dict(self) -> Dict:
        """Convert report to dictionary"""
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "report_date": self.report_date,
            "timestamp": self.timestamp,
            "summary": {
                "total_accounts": self.total_accounts,
                "reconciled_accounts": self.reconciled_accounts,
                "unreconciled_accounts": self.unreconciled_accounts,
                "total_variance": self.total_variance,
                "total_variance_abs": self.total_variance_abs,
                "total_bridged": self.total_bridged,
                "bridging_coverage_percent": round(self.bridging_coverage, 2),
                "remaining_variance": self.remaining_variance,
                "fully_reconciled": self.fully_reconciled
            },
            "gl_accounts": [acc.to_dict() for acc in self.gl_accounts],
            "variance_bridges": [bridge.to_dict() for bridge in self.variance_bridges],
            "bridges_by_category": {
                category: [b.to_dict() for b in bridges]
                for category, bridges in self.bridges_by_category.items()
            }
        }


class GLJustificationEngine:
    """Engine for GL reconciliation, variance bridging, and proofing"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.gl_proofing_dir = os.path.join(output_dir, "gl_proofing")
        os.makedirs(self.gl_proofing_dir, exist_ok=True)
        
        self.proofing_reports: List[GLProofingReport] = []
        self.variance_threshold = 1000  # Default threshold for variance alerts
        self.aging_thresholds = {
            "0_1": {"days": 1, "priority": "LOW"},
            "1_3": {"days": 3, "priority": "MEDIUM"},
            "3_7": {"days": 7, "priority": "HIGH"},
            "7_plus": {"days": 999, "priority": "CRITICAL"}
        }
    
    def create_proofing_report(
        self,
        run_id: str,
        report_date: str,
        gl_accounts_data: List[Dict],
        variance_bridges_data: List[Dict]
    ) -> GLProofingReport:
        """
        Create a GL proofing report
        
        Args:
            run_id: Reconciliation run ID
            report_date: Report date (YYYY-MM-DD)
            gl_accounts_data: List of GL account data with opening, closing, book balances
            variance_bridges_data: List of variance bridge explanations
        
        Returns:
            GLProofingReport with full reconciliation details
        """
        # Create GL account objects
        gl_accounts = [
            GLAccount(
                account_code=acc["code"],
                account_name=acc["name"],
                opening_balance=acc.get("opening_balance", 0),
                closing_balance=acc.get("closing_balance", 0),
                book_balance=acc.get("book_balance", 0)
            )
            for acc in gl_accounts_data
        ]
        
        # Create variance bridge objects
        variance_bridges = []
        for i, bridge_data in enumerate(variance_bridges_data):
            aging_days = self._calculate_aging_days(
                bridge_data.get("transaction_date"),
                report_date
            )
            
            # Determine priority based on aging and amount
            priority = self._determine_priority(
                bridge_data.get("amount", 0),
                aging_days
            )
            
            bridge = VarianceBridge(
                bridge_id=f"BR_{run_id}_{i:03d}",
                category=VarianceCategory[bridge_data.get("category", "UNKNOWN_VARIANCE")],
                description=bridge_data.get("description", ""),
                amount=bridge_data.get("amount", 0),
                justification=bridge_data.get("justification", "Pending investigation"),
                aging_days=aging_days,
                priority=priority
            )
            variance_bridges.append(bridge)
        
        # Create proofing report
        report = GLProofingReport(
            run_id=run_id,
            report_date=report_date,
            gl_accounts=gl_accounts,
            variance_bridges=variance_bridges
        )
        
        self.proofing_reports.append(report)
        self._save_proofing_report(report)
        
        logger.info(f"GL Proofing Report created: {report.report_id}")
        logger.info(f"  Total Variance: ₹{report.total_variance_abs:,.2f}")
        logger.info(f"  Bridged: ₹{report.total_bridged:,.2f} ({report.bridging_coverage:.1f}%)")
        logger.info(f"  Remaining: ₹{report.remaining_variance:,.2f}")
        
        return report
    
    def _calculate_aging_days(self, transaction_date: str, report_date: str) -> int:
        """Calculate days aged from transaction date to report date"""
        try:
            txn_date = datetime.strptime(transaction_date, "%Y-%m-%d").date()
            rep_date = datetime.strptime(report_date, "%Y-%m-%d").date()
            return (rep_date - txn_date).days
        except (ValueError, TypeError):
            return 0
    
    def _determine_priority(self, amount: float, aging_days: int) -> str:
        """
        Determine priority level based on amount and aging
        
        Rules:
        - CRITICAL: Amount > 10x threshold OR aging > 7 days
        - HIGH: Amount > 5x threshold OR aging 3-7 days
        - MEDIUM: Amount > 2x threshold OR aging 1-3 days
        - LOW: Otherwise
        """
        amount_abs = abs(amount)
        
        if amount_abs > self.variance_threshold * 10 or aging_days > 7:
            return "CRITICAL"
        elif amount_abs > self.variance_threshold * 5 or aging_days >= 3:
            return "HIGH"
        elif amount_abs > self.variance_threshold * 2 or aging_days >= 1:
            return "MEDIUM"
        else:
            return "LOW"
    
    def add_variance_bridge(
        self,
        run_id: str,
        category: str,
        description: str,
        amount: float,
        justification: str,
        transaction_date: Optional[str] = None,
        report_date: str = None
    ) -> VarianceBridge:
        """Add a variance bridge to explain part of the variance"""
        
        report_date = report_date or datetime.now().strftime("%Y-%m-%d")
        aging_days = self._calculate_aging_days(
            transaction_date or report_date,
            report_date
        )
        
        priority = self._determine_priority(amount, aging_days)
        
        bridge = VarianceBridge(
            bridge_id=f"BR_{run_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            category=VarianceCategory[category],
            description=description,
            amount=amount,
            justification=justification,
            aging_days=aging_days,
            priority=priority
        )
        
        logger.info(f"Variance bridge added: {bridge.bridge_id} - {description} (₹{amount:,.2f})")
        
        return bridge
    
    def resolve_variance_bridge(self, bridge_id: str, resolved_by: str = "System"):
        """Mark a variance bridge as resolved"""
        for report in self.proofing_reports:
            for bridge in report.variance_bridges:
                if bridge.bridge_id == bridge_id:
                    bridge.resolved = True
                    bridge.resolved_by = resolved_by
                    bridge.resolution_date = datetime.now().isoformat()
                    logger.info(f"Variance bridge resolved: {bridge_id}")
                    return
        
        logger.warning(f"Variance bridge not found: {bridge_id}")
    
    def get_unreconciled_accounts(self, run_id: str) -> List[GLAccount]:
        """Get list of unreconciled GL accounts for a specific run"""
        for report in self.proofing_reports:
            if report.run_id == run_id:
                return [acc for acc in report.gl_accounts if not acc.reconciled]
        return []
    
    def get_high_priority_bridges(self, run_id: str) -> List[VarianceBridge]:
        """Get high and critical priority variance bridges"""
        for report in self.proofing_reports:
            if report.run_id == run_id:
                return [
                    bridge for bridge in report.variance_bridges
                    if bridge.priority in ["HIGH", "CRITICAL"]
                ]
        return []
    
    def get_aging_summary(self, run_id: str) -> Dict:
        """Get variance bridge aging summary"""
        for report in self.proofing_reports:
            if report.run_id == run_id:
                aging_summary = {
                    "0_1_days": [],
                    "1_3_days": [],
                    "3_7_days": [],
                    "7_plus_days": []
                }
                
                for bridge in report.variance_bridges:
                    if bridge.aging_days <= 1:
                        aging_summary["0_1_days"].append(bridge.to_dict())
                    elif bridge.aging_days <= 3:
                        aging_summary["1_3_days"].append(bridge.to_dict())
                    elif bridge.aging_days <= 7:
                        aging_summary["3_7_days"].append(bridge.to_dict())
                    else:
                        aging_summary["7_plus_days"].append(bridge.to_dict())
                
                return aging_summary
        return {}
    
    def _save_proofing_report(self, report: GLProofingReport):
        """Save proofing report to file"""
        try:
            filepath = os.path.join(
                self.gl_proofing_dir,
                f"{report.report_id}.json"
            )
            with open(filepath, 'w') as f:
                json.dump(report.to_dict(), f, indent=2)
            logger.info(f"GL Proofing Report saved: {filepath}")
        except Exception as e:
            logger.error(f"Error saving proofing report: {e}")
    
    def get_report(self, report_id: str) -> Optional[Dict]:
        """Get a specific proofing report"""
        for report in self.proofing_reports:
            if report.report_id == report_id:
                return report.to_dict()
        
        # Try to load from file
        try:
            filepath = os.path.join(self.gl_proofing_dir, f"{report_id}.json")
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading report: {e}")
        
        return None
    
    def get_all_reports(self) -> List[Dict]:
        """Get all proofing reports"""
        return [report.to_dict() for report in self.proofing_reports]


# Helper function for API integration
def create_gl_engine(output_dir: str) -> GLJustificationEngine:
    """Factory function to create GL justification engine"""
    return GLJustificationEngine(output_dir)
