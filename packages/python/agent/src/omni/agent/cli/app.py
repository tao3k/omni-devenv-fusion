"""
Omni Agent CLI Entry Point (Refactored)

Responsibilities:
1. Bootstrap Environment: Parse --conf and set PRJ_CONFIG_HOME.
2. Initialize Infrastructure: Logging, Settings.
3. Dispatch Commands.
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

import typer
from typing import Any

from omni.foundation.config.dirs import PRJ_DIRS, PRJ_RUNTIME
from omni.foundation.config.logging import configure_logging

# Foundation Imports (Layer 0-2)
from omni.foundation.config.settings import get_settings, set_configuration_directory

# Command Imports
from .commands import (
    register_mcp_command,
    register_route_command,
    register_run_command,
    register_skill_command,
    register_sync_command,
)

app = typer.Typer(
    name="omni-agent",
    help="Omni Dev Fusion Agent CLI - The Neural Nexus",
    no_args_is_help=True,
    add_completion=False,
    invoke_without_command=True,
)

# Global verbose flag (set by entry_point before any command runs)
_verbose_flag: bool = False


def _get_git_commit() -> str:
    """Get the current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent,
        )
        return result.stdout.strip()[:8] if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _get_rust_version() -> str:
    """Get Rust version."""
    try:
        result = subprocess.run(
            ["rustc", "--version"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _get_package_version(package_name: str) -> str:
    """Get installed package version using importlib.metadata."""
    try:
        from importlib.metadata import version

        return version(package_name)
    except Exception:
        return "not installed"


@app.command()
def version():
    """
    Display version information and debug details.
    """
    from omni import __version__

    git_commit = _get_git_commit()
    rust_version = _get_rust_version()
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # Key dependencies
    omni_core_version = _get_package_version("omni-core")
    omni_mcp_version = _get_package_version("omni-mcp")
    langgraph_version = _get_package_version("langgraph")
    lance_version = _get_package_version("lance")

    typer.echo("=" * 60)
    typer.echo("Omni Dev Fusion - Version Info")
    typer.echo("=" * 60)
    typer.echo(f"  Omni Agent:      {__version__}")
    typer.echo(f"  Git Commit:      {git_commit}")
    typer.echo(f"  Python:          {python_version}")
    typer.echo(f"  Rust:            {rust_version}")
    typer.echo("-" * 60)
    typer.echo("  Dependencies:")
    typer.echo(f"    omni-core:     {omni_core_version}")
    typer.echo(f"    omni-mcp:      {omni_mcp_version}")
    typer.echo(f"    langgraph:     {langgraph_version}")
    typer.echo(f"    lance:         {lance_version}")
    typer.echo("=" * 60)

    # Debug info
    typer.secho("\nDebug Info:", bold=True)
    typer.echo(f"  Executable: {sys.executable}")
    typer.echo(f"  Path: {Path(sys.executable).parent}")
    typer.echo(f"  Platform: {sys.platform}")

    # Settings location
    settings = get_settings()
    typer.echo(f"\nConfig Location: {getattr(settings, '_config_dir', 'default')}")
    typer.echo(f"Cache Location: {PRJ_RUNTIME('agent')}")
    typer.echo("")


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

    # Store verbose flag globally for subcommands to check
    global _verbose_flag
    _verbose_flag = verbose

    # Ensure Runtime Directories Exist
    try:
        PRJ_RUNTIME.ensure_dir("logs")
        PRJ_RUNTIME.ensure_dir("sockets")
        PRJ_RUNTIME.ensure_dir("pids")
    except Exception as e:
        if verbose:
            typer.secho(f"Warning: Could not create runtime dirs: {e}", fg=typer.colors.YELLOW)


def _is_verbose() -> bool:
    """Check if verbose mode is enabled (checks global flag)."""
    return _verbose_flag


def _verbose_callback(ctx: typer.Context, param: Any, value: bool) -> None:
    """Callback to set verbose flag when --verbose/-v is used."""
    global _verbose_flag
    if value:
        _verbose_flag = True
        # Reconfigure logging immediately if already configured
        try:
            configure_logging(level="DEBUG")
        except Exception:
            pass  # Logging might not be configured yet


@app.callback()
def main(
    ctx: typer.Context,
    conf: str | None = typer.Option(
        None,
        "--conf",
        "-c",
        help="Path to custom configuration directory (Sets PRJ_CONFIG_HOME)",
        envvar="OMNI_CONF",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging",
        is_eager=True,
        callback=_verbose_callback,
    ),
):
    """
    Initialize the Agent Environment.

    Global Options:
        --conf, -c     Custom configuration directory
        --verbose, -v  Enable debug logging
    """
    # Bootstrap is handled in entry_point() for proper parameter passing
    pass


# Register subcommands
register_skill_command(app)
register_mcp_command(app)
register_route_command(app)
register_run_command(app)
register_sync_command(app)


def entry_point():
    """Entry point for CLI (used by pyproject.toml entry_points).

    Pre-parses global options (--verbose, -v, --conf, -c) before Typer takes over,
    ensuring logging is configured BEFORE any command runs.
    """
    import sys

    # Pre-parse to detect --verbose and --conf before Typer takes over
    conf = None
    verbose = False
    argv = sys.argv[1:] if len(sys.argv) > 1 else ["--help"]

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--verbose", "-v"):
            verbose = True
            argv.pop(i)
            continue
        elif arg in ("--conf", "-c") and i + 1 < len(argv):
            conf = argv[i + 1]
            argv.pop(i + 1)
            argv.pop(i)
            continue
        elif arg.startswith("--conf="):
            conf = arg.split("=", 1)[1]
            argv.pop(i)
            continue
        i += 1

    # Bootstrap configuration (logging) BEFORE any command runs
    _bootstrap_configuration(conf, verbose)

    # Restore argv and invoke app
    sys.argv = ["omni"] + argv

    try:
        app()
    except SystemExit:
        # Typer may call sys.exit(), let it pass through
        pass


if __name__ == "__main__":
    entry_point()


__all__ = ["app", "entry_point", "main", "_is_verbose"]
