"""
route.py - Router Test Command

Test the Hybrid Router with semantic + keyword search and caching.

Usage:
    omni route test "git commit"           # Test routing for a query
    omni route test "git commit" --debug   # Show detailed scoring
    omni route stats                       # Show router statistics
    omni route cache                       # Show cache stats
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..console import err_console

route_app = typer.Typer(
    name="route",
    help="Router testing and diagnostics",
)

console = Console()


@route_app.command("test")
def test_route(
    query: str = typer.Argument(..., help="User intent to route"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Show detailed scoring"),
    limit: int = typer.Option(5, "-n", "--number", help="Maximum results"),
    threshold: float = typer.Option(
        0.4, "-t", "--threshold", help="Score threshold (default: 0.4, lower for more results)"
    ),
) -> None:
    """
    Test the Hybrid Router logic for a query.

    Shows which tools/skills would be matched for the given query,
    along with their semantic and keyword scores.
    """
    try:
        from omni.core.router.hybrid_search import HybridSearch
    except ImportError as e:
        console.print(f"[red]Error: Could not import router module: {e}[/]")
        raise typer.Exit(1)

    import asyncio

    async def run_test():
        search = HybridSearch()
        results = await search.search(
            query=query,
            limit=limit,
            min_score=threshold,
        )

        # Display results
        if not results:
            console.print("[yellow]No matches found for this query.[/]")
            console.print("[dim]Try lowering the threshold or using different keywords.[/dim]")
            return

        # Create results table
        table = Table(title=f"Routing Results for: {query}")
        table.add_column("Tool", style="cyan")
        table.add_column("Score", style="magenta")
        table.add_column("Confidence", style="blue")

        if debug:
            table.add_column("Details", style="dim")

        for result in results:
            # Format confidence with color
            conf_style = {
                "HIGH": "green",
                "MEDIUM": "yellow",
                "LOW": "red",
            }.get(result.get("confidence", ""), "white")

            score_str = f"{result.get('score', 0):.3f}"

            # Use full tool name (skill.command)
            tool_id = f"{result.get('skill_name', '')}.{result.get('command', '')}"
            if result.get("command") and not result.get("skill_name"):
                tool_id = result.get("id", result.get("command", ""))

            if debug:
                table.add_row(
                    tool_id,
                    score_str,
                    f"[{conf_style}]{result.get('confidence', 'unknown')}[/]",
                    f"sem={result.get('score', 0) * 0.7:.2f} | kw={result.get('score', 0) * 0.3:.2f}",
                )
            else:
                table.add_row(
                    tool_id,
                    score_str,
                    f"[{conf_style}]{result.get('confidence', 'unknown')}[/]",
                )

        console.print(table)

        # Show stats
        stats = search.stats()
        console.print(
            f"\n[dim]Search weights: semantic={stats['semantic_weight']}, keyword={stats['keyword_weight']}[/dim]"
        )

    asyncio.run(run_test())


@route_app.command("stats")
def route_stats() -> None:
    """Show router statistics."""
    try:
        from omni.core.router.hybrid_search import HybridSearch
    except ImportError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)

    search = HybridSearch()
    stats = search.stats()

    console.print(
        Panel.fit(
            f"[bold]Router Statistics[/]\n\n"
            f"[bold]Hybrid Search:[/]\n"
            f"  Semantic weight: {stats['semantic_weight']}\n"
            f"  Keyword weight: {stats['keyword_weight']}\n"
            f"  RRF smoothing (k): {stats['rrf_k']}\n"
            f"  Strategy: {stats['strategy']}\n\n"
            f"[bold]Field Boosting:[/]\n"
            f"  Name token boost: {stats['field_boosting']['name_token_boost']}\n"
            f"  Exact phrase boost: {stats['field_boosting']['exact_phrase_boost']}",
            title="Router Stats",
            border_style="green",
        )
    )


@route_app.command("cache")
def route_cache(
    clear: bool = typer.Option(False, "-c", "--clear", help="Clear the cache"),
) -> None:
    """Manage router cache."""
    try:
        from omni.core.router.main import OmniRouter
    except ImportError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)

    from omni.core.router.main import RouterRegistry

    router = RouterRegistry.get("route_cache")

    if clear:
        count = router.cache.clear()
        console.print(f"[green]Cleared {count} cache entries.[/green]")
    else:
        stats = router.cache.stats()
        console.print(
            Panel.fit(
                f"[bold]Search Cache[/]\n\n"
                f"Size: [cyan]{stats['size']}[/] / {stats['max_size']}\n"
                f"TTL: [cyan]{stats['ttl_seconds']}[/] seconds\n"
                f"Hit rate: [cyan]{stats['hit_rate']:.1%}[/]",
                title="Cache",
                border_style="blue",
            )
        )


def register_route_command(parent_app: typer.Typer) -> None:
    """Register the route command with the parent app."""
    parent_app.add_typer(route_app, name="route")


__all__ = ["route_app", "register_route_command"]
