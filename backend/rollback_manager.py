"""
Rollback Manager - Handles granular rollback operations at multiple levels
Supports: Full, Ingestion, Mid-Recon, Cycle-Wise, and Accounting Rollback
"""

import os
import json
import shutil
try:
    import portalocker
except Exception:
    # Fallback dummy portalocker for test environments without the package
    class _DummyPortalocker:
        LOCK_EX = 0
        LOCK_NB = 0
        class LockException(Exception):
            pass

        @staticmethod
        def lock(fd, flags):
            return True

    portalocker = _DummyPortalocker()
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
from logging_config import get_logger

logger = get_logger(__name__)


class RollbackLevel(Enum):
    """Rollback operation levels"""
    WHOLE_PROCESS = "whole_process"  # Complete process rollback
    INGESTION = "ingestion"          # File ingestion rollback
    MID_RECON = "mid_recon"          # Mid-reconciliation rollback
    CYCLE_WISE = "cycle_wise"        # Specific NPCI cycle
    ACCOUNTING = "accounting"        # Accounting/voucher rollback


class RollbackStatus(Enum):
    """Status of rollback operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class RollbackManager:
    """Manages granular rollback operations"""
    
    def __init__(self, upload_dir: str = "./data/uploads", output_dir: str = "./data/output"):
        self.upload_dir = upload_dir
        self.output_dir = output_dir
        self.rollback_history_file = os.path.join(output_dir, "rollback_history.json")
        self._ensure_history_file()
    
    def _ensure_history_file(self):
        """Ensure rollback history file exists"""
        os.makedirs(os.path.dirname(self.rollback_history_file), exist_ok=True)
        if not os.path.exists(self.rollback_history_file):
            with open(self.rollback_history_file, 'w') as f:
                json.dump([], f)
    
    def _log_rollback(self, rollback_level: RollbackLevel, run_id: str, details: Dict) -> str:
        """Log rollback operation with timestamp and details"""
        with open(self.rollback_history_file, 'r') as f:
            history = json.load(f)

        # Generate a more user-friendly rollback ID
        # Format: RB_{LEVEL}_{SEQUENTIAL_NUMBER}_{SHORT_DATE}
        level_short = {
            RollbackLevel.WHOLE_PROCESS: "FULL",
            RollbackLevel.INGESTION: "ING",
            RollbackLevel.MID_RECON: "MID",
            RollbackLevel.CYCLE_WISE: "CYC",
            RollbackLevel.ACCOUNTING: "ACC"
        }.get(rollback_level, "UNK")

        # Get next sequential number for this level
        existing_ids = [r.get("rollback_id", "") for r in history if r.get("level") == rollback_level.value]
        sequential_num = len(existing_ids) + 1

        # Short date format (MMDD)
        short_date = datetime.now().strftime('%m%d')

        rollback_id = f"RB_{level_short}_{sequential_num:03d}_{short_date}"

        record = {
            "rollback_id": rollback_id,
            "level": rollback_level.value,
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "status": RollbackStatus.PENDING.value,
            "details": details
        }

        history.append(record)
        with open(self.rollback_history_file, 'w') as f:
            json.dump(history, f, indent=2)

        return rollback_id
    
    def _update_rollback_status(self, rollback_id: str, status: RollbackStatus):
        """Update rollback operation status"""
        with open(self.rollback_history_file, 'r') as f:
            history = json.load(f)
        
        for record in history:
            if record["rollback_id"] == rollback_id:
                record["status"] = status.value
                record["updated_at"] = datetime.now().isoformat()
                break
        
        with open(self.rollback_history_file, 'w') as f:
            json.dump(history, f, indent=2)

    # ========================================================================
    # STAGE 0: FULL ROLLBACK
    # ========================================================================

    def whole_process_rollback(self, run_id: str, reason: str,
                              confirmation_required: bool = True) -> Dict:
        """
        Complete rollback of the entire process from upload to reconciliation
        Removes all output files and resets to pre-upload state
        WARNING: This is a destructive operation that cannot be undone

        Args:
            run_id: Current run identifier
            reason: Reason for full rollback (e.g., 'Process restart required')
            confirmation_required: Whether user confirmation is needed (default: True)

        Returns:
            Dict with rollback details
        """
        # Validate rollback operation
        can_rollback, validation_msg = self._validate_rollback_allowed(run_id, RollbackLevel.WHOLE_PROCESS)
        if not can_rollback:
            raise ValueError(f"Whole process rollback not allowed: {validation_msg}")

        # Validate reason
        if not reason or not reason.strip():
            raise ValueError("Rollback reason cannot be empty")

        if confirmation_required:
            return {
                "status": "confirmation_required",
                "message": (
                    f"⚠️ FULL ROLLBACK WARNING: This will permanently "
                    f"delete all processed data for run {run_id}. This action "
                    f"cannot be undone. Reason: {reason}"
                ),
                "run_id": run_id,
                "reason": reason,
                "confirmation_details": {
                    "rollback_level": "full",
                    "reason": reason,
                    "action": "complete_data_deletion",
                    "warning": "This will delete all output files and reset the process"
                }
            }

        if not self._acquire_rollback_lock(run_id):
            raise ValueError(f"Another rollback operation is in progress for run {run_id}")

        rollback_id = self._log_rollback(
            RollbackLevel.WHOLE_PROCESS,
            run_id,
            {
                "reason": reason,
                "action": "complete_process_reset",
                "confirmation_provided": not confirmation_required
            }
        )

        try:
            self._update_rollback_status(rollback_id, RollbackStatus.IN_PROGRESS)

            output_dir = os.path.join(self.output_dir, run_id)
            upload_dir = os.path.join(self.upload_dir, run_id)

            # Create comprehensive backup before deletion
            backup_dir = os.path.join(self.output_dir, f"full_backup_{run_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            try:
                if os.path.exists(output_dir):
                    shutil.copytree(output_dir, backup_dir)
                    logger.info(f"Full backup created: {backup_dir}")
                else:
                    logger.warning(f"No output directory to backup: {output_dir}")
            except Exception as backup_error:
                logger.error(f"Failed to create full backup: {str(backup_error)}")
                raise ValueError(f"Cannot proceed without backup: {str(backup_error)}")

            # Track what was deleted
            deleted_files = []
            deleted_dirs = []

            # Delete output directory (recon, accounting, etc.)
            if os.path.exists(output_dir):
                try:
                    # List files before deletion for logging
                    for root, dirs, files in os.walk(output_dir):
                        for file in files:
                            deleted_files.append(os.path.join(root, file))
                        for dir_name in dirs:
                            deleted_dirs.append(os.path.join(root, dir_name))

                    shutil.rmtree(output_dir)
                    logger.info(f"Deleted output directory: {output_dir}")
                except Exception as delete_error:
                    logger.error(f"Failed to delete output directory: {str(delete_error)}")
                    raise ValueError(f"Failed to delete output directory: {str(delete_error)}")

            # Reset upload metadata (but keep uploaded files)
            metadata_path = os.path.join(upload_dir, "metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)

                    # Clear processing status and results
                    metadata["processing_status"] = "reset"
                    metadata["recon_completed"] = False
                    metadata["accounting_completed"] = False
                    metadata["last_processed"] = None
                    metadata["results_summary"] = {}

                    # Add full rollback record
                    if "rollback_history" not in metadata:
                        metadata["rollback_history"] = []
                    metadata["rollback_history"].append({
                        "rollback_id": rollback_id,
                        "timestamp": datetime.now().isoformat(),
                        "reason": reason,
                        "action": "full_process_reset",
                        "deleted_output_dir": output_dir,
                        "backup_location": backup_dir
                    })

                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=2)

                    logger.info(f"Reset metadata for run {run_id}")
                except Exception as meta_error:
                    logger.warning(f"Failed to reset metadata: {str(meta_error)}")

            self._update_rollback_status(rollback_id, RollbackStatus.COMPLETED)

            return {
                "status": "success",
                "rollback_id": rollback_id,
                "message": (
                    f"Full rollback completed for run {run_id}. All processed "
                    f"data has been deleted and the process has been reset."
                ),
                "reason": reason,
                "run_id": run_id,
                "backup_created": backup_dir,
                "deleted_files_count": len(deleted_files),
                "deleted_dirs_count": len(deleted_dirs),
                "confirmation_provided": not confirmation_required,
                "warning": "Process has been completely reset. You can restart from file upload."
            }

        except Exception as e:
            logger.error(f"Full rollback failed: {str(e)}")
            self._update_rollback_status(rollback_id, RollbackStatus.FAILED)
            raise
        finally:
            self._release_rollback_lock()

    # ========================================================================
    # STAGE 1: INGESTION ROLLBACK
    # ========================================================================
    
    def ingestion_rollback(self, run_id: str, failed_filename: str,
                          validation_error: str) -> Dict:
        """
        Rollback specific file that failed validation during upload
        Removes only the failed file, preserves other uploaded files

        Args:
            run_id: Current run identifier
            failed_filename: Name of the file that failed validation (can be original or standardized name)
            validation_error: Description of the validation error

        Returns:
            Dict with rollback details and status
        """
        rollback_id = self._log_rollback(
            RollbackLevel.INGESTION,
            run_id,
            {
                "failed_file": failed_filename,
                "error": validation_error,
                "action": "remove_failed_file"
            }
        )

        try:
            self._update_rollback_status(rollback_id, RollbackStatus.IN_PROGRESS)

            run_folder = os.path.join(self.upload_dir, run_id)

            # Check if run folder exists
            if not os.path.exists(run_folder):
                logger.info(f"Run folder does not exist for {run_id} - no rollback needed")
                self._update_rollback_status(rollback_id, RollbackStatus.COMPLETED)
                return {
                    "status": "success",
                    "rollback_id": rollback_id,
                    "message": (
                        f"Ingestion rollback completed - no files to rollback "
                        f"for {failed_filename} (run folder not yet created)"
                    ),
                    "removed_file": None,
                    "original_request": failed_filename,
                    "run_id": run_id,
                    "note": "Run folder did not exist - validation failed before file upload"
                }

            # Try to find the file - check both original and standardized names
            failed_file_path = None
            actual_filename = None

            # First, try exact match
            exact_path = os.path.join(run_folder, failed_filename)
            if os.path.exists(exact_path):
                failed_file_path = exact_path
                actual_filename = failed_filename
            else:
                # Check file mapping if available
                mapping_file = os.path.join(run_folder, "file_mapping.json")
                if os.path.exists(mapping_file):
                    try:
                        with open(mapping_file, 'r') as f:
                            file_mapping = json.load(f)

                        # Find file by type or partial match
                        for file_type, mapped_name in file_mapping.items():
                            if (file_type in failed_filename.lower() or
                                failed_filename.lower() in file_type or
                                failed_filename.lower() in mapped_name.lower()):
                                mapped_path = os.path.join(run_folder, mapped_name)
                                if os.path.exists(mapped_path):
                                    failed_file_path = mapped_path
                                    actual_filename = mapped_name
                                    break
                    except Exception as mapping_error:
                        logger.warning(f"Could not read file mapping: {mapping_error}")

                # If still not found, search directory for similar files
                if not failed_file_path:
                    for filename in os.listdir(run_folder):
                        if (failed_filename.lower() in filename.lower() or
                            any(keyword in filename.lower() for keyword in ['cbs', 'switch', 'npci', 'ntsl', 'adjustment'] if keyword in failed_filename.lower())):
                            file_path = os.path.join(run_folder, filename)
                            if os.path.exists(file_path) and os.path.isfile(file_path):
                                failed_file_path = file_path
                                actual_filename = filename
                                break

            if not failed_file_path:
                logger.warning(f"File not found for rollback: {failed_filename}")
                # Don't fail the rollback if file is already gone
                actual_filename = failed_filename
            else:
                # Remove the failed file
                try:
                    os.remove(failed_file_path)
                    logger.info(f"Ingestion rollback: Removed {actual_filename} from {run_id}")
                except Exception as remove_error:
                    logger.error(f"Failed to remove file {failed_file_path}: {remove_error}")
                    raise ValueError(f"Could not remove failed file: {remove_error}")

            # Update metadata
            metadata_path = os.path.join(run_folder, "metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)

                    # Remove from uploaded_files (try multiple ways to match)
                    if "uploaded_files" in metadata:
                        original_list = metadata["uploaded_files"]
                        filtered_list = []

                        for uploaded_file in original_list:
                            # Keep file if it doesn't match the failed file in any way
                            if not (uploaded_file == failed_filename or
                                   uploaded_file == actual_filename or
                                   failed_filename.lower() in uploaded_file.lower() or
                                   (actual_filename and actual_filename.lower() in uploaded_file.lower())):
                                filtered_list.append(uploaded_file)

                        metadata["uploaded_files"] = filtered_list
                        logger.info(f"Updated uploaded_files list, removed: {failed_filename}")

                    # Add rollback record
                    if "rollback_history" not in metadata:
                        metadata["rollback_history"] = []
                    metadata["rollback_history"].append({
                        "rollback_id": rollback_id,
                        "timestamp": datetime.now().isoformat(),
                        "removed_file": actual_filename or failed_filename,
                        "original_request": failed_filename,
                        "reason": validation_error
                    })

                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=2)

                    logger.info(f"Updated metadata for run {run_id}")
                except Exception as meta_error:
                    logger.warning(f"Failed to update metadata: {meta_error}")
                    # Don't fail rollback for metadata issues

            self._update_rollback_status(rollback_id, RollbackStatus.COMPLETED)

            return {
                "status": "success",
                "rollback_id": rollback_id,
                "message": (
                    f"Ingestion rollback completed for "
                    f"{actual_filename or failed_filename}"
                ),
                "removed_file": actual_filename or failed_filename,
                "original_request": failed_filename,
                "run_id": run_id
            }

        except Exception as e:
            logger.error(f"Ingestion rollback failed: {str(e)}")
            self._update_rollback_status(rollback_id, RollbackStatus.FAILED)
            raise
        finally:
            self._release_rollback_lock()
    
    # ========================================================================
    # STAGE 2: MID-RECON ROLLBACK
    # ========================================================================
    
    def mid_recon_rollback(self, run_id: str, error_message: str,
                          affected_transactions: Optional[List[str]] = None,
                          confirmation_required: bool = False) -> Dict:
        """
        Rollback uncommitted transactions during reconciliation
        Triggered by critical errors (DB disconnection, crashes, etc.)
        Restores all affected transactions to 'unmatched' state with atomic operations

        Args:
            run_id: Current run identifier
            error_message: Description of the error that triggered rollback
            affected_transactions: List of transaction IDs to rollback
            confirmation_required: Whether user confirmation is needed

        Returns:
            Dict with rollback details
        """
        # Validate rollback operation
        can_rollback, validation_msg = self._validate_rollback_allowed(run_id, RollbackLevel.MID_RECON)
        if not can_rollback:
            raise ValueError(f"Mid-recon rollback not allowed: {validation_msg}")

        if confirmation_required:
            return {
                "status": "confirmation_required",
                "message": (
                    f"Mid-recon rollback requires confirmation. Error: "
                    f"{error_message}"
                ),
                "affected_transactions": affected_transactions or [],
                "run_id": run_id,
                "confirmation_details": {
                    "rollback_level": "mid_recon",
                    "error_message": error_message,
                    "affected_count": len(affected_transactions) if affected_transactions else 0
                }
            }

        rollback_id = self._log_rollback(
            RollbackLevel.MID_RECON,
            run_id,
            {
                "error": error_message,
                "affected_count": len(affected_transactions) if affected_transactions else 0,
                "action": "restore_unmatched_state",
                "confirmation_provided": not confirmation_required
            }
        )

        try:
            self._update_rollback_status(rollback_id, RollbackStatus.IN_PROGRESS)

            # Load current recon output
            output_dir = os.path.join(self.output_dir, run_id)
            recon_output_path = os.path.join(output_dir, "recon_output.json")

            if not os.path.exists(recon_output_path):
                raise FileNotFoundError(f"Reconciliation output not found: {recon_output_path}")

            with open(recon_output_path, 'r') as f:
                recon_data = json.load(f)

            # Create backup before rolling back (atomic operation)
            backup_path = os.path.join(output_dir, f"recon_output_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            try:
                shutil.copy(recon_output_path, backup_path)
                logger.info(f"Backup created: {backup_path}")
            except Exception as backup_error:
                logger.error(f"Failed to create backup: {str(backup_error)}")
                raise ValueError(f"Cannot proceed without backup: {str(backup_error)}")

            # Atomic transaction state restoration
            transactions_restored = []

            # Support two recon_output formats: (A) mapping rrn->record, (B) legacy dict with 'matched'/'unmatched' lists
            if isinstance(recon_data, dict) and not recon_data.get("matched") and not recon_data.get("unmatched"):
                # Format A: dictionary keyed by RRN
                if affected_transactions:
                    for txn_id in affected_transactions:
                        # Direct lookup by rrn
                        entry = recon_data.get(txn_id)
                        if not entry:
                            # Try to find by rrn field inside values
                            for k, v in recon_data.items():
                                if isinstance(v, dict) and (v.get('rrn') == txn_id or v.get('txn_id') == txn_id):
                                    entry = v
                                    break

                        if entry and entry.get('status') == 'MATCHED':
                            if 'rollback_metadata' not in entry:
                                entry['rollback_metadata'] = []
                            entry['rollback_metadata'].append({
                                'rollback_id': rollback_id,
                                'previous_status': 'MATCHED',
                                'rollback_timestamp': datetime.now().isoformat(),
                                'rollback_reason': error_message
                            })
                            # Mark as unmatched/orphan for re-processing
                            entry['status'] = 'ORPHAN'
                            transactions_restored.append(txn_id)
                        else:
                            logger.warning(f"Transaction {txn_id} not found or not matched in data")
                else:
                    # Rollback all matched transactions
                    for rrn_key, entry in recon_data.items():
                        if isinstance(entry, dict) and entry.get('status') == 'MATCHED':
                            if 'rollback_metadata' not in entry:
                                entry['rollback_metadata'] = []
                            entry['rollback_metadata'].append({
                                'rollback_id': rollback_id,
                                'previous_status': 'MATCHED',
                                'rollback_timestamp': datetime.now().isoformat(),
                                'rollback_reason': error_message
                            })
                            entry['status'] = 'ORPHAN'
                            transactions_restored.append(rrn_key)
            else:
                # Legacy format: lists under 'matched' and 'unmatched'
                original_matched = recon_data.get("matched", [])
                original_unmatched = recon_data.get("unmatched", [])

                if affected_transactions:
                    # Find and validate affected transactions
                    affected_txns_found = []
                    for txn_id in affected_transactions:
                        matching_txns = [
                            t for t in original_matched
                            if t.get("txn_id") == txn_id or t.get("rrn") == txn_id
                        ]
                        if matching_txns:
                            affected_txns_found.extend(matching_txns)
                        else:
                            logger.warning(f"Transaction {txn_id} not found in matched transactions")

                    # Remove affected transactions from matched
                    remaining_matched = [
                        t for t in original_matched
                        if not any(t.get("txn_id") == txn_id or t.get("rrn") == txn_id for txn_id in affected_transactions)
                    ]

                    # Add affected transactions back to unmatched with rollback metadata
                    restored_unmatched = original_unmatched.copy()
                    for txn in affected_txns_found:
                        txn_copy = txn.copy()
                        txn_copy["rollback_metadata"] = {
                            "rollback_id": rollback_id,
                            "previous_status": "matched",
                            "rollback_timestamp": datetime.now().isoformat(),
                            "rollback_reason": error_message
                        }
                        restored_unmatched.append(txn_copy)
                        transactions_restored.append(txn.get("rrn") or txn.get("txn_id"))

                    # Update recon data atomically
                    recon_data["matched"] = remaining_matched
                    recon_data["unmatched"] = restored_unmatched
                else:
                    # Rollback all matched transactions if no specific transactions provided
                    logger.warning("No specific transactions provided - rolling back all matched transactions")
                    all_matched_txns = original_matched.copy()
                    recon_data["matched"] = []
                    recon_data["unmatched"] = original_unmatched + all_matched_txns
                    transactions_restored = [t.get("rrn") or t.get("txn_id") for t in all_matched_txns]

            # Update status counters with rollback information
            recon_data["summary"] = {
                "total_matched": len(recon_data.get("matched", [])),
                "total_unmatched": len(recon_data.get("unmatched", [])),
                "last_rollback": {
                    "rollback_id": rollback_id,
                    "level": "mid_recon",
                    "transactions_restored": len(transactions_restored),
                    "error_message": error_message,
                    "timestamp": datetime.now().isoformat()
                },
                "rollback_timestamp": datetime.now().isoformat()
            }

            # Atomic save operation
            temp_file = recon_output_path + ".tmp"
            try:
                with open(temp_file, 'w') as f:
                    json.dump(recon_data, f, indent=2)
                os.replace(temp_file, recon_output_path)  # Atomic file replacement
                logger.info(
                    f"Mid-recon rollback completed for {run_id}. "
                    f"{len(transactions_restored)} transactions restored."
                )
            except Exception as save_error:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                raise ValueError(f"Failed to save rolled back data: {str(save_error)}")

            self._update_rollback_status(rollback_id, RollbackStatus.COMPLETED)

            return {
                "status": "success",
                "rollback_id": rollback_id,
                "message": (
                    f"Mid-recon rollback completed. "
                    f"{len(transactions_restored)} transactions restored to "
                    f"unmatched state."
                ),
                "affected_transactions": affected_transactions or [],
                "transactions_restored": transactions_restored,
                "run_id": run_id,
                "backup_created": backup_path,
                "confirmation_provided": not confirmation_required
            }

        except Exception as e:
            logger.error(f"Mid-recon rollback failed: {str(e)}")
            self._update_rollback_status(rollback_id, RollbackStatus.FAILED)
            raise
        finally:
            self._release_rollback_lock()
    
    # ========================================================================
    # STAGE 3: CYCLE-WISE ROLLBACK
    # ========================================================================
    
    def cycle_wise_rollback(self, run_id: str, cycle_id: str,
                           confirmation_required: bool = False) -> Dict:
        """
        Rollback specific NPCI cycle for re-processing with atomic operations
        Does not affect other cycles or previously matched transactions
        NPCI operates on 10 cycles: 1C, 2C, 3C, 4C, 5C, 6C, 7C, 8C, 9C, 10C

        Args:
            run_id: Current run identifier
            cycle_id: NPCI cycle to rollback (e.g., '1C', '3B')
            confirmation_required: Whether user confirmation is needed

        Returns:
            Dict with rollback details
        """
        # Validate rollback operation
        can_rollback, validation_msg = self._validate_rollback_allowed(run_id, RollbackLevel.CYCLE_WISE)
        if not can_rollback:
            raise ValueError(f"Cycle-wise rollback not allowed: {validation_msg}")

        # Validate cycle_id format
        valid_cycles = ['1C', '2C', '3C', '4C', '5C', '6C', '7C', '8C', '9C', '10C']
        if cycle_id not in valid_cycles:
            raise ValueError(f"Invalid cycle ID '{cycle_id}'. Valid cycles: {', '.join(valid_cycles)}")

        if confirmation_required:
            return {
                "status": "confirmation_required",
                "message": (
                    f"Cycle-wise rollback requires confirmation for cycle "
                    f"{cycle_id}"
                ),
                "cycle_id": cycle_id,
                "run_id": run_id,
                "confirmation_details": {
                    "rollback_level": "cycle_wise",
                    "cycle_id": cycle_id,
                    "action": "restore_cycle_data"
                }
            }

        rollback_id = self._log_rollback(
            RollbackLevel.CYCLE_WISE,
            run_id,
            {
                "cycle_id": cycle_id,
                "action": "restore_cycle_data",
                "confirmation_provided": not confirmation_required
            }
        )

        try:
            self._update_rollback_status(rollback_id, RollbackStatus.IN_PROGRESS)

            output_dir = os.path.join(self.output_dir, run_id)
            recon_output_path = os.path.join(output_dir, "recon_output.json")

            if not os.path.exists(recon_output_path):
                raise FileNotFoundError(f"Reconciliation output not found: {recon_output_path}")

            with open(recon_output_path, 'r') as f:
                recon_data = json.load(f)

            # Create backup before rolling back (atomic operation)
            backup_path = os.path.join(output_dir, f"cycle_{cycle_id}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            try:
                shutil.copy(recon_output_path, backup_path)
                logger.info(f"Backup created: {backup_path}")
            except Exception as backup_error:
                logger.error(f"Failed to create backup: {str(backup_error)}")
                raise ValueError(f"Cannot proceed without backup: {str(backup_error)}")

            # Remove cycle-specific generated files (reports, ttum, annexure, audit)
            deleted_paths = []
            for sub in ('reports', 'ttum', 'annexure', 'audit'):
                subdir = os.path.join(output_dir, sub, f'cycle_{cycle_id}')
                if os.path.exists(subdir):
                    try:
                        # collect files for logging
                        for root, dirs, files in os.walk(subdir):
                            for fn in files:
                                deleted_paths.append(os.path.join(root, fn))
                        shutil.rmtree(subdir)
                        logger.info(f"Deleted cycle-specific directory: {subdir}")
                    except Exception as del_err:
                        logger.warning(f"Failed to delete {subdir}: {del_err}")

            # Atomic cycle transaction restoration
            transactions_restored = []
            cycle_txns = []  # Initialize here to avoid scope issues

            # Support mapping-format (rrn->record) or legacy list-format
            if isinstance(recon_data, dict) and not recon_data.get('matched') and not recon_data.get('unmatched'):
                cycle_txns = []
                for rrn_key, entry in recon_data.items():
                    if isinstance(entry, dict) and entry.get('cycle_id') == cycle_id and entry.get('status') == 'MATCHED':
                        cycle_txns.append((rrn_key, entry))

                if not cycle_txns:
                    logger.warning(f"No transactions found for cycle {cycle_id} in matched transactions")

                for rrn_key, txn in cycle_txns:
                    if 'rollback_metadata' not in txn:
                        txn['rollback_metadata'] = []
                    txn['rollback_metadata'].append({
                        'rollback_id': rollback_id,
                        'previous_status': 'MATCHED',
                        'cycle_id': cycle_id,
                        'rollback_timestamp': datetime.now().isoformat(),
                        'rollback_reason': f'Cycle {cycle_id} rollback for re-processing'
                    })
                    txn['status'] = 'ORPHAN'
                    transactions_restored.append(rrn_key)
            else:
                matched_txns = recon_data.get("matched", [])
                original_unmatched = recon_data.get("unmatched", [])

                # Find transactions from specific cycle with validation
                cycle_txns = []
                for txn in matched_txns:
                    if txn.get("cycle_id") == cycle_id:
                        cycle_txns.append(txn)

                if not cycle_txns:
                    logger.warning(f"No transactions found for cycle {cycle_id} in matched transactions")

                # Remove cycle transactions from matched
                remaining_matched = [t for t in matched_txns if t.get("cycle_id") != cycle_id]

                # Add cycle transactions back to unmatched with rollback metadata
                restored_unmatched = original_unmatched.copy()
                for txn in cycle_txns:
                    txn_copy = txn.copy()
                    txn_copy["rollback_metadata"] = {
                        "rollback_id": rollback_id,
                        "previous_status": "matched",
                        "cycle_id": cycle_id,
                        "rollback_timestamp": datetime.now().isoformat(),
                        "rollback_reason": f"Cycle {cycle_id} rollback for re-processing"
                    }
                    restored_unmatched.append(txn_copy)
                    transactions_restored.append(txn_copy.get('rrn') or txn_copy.get('txn_id'))

                # Update recon data atomically
                recon_data["matched"] = remaining_matched
                recon_data["unmatched"] = restored_unmatched

            # Update status counters with detailed rollback information
            try:
                # determine counts depending on data format
                if isinstance(recon_data, dict) and not recon_data.get('matched') and not recon_data.get('unmatched'):
                    matched_count = len([v for v in recon_data.values() if isinstance(v, dict) and v.get('status') == 'MATCHED'])
                    unmatched_count = len([v for v in recon_data.values() if isinstance(v, dict) and v.get('status') in ['ORPHAN','PARTIAL_MATCH','PARTIAL_MISMATCH']])
                    restored_count = len(transactions_restored)
                else:
                    matched_count = len(recon_data.get('matched', []))
                    unmatched_count = len(recon_data.get('unmatched', []))
                    restored_count = len(transactions_restored)

                recon_data['summary'] = {
                    'total_matched': matched_count,
                    'total_unmatched': unmatched_count,
                    'last_cycle_rollback': {
                        'rollback_id': rollback_id,
                        'cycle_id': cycle_id,
                        'transactions_restored': restored_count,
                        'timestamp': datetime.now().isoformat(),
                        'confirmation_provided': not confirmation_required
                    },
                    'rollback_timestamp': datetime.now().isoformat()
                }
            except Exception:
                # Fallback summary if something unexpected occurred
                recon_data['summary'] = {
                    'total_matched': 0,
                    'total_unmatched': 0,
                    'last_cycle_rollback': {
                        'rollback_id': rollback_id,
                        'cycle_id': cycle_id,
                        'transactions_restored': len(transactions_restored),
                        'timestamp': datetime.now().isoformat(),
                        'confirmation_provided': not confirmation_required
                    },
                    'rollback_timestamp': datetime.now().isoformat()
                }

            # Atomic save operation
            temp_file = recon_output_path + ".tmp"
            try:
                with open(temp_file, 'w') as f:
                    json.dump(recon_data, f, indent=2)
                os.replace(temp_file, recon_output_path)  # Atomic file replacement
                logger.info(
                    f"Cycle-wise rollback for {cycle_id} completed. "
                    f"{len(cycle_txns)} transactions restored."
                )
            except Exception as save_error:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                raise ValueError(f"Failed to save rolled back data: {str(save_error)}")

            self._update_rollback_status(rollback_id, RollbackStatus.COMPLETED)

            return {
                "status": "success",
                "rollback_id": rollback_id,
                "message": (
                    f"Cycle {cycle_id} rolled back for re-processing. "
                    f"{len(cycle_txns)} transactions restored."
                ),
                "cycle_id": cycle_id,
                "transactions_restored": len(cycle_txns),
                "run_id": run_id,
                "backup_created": backup_path,
                "deleted_files_count": len(deleted_paths),
                "deleted_paths": deleted_paths,
                "confirmation_provided": not confirmation_required
            }

        except Exception as e:
            logger.error(f"Cycle-wise rollback failed: {str(e)}")
            self._update_rollback_status(rollback_id, RollbackStatus.FAILED)
            raise
        finally:
            self._release_rollback_lock()
    
    # ========================================================================
    # STAGE 4: ACCOUNTING ROLLBACK
    # ========================================================================
    
    def accounting_rollback(self, run_id: str, reason: str,
                           voucher_ids: Optional[List[str]] = None,
                           confirmation_required: bool = False) -> Dict:
        """
        Rollback voucher generation when CBS upload fails with atomic operations
        Resets status from 'settled/voucher generated' to 'matched/pending'
        Prevents corrupted GL entries with comprehensive validation

        Args:
            run_id: Current run identifier
            reason: Reason for rollback (e.g., 'CBS upload failure')
            voucher_ids: List of voucher IDs to rollback (None for all)
            confirmation_required: Whether user confirmation is needed

        Returns:
            Dict with rollback details
        """
        # Validate rollback operation
        can_rollback, validation_msg = self._validate_rollback_allowed(run_id, RollbackLevel.ACCOUNTING)
        if not can_rollback:
            raise ValueError(f"Accounting rollback not allowed: {validation_msg}")

        # Validate reason
        if not reason or not reason.strip():
            raise ValueError("Rollback reason cannot be empty")

        if confirmation_required:
            voucher_count = len(voucher_ids) if voucher_ids else "all"
            return {
                "status": "confirmation_required",
                "message": (
                    f"Accounting rollback requires confirmation. "
                    f"{voucher_count} vouchers will be reset."
                ),
                "reason": reason,
                "voucher_ids": voucher_ids,
                "run_id": run_id,
                "confirmation_details": {
                    "rollback_level": "accounting",
                    "reason": reason,
                    "voucher_count": len(voucher_ids) if voucher_ids else 0,
                    "action": "reset_vouchers_to_pending"
                }
            }

        rollback_id = self._log_rollback(
            RollbackLevel.ACCOUNTING,
            run_id,
            {
                "reason": reason,
                "voucher_count": len(voucher_ids) if voucher_ids else 0,
                "action": "reset_to_matched_pending",
                "confirmation_provided": not confirmation_required
            }
        )

        try:
            self._update_rollback_status(rollback_id, RollbackStatus.IN_PROGRESS)

            output_dir = os.path.join(self.output_dir, run_id)
            accounting_path = os.path.join(output_dir, "accounting_output.json")

            if not os.path.exists(accounting_path):
                raise FileNotFoundError(f"Accounting output not found: {accounting_path}")

            with open(accounting_path, 'r') as f:
                accounting_data = json.load(f)

            # Create backup before rolling back (atomic operation)
            backup_path = os.path.join(output_dir, f"accounting_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            try:
                shutil.copy(accounting_path, backup_path)
                logger.info(f"Backup created: {backup_path}")
            except Exception as backup_error:
                logger.error(f"Failed to create backup: {str(backup_error)}")
                raise ValueError(f"Cannot proceed without backup: {str(backup_error)}")

            # Atomic voucher status reset
            vouchers = accounting_data.get("vouchers", [])
            vouchers_reset = []
            vouchers_not_found = []

            if voucher_ids:
                # Specific voucher rollback
                for voucher_id in voucher_ids:
                    voucher_found = False
                    for voucher in vouchers:
                        if voucher.get("voucher_id") == voucher_id:
                            if voucher.get("status") == "voucher_generated":
                                voucher["previous_status"] = voucher["status"]
                                voucher["status"] = "matched/pending"
                                voucher["rollback_metadata"] = {
                                    "rollback_id": rollback_id,
                                    "rollback_timestamp": datetime.now().isoformat(),
                                    "rollback_reason": reason,
                                    "previous_gl_entries": voucher.get("gl_entries", [])
                                }
                                # Clear GL entries to prevent corruption
                                voucher["gl_entries"] = []
                                vouchers_reset.append(voucher_id)
                                voucher_found = True
                                break
                    if not voucher_found:
                        vouchers_not_found.append(voucher_id)
            else:
                # Rollback all vouchers
                for voucher in vouchers:
                    if voucher.get("status") == "voucher_generated":
                        voucher["previous_status"] = voucher["status"]
                        voucher["status"] = "matched/pending"
                        voucher["rollback_metadata"] = {
                            "rollback_id": rollback_id,
                            "rollback_timestamp": datetime.now().isoformat(),
                            "rollback_reason": reason,
                            "previous_gl_entries": voucher.get("gl_entries", [])
                        }
                        # Clear GL entries to prevent corruption
                        voucher["gl_entries"] = []
                        vouchers_reset.append(voucher.get("voucher_id"))

            # Log warnings for vouchers not found
            if vouchers_not_found:
                logger.warning(f"Vouchers not found for rollback: {', '.join(vouchers_not_found)}")

            # Update accounting summary with detailed rollback information
            accounting_data["accounting_status"] = {
                "status": "rolled_back",
                "vouchers_reset": len(vouchers_reset),
                "vouchers_not_found": len(vouchers_not_found),
                "rollback_reason": reason,
                "rollback_id": rollback_id,
                "timestamp": datetime.now().isoformat(),
                "confirmation_provided": not confirmation_required,
                "gl_entries_cleared": True
            }

            # Atomic save operation
            temp_file = accounting_path + ".tmp"
            try:
                with open(temp_file, 'w') as f:
                    json.dump(accounting_data, f, indent=2)
                os.replace(temp_file, accounting_path)  # Atomic file replacement
                logger.info(
                    f"Accounting rollback completed for {run_id}. "
                    f"{len(vouchers_reset)} vouchers reset. Reason: {reason}"
                )
            except Exception as save_error:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                raise ValueError(f"Failed to save rolled back accounting data: {str(save_error)}")

            self._update_rollback_status(rollback_id, RollbackStatus.COMPLETED)

            return {
                "status": "success",
                "rollback_id": rollback_id,
                "message": (
                    f"Accounting rollback completed. "
                    f"{len(vouchers_reset)} vouchers reset to matched/pending "
                    f"state."
                ),
                "reason": reason,
                "vouchers_reset": vouchers_reset,
                "vouchers_not_found": vouchers_not_found,
                "run_id": run_id,
                "backup_created": backup_path,
                "confirmation_provided": not confirmation_required,
                "gl_entries_cleared": True
            }

        except Exception as e:
            logger.error(f"Accounting rollback failed: {str(e)}")
            self._update_rollback_status(rollback_id, RollbackStatus.FAILED)
            raise
        finally:
            self._release_rollback_lock()
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_rollback_history(self, run_id: Optional[str] = None) -> List[Dict]:
        """Get rollback history, optionally filtered by run_id"""
        with open(self.rollback_history_file, 'r') as f:
            history = json.load(f)
        
        if run_id:
            return [r for r in history if r.get("run_id") == run_id]
        return history
    
    def _validate_run_exists(self, run_id: str) -> bool:
        """Validate that the run folder exists in either upload or output dir"""
        upload_run = os.path.exists(os.path.join(self.upload_dir, run_id))
        output_run = os.path.exists(os.path.join(self.output_dir, run_id))
        return upload_run or output_run

    def _validate_files_exist(self, run_id: str, required_files: List[str]) -> Tuple[bool, str]:
        """Validate that required files exist for rollback"""
        run_folder = os.path.join(self.upload_dir, run_id)
        missing_files = []

        for file in required_files:
            if not os.path.exists(os.path.join(run_folder, file)):
                missing_files.append(file)

        if missing_files:
            return False, f"Missing required files: {', '.join(missing_files)}"

        return True, "All required files present"

    def _detect_recon_format(self, recon_data: Dict) -> str:
        """Reliably detect reconciliation data format"""
        if isinstance(recon_data, dict):
            # Check for legacy format markers
            if "matched" in recon_data and "unmatched" in recon_data:
                if isinstance(recon_data["matched"], list):
                    return "legacy"

            # Check for new format (RRN keys with record values)
            for key, value in recon_data.items():
                if isinstance(value, dict) and "status" in value:
                    return "rrn_keyed"

        return "unknown"

    def _execute_with_rollback(self, operations: List[Callable], cleanup: Callable):
        """Execute operations with automatic cleanup on failure"""
        completed_ops = []
        try:
            for op in operations:
                result = op()
                completed_ops.append(result)
            return True
        except Exception as e:
            logger.error(f"Operation failed, rolling back: {e}")
            cleanup(completed_ops)
            raise

    def _acquire_rollback_lock(self, run_id: str) -> bool:
        """Acquire exclusive lock for rollback operation"""
        lock_file = os.path.join(self.output_dir, f"{run_id}.rollback.lock")
        try:
            self.lock_fd = open(lock_file, 'w')
            portalocker.lock(self.lock_fd, portalocker.LOCK_EX | portalocker.LOCK_NB)
            return True
        except portalocker.LockException:
            return False

    def _release_rollback_lock(self):
        """Release rollback lock"""
        if hasattr(self, 'lock_fd'):
            self.lock_fd.close()

    def _validate_rollback_allowed(self, run_id: str, rollback_level: RollbackLevel) -> Tuple[bool, str]:
        """Validate if rollback operation is allowed based on current state"""
        # Check for recent rollback (prevent cascading rollbacks)
        history = self.get_rollback_history(run_id)
        if history and history[-1]["status"] == RollbackStatus.IN_PROGRESS.value:
            return False, "Rollback already in progress for this run"

        # Check if run exists
        if not self._validate_run_exists(run_id):
            return False, f"Run {run_id} not found"

        # Level-specific validations
        if rollback_level == RollbackLevel.WHOLE_PROCESS:
            # Full rollback requires output directory to exist (something to rollback)
            output_dir = os.path.join(self.output_dir, run_id)
            if not os.path.exists(output_dir):
                return False, "No output directory found - nothing to rollback"

        elif rollback_level == RollbackLevel.MID_RECON:
            output_dir = os.path.join(self.output_dir, run_id)
            recon_file = os.path.join(output_dir, "recon_output.json")
            if not os.path.exists(recon_file):
                return False, "No reconciliation output found for mid-recon rollback"

        elif rollback_level == RollbackLevel.CYCLE_WISE:
            output_dir = os.path.join(self.output_dir, run_id)
            recon_file = os.path.join(output_dir, "recon_output.json")
            if not os.path.exists(recon_file):
                return False, "No reconciliation output found for cycle-wise rollback"

        elif rollback_level == RollbackLevel.ACCOUNTING:
            output_dir = os.path.join(self.output_dir, run_id)
            accounting_file = os.path.join(output_dir, "accounting_output.json")
            if not os.path.exists(accounting_file):
                return False, "No accounting output found for accounting rollback"
            # Disallow accounting rollback if TTUM files have been downloaded
            try:
                ttum_flag = os.path.join(output_dir, 'ttum', 'download_meta.json')
                if os.path.exists(ttum_flag):
                    with open(ttum_flag, 'r') as f:
                        meta = json.load(f)
                    if isinstance(meta, dict) and meta.get('is_downloaded'):
                        return False, "TTUM already downloaded; accounting rollback disabled"
            except Exception:
                # If flag cannot be read, err on safer side and allow rollback
                pass

        return True, "Rollback allowed"

    def can_rollback(self, run_id: str, rollback_level: RollbackLevel) -> Tuple[bool, str]:
        """Check if rollback operation is allowed"""
        return self._validate_rollback_allowed(run_id, rollback_level)
