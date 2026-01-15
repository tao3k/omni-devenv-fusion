"""app.py - Typer Application Configuration"""

from __future__ import annotations

import typer

from common.log_config import configure_logging

# Configure logging first (logs go to stderr per UNIX philosophy)
configure_logging(level="INFO")

app = typer.Typer(
    name="omni",
    help="Omni DevEnv - CCA Runtime Integration",
    add_completion=False,
)


def main():
    """Entry point for CLI (used by pyproject.toml entry_points)."""
    app()


# Register subcommands
from .commands import (
    register_skill_command,
    register_mcp_command,
    register_route_command,
    register_run_command,
    register_ingest_command,
)

register_skill_command(app)
register_mcp_command(app)
register_route_command(app)  # Wisdom-Aware Routing
register_run_command(app)  # Omni Loop
register_ingest_command(app)  # Ingest knowledge/skills


__all__ = ["app", "main"]
