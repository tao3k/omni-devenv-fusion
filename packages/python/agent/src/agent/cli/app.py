"""
app.py - Typer Application Configuration

Phase 35.2: Modular CLI Architecture

Provides the main Typer application instance and entry point.
"""

from __future__ import annotations

import typer

from common.log_config import configure_logging

# Configure logging first (logs go to stderr per UNIX philosophy)
configure_logging(level="INFO")

app = typer.Typer(
    name="omni",
    help="Omni DevEnv - Phase 35.2 Modular CLI",
    add_completion=False,
)


def main():
    """Entry point for CLI (used by pyproject.toml entry_points)."""
    app()


# Register subcommands
from .commands import register_skill_command, register_mcp_command

register_skill_command(app)
register_mcp_command(app)


__all__ = ["app", "main"]
