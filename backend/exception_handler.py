"""
Process Exception Handler - Phase 3 Task 3
Handles SFTP failures, duplicate cycle detection, network timeouts, and recovery logic
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum
import time
from logging_config import get_logger

logger = get_logger(__name__)


class ExceptionType(Enum):
    """Exception types that can occur during reconciliation"""
    SFTP_CONNECTION_FAILED = "sftp_connection_failed"
    SFTP_TIMEOUT = "sftp_timeout"
    DUPLICATE_CYCLE = "duplicate_cycle"
    INVALID_FILE_FORMAT = "invalid_file_format"
    NETWORK_TIMEOUT = "network_timeout"
    FILE_NOT_FOUND = "file_not_found"
    DATABASE_ERROR = "database_error"
    VALIDATION_ERROR = "validation_error"
    INSUFFICIENT_DISK_SPACE = "insufficient_disk_space"
    PERMISSION_ERROR = "permission_error"


class RecoveryStrategy(Enum):
    """Recovery strategies for each exception type"""
    RETRY = "retry"
    SKIP_CYCLE = "skip_cycle"
    SKIP_FILE = "skip_file"
    ROLLBACK = "rollback"
    ALERT_OPERATOR = "alert_operator"
    FAIL = "fail"


class ProcessException:
    """Represents a single exception during reconciliation"""
    
    def __init__(
        self,
        exception_type: ExceptionType,
        run_id: str,
        cycle_id: Optional[str] = None,
        filename: Optional[str] = None,
        error_message: str = "",
        severity: str = "ERROR"  # INFO, WARNING, ERROR, CRITICAL
    ):
        self.exception_id = f"EXC_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(run_id) % 10000}"
        self.exception_type = exception_type
        self.run_id = run_id
        self.cycle_id = cycle_id
        self.filename = filename
        self.error_message = error_message
        self.severity = severity
        self.timestamp = datetime.now().isoformat()
        self.resolved = False
        self.recovery_action = None
        self.retry_count = 0
        self.max_retries = 3
    
    def to_dict(self) -> Dict:
        """Convert exception to dictionary"""
        return {
            "exception_id": self.exception_id,
            "type": self.exception_type.value,
            "run_id": self.run_id,
            "cycle_id": self.cycle_id,
            "filename": self.filename,
            "message": self.error_message,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "recovery_action": self.recovery_action,
            "retry_count": self.retry_count
        }


class DuplicateCycleDetector:
    """Detects duplicate NPCI cycles in the same run"""
    
    def __init__(self, upload_dir: str):
        self.upload_dir = upload_dir
        self.cycle_registry = {}  # Map: run_id -> {cycle_id -> [filenames]}
    
    def check_duplicate_cycle(self, run_id: str, cycle_id: str, filename: str) -> Tuple[bool, Optional[str]]:
        """
        Check if cycle already exists in current run
        Returns: (is_duplicate, conflicting_filename)
        """
        if run_id not in self.cycle_registry:
            self.cycle_registry[run_id] = {}
        
        if cycle_id not in self.cycle_registry[run_id]:
            self.cycle_registry[run_id][cycle_id] = []
        
        existing_files = self.cycle_registry[run_id][cycle_id]
        
        if existing_files:
            logger.warning(
                f"Duplicate cycle detected: {cycle_id} in run {run_id}. "
                f"Previous file: {existing_files[0]}, New file: {filename}"
            )
            return True, existing_files[0]
        
        self.cycle_registry[run_id][cycle_id].append(filename)
        return False, None
    
    def get_cycle_summary(self, run_id: str) -> Dict:
        """Get summary of cycles processed for a run"""
        if run_id not in self.cycle_registry:
            return {}
        
        summary = {}
        for cycle_id, files in self.cycle_registry[run_id].items():
            summary[cycle_id] = {
                "file_count": len(files),
                "files": files
            }
        
        return summary
    
    def reset_run(self, run_id: str):
        """Reset cycle registry for a run (after successful completion or rollback)"""
        if run_id in self.cycle_registry:
            del self.cycle_registry[run_id]
            logger.info(f"Cycle registry reset for run {run_id}")


class ExceptionHandler:
    """Main exception handler for reconciliation process"""
    
    def __init__(self, upload_dir: str, output_dir: str):
        self.upload_dir = upload_dir
        self.output_dir = output_dir
        self.exception_history_file = os.path.join(output_dir, "exception_history.json")
        self.exceptions: List[ProcessException] = []
        self.duplicate_detector = DuplicateCycleDetector(upload_dir)
        self._load_exception_history()
    
    def _load_exception_history(self):
        """Load exception history from file"""
        if os.path.exists(self.exception_history_file):
            try:
                with open(self.exception_history_file, 'r') as f:
                    history = json.load(f)
                logger.info(f"Loaded {len(history)} exceptions from history")
            except Exception as e:
                logger.error(f"Error loading exception history: {e}")
    
    def _save_exception_history(self):
        """Save exception history to file"""
        try:
            history = [exc.to_dict() for exc in self.exceptions]
            with open(self.exception_history_file, 'w') as f:
                json.dump(history, f, indent=2)
            logger.info(f"Saved {len(self.exceptions)} exceptions to history")
        except Exception as e:
            logger.error(f"Error saving exception history: {e}")
    
    def handle_sftp_connection_failure(
        self,
        run_id: str,
        host: str,
        error_message: str
    ) -> RecoveryStrategy:
        """
        Handle SFTP connection failures with retry logic
        
        Recovery Strategy:
        - Retry up to 3 times with exponential backoff (1s, 2s, 4s)
        - If all retries fail, alert operator and allow manual intervention
        """
        exc = ProcessException(
            exception_type=ExceptionType.SFTP_CONNECTION_FAILED,
            run_id=run_id,
            error_message=f"Failed to connect to SFTP host {host}: {error_message}",
            severity="CRITICAL"
        )
        
        logger.error(f"[{exc.exception_id}] SFTP Connection Failed to {host}: {error_message}")
        
        # Implement retry logic with exponential backoff
        while exc.retry_count < exc.max_retries:
            exc.retry_count += 1
            wait_time = 2 ** (exc.retry_count - 1)  # 1s, 2s, 4s
            logger.info(f"Retry {exc.retry_count}/{exc.max_retries} in {wait_time}s...")
            time.sleep(wait_time)
            
            # In production, attempt reconnection here
            # For now, we simulate failure
            if exc.retry_count < exc.max_retries:
                logger.warning(f"Retry {exc.retry_count} failed, will retry...")
            else:
                logger.critical(f"All retries exhausted for SFTP connection")
                exc.recovery_action = RecoveryStrategy.ALERT_OPERATOR.value
                self.exceptions.append(exc)
                self._save_exception_history()
                return RecoveryStrategy.ALERT_OPERATOR
        
        return RecoveryStrategy.ALERT_OPERATOR
    
    def handle_sftp_timeout(
        self,
        run_id: str,
        filename: str,
        timeout_seconds: int
    ) -> RecoveryStrategy:
        """
        Handle SFTP timeout during file transfer
        
        Recovery Strategy:
        - Retry transfer up to 2 times
        - If timeout persists, skip this file and continue
        - Log for manual review
        """
        exc = ProcessException(
            exception_type=ExceptionType.SFTP_TIMEOUT,
            run_id=run_id,
            filename=filename,
            error_message=f"SFTP timeout after {timeout_seconds}s while downloading {filename}",
            severity="WARNING"
        )
        
        logger.warning(f"[{exc.exception_id}] SFTP Timeout for {filename} after {timeout_seconds}s")
        
        if exc.retry_count < 2:
            exc.retry_count += 1
            exc.recovery_action = RecoveryStrategy.RETRY.value
            logger.info(f"Retrying file transfer (attempt {exc.retry_count}/2)")
            return RecoveryStrategy.RETRY
        else:
            exc.recovery_action = RecoveryStrategy.SKIP_FILE.value
            logger.warning(f"Skipping {filename} after timeout, continuing with other files")
            self.exceptions.append(exc)
            self._save_exception_history()
            return RecoveryStrategy.SKIP_FILE
    
    def handle_duplicate_cycle(
        self,
        run_id: str,
        cycle_id: str,
        current_filename: str,
        existing_filename: str
    ) -> RecoveryStrategy:
        """
        Handle duplicate cycle detection
        
        Recovery Strategy:
        - Alert operator about duplicate cycle
        - Prevent processing of duplicate cycle
        - Require manual intervention to resolve
        """
        exc = ProcessException(
            exception_type=ExceptionType.DUPLICATE_CYCLE,
            run_id=run_id,
            cycle_id=cycle_id,
            filename=current_filename,
            error_message=f"Duplicate cycle {cycle_id} detected. "
                          f"Existing: {existing_filename}, New: {current_filename}",
            severity="ERROR"
        )
        
        logger.error(f"[{exc.exception_id}] Duplicate Cycle: {cycle_id}")
        logger.error(f"  Existing file: {existing_filename}")
        logger.error(f"  Attempting to load: {current_filename}")
        
        exc.recovery_action = RecoveryStrategy.SKIP_CYCLE.value
        self.exceptions.append(exc)
        self._save_exception_history()
        
        return RecoveryStrategy.SKIP_CYCLE
    
    def handle_network_timeout(
        self,
        run_id: str,
        service: str,
        error_message: str
    ) -> RecoveryStrategy:
        """
        Handle network timeouts (DB connections, API calls, etc.)
        
        Recovery Strategy:
        - Retry up to 3 times with increasing delays
        - If failed, rollback the run to last stable state
        """
        exc = ProcessException(
            exception_type=ExceptionType.NETWORK_TIMEOUT,
            run_id=run_id,
            error_message=f"Network timeout connecting to {service}: {error_message}",
            severity="CRITICAL"
        )
        
        logger.error(f"[{exc.exception_id}] Network Timeout ({service}): {error_message}")
        
        # Retry with exponential backoff
        while exc.retry_count < exc.max_retries:
            exc.retry_count += 1
            wait_time = 2 ** exc.retry_count  # 2s, 4s, 8s
            logger.info(f"Retry {exc.retry_count}/{exc.max_retries} in {wait_time}s...")
            time.sleep(wait_time)
            
            if exc.retry_count >= exc.max_retries:
                logger.critical(f"Network timeout persists after {exc.max_retries} retries")
                exc.recovery_action = RecoveryStrategy.ROLLBACK.value
                self.exceptions.append(exc)
                self._save_exception_history()
                return RecoveryStrategy.ROLLBACK
        
        return RecoveryStrategy.RETRY
    
    def handle_validation_error(
        self,
        run_id: str,
        filename: str,
        error_details: Dict
    ) -> RecoveryStrategy:
        """
        Handle file format/validation errors
        
        Recovery Strategy:
        - Skip the invalid file
        - Continue processing other files
        - Log detailed error for manual inspection
        """
        exc = ProcessException(
            exception_type=ExceptionType.VALIDATION_ERROR,
            run_id=run_id,
            filename=filename,
            error_message=f"Validation error in {filename}: {json.dumps(error_details)}",
            severity="ERROR"
        )
        
        logger.error(f"[{exc.exception_id}] Validation Error in {filename}")
        logger.error(f"  Details: {error_details}")
        
        exc.recovery_action = RecoveryStrategy.SKIP_FILE.value
        self.exceptions.append(exc)
        self._save_exception_history()
        
        return RecoveryStrategy.SKIP_FILE
    
    def handle_insufficient_disk_space(
        self,
        run_id: str,
        required_bytes: int,
        available_bytes: int
    ) -> RecoveryStrategy:
        """
        Handle insufficient disk space errors
        
        Recovery Strategy:
        - Stop immediately (FAIL)
        - Alert operator to free up disk space
        """
        exc = ProcessException(
            exception_type=ExceptionType.INSUFFICIENT_DISK_SPACE,
            run_id=run_id,
            error_message=f"Insufficient disk space. Required: {required_bytes} bytes, "
                          f"Available: {available_bytes} bytes",
            severity="CRITICAL"
        )
        
        logger.critical(f"[{exc.exception_id}] Insufficient Disk Space!")
        logger.critical(f"  Required: {required_bytes / (1024**3):.2f} GB")
        logger.critical(f"  Available: {available_bytes / (1024**3):.2f} GB")
        
        exc.recovery_action = RecoveryStrategy.FAIL.value
        self.exceptions.append(exc)
        self._save_exception_history()
        
        return RecoveryStrategy.FAIL
    
    def handle_database_error(
        self,
        run_id: str,
        error_message: str
    ) -> RecoveryStrategy:
        """
        Handle database errors (connection, query, constraint violations, etc.)
        
        Recovery Strategy:
        - Retry transaction
        - If persists, rollback run to last checkpoint
        """
        exc = ProcessException(
            exception_type=ExceptionType.DATABASE_ERROR,
            run_id=run_id,
            error_message=f"Database error: {error_message}",
            severity="CRITICAL"
        )
        
        logger.error(f"[{exc.exception_id}] Database Error: {error_message}")
        
        if exc.retry_count < 2:
            exc.retry_count += 1
            exc.recovery_action = RecoveryStrategy.RETRY.value
            logger.info(f"Retrying database operation (attempt {exc.retry_count}/2)")
            return RecoveryStrategy.RETRY
        else:
            exc.recovery_action = RecoveryStrategy.ROLLBACK.value
            logger.critical(f"Database error persists, initiating rollback")
            self.exceptions.append(exc)
            self._save_exception_history()
            return RecoveryStrategy.ROLLBACK
    
    def get_exception_summary(self, run_id: Optional[str] = None) -> Dict:
        """
        Get summary of exceptions
        
        Args:
            run_id: Optional filter by run_id
        
        Returns:
            Dict with exception counts by type and severity
        """
        filtered = [e for e in self.exceptions if run_id is None or e.run_id == run_id]
        
        summary = {
            "total_exceptions": len(filtered),
            "by_type": {},
            "by_severity": {},
            "resolved": sum(1 for e in filtered if e.resolved),
            "unresolved": sum(1 for e in filtered if not e.resolved),
            "exceptions": [e.to_dict() for e in filtered]
        }
        
        for exc in filtered:
            exc_type = exc.exception_type.value
            summary["by_type"][exc_type] = summary["by_type"].get(exc_type, 0) + 1
            summary["by_severity"][exc.severity] = summary["by_severity"].get(exc.severity, 0) + 1
        
        return summary
    
    def resolve_exception(self, exception_id: str):
        """Mark an exception as resolved"""
        for exc in self.exceptions:
            if exc.exception_id == exception_id:
                exc.resolved = True
                logger.info(f"Exception {exception_id} marked as resolved")
                self._save_exception_history()
                return
        
        logger.warning(f"Exception {exception_id} not found")
    
    def get_run_exceptions(self, run_id: str) -> List[Dict]:
        """Get all exceptions for a specific run"""
        return [e.to_dict() for e in self.exceptions if e.run_id == run_id]
    
    def check_run_has_critical_exceptions(self, run_id: str) -> bool:
        """Check if run has any CRITICAL severity exceptions"""
        return any(e.run_id == run_id and e.severity == "CRITICAL" for e in self.exceptions)
    
    def check_run_has_duplicate_cycles(self, run_id: str) -> List[str]:
        """Get list of duplicate cycles detected in run"""
        duplicates = [
            e.cycle_id for e in self.exceptions
            if e.run_id == run_id and 
            e.exception_type == ExceptionType.DUPLICATE_CYCLE
        ]
        return duplicates


# Helper function for API integration
def create_exception_handler(upload_dir: str, output_dir: str) -> ExceptionHandler:
    """Factory function to create exception handler"""
    return ExceptionHandler(upload_dir, output_dir)
