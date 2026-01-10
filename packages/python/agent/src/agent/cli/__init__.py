"""
agent/cli - Atomic CLI Module for Omni DevEnv

Phase 35.2: Modular CLI with UNIX Philosophy

Submodules:
- app.py: Typer application and configuration
- console.py: Console and output formatting
- commands/skill.py: Skill command group
- runner.py: Skill execution logic

UNIX Philosophy:
- stdout: Only skill results (pure data for pipes)
- stderr: Logs and progress (visible to user, invisible to pipes)

Usage:
    from agent.cli import app, main

    app()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .app import app, main
from .console import err_console

if TYPE_CHECKING:
    from rich.console import Console

__all__ = [
    "app",
    "main",
    "err_console",
]
