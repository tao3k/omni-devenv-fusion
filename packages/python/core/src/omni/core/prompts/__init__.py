"""
inject_prompt.py - Prompt Injection Utilities

Provides utilities for injecting prompts into the cognitive context system.

Usage:
    from omni.core.prompts import inject_prompt, load_prompt

    # Inject a prompt into a content string
    content = inject_prompt("Your content here", category="knowledge")

    # Load and inject a prompt from a file
    content = load_prompt("assets/prompts/system_core.md", category="system")

    # Inject with custom tag
    content = load_prompt(
        "assets/prompts/custom.md",
        tag="<custom_prompt>{content}</custom_prompt>"
    )
"""

from pathlib import Path
from typing import Optional

# Default prompt categories and their tags
PROMPT_TAGS = {
    "knowledge": "<knowledge_system>\n{content}\n</knowledge_system>",
    "system": "<system_context>\n{content}\n</system_context>",
    "persona": "<persona>\n{content}\n</persona>",
    "custom": "{content}",
}


def inject_prompt(content: str, category: str = "custom", **kwargs) -> str:
    """Inject content into a prompt tag.

    Args:
        content: The content to inject
        category: Category determines the wrapper tag (knowledge, system, persona, custom)
        **kwargs: Additional template variables

    Returns:
        Content wrapped in the appropriate tag
    """
    tag = PROMPT_TAGS.get(category, PROMPT_TAGS["custom"])
    return tag.format(content=content, **kwargs)


def load_prompt(
    path: str,
    category: str = "custom",
    tag: Optional[str] = None,
    encoding: str = "utf-8",
) -> str:
    """Load a prompt from a file and inject it.

    Args:
        path: Path to the prompt file (relative to project root or absolute)
        category: Category determines the wrapper tag
        tag: Custom tag format (overrides category)
        encoding: File encoding (default: utf-8)

    Returns:
        Loaded content wrapped in tag, or empty string if file not found
    """
    prompt_path = Path(path)
    if not prompt_path.is_absolute():
        try:
            from omni.foundation.runtime.gitops import get_project_root

            _root = get_project_root()
        except Exception:
            _root = Path.cwd()
        prompt_path = _root / prompt_path

    if not prompt_path.exists():
        return ""

    content = prompt_path.read_text(encoding=encoding)

    if tag:
        return tag.format(content=content)
    return inject_prompt(content, category)


def merge_prompts(*prompts: str, separator: str = "\n\n") -> str:
    """Merge multiple prompt strings together.

    Args:
        *prompts: Variable number of prompt strings
        separator: String to use between prompts (default: double newline)

    Returns:
        Merged prompt string
    """
    return separator.join(p for p in prompts if p)


def load_and_merge(
    *paths: str,
    category: str = "custom",
    separator: str = "\n\n",
) -> str:
    """Load multiple prompt files and merge them.

    Args:
        *paths: Paths to prompt files
        category: Category for all prompts
        separator: String between prompts

    Returns:
        Merged prompt string
    """
    prompts = [load_prompt(p, category=category) for p in paths]
    return merge_prompts(*prompts, separator=separator)


__all__ = [
    "inject_prompt",
    "load_prompt",
    "merge_prompts",
    "load_and_merge",
    "PROMPT_TAGS",
]
