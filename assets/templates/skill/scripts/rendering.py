"""
{{ skill_name }}/scripts/rendering.py - Rendering Layer (Phase 35.2)

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

import jinja2
from pathlib import Path
from functools import lru_cache
from datetime import datetime
from typing import Optional, List, Dict, Any


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
    checks: Optional[List[str]] = None,
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
    suggestion: Optional[str] = None,
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


def list_templates() -> List[str]:
    """List available templates."""
    try:
        env = _get_jinja_env()
        return [t.name for t in env.list_templates() if t.endswith(".j2")]
    except FileNotFoundError:
        return []
