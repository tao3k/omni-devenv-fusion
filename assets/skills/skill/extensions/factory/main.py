"""
main.py
 The Main Entry Point for the Adaptation Factory Extension

Lives in assets/skills/skill/extensions/factory/main.py
This is the entry point exposed to the CLI plugin.

Usage (from CLI plugin):
    from factory.main import run
    await run(requirement, debug=debug)
"""

import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel

console = Console()


async def run(
    requirement: str,
    debug: bool = False,
    auto_load: bool = True,
) -> dict[str, Any]:
    """
    The main execution flow exposed to the CLI plugin.

    Args:
        requirement: Natural language description of the skill to generate
        debug: Enable debug logging
        auto_load: Whether to auto-load the generated skill

    Returns:
        Dict with success status and result details
    """
    from .core import MetaAgent
    from .result import GenerationResult

    console.print(
        Panel(
            f"[bold]🏭 Adaptation Factory[/bold]\nTarget: [cyan]{requirement}[/cyan]",
            title="Meta-Agent v2.0",
            expand=False,
        )
    )

    if debug:
        console.print("[dim]🔧 Debug mode enabled[/dim]")

    # Initialize the Meta-Agent
    agent = MetaAgent()

    # Execute the generation loop
    result = await agent.generate_skill(requirement)

    # Format output
    if result.success:
        console.print(
            Panel(
                f"[green]✅ SUCCESS[/green]\n"
                f"Skill: [bold]{result.skill_name}[/bold]\n"
                f"Location: {result.path}",
                title="Generation Complete",
                expand=False,
            )
        )

        return {
            "success": True,
            "skill_name": result.skill_name,
            "path": str(result.path) if result.path else None,
            "duration_ms": result.duration_ms,
        }
    else:
        console.print(
            Panel(
                f"[red]❌ FAILURE[/red]\nError: {result.error}",
                title="Generation Failed",
                expand=False,
            )
        )

        return {
            "success": False,
            "skill_name": result.skill_name,
            "error": result.error,
            "duration_ms": result.duration_ms,
        }


def main():
    """
    CLI entry point when running this module directly.
    """
    import asyncio
    import typer

    app = typer.Typer(
        name="factory",
        help="Adaptation Factory - Generate new skills from natural language",
    )

    @app.command()
    def generate(
        requirement: str = typer.Argument(..., help="Skill requirement description"),
        debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output"),
        auto_load: bool = typer.Option(
            True, "--auto-load/--no-auto-load", help="Auto-load generated skill"
        ),
    ):
        """Generate a new skill from a requirement."""
        result = asyncio.run(run(requirement, debug=debug, auto_load=auto_load))
        sys.exit(0 if result["success"] else 1)

    @app.command()
    def harvest(
        min_frequency: int = typer.Option(2, "--min-freq", "-f", help="Minimum pattern frequency"),
        limit: int = typer.Option(5, "--limit", "-l", help="Maximum suggestions"),
    ):
        """Harvest skill patterns from session history."""
        from .core import MetaAgent

        console.print("[bold]🔍 Harvesting skill patterns...[/bold]")
        agent = MetaAgent()
        suggestions = asyncio.run(
            agent.harvest_and_suggest(min_frequency=min_frequency, limit=limit)
        )

        if not suggestions:
            console.print("[yellow]No patterns found.[/yellow]")
            return

        console.print(f"[green]Found {len(suggestions)} suggestions:[/green]")
        for i, s in enumerate(suggestions, 1):
            console.print(f"  {i}. [bold]{s['name']}[/bold] - {s['description']}")

    app()


if __name__ == "__main__":
    main()
