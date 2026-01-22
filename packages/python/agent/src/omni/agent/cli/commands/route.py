"""route.py - Wisdom-Aware Routing Command (Legacy System)

This command references the old semantic routing system which has been
deprecated in favor of the new Kernel-based architecture.

The route command is temporarily disabled pending migration.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

route_app = typer.Typer(
    name="route",
    help="Wisdom-Aware Routing (Legacy System - Temporarily Disabled)",
    deprecated=True,
)


def print_disabled_banner():
    """Print disabled banner."""
    console = Console()
    banner = Panel(
        "[yellow]⚠️  Wisdom-Aware Routing has been deprecated.[/yellow]\n\n"
        "[dim]This command references the old semantic routing system.\n"
        "Routing is now handled natively by the Kernel.[/dim]\n\n"
        "[green]Note:[/green] The MCP server automatically routes requests\n"
        "to the appropriate skills based on the command name.",
        title="⚠️ Command Disabled",
        expand=False,
    )
    console.print(banner)


@route_app.callback()
def route_callback():
    """Show disabled message."""
    print_disabled_banner()
    raise typer.Exit(1)


@route_app.command("invoke", help="Test routing", deprecated=True)
def route_invoke(query: str = typer.Argument(..., help="Query to route")):
    """Test Wisdom-Aware Routing."""
    print_disabled_banner()
    raise typer.Exit(1)


@route_app.command("wisdom", help="Search wisdom", deprecated=True)
def route_wisdom(query: str = typer.Argument(..., help="Query to search")):
    """Search harvested knowledge for relevant lessons."""
    print_disabled_banner()
    raise typer.Exit(1)


@route_app.command("status", help="Show routing status", deprecated=True)
def route_status():
    """Show Wisdom-Aware Routing status."""
    print_disabled_banner()
    raise typer.Exit(1)


def register_route_command(parent_app: typer.Typer):
    """Register the route command with the parent app."""
    parent_app.add_typer(route_app, name="route")
