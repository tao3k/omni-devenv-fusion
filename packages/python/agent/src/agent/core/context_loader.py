"""
src/agent/core/context_loader.py

Phase 48: Hyper-Context Loader (Rust Accelerated).
Phase 13.8: Configuration-Driven Context (Legacy)

Upgraded to use omni_core_rs for:
- Safe file reading with binary detection and size limits
- GIL release pattern for concurrent file operations

[Phase 48.1] Legacy fallback removed - Full Rust adoption.
"""

import subprocess
from pathlib import Path
import structlog

from common.config.settings import get_setting
from common.gitops import get_project_root

# [Phase 48] Import Rust Core
import omni_core_rs

logger = structlog.get_logger(__name__)

# Default file size limit (100KB per file)
DEFAULT_MAX_FILE_SIZE = 100 * 1024


class ContextLoader:
    """
    Load and combine system prompts from configuration and local overrides.
    Phase 48: Rust-accelerated file reading with safety checks.
    [Phase 48.1] Pure Rust implementation - no legacy fallback.
    """

    def __init__(self, max_file_size: int = DEFAULT_MAX_FILE_SIZE):
        self.root = get_project_root()
        self.max_file_size = max_file_size

    def _read_file_safe(self, rel_path: str) -> str:
        """
        Safely read a text file relative to project root.
        Uses omni_core_rs.read_file_safe for:
        - Size limit (returns error if too big)
        - Binary detection (returns error if binary)
        - Encoding (lossy utf-8 fallback)
        """
        if not rel_path:
            return ""

        full_path = self.root / rel_path
        if not full_path.exists():
            # It's okay if user custom file doesn't exist
            if "user_custom" not in rel_path:
                logger.warning(f"Prompt file not found: {full_path}")
            return ""

        # [Phase 48] Pure Rust path - no fallback
        try:
            return omni_core_rs.read_file_safe(str(full_path), self.max_file_size)
        except Exception as e:
            logger.error(f"Error reading prompt file {rel_path}: {e}")
            return ""

    def _get_git_status_summary(self) -> str:
        """
        [Context Injection] Auto-inject Git status for zero-click awareness.
        Read-only, fast, no MCP tool call needed.
        """
        try:
            # 1. Get current branch
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                cwd=self.root,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()

            # 2. Get short status
            status = subprocess.check_output(
                ["git", "status", "--short"], cwd=self.root, text=True, stderr=subprocess.DEVNULL
            ).strip()

            if not status:
                return f"🟢 Git Branch: `{branch}` (Clean)"

            # Limit output to prevent context explosion
            lines = status.split("\n")
            if len(lines) > 15:
                display = "\n".join(lines[:15]) + f"\n... ({len(lines) - 15} more files)"
            else:
                return f"🔶 Git Branch: `{branch}`\n{status}"

            return f"🔶 Git Branch: `{branch}`\n{display}"

        except subprocess.CalledProcessError:
            return "⚪ Git Status: Not a git repository"
        except Exception as e:
            return f"⚪ Git Status: Error - {str(e)}"

    def get_combined_system_prompt(self) -> str:
        """
        Combine System Core Prompt + User Custom Prompt.
        Phase 13.9: Auto-inject Git status for zero-click awareness.

        Returns:
            Combined prompt string ready for MCP server initialization.
        """
        # 1. Load Core (The Constitution) - from settings.yaml
        core_path = get_setting("prompts.core_path", "assets/prompts/system_core.md")
        core_content = self._read_file_safe(core_path)

        # 2. Load User Custom (The Preferences) - from settings.yaml
        user_path = get_setting("prompts.user_custom_path", ".cache/user_custom.md")
        user_content = self._read_file_safe(user_path)

        # 3. [Phase 13.9] Inject Git Status (Context Injection)
        git_status = self._get_git_status_summary()

        # 4. Combine with placeholders
        combined = core_content.replace("{{git_status}}", git_status)
        combined += "\n\n"
        if user_content:
            combined += f"---\n{user_content}"

        return combined


# Singleton helper
def load_system_context() -> str:
    """Convenience function to load combined system context."""
    return ContextLoader().get_combined_system_prompt()
