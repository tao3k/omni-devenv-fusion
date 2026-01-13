"""
src/agent/core/router/sniffer.py
Context Sniffer - The Sensory System of the Router.

Phase 42: Provides real-time environment snapshots (Git status, active files)
to the Semantic Router to prevent hallucinated actions.
"""
import asyncio
import os
from pathlib import Path
from typing import Optional

from common.gitops import get_project_root


class ContextSniffer:
    """
    Fast, asynchronous environment state detector.
    """

    def __init__(self):
        self.root = get_project_root()

    async def _get_git_status(self) -> str:
        """
        Get concise git status.
        Returns: Branch name + Modified file count/names.
        """
        try:
            # 1. Get Branch
            proc_branch = await asyncio.create_subprocess_shell(
                "git rev-parse --abbrev-ref HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.root
            )
            stdout_br, _ = await proc_branch.communicate()
            branch = stdout_br.decode().strip() or "unknown"

            # 2. Get Status (short format)
            proc_status = await asyncio.create_subprocess_shell(
                "git status --porcelain",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.root
            )
            stdout_st, _ = await proc_status.communicate()

            status_lines = stdout_st.decode().strip().split('\n')
            status_lines = [l for l in status_lines if l.strip()]

            count = len(status_lines)
            if count == 0:
                return f"Branch: {branch} (Clean)"

            # Show up to 3 modified files
            details = ", ".join([l.strip() for l in status_lines[:3]])
            if count > 3:
                details += f", ... (+{count-3} more)"

            return f"Branch: {branch} | Modified: {count} files ({details})"

        except Exception:
            return "Git: Unavailable"

    async def _get_active_files(self) -> str:
        """
        Read the Scratchpad to see what the user is focused on.
        """
        try:
            # Assuming standard location from Harvester/Scratchpad module
            scratchpad_path = self.root / ".memory" / "active_context" / "SCRATCHPAD.md"
            if scratchpad_path.exists():
                content = scratchpad_path.read_text(encoding="utf-8").strip()
                lines = content.split('\n')
                # Extract simple summary (first few lines or specific section)
                # For now, just return presence
                return f"Active Context: {len(lines)} lines in SCRATCHPAD.md"
            return "Active Context: Empty"
        except Exception:
            return "Active Context: Unknown"

    async def get_snapshot(self) -> str:
        """
        Get a text snapshot of the current environment state.
        Parallelizes IO operations.
        """
        git_task = asyncio.create_task(self._get_git_status())
        files_task = asyncio.create_task(self._get_active_files())

        git_status, file_status = await asyncio.gather(git_task, files_task)

        return f"""[ENVIRONMENT STATE]
- {git_status}
- {file_status}"""


# Singleton
_sniffer_instance: Optional[ContextSniffer] = None


def get_sniffer() -> ContextSniffer:
    """Get or create the singleton ContextSniffer instance."""
    global _sniffer_instance
    if _sniffer_instance is None:
        _sniffer_instance = ContextSniffer()
    return _sniffer_instance


__all__ = ["ContextSniffer", "get_sniffer"]
