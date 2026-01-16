# agent/cli/commands/skill/__init__.py
"""
Skill Command Group Package.

Modular CLI Architecture for skill management.

Commands are organized into modules:
- query.py: list, discover, info, search commands
- manage.py: run, install, update, test, check commands
- index_cmd.py: reindex, sync, index-stats, watch commands
- create.py: templates, create commands
"""

from __future__ import annotations

import typer

# Import the skill_app from base
from .base import skill_app

# Import all command modules to register commands with skill_app
from . import query  # noqa: F401
from . import manage  # noqa: F401
from . import index_cmd  # noqa: F401
from . import create  # noqa: F401

# Re-export specific commands for backward compatibility
from .query import skill_discover


def register_skill_command(app_instance: typer.Typer) -> None:
    """Register skill subcommand with the main app."""
    app_instance.add_typer(skill_app, name="skill")


__all__ = ["skill_app", "register_skill_command"]
