"""
omni.agent.core.common.prompts - Centralized Prompt Loading API.

Loads system prompts from the assets/prompts directory.
Zero logic for language translation - relies on LLM polyglot capabilities.

Usage:
    from omni.agent.core.common.prompts import PromptLoader

    # Load a prompt
    content = PromptLoader.load("routing/intent_protocol")

    # Load and render with variables
    content = PromptLoader.load_rendered("routing/intent_protocol", {"key": "value"})
"""

from __future__ import annotations

import structlog
from pathlib import Path
from functools import lru_cache
from typing import Dict, Optional

from omni.foundation.runtime.gitops import get_project_root
from omni.foundation.services.reference import get_conf_dir

logger = structlog.get_logger(__name__)


class PromptLoader:
    """
    Loads system prompts from the assets/prompts directory.

    Features:
    - LRU caching to minimize I/O in tight loops
    - Supports Jinja2-style variable substitution
    - Graceful fallback when prompts don't exist
    """

    @staticmethod
    def _get_prompts_dir() -> Path:
        """Get the prompts directory (assets/prompts)."""
        # Use the same resolution as other assets (reference.py)
        conf_dir = get_conf_dir()
        # If conf_dir is "assets", resolve relative to project root
        if conf_dir == "assets":
            return get_project_root() / "assets" / "prompts"
        return Path(conf_dir) / "prompts"

    @staticmethod
    @lru_cache(maxsize=64)
    def load(name: str, must_exist: bool = True) -> str:
        """
        Load a prompt by relative path.

        Args:
            name: Relative path from assets/prompts (without .md extension)
            must_exist: If True, raise error when prompt is missing

        Returns:
            Prompt content as string, or empty string if not found

        Example:
            >>> PromptLoader.load("routing/intent_protocol")
            # Loads from: assets/prompts/routing/intent_protocol.md
        """
        # Auto-complete .md extension
        filename = f"{name}.md" if not name.endswith(".md") else name
        prompts_dir = PromptLoader._get_prompts_dir()
        path = prompts_dir / filename

        if not path.exists():
            msg = f"Prompt asset missing: {path}"
            if must_exist:
                logger.error(msg)
                raise FileNotFoundError(msg)
            else:
                logger.debug(msg)
                return ""

        try:
            content = path.read_text(encoding="utf-8").strip()
            logger.debug(f"Loaded prompt asset: {name}", size=len(content))
            return content
        except Exception as e:
            logger.error(f"Failed to read prompt {name}: {e}")
            if must_exist:
                raise
            return ""

    @staticmethod
    def load_rendered(name: str, variables: Dict[str, str]) -> str:
        """
        Load a prompt and render it with variables.

        Args:
            name: Relative path from assets/prompts
            variables: Key-value pairs for template substitution

        Returns:
            Rendered prompt content
        """
        raw = PromptLoader.load(name, must_exist=False)
        if not raw:
            return ""

        # Simple variable substitution (no Jinja2 dependency)
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"  # {{key}}
            raw = raw.replace(placeholder, str(value))

        return raw

    @staticmethod
    def clear_cache() -> None:
        """Clear the LRU cache. Useful for hot-reloading during development."""
        PromptLoader.load.cache_clear()
        logger.debug("PromptLoader cache cleared")


# =============================================================================
# Convenience Functions
# =============================================================================


def get_prompt(name: str) -> str:
    """Convenience function to get a prompt."""
    return PromptLoader.load(name)


def get_prompt_path(name: str) -> Path:
    """Get the filesystem path to a prompt."""
    filename = f"{name}.md" if not name.endswith(".md") else name
    return PromptLoader._get_prompts_dir() / filename


__all__ = [
    "PromptLoader",
    "get_prompt",
    "get_prompt_path",
]
