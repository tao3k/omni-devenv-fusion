# agent/cli/commands/skill/base.py
"""
Base module for skill CLI commands.

Contains shared utilities and the Typer app instance.
"""

from __future__ import annotations

import typer

from rich.panel import Panel

from common.skills_path import SKILLS_DIR

from ...console import cli_log_handler, print_result, err_console
from ...runner import run_skills

# Main skill app
skill_app = typer.Typer(help="Skill management commands")


def _load_templates_module():
    """Load templates module directly from file."""
    import importlib.util
    from pathlib import Path

    templates_path = Path("assets/skills/skill/scripts/templates.py")
    if not templates_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("templates", templates_path)
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
