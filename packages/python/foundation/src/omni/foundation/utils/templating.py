"""
omni.foundation.templating - Jinja2 Template Engine

Lightweight template rendering for skill prompts and text generation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2

logger = __import__("logging").getLogger(__name__)


class TemplateEngine:
    """Jinja2-based template engine for skill rendering."""

    def __init__(self, search_paths: list[Path] | None = None) -> None:
        """Initialize template engine.

        Args:
            search_paths: List of paths to search for templates.
        """
        self.loader = jinja2.FileSystemLoader(search_paths or [])
        self.env = jinja2.Environment(
            loader=self.loader,
            autoescape=False,  # Safe for raw text generation
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template file.

        Args:
            template_name: Name of the template file.
            context: Variables to pass to the template.

        Returns:
            Rendered template string.
        """
        template = self.env.get_template(template_name)
        return template.render(**context)

    def render_string(self, source: str, context: dict[str, Any]) -> str:
        """Render a template string.

        Args:
            source: Template source string.
            context: Variables to pass to the template.

        Returns:
            Rendered template string.
        """
        template = self.env.from_string(source)
        return template.render(**context)


# Global template engine instance
_engine: TemplateEngine | None = None


def get_engine() -> TemplateEngine:
    """Get the global template engine instance."""
    global _engine
    if _engine is None:
        _engine = TemplateEngine()
    return _engine


def render_string(source: str, **kwargs) -> str:
    """Render a template string using the global engine.

    Args:
        source: Template source string.
        **kwargs: Variables to pass to the template.

    Returns:
        Rendered template string.
    """
    return get_engine().render_string(source, kwargs)
