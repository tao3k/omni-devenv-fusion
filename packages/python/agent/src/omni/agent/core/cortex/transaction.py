"""
transaction.py - Homeostasis Transaction Shield

Provides Git-based transaction isolation for concurrent task execution.

Features:
- Branch-level isolation for each TaskNode
- Automatic commit and verification workflow
- Rollback capabilities
- Conflict detection integration

Integration: CortexOrchestrator → TransactionShield → Git/ImmuneSystem
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.cortex.transaction")


class TransactionStatus(str, Enum):
    """Transaction lifecycle status."""

    IDLE = "idle"
    PREPARING = "preparing"
    ISOLATED = "isolated"
    MODIFYING = "modifying"
    COMMITTED = "committed"
    VERIFIED = "verified"
    MERGED = "merged"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ConflictSeverity(str, Enum):
    """Conflict severity levels."""

    NONE = "none"
    LOW = "low"  # Style/naming only
    MEDIUM = "medium"  # Logic-affecting
    HIGH = "high"  # Breaking change
    CRITICAL = "critical"  # Compile/runtime error

    @property
    def level(self) -> int:
        """Get integer level for comparison."""
        levels = {
            "none": 0,
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4,
        }
        return levels.get(self.value, 0)

    def __gt__(self, other):
        if isinstance(other, ConflictSeverity):
            return self.level > other.level
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, ConflictSeverity):
            return self.level < other.level
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, ConflictSeverity):
            return self.level >= other.level
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, ConflictSeverity):
            return self.level <= other.level
        return NotImplemented


@dataclass
class Transaction:
    """Represents an isolated modification transaction."""

    task_id: str
    branch_name: str
    status: TransactionStatus = TransactionStatus.IDLE
    base_commit: str = ""
    changes: dict[str, Any] = field(default_factory=dict)
    conflicts: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    committed_at: datetime | None = None
    verified_at: datetime | None = None
    error: str | None = None

    def __hash__(self):
        return hash(self.task_id)

    def __eq__(self, other):
        if isinstance(other, Transaction):
            return self.task_id == other.task_id
        return False


@dataclass
class ConflictReport:
    """Report of detected conflicts between transactions."""

    has_conflicts: bool
    severity: ConflictSeverity
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    auto_resolvable: bool = False


class TransactionShield:
    """
    Git-based transaction isolation system.

    Responsibilities:
    1. Create isolated branches for each task
    2. Track modifications and commit changes
    3. Verify changes via Immune System
    4. Handle rollback on failure

    Example:
        shield = TransactionShield()
        await shield.begin_transaction("task_123")
        # ... make changes ...
        await shield.commit_and_verify("task_123")
    """

    def __init__(
        self,
        base_branch: str = "main",
        workspace_prefix: str = "omni-task",
    ):
        """Initialize the transaction shield.

        Args:
            base_branch: The main branch to fork from
            workspace_prefix: Prefix for task branches
        """
        self.base_branch = base_branch
        self.workspace_prefix = workspace_prefix
        self._transactions: dict[str, Transaction] = {}
        self._repo_root: Path | None = None

    @property
    def repo_root(self) -> Path:
        """Get the repository root."""
        if self._repo_root is None:
            self._repo_root = self._find_repo_root()
        return self._repo_root

    def _find_repo_root(self) -> Path:
        """Find the Git repository root."""
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".git").exists():
                return parent
        return cwd

    def _get_branch_name(self, task_id: str) -> str:
        """Generate an isolated branch name for a task."""
        # Use last 8 chars to make names more distinguishable
        short_id = task_id[-8:] if len(task_id) > 8 else task_id
        return f"{self.workspace_prefix}/{short_id}"

    async def _run_git(self, *args, cwd: Path | None = None) -> tuple[int, str, str]:
        """Run a Git command."""
        cmd = ["git"] + list(args)
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Git command timed out"
        except FileNotFoundError:
            return -1, "", "Git not found"

    async def begin_transaction(self, task_id: str) -> Transaction:
        """Begin an isolated transaction for a task.

        Creates a new branch from the current HEAD.

        Args:
            task_id: The task identifier

        Returns:
            Transaction object with branch information
        """
        branch_name = self._get_branch_name(task_id)

        logger.info(
            "transaction.beginning",
            task_id=task_id,
            branch=branch_name,
        )

        # Get current commit SHA
        code, stdout, _ = await self._run_git("rev-parse", "HEAD")
        base_commit = stdout.strip() if code == 0 else ""

        # Create transaction record
        transaction = Transaction(
            task_id=task_id,
            branch_name=branch_name,
            status=TransactionStatus.PREPARING,
            base_commit=base_commit,
        )
        self._transactions[task_id] = transaction

        # Create and checkout the branch
        code, _, stderr = await self._run_git("checkout", "-b", branch_name)

        if code != 0:
            # Branch might exist, try to checkout
            code, _, stderr = await self._run_git("checkout", branch_name)

        if code != 0:
            transaction.status = TransactionStatus.FAILED
            transaction.error = f"Failed to create branch: {stderr}"
            logger.error(
                "transaction.branch_failed",
                task_id=task_id,
                error=stderr,
            )
            return transaction

        transaction.status = TransactionStatus.ISOLATED
        logger.info(
            "transaction.isolated",
            task_id=task_id,
            branch=branch_name,
            base_commit=base_commit[:8],
        )

        return transaction

    async def record_modification(
        self,
        task_id: str,
        file_path: str,
        old_content: str | None = None,
        new_content: str | None = None,
    ) -> bool:
        """Record a file modification in the transaction.

        Args:
            task_id: The task identifier
            file_path: Path to the modified file
            old_content: Previous content (for diff)
            new_content: New content

        Returns:
            True if recorded successfully
        """
        transaction = self._transactions.get(task_id)
        if not transaction:
            logger.warning(
                "transaction.not_found",
                task_id=task_id,
            )
            return False

        if transaction.status == TransactionStatus.ISOLATED:
            transaction.status = TransactionStatus.MODIFYING

        if file_path not in transaction.changes:
            transaction.changes[file_path] = {
                "old_hash": hashlib.md5(old_content.encode()).hexdigest() if old_content else None,
                "new_hash": hashlib.md5(new_content.encode()).hexdigest() if new_content else None,
            }
        else:
            # Update the new hash
            transaction.changes[file_path]["new_hash"] = (
                hashlib.md5(new_content.encode()).hexdigest() if new_content else None
            )

        return True

    async def commit_changes(
        self,
        task_id: str,
        message: str | None = None,
    ) -> bool:
        """Commit the transaction changes.

        Args:
            task_id: The task identifier
            message: Optional commit message

        Returns:
            True if committed successfully
        """
        transaction = self._transactions.get(task_id)
        if not transaction:
            return False

        if not transaction.changes:
            logger.info(
                "transaction.no_changes",
                task_id=task_id,
            )
            return True

        # Stage all changes
        code, _, stderr = await self._run_git("add", "-A")
        if code != 0:
            transaction.error = f"Failed to stage changes: {stderr}"
            return False

        # Create commit
        commit_msg = message or f"omni: {transaction.task_id}"
        code, _, stderr = await self._run_git("commit", "-m", commit_msg)

        if code != 0:
            transaction.error = f"Failed to commit: {stderr}"
            logger.error(
                "transaction.commit_failed",
                task_id=task_id,
                error=stderr,
            )
            return False

        transaction.status = TransactionStatus.COMMITTED
        transaction.committed_at = datetime.now()

        # Get commit SHA
        code, stdout, _ = await self._run_git("rev-parse", "HEAD")
        if code == 0:
            transaction.changes["_commit"] = stdout.strip()

        logger.info(
            "transaction.committed",
            task_id=task_id,
            commit=transaction.changes.get("_commit", "")[:8],
            files=len([k for k in transaction.changes if k != "_commit"]),
        )

        return True

    async def verify_transaction(
        self,
        task_id: str,
        verification_script: str | None = None,
    ) -> bool:
        """Verify a transaction via tests and Immune System.

        Args:
            task_id: The task identifier
            verification_script: Optional custom verification command

        Returns:
            True if verification passed
        """
        transaction = self._transactions.get(task_id)
        if not transaction:
            return False

        logger.info(
            "transaction.verifying",
            task_id=task_id,
        )

        # Run verification
        if verification_script:
            code, stdout, stderr = await self._run_git("sh", "-c", verification_script)
            if code != 0:
                transaction.error = f"Verification failed: {stderr}"
                transaction.status = TransactionStatus.FAILED
                logger.error(
                    "transaction.verification_failed",
                    task_id=task_id,
                    error=stderr,
                )
                return False

        # Run Immune static security scan on changed Python files
        immune_ok, immune_error = await self._run_immune_scan(transaction)
        if not immune_ok:
            transaction.error = immune_error
            transaction.status = TransactionStatus.FAILED
            logger.error(
                "transaction.immune_scan_failed",
                task_id=task_id,
                error=immune_error,
            )
            return False

        transaction.status = TransactionStatus.VERIFIED
        transaction.verified_at = datetime.now()

        logger.info(
            "transaction.verified",
            task_id=task_id,
        )

        return True

    async def _run_immune_scan(self, transaction: Transaction) -> tuple[bool, str | None]:
        """Run Immune static scan for changed Python files in the transaction."""
        from omni.foundation.bridge.rust_immune import scan_code_security

        changed_py_files = [
            path
            for path in transaction.changes.keys()
            if path != "_commit" and str(path).endswith(".py")
        ]
        if not changed_py_files:
            return True, None

        violation_summaries: list[str] = []

        for rel_path in changed_py_files:
            abs_path = self.repo_root / rel_path
            if not abs_path.exists():
                continue

            try:
                source = abs_path.read_text("utf-8")
            except UnicodeDecodeError:
                # Non-UTF8 files are skipped from Python source security scan.
                continue
            except Exception as exc:
                return False, f"Immune scan failed: {rel_path}: [READ-ERR] {exc}"

            is_safe, violations = scan_code_security(source)
            if is_safe:
                continue

            for violation in violations:
                rule = violation.get("rule_id", "UNKNOWN")
                line = violation.get("line", "?")
                desc = violation.get("description", "")
                violation_summaries.append(f"{rel_path}:{line} [{rule}] {desc}")

        if violation_summaries:
            preview = "; ".join(violation_summaries[:3])
            return False, f"Immune scan failed: {preview}"

        logger.info(
            "transaction.immune_scan_passed",
            task_id=transaction.task_id,
            files_scanned=len(changed_py_files),
        )
        return True, None

    async def merge_transaction(
        self,
        task_id: str,
        target_branch: str | None = None,
    ) -> bool:
        """Merge a transaction back to the target branch.

        Args:
            task_id: The task identifier
            target_branch: Branch to merge into (defaults to base_branch)

        Returns:
            True if merged successfully
        """
        transaction = self._transactions.get(task_id)
        if not transaction:
            return False

        target = target_branch or self.base_branch

        logger.info(
            "transaction.merging",
            task_id=task_id,
            target=target,
        )

        # Switch to target branch
        code, _, stderr = await self._run_git("checkout", target)
        if code != 0:
            transaction.error = f"Failed to checkout target: {stderr}"
            return False

        # Merge the task branch
        code, stdout, stderr = await self._run_git(
            "merge",
            transaction.branch_name,
            "--no-ff",
            "-m",
            f"Merge {transaction.branch_name} into {target}",
        )

        if code != 0:
            # Merge conflict - this needs manual resolution or auto-healing
            transaction.error = f"Merge conflict: {stderr}"
            logger.error(
                "transaction.merge_conflict",
                task_id=task_id,
                error=stderr,
            )
            return False

        transaction.status = TransactionStatus.MERGED

        logger.info(
            "transaction.merged",
            task_id=task_id,
            target=target,
        )

        return True

    async def rollback_transaction(self, task_id: str) -> bool:
        """Rollback a transaction and clean up.

        Args:
            task_id: The task identifier

        Returns:
            True if rolled back successfully
        """
        transaction = self._transactions.get(task_id)
        if not transaction:
            return False

        logger.info(
            "transaction.rolling_back",
            task_id=task_id,
            branch=transaction.branch_name,
        )

        # Switch back to base branch
        code, _, stderr = await self._run_git("checkout", self.base_branch)
        if code != 0:
            transaction.error = f"Failed to checkout base: {stderr}"
            return False

        # Delete the task branch
        code, _, stderr = await self._run_git("branch", "-D", transaction.branch_name)
        if code != 0:
            # Branch might already be deleted
            logger.debug(
                "transaction.branch_delete_failed",
                branch=transaction.branch_name,
            )

        transaction.status = TransactionStatus.ROLLED_BACK

        logger.info(
            "transaction.rolled_back",
            task_id=task_id,
        )

        return True

    def get_transaction(self, task_id: str) -> Transaction | None:
        """Get a transaction by task ID."""
        return self._transactions.get(task_id)

    def get_all_transactions(self) -> dict[str, Transaction]:
        """Get all active transactions."""
        return self._transactions.copy()

    async def cleanup_all(self) -> int:
        """Clean up all active transactions (rollback and remove)."""
        cleaned = 0
        for task_id in list(self._transactions.keys()):
            if await self.rollback_transaction(task_id):
                cleaned += 1
        return cleaned


class ConflictDetector:
    """Detects conflicts between transactions using AST analysis."""

    def __init__(self):
        self._previous_symbols: dict[str, dict] = {}

    def record_symbols(self, task_id: str, symbols: dict) -> None:
        """Record symbols from a transaction."""
        self._previous_symbols[task_id] = symbols

    def detect_conflicts(
        self,
        task_a: str,
        task_b: str,
    ) -> ConflictReport:
        """Detect conflicts between two transactions.

        Args:
            task_a: First task ID
            task_b: Second task ID

        Returns:
            ConflictReport with detected conflicts
        """
        symbols_a = self._previous_symbols.get(task_a, {})
        symbols_b = self._previous_symbols.get(task_b, {})

        conflicts = []
        suggestions = []
        max_severity = ConflictSeverity.NONE

        # Check for function signature changes
        func_conflicts = self._check_function_conflicts(
            symbols_a.get("functions", {}),
            symbols_b.get("functions", {}),
        )
        conflicts.extend(func_conflicts["conflicts"])
        suggestions.extend(func_conflicts["suggestions"])
        if func_conflicts["severity"] > max_severity:
            max_severity = func_conflicts["severity"]

        # Check for class/struct changes
        class_conflicts = self._check_class_conflicts(
            symbols_a.get("classes", {}),
            symbols_b.get("classes", {}),
        )
        conflicts.extend(class_conflicts["conflicts"])
        suggestions.extend(class_conflicts["suggestions"])
        if class_conflicts["severity"] > max_severity:
            max_severity = class_conflicts["severity"]

        # Check for import changes
        import_conflicts = self._check_import_conflicts(
            symbols_a.get("imports", []),
            symbols_b.get("imports", []),
        )
        conflicts.extend(import_conflicts["conflicts"])
        suggestions.extend(import_conflicts["suggestions"])
        if import_conflicts["severity"] > max_severity:
            max_severity = import_conflicts["severity"]

        return ConflictReport(
            has_conflicts=len(conflicts) > 0,
            severity=max_severity,
            conflicts=conflicts,
            suggestions=suggestions,
            auto_resolvable=max_severity in (ConflictSeverity.NONE, ConflictSeverity.LOW),
        )

    def _check_function_conflicts(
        self,
        funcs_a: dict,
        funcs_b: dict,
    ) -> dict:
        """Check for function signature conflicts."""
        conflicts = []
        suggestions = []
        severity = ConflictSeverity.NONE

        common_funcs = set(funcs_a.keys()) & set(funcs_b.keys())

        for func_name in common_funcs:
            sig_a = funcs_a[func_name].get("signature", "")
            sig_b = funcs_b[func_name].get("signature", "")

            if sig_a != sig_b:
                # Function signature changed in one branch
                conflict = {
                    "type": "function_signature",
                    "symbol": func_name,
                    "branch_a": sig_a,
                    "branch_b": sig_b,
                }
                conflicts.append(conflict)
                suggestions.append(f"Update call sites of {func_name} to match new signature")
                severity = ConflictSeverity.HIGH

        return {
            "conflicts": conflicts,
            "suggestions": suggestions,
            "severity": severity,
        }

    def _check_class_conflicts(
        self,
        classes_a: dict,
        classes_b: dict,
    ) -> dict:
        """Check for class/struct conflicts."""
        conflicts = []
        suggestions = []
        severity = ConflictSeverity.NONE

        common_classes = set(classes_a.keys()) & set(classes_b.keys())

        for class_name in common_classes:
            attrs_a = set(classes_a[class_name].get("attributes", []))
            attrs_b = set(classes_b[class_name].get("attributes", []))

            # Check for removed attributes
            removed = attrs_a - attrs_b
            if removed:
                conflicts.append(
                    {
                        "type": "class_attributes_removed",
                        "class": class_name,
                        "removed": list(removed),
                    }
                )
                suggestions.append(f"Review usage of removed attributes in {class_name}: {removed}")
                severity = ConflictSeverity.CRITICAL

            # Check for type changes
            attrs_common = attrs_a & attrs_b
            for attr in attrs_common:
                type_a = classes_a[class_name]["attributes"][attr].get("type", "")
                type_b = classes_b[class_name]["attributes"][attr].get("type", "")
                if type_a != type_b:
                    conflicts.append(
                        {
                            "type": "attribute_type_changed",
                            "class": class_name,
                            "attribute": attr,
                            "type_a": type_a,
                            "type_b": type_b,
                        }
                    )
                    suggestions.append(f"Update type annotation of {class_name}.{attr}")
                    severity = ConflictSeverity.HIGH

        return {
            "conflicts": conflicts,
            "suggestions": suggestions,
            "severity": severity,
        }

    def _check_import_conflicts(
        self,
        imports_a: list[str],
        imports_b: list[str],
    ) -> dict:
        """Check for import conflicts."""
        conflicts = []
        suggestions = []
        severity = ConflictSeverity.NONE

        # Check for same module imported differently
        # This is typically a LOW severity issue
        set_a = set(imports_a)
        set_b = set(imports_b)

        common_imports = set_a & set_b

        return {
            "conflicts": conflicts,
            "suggestions": suggestions,
            "severity": severity,
        }


__all__ = [
    "TransactionShield",
    "Transaction",
    "TransactionStatus",
    "ConflictDetector",
    "ConflictReport",
    "ConflictSeverity",
]
