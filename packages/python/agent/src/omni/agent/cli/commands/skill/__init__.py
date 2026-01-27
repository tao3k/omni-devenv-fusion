# agent/cli/commands/skill/__init__.py
"""
Skill Command Group Package.

Modular CLI Architecture for skill management.

Commands are organized into modules:
- analyze.py: Analytics using Arrow-native operations
- query.py: list, discover, info, search commands
- manage.py: run, install, update, test, check commands
- index_cmd.py: reindex, sync, index-stats, watch commands
- generate.py: AI-powered skill generation (Meta-Agent)
"""

from __future__ import annotations

import typer

# Import all command modules to register commands with skill_app
from . import (
    analyze,  # noqa: F401 - Arrow-native analytics
    generate,  # noqa: F401 - Meta-Agent skill generation
    index_cmd,  # noqa: F401
    manage,  # noqa: F401
    query,  # noqa: F401
)

# Import the skill_app from base
from .base import skill_app

# Re-export specific commands for backward compatibility
from .query import skill_discover


def register_skill_command(app_instance: typer.Typer) -> None:
    """Register skill subcommand with the main app."""
    app_instance.add_typer(skill_app, name="skill")


__all__ = ["register_skill_command", "skill_app"]
