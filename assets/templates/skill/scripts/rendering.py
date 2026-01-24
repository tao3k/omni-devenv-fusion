"""
{{ skill_name }}/scripts/rendering.py - Rendering Layer

Jinja2 templates for structured output.

Architecture:
    workflow.py  -> Logic (preparation, validation)
    rendering.py -> Presentation (Jinja2 templates)

Usage:
    from .rendering import render_result

    result = render_result(
        subject="Feature description",
        body="Detailed description",
        verified=True
    )
"""

from datetime import datetime
from functools import lru_cache
from pathlib import Path

import jinja2

_TEMPLATES_BASE = Path(__file__).parent.parent.parent.parent / "assets" / "templates"


@lru_cache(maxsize=1)
def _get_jinja_env() -> jinja2.Environment:
    """Get cached Jinja2 environment."""
    skill_templates = _TEMPLATES_BASE / "{{ skill_name }}"
    if not skill_templates.exists():
        raise FileNotFoundError(f"Templates not found: {skill_templates}")
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(skill_templates)),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_result(
    subject: str,
    body: str = "",
    verified: bool = True,
    checks: list[str] | None = None,
) -> str:
    """Render result using Jinja2 template."""
    env = _get_jinja_env()
    try:
        template = env.get_template("result.j2")
        return template.render(
            subject=subject,
            body=body,
            verified=verified,
            checks=checks or [],
            timestamp=datetime.now().isoformat(),
        )
    except jinja2.TemplateNotFound:
        # Fallback to simple format if template not found
        return f"# {subject}\n\n{body}"


def render_error(
    error_type: str,
    message: str,
    suggestion: str | None = None,
) -> str:
    """Render error message."""
    env = _get_jinja_env()
    try:
        template = env.get_template("error.j2")
        return template.render(
            error_type=error_type,
            message=message,
            suggestion=suggestion,
            timestamp=datetime.now().isoformat(),
        )
    except jinja2.TemplateNotFound:
        return f"Error [{error_type}]: {message}"


def list_templates() -> list[str]:
    """List available templates."""
    try:
        env = _get_jinja_env()
        return [t.name for t in env.list_templates() if t.endswith(".j2")]
    except FileNotFoundError:
        return []
