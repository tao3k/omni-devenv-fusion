"""
src/agent/core/context_loader.py

Phase 13.8: Configuration-Driven Context

Responsible for hydrating the Agent's context from configuration and local overrides.
遵循配置与代码分离 (Configuration vs Code) 原则.
"""
from pathlib import Path
import structlog

# Reuse existing Settings class from mcp_core
from common.mcp_core.settings import get_setting

logger = structlog.get_logger(__name__)


class ContextLoader:
    """Load and combine system prompts from config files."""

    def __init__(self):
        self.root = Path(__file__).parent.parent.parent.parent  # Project root

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

    def get_combined_system_prompt(self) -> str:
        """
        Combine System Core Prompt + User Custom Prompt.

        Returns:
            Combined prompt string ready for MCP server initialization.
        """
        # 1. Load Core (The Constitution) - from settings.yaml
        core_path = get_setting("prompts.core_path", "agent/prompts/system_core.md")
        core_content = self._read_file_safe(core_path)

        # 2. Load User Custom (The Preferences) - from settings.yaml
        user_path = get_setting("prompts.user_custom_path", "agent/.cache/user_custom.md")
        user_content = self._read_file_safe(user_path)

        # 3. Combine
        combined = f"{core_content}\n\n"
        if user_content:
            combined += f"---\n{user_content}"

        return combined


# Singleton helper
def load_system_context() -> str:
    """Convenience function to load combined system context."""
    return ContextLoader().get_combined_system_prompt()
