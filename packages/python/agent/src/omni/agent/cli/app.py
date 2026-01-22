"""
Omni Agent CLI Entry Point (Refactored)

Responsibilities:
1. Bootstrap Environment: Parse --conf and set PRJ_CONFIG_HOME.
2. Initialize Infrastructure: Logging, Settings.
3. Dispatch Commands.
"""

from __future__ import annotations

import os
from typing import Optional

import typer

# Foundation Imports (Layer 0-2)
from omni.foundation.config.settings import get_settings, set_configuration_directory
from omni.foundation.config.logging import configure_logging
from omni.foundation.config.dirs import PRJ_RUNTIME, PRJ_DIRS

# Command Imports
from .commands import (
    register_ingest_command,
    register_mcp_command,
    register_route_command,
    register_run_command,
    register_skill_command,
)

app = typer.Typer(
    name="omni-agent",
    help="Omni Dev Fusion Agent CLI - The Neural Nexus",
    no_args_is_help=True,
    add_completion=False,
)


def _bootstrap_configuration(
    conf_path: str | None,
    verbose: bool = False,
) -> None:
    """
    Core Bootstrap Logic.

    Strategy:
    If user provides --conf, we treat that directory as the new PRJ_CONFIG_HOME.
    This effectively "mounts" the user's config directory into the system's
    standard location via environment variables.
    """
    from pathlib import Path

    if conf_path:
        path_obj = Path(conf_path).resolve()
        if not path_obj.exists():
            typer.secho(f"Warning: Config directory not found: {path_obj}", fg=typer.colors.YELLOW)

        # 1. Set the global environment pointer
        os.environ["PRJ_CONFIG_HOME"] = str(path_obj)

        # 2. Update Foundation layer
        set_configuration_directory(str(path_obj))

        # 3. Clear Directory Cache (Crucial!)
        PRJ_DIRS.clear_cache()

        # 4. Reload Settings
        get_settings().reload()

        typer.secho(f"Configuration loaded from: {path_obj}", fg=typer.colors.BRIGHT_BLACK)

    # Configure Logging (always run)
    settings = get_settings()
    log_level = settings.get("logging.level", "INFO")
    if verbose:
        log_level = "DEBUG"

    configure_logging(level=log_level)

    # Ensure Runtime Directories Exist
    try:
        PRJ_RUNTIME.ensure_dir("logs")
        PRJ_RUNTIME.ensure_dir("sockets")
        PRJ_RUNTIME.ensure_dir("pids")
    except Exception as e:
        if verbose:
            typer.secho(f"Warning: Could not create runtime dirs: {e}", fg=typer.colors.YELLOW)


@app.callback()
def main(
    conf: Optional[str] = typer.Option(
        None,
        "--conf",
        "-c",
        help="Path to custom configuration directory (Sets PRJ_CONFIG_HOME)",
        envvar="OMNI_CONF",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    """
    Initialize the Agent Environment.
    """
    # Bootstrap is handled in entry_point() for proper parameter passing
    pass


# Register subcommands
register_skill_command(app)
register_mcp_command(app)
register_route_command(app)
register_run_command(app)
register_ingest_command(app)


def entry_point():
    """Entry point for CLI (used by pyproject.toml entry_points)."""
    # Run bootstrap before parsing
    from omni.foundation.config.settings import Settings
    from omni.foundation.config.dirs import PRJ_DIRS

    # Parse arguments manually to get --conf and --verbose before Typer takes over
    conf = None
    verbose = False

    import sys

    for i, arg in enumerate(sys.argv[1:]):
        if arg in ("--conf", "-c") and i + 2 < len(sys.argv):
            conf = sys.argv[i + 2]
        elif arg.startswith("--conf="):
            conf = arg.split("=", 1)[1]
        elif arg in ("--verbose", "-v"):
            verbose = True

    # Run bootstrap
    _bootstrap_configuration(conf, verbose)

    # Then invoke app
    app()


if __name__ == "__main__":
    entry_point()


__all__ = ["app", "entry_point", "main"]
