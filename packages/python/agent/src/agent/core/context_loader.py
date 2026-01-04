"""
src/agent/core/context_loader.py

Phase 13.8: Configuration-Driven Context

Responsible for hydrating the Agent's context from configuration and local overrides.
Phase 13.9: Context Injection - Auto-inject Git status for zero-click awareness.
Follows the Configuration vs Code separation principle.
"""

import subprocess
from pathlib import Path
import structlog

# Reuse existing Settings class from mcp_core
from common.mcp_core.settings import get_setting
from common.mcp_core.gitops import get_project_root

logger = structlog.get_logger(__name__)


class ContextLoader:
    """Load and combine system prompts from config files."""

    def __init__(self):
        self.root = get_project_root()

    def _read_file_safe(self, rel_path: str) -> str:
        """Safely read a text file relative to project root."""
        if not rel_path:
            return ""

        full_path = self.root / rel_path
        if full_path.exists():
            try:
                return full_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Error reading prompt file {rel_path}: {e}")
                return ""
        else:
            # It's okay if user custom file doesn't exist
            if "user_custom" not in rel_path:
                logger.warning(f"Prompt file not found: {full_path}")
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
        core_path = get_setting("prompts.core_path", "agent/prompts/system_core.md")
        core_content = self._read_file_safe(core_path)

        # 2. Load User Custom (The Preferences) - from settings.yaml
        user_path = get_setting("prompts.user_custom_path", "agent/.cache/user_custom.md")
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
