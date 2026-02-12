"""
validator.py - Level 1 Immune Defense: Static Analysis

Uses Rust's omni-ast (ast-grep based) for high-performance security scanning.
Delegates to Rust core via the bridge for heavy pattern matching.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from omni.foundation.bridge.rust_immune import is_code_safe, scan_code_security

logger = logging.getLogger("omni.immune.validator")


class SecurityViolation:
    """Represents a security violation found during scanning."""

    def __init__(
        self,
        rule_id: str,
        description: str,
        line: int,
        snippet: str,
    ):
        self.rule_id = rule_id
        self.description = description
        self.line = line
        self.snippet = snippet

    def __repr__(self) -> str:
        return f"[{self.rule_id}] {self.description} (Line {self.line})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "line": self.line,
            "snippet": self.snippet,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SecurityViolation":
        return cls(
            rule_id=str(data.get("rule_id", "UNKNOWN")),
            description=str(data.get("description", "")),
            line=int(data.get("line", 0) or 0),
            snippet=str(data.get("snippet", "")),
        )


class StaticValidator:
    """
    Level 1 Defense: Rust-Powered Static Security Analysis.

    This validator uses omni-ast's ast-grep engine for:
    - 100x faster pattern matching than Python AST
    - Detection of forbidden imports (os, subprocess, socket, etc.)
    - Detection of dangerous calls (eval, exec, compile, etc.)
    - Detection of suspicious patterns (getattr, setattr, etc.)
    """

    @staticmethod
    def scan(file_path: Path) -> tuple[bool, list[SecurityViolation]]:
        """
        Scan a file for security violations.

        Args:
            file_path: Path to the Python file to scan

        Returns:
            Tuple of (is_safe: bool, violations: list of SecurityViolation)
        """
        try:
            source = file_path.read_text("utf-8")
            return StaticValidator.scan_content(source, file_path.name)
        except UnicodeDecodeError:
            logger.warning(f"Skipping non-UTF8 file: {file_path}")
            return True, []
        except Exception as e:
            logger.error(f"Validator error scanning {file_path}: {e}")
            return False, [SecurityViolation("VALIDATOR-ERR", str(e), 1, "")]

    @staticmethod
    def scan_content(
        content: str, filename: str = "<string>"
    ) -> tuple[bool, list[SecurityViolation]]:
        """
        Scan content directly for security violations.

        Args:
            content: Python source code string
            filename: Name for logging purposes

        Returns:
            Tuple of (is_safe: bool, violations: list of SecurityViolation)
        """
        is_safe, violations = scan_code_security(content)

        if not is_safe:
            formatted = [SecurityViolation.from_dict(v) for v in violations]
            logger.warning(
                f"[Rust Guard] {filename}: blocked by {len(formatted)} security violation(s)"
            )
            return False, formatted

        return True, []

    @staticmethod
    def quick_check(content: str) -> bool:
        """
        Quick boolean check if content is safe.

        Useful for pre-filtering before more expensive operations.
        """
        return is_code_safe(content)

    @staticmethod
    def validate_imports(content: str) -> list[str]:
        """
        Validate that imports are allowed.

        Returns list of forbidden imports found.
        """
        is_safe, violations = scan_code_security(content)
        if is_safe:
            return []
        return [v["rule_id"] for v in violations if "IMPORT" in v["rule_id"]]


# Module-level convenience
def scan_file(file_path: Path) -> tuple[bool, list[SecurityViolation]]:
    """Scan a file for security violations."""
    return StaticValidator.scan(file_path)


def scan_content(content: str, filename: str = "<string>") -> tuple[bool, list[SecurityViolation]]:
    """Scan content for security violations."""
    return StaticValidator.scan_content(content, filename)


def quick_check(content: str) -> bool:
    """Quick boolean safety check."""
    return StaticValidator.quick_check(content)


__all__ = [
    "SecurityViolation",
    "StaticValidator",
    "scan_file",
    "scan_content",
    "quick_check",
]
