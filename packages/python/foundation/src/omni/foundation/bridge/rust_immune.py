"""
rust_immune.py - Rust Core Bridge for Immune System

Provides high-performance security scanning and sandbox execution
by bridging to omni-ast and omni-security Rust crates.

Exports:
- scan_code_security(): AST-based security analysis
- run_sandbox(): Isolated script execution (Docker/NsJail)
- is_code_safe(): Quick boolean safety check
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.immune.bridge")

# Try to import Rust bindings
try:
    import omni_core_rs

    _RUST_AVAILABLE = True
    logger.info("Rust core bindings loaded successfully")
except ImportError:
    _RUST_AVAILABLE = False
    logger.warning("Rust core bindings not available - immune system will use Python fallbacks")


class RustImmuneBridge:
    """
    Gateway to Rust Core Security Features.

    Level 1: Static Analysis via omni-ast (ast-grep based)
    Level 2: Dynamic Execution via omni-security (Docker/NsJail)
    """

    @staticmethod
    def is_available() -> bool:
        """Check if Rust core is available."""
        return _RUST_AVAILABLE

    # =============================================================================
    # Level 1: Static Security Analysis (omni-ast)
    # =============================================================================

    @staticmethod
    def scan_code_security(code: str) -> tuple[bool, list[dict[str, Any]]]:
        """
        Scan Python code for security violations using omni-ast.

        Detects:
        - Forbidden imports: os, subprocess, socket, ctypes, etc.
        - Dangerous calls: eval(), exec(), compile(), etc.
        - Suspicious patterns: getattr(), setattr(), globals(), etc.

        Args:
            code: Python source code to scan

        Returns:
            Tuple of (is_safe: bool, violations: list of violation dicts)
        """
        if not _RUST_AVAILABLE:
            raise RuntimeError("Rust core bindings not available. Run: just build-rust-dev")

        # Call Rust binding: returns list of (rule_id, description, line, snippet)
        violations = omni_core_rs.scan_code_security(code)

        if violations:
            formatted = [
                {
                    "rule_id": rule_id,
                    "description": description,
                    "line": line,
                    "snippet": snippet,
                }
                for rule_id, description, line, snippet in violations
            ]
            logger.warning(
                f"[Rust Guard] Blocked code with {len(violations)} security violation(s)"
            )
            return False, formatted

        return True, []

    @staticmethod
    def is_code_safe(code: str) -> bool:
        """Quick boolean check if code is safe (no violations)."""
        if not _RUST_AVAILABLE:
            raise RuntimeError("Rust core bindings not available. Run: just build-rust-dev")

        try:
            return omni_core_rs.is_code_safe(code)
        except Exception:
            return False

    # =============================================================================
    # Level 2: Sandbox Execution (omni-security)
    # =============================================================================

    @staticmethod
    def run_sandbox(script_path: str) -> dict[str, Any]:
        """
        Execute a Python script in an isolated sandbox (Docker or NsJail).

        Args:
            script_path: Path to the Python script to execute

        Returns:
            Dict with:
                - success: bool
                - exit_code: int
                - stdout: str
                - stderr: str
                - duration_ms: int
        """
        if not _RUST_AVAILABLE:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "Sandbox unavailable: Rust core not loaded",
                "duration_ms": 0,
            }

        try:
            runner = omni_core_rs.PySandboxRunner()

            if not runner.is_available():
                return {
                    "success": False,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "Sandbox runtime (Docker/NsJail) not found on this system",
                    "duration_ms": 0,
                }

            result = runner.run_python(script_path)

            return {
                "success": result.success,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_ms": result.duration_ms,
            }

        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Sandbox Error: {str(e)}",
                "duration_ms": 0,
            }

    @staticmethod
    def check_permission(tool_name: str, permissions: list[str]) -> bool:
        """
        Check if a tool execution is allowed by the permission gate.

        Args:
            tool_name: Full tool name (e.g., "filesystem.read_file")
            permissions: List of permission patterns (e.g., ["filesystem:*", "git:status"])

        Returns:
            True if allowed, False otherwise
        """
        if not _RUST_AVAILABLE:
            # Default: allow if permissions list is non-empty (Zero Trust fallback)
            return len(permissions) > 0

        try:
            return omni_core_rs.check_permission(tool_name, permissions)
        except Exception:
            return False


# Module-level convenience functions
def scan_code_security(code: str) -> tuple[bool, list[dict[str, Any]]]:
    """Scan code for security violations."""
    return RustImmuneBridge.scan_code_security(code)


def is_code_safe(code: str) -> bool:
    """Quick check if code is safe."""
    return RustImmuneBridge.is_code_safe(code)


def run_sandbox(script_path: str) -> dict[str, Any]:
    """Execute script in sandbox."""
    return RustImmuneBridge.run_sandbox(script_path)


def check_permission(tool_name: str, permissions: list[str]) -> bool:
    """Check tool permission."""
    return RustImmuneBridge.check_permission(tool_name, permissions)


def is_rust_available() -> bool:
    """Check if Rust core is available."""
    return RustImmuneBridge.is_available()


__all__ = [
    "RustImmuneBridge",
    "scan_code_security",
    "is_code_safe",
    "run_sandbox",
    "check_permission",
    "is_rust_available",
]
