"""
src/agent/core/router/sniffer.py
Context Sniffer - The Sensory System of the Router.

Phase 42: Python Implementation (Subprocess based).
Phase 45: Hybrid Architecture (Rust Core + Python Fallback).
"""

import asyncio
import os
import time
import structlog
from pathlib import Path
from typing import Optional

from common.gitops import get_project_root

logger = structlog.get_logger(__name__)

# [Phase 45] Try importing Rust Accelerator
try:
    import omni_core_rs

    RUST_AVAILABLE = True
    logger.info("🦀 Rust core (omni_core_rs) loaded successfully")
except ImportError:
    RUST_AVAILABLE = False
    logger.warning("⚠️ omni_core_rs not found. Falling back to slow Python sniffer.")


class ContextSniffer:
    """
    Fast, asynchronous environment state detector.

    Hybrid Implementation:
    - Routes to Rust core (omni_core_rs) if available
    - Falls back to pure Python implementation if Rust fails
    """

    def __init__(self):
        self.root = get_project_root()
        self._use_rust = RUST_AVAILABLE

    # -------------------------------------------------------------------------
    # Phase 45: Rust Accelerator Path
    # -------------------------------------------------------------------------
    async def _get_snapshot_rust(self) -> str:
        """DELEGATE TO RUST CORE (Release the Kraken)."""
        try:
            # Offload to thread pool because Rust IO implies GIL release in PyO3
            return await asyncio.to_thread(omni_core_rs.get_environment_snapshot, str(self.root))
        except Exception as e:
            logger.error(f"Rust sniffer crashed: {e}. Fallback to Python.", exc_info=True)
            self._use_rust = False  # Disable broken Rust module for this session
            return await self._get_snapshot_python()

    # -------------------------------------------------------------------------
    # Phase 42: Python Fallback Path (Legacy)
    # -------------------------------------------------------------------------
    async def _get_git_status_python(self) -> str:
        """
        Get concise git status (Python fallback).
        Returns: Branch name + Modified file count/names.
        """
        try:
            # 1. Get Branch
            proc_branch = await asyncio.create_subprocess_shell(
                "git rev-parse --abbrev-ref HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.root,
            )
            stdout_br, _ = await proc_branch.communicate()
            branch = stdout_br.decode().strip() or "unknown"

            # 2. Get Status (short format)
            proc_status = await asyncio.create_subprocess_shell(
                "git status --porcelain",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.root,
            )
            stdout_st, _ = await proc_status.communicate()

            status_lines = stdout_st.decode().strip().split("\n")
            status_lines = [l for l in status_lines if l.strip()]

            count = len(status_lines)
            if count == 0:
                return f"Branch: {branch} (Clean)"

            # Show up to 3 modified files
            details = ", ".join([l.strip() for l in status_lines[:3]])
            if count > 3:
                details += f", ... (+{count - 3} more)"

            return f"Branch: {branch} | Modified: {count} files ({details})"

        except Exception:
            return "Git: Unavailable"

    async def _get_active_files_python(self) -> str:
        """
        Read the Scratchpad to see what the user is focused on (Python fallback).
        """
        try:
            # Assuming standard location from Harvester/Scratchpad module
            scratchpad_path = self.root / ".memory" / "active_context" / "SCRATCHPAD.md"
            if scratchpad_path.exists():
                content = scratchpad_path.read_text(encoding="utf-8").strip()
                lines = content.split("\n")
                return f"Active Context: {len(lines)} lines in SCRATCHPAD.md"
            return "Active Context: Empty"
        except Exception:
            return "Active Context: Unknown"

    async def _get_snapshot_python(self) -> str:
        """Legacy slow snapshot (Python fallback)."""
        git_task = asyncio.create_task(self._get_git_status_python())
        files_task = asyncio.create_task(self._get_active_files_python())

        git_status, file_status = await asyncio.gather(git_task, files_task)

        return f"[ENVIRONMENT STATE]\n- {git_status}\n- {file_status}"

    # -------------------------------------------------------------------------
    # Main Interface
    # -------------------------------------------------------------------------
    async def get_snapshot(self) -> str:
        """
        Get a text snapshot of the current environment state.

        Routes to Rust or Python based on availability and performance.
        """
        start_time = time.perf_counter()

        if self._use_rust:
            result = await self._get_snapshot_rust()
            method = "Rust 🦀"
        else:
            result = await self._get_snapshot_python()
            method = "Python 🐍"

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Performance Logging (Phase 45.4 Verification)
        if duration_ms > 100:
            logger.warning(f"Sniffer ({method}) slow", duration_ms=f"{duration_ms:.2f}ms")
        else:
            logger.debug(f"Sniffer ({method})", duration_ms=f"{duration_ms:.2f}ms")

        return result


# Singleton
_sniffer_instance: Optional[ContextSniffer] = None


def get_sniffer() -> ContextSniffer:
    """Get or create the singleton ContextSniffer instance."""
    global _sniffer_instance
    if _sniffer_instance is None:
        _sniffer_instance = ContextSniffer()
    return _sniffer_instance


__all__ = ["ContextSniffer", "get_sniffer"]
