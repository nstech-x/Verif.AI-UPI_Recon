"""
Audit Trail & Logging - Phase 3 Task 5 (Final)
Comprehensive logging of all operations with user tracking, timestamps, and compliance
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid
from logging_config import get_logger

logger = get_logger(__name__)


class AuditAction(Enum):
    """Types of auditable actions in the system"""
    # Upload operations
    FILE_UPLOADED = "file_uploaded"
    FILE_VALIDATED = "file_validated"
    FILE_REJECTED = "file_rejected"
    
    # Reconciliation operations
    RECON_STARTED = "recon_started"
    RECON_COMPLETED = "recon_completed"
    RECON_FAILED = "recon_failed"
    CYCLE_PROCESSED = "cycle_processed"
    TRANSACTION_MATCHED = "transaction_matched"
    TRANSACTION_UNMATCHED = "transaction_unmatched"
    
    # Rollback operations
    ROLLBACK_INITIATED = "rollback_initiated"
    ROLLBACK_COMPLETED = "rollback_completed"
    ROLLBACK_FAILED = "rollback_failed"
    
    # Force match operations
    FORCE_MATCH_INITIATED = "force_match_initiated"
    FORCE_MATCH_COMPLETED = "force_match_completed"
    
    # Exception handling
    EXCEPTION_LOGGED = "exception_logged"
    EXCEPTION_RESOLVED = "exception_resolved"
    
    # GL operations
    GL_PROOFING_CREATED = "gl_proofing_created"
    VARIANCE_BRIDGE_ADDED = "variance_bridge_added"
    VARIANCE_BRIDGE_RESOLVED = "variance_bridge_resolved"
    
    # User operations
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_ACTION = "user_action"
    
    # System operations
    CONFIG_CHANGED = "config_changed"
    SYSTEM_ERROR = "system_error"
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"


class AuditLevel(Enum):
    """Audit logging levels for compliance"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditEntry:
    """Represents a single audit log entry"""
    
    def __init__(
        self,
        action: AuditAction,
        run_id: str,
        user_id: Optional[str] = None,
        level: AuditLevel = AuditLevel.INFO,
        details: Optional[Dict[str, Any]] = None,
        source_system: str = "API"
    ):
        self.audit_id = f"AUD_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"
        self.action = action
        self.run_id = run_id
        self.user_id = user_id or "SYSTEM"
        self.level = level
        self.timestamp = datetime.now().isoformat()
        self.details = details or {}
        self.source_system = source_system
        self.ip_address = None
        self.session_id = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary"""
        return {
            "audit_id": self.audit_id,
            "action": self.action.value,
            "run_id": self.run_id,
            "user_id": self.user_id,
            "level": self.level.value,
            "timestamp": self.timestamp,
            "details": self.details,
            "source_system": self.source_system,
            "ip_address": self.ip_address,
            "session_id": self.session_id
        }


class AuditTrail:
    """Comprehensive audit trail manager for compliance and tracking"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.audit_log_dir = os.path.join(output_dir, "audit_logs")
        os.makedirs(self.audit_log_dir, exist_ok=True)
        
        self.entries: List[AuditEntry] = []
        self.max_entries_per_file = 10000  # Rotate audit logs at 10k entries
        self._load_audit_logs()
    
    def _load_audit_logs(self):
        """Load existing audit logs from files"""
        try:
            if os.path.exists(self.audit_log_dir):
                for filename in os.listdir(self.audit_log_dir):
                    if filename.endswith(".json"):
                        filepath = os.path.join(self.audit_log_dir, filename)
                        try:
                            with open(filepath, 'r') as f:
                                data = json.load(f)
                                if isinstance(data, list):
                                    logger.info(f"Loaded {len(data)} audit entries from {filename}")
                        except Exception as e:
                            logger.error(f"Error loading audit log {filename}: {e}")
        except Exception as e:
            logger.error(f"Error initializing audit logs: {e}")
    
    def log_action(
        self,
        action: AuditAction,
        run_id: str,
        user_id: Optional[str] = None,
        level: AuditLevel = AuditLevel.INFO,
        details: Optional[Dict[str, Any]] = None,
        source_system: str = "API"
    ) -> AuditEntry:
        """
        Log an action to the audit trail
        
        Args:
            action: Type of action being audited
            run_id: Associated run/reconciliation ID
            user_id: User performing the action
            level: Severity/logging level
            details: Additional context/details
            source_system: System initiating the action
        
        Returns:
            AuditEntry that was logged
        """
        entry = AuditEntry(
            action=action,
            run_id=run_id,
            user_id=user_id,
            level=level,
            details=details,
            source_system=source_system
        )
        
        self.entries.append(entry)
        self._save_entry(entry)
        
        # Log to application logger as well
        log_method = getattr(logger, level.value.lower(), logger.info)
        log_method(f"[{entry.audit_id}] {action.value} - Run: {run_id}, User: {entry.user_id}")
        
        return entry
    
    def _save_entry(self, entry: AuditEntry):
        """Save an audit entry to file"""
        try:
            # Ensure audit log directory exists
            os.makedirs(self.audit_log_dir, exist_ok=True)
            
            # Determine which file to save to (based on date)
            date_str = datetime.now().strftime("%Y%m%d")
            filepath = os.path.join(self.audit_log_dir, f"audit_trail_{date_str}.json")
            
            # Load existing entries
            entries_data = []
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r') as f:
                        entries_data = json.load(f)
                except json.JSONDecodeError:
                    entries_data = []
            
            # Add new entry
            entries_data.append(entry.to_dict())
            
            # Rotate if too large
            if len(entries_data) > self.max_entries_per_file:
                self._rotate_audit_log(filepath, entries_data)
                entries_data = [entry.to_dict()]  # Start fresh
            
            # Save
            with open(filepath, 'w') as f:
                json.dump(entries_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving audit entry: {e}")
    
    def _rotate_audit_log(self, filepath: str, entries: List[Dict]):
        """Rotate audit log when it exceeds max entries"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_path = filepath.replace(".json", f"_{timestamp}_rotated.json")
            
            with open(rotated_path, 'w') as f:
                json.dump(entries, f, indent=2)
            
            logger.info(f"Rotated audit log to {rotated_path}")
        except Exception as e:
            logger.error(f"Error rotating audit log: {e}")
    
    def get_run_audit_trail(self, run_id: str) -> List[Dict]:
        """Get all audit entries for a specific run"""
        return [
            entry.to_dict()
            for entry in self.entries
            if entry.run_id == run_id
        ]
    
    def get_user_actions(self, user_id: str, limit: int = 100) -> List[Dict]:
        """Get all actions performed by a specific user"""
        entries = [
            entry.to_dict()
            for entry in self.entries
            if entry.user_id == user_id
        ]
        return entries[-limit:]  # Return last N entries
    
    def get_action_count(self, action: AuditAction) -> int:
        """Get count of a specific action type"""
        return sum(1 for entry in self.entries if entry.action == action)
    
    def get_actions_by_date(self, start_date: str, end_date: str) -> List[Dict]:
        """
        Get audit entries within a date range
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            List of audit entries within the date range
        """
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            
            filtered = [
                entry.to_dict()
                for entry in self.entries
                if start <= datetime.fromisoformat(entry.timestamp) <= end
            ]
            return filtered
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return []
    
    def log_file_upload(
        self,
        run_id: str,
        filename: str,
        file_size: int,
        user_id: Optional[str] = None,
        status: str = "success"
    ):
        """Log file upload operation"""
        return self.log_action(
            action=AuditAction.FILE_UPLOADED,
            run_id=run_id,
            user_id=user_id,
            details={
                "filename": filename,
                "file_size": file_size,
                "status": status
            }
        )
    
    def log_reconciliation_event(
        self,
        run_id: str,
        event: str,  # started, completed, failed
        user_id: Optional[str] = None,
        matched_count: int = 0,
        unmatched_count: int = 0,
        error: Optional[str] = None
    ):
        """Log reconciliation lifecycle events"""
        action_map = {
            "started": AuditAction.RECON_STARTED,
            "completed": AuditAction.RECON_COMPLETED,
            "failed": AuditAction.RECON_FAILED
        }
        
        level_map = {
            "started": AuditLevel.INFO,
            "completed": AuditLevel.INFO,
            "failed": AuditLevel.ERROR
        }
        
        return self.log_action(
            action=action_map.get(event, AuditAction.RECON_STARTED),
            run_id=run_id,
            user_id=user_id,
            level=level_map.get(event, AuditLevel.INFO),
            details={
                "event": event,
                "matched_count": matched_count,
                "unmatched_count": unmatched_count,
                "error": error
            }
        )
    
    def log_rollback_operation(
        self,
        run_id: str,
        rollback_level: str,
        user_id: Optional[str] = None,
        status: str = "completed",
        details: Optional[Dict] = None
    ):
        """Log rollback operation"""
        action_map = {
            "completed": AuditAction.ROLLBACK_COMPLETED,
            "failed": AuditAction.ROLLBACK_FAILED
        }
        
        return self.log_action(
            action=action_map.get(status, AuditAction.ROLLBACK_INITIATED),
            run_id=run_id,
            user_id=user_id,
            details={
                "rollback_level": rollback_level,
                "status": status,
                **(details or {})
            }
        )
    
    def log_force_match(
        self,
        run_id: str,
        rrn: str,
        source1: str,
        source2: str,
        user_id: Optional[str] = None,
        status: str = "completed"
    ):
        """Log force match operation"""
        action_map = {
            "completed": AuditAction.FORCE_MATCH_COMPLETED
        }
        
        return self.log_action(
            action=action_map.get(status, AuditAction.FORCE_MATCH_INITIATED),
            run_id=run_id,
            user_id=user_id,
            details={
                "rrn": rrn,
                "source1": source1,
                "source2": source2,
                "status": status
            }
        )
    
    def log_gl_operation(
        self,
        run_id: str,
        operation: str,  # proofing_created, variance_bridge_added, variance_bridge_resolved
        user_id: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        """Log GL operations"""
        action_map = {
            "proofing_created": AuditAction.GL_PROOFING_CREATED,
            "variance_bridge_added": AuditAction.VARIANCE_BRIDGE_ADDED,
            "variance_bridge_resolved": AuditAction.VARIANCE_BRIDGE_RESOLVED
        }
        
        return self.log_action(
            action=action_map.get(operation, AuditAction.USER_ACTION),
            run_id=run_id,
            user_id=user_id,
            details={
                "operation": operation,
                **(details or {})
            }
        )
    
    def log_exception(
        self,
        run_id: str,
        exception_type: str,
        error_message: str,
        user_id: Optional[str] = None
    ):
        """Log exception events"""
        return self.log_action(
            action=AuditAction.EXCEPTION_LOGGED,
            run_id=run_id,
            user_id=user_id,
            level=AuditLevel.ERROR,
            details={
                "exception_type": exception_type,
                "error_message": error_message
            }
        )
    
    def log_data_export(
        self,
        run_id: str,
        export_format: str,
        record_count: int,
        user_id: Optional[str] = None
    ):
        """Log data export operations"""
        return self.log_action(
            action=AuditAction.DATA_EXPORTED,
            run_id=run_id,
            user_id=user_id,
            details={
                "export_format": export_format,
                "record_count": record_count
            }
        )
    
    def get_audit_summary(self, run_id: Optional[str] = None) -> Dict:
        """Get summary of audit trail"""
        filtered = self.entries if not run_id else [e for e in self.entries if e.run_id == run_id]
        
        summary = {
            "total_entries": len(filtered),
            "by_action": {},
            "by_level": {},
            "by_user": {},
            "date_range": None
        }
        
        if filtered:
            timestamps = [datetime.fromisoformat(e.timestamp) for e in filtered]
            summary["date_range"] = {
                "earliest": min(timestamps).isoformat(),
                "latest": max(timestamps).isoformat()
            }
            
            for entry in filtered:
                action = entry.action.value
                summary["by_action"][action] = summary["by_action"].get(action, 0) + 1
                summary["by_level"][entry.level.value] = summary["by_level"].get(entry.level.value, 0) + 1
                summary["by_user"][entry.user_id] = summary["by_user"].get(entry.user_id, 0) + 1
        
        return summary
    
    def generate_compliance_report(
        self,
        run_id: str,
        report_type: str = "full"  # full, critical, high_privilege
    ) -> Dict:
        """
        Generate compliance report for auditing
        
        Includes:
        - All actions performed on a run
        - User accountability
        - Timestamps for all operations
        - Data change tracking
        """
        entries = self.get_run_audit_trail(run_id)
        
        report = {
            "report_id": f"COMP_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "run_id": run_id,
            "report_date": datetime.now().isoformat(),
            "report_type": report_type,
            "total_entries": len(entries),
            "entries": entries if report_type == "full" else [
                e for e in entries
                if e["level"] in ["ERROR", "CRITICAL"] or e["action"] in [
                    "rollback_initiated",
                    "data_deleted",
                    "force_match_initiated",
                    "config_changed"
                ]
            ]
        }
        
        return report


# Helper function for API integration
def create_audit_trail(output_dir: str) -> AuditTrail:
    """Factory function to create audit trail manager"""
    return AuditTrail(output_dir)
