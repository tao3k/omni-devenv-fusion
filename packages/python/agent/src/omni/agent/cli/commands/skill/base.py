# agent/cli/commands/skill/base.py
"""
Base module for skill CLI commands.

Contains shared utilities and the Typer app instance.
"""

from __future__ import annotations

import typer
from rich.panel import Panel

from omni.foundation.config.skills import SKILLS_DIR

from ...console import cli_log_handler, err_console, print_result
from ...runner import run_skills

# Main skill app
skill_app = typer.Typer(help="Skill management commands")


def _load_templates_module():
    """Load templates module directly from file."""
    import importlib.util

    # SSOT: Use SKILLS_DIR for skill template path
    templates_path = SKILLS_DIR(skill="skill", filename="scripts/templates.py")
    if not templates_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("templates", str(templates_path))
    if spec is None or spec.loader is None:
        return None
    templates = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(templates)
    return templates


__all__ = [
    "skill_app",
    "err_console",
    "print_result",
    "cli_log_handler",
    "run_skills",
    "SKILLS_DIR",
    "Panel",
    "_load_templates_module",
]
