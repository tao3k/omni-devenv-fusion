# agent/cli/commands/skill/analyze.py
"""
Skill Analytics Command - Arrow-Native Tool Analysis

High-performance skill analytics using PyArrow for columnar operations.

Commands:
- analyze: Analyze skill/tool statistics using Arrow
- stats: Quick skill database statistics
- context: Generate system context for LLM prompts

This module delegates to omni.core.skills.analyzer for actual analytics logic.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .base import skill_app

console = Console()


@skill_app.command("analyze")
def skill_analyze(
    category: Optional[str] = typer.Option(
        None, "-c", "--category", help="Filter by skill category"
    ),
    missing_docs: bool = typer.Option(
        False, "-m", "--missing-docs", help="Show tools without documentation"
    ),
    export_json: bool = typer.Option(False, "-j", "--json", help="Export analysis as JSON"),
) -> None:
    """Analyze skill/tool statistics using Arrow-native operations.

    This command uses PyArrow for high-performance analytics on the skill database.
    Provides insights into tool distribution, documentation coverage, and skill organization.

    Examples:
        omni skill analyze                    # Full analysis
        omni skill analyze -c git             # Git tools only
        omni skill analyze -m                 # Find undocumented tools
        omni skill analyze -j > stats.json    # Export as JSON
    """
    try:
        from omni.core.skills.analyzer import analyze_tools, get_category_distribution
    except ImportError as e:
        console.print(f"[red]Error: Could not import analyzer module: {e}[/]")
        raise typer.Exit(1)

    try:
        import pyarrow as pa
    except ImportError:
        console.print("[red]Error: pyarrow is required. Install with: pip install pyarrow[/]")
        raise typer.Exit(1)

    # Run analysis
    try:
        result = analyze_tools(category=category, missing_docs=missing_docs)
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)

    table = result["table"]
    total_tools = result["total_tools"]
    missing_count = result["missing_documentation"]
    categories = result["category_distribution"]

    if total_tools == 0:
        console.print("[yellow]No tools found in the database.[/]")
        console.print("[cyan]Tip: Run 'omni skill reindex' to index your skills.[/]")
        raise typer.Exit(0)

    # Display results
    if export_json:
        output = {
            "timestamp": datetime.now().isoformat(),
            "total_tools": total_tools,
            "missing_documentation": missing_count,
            "category_distribution": categories,
            "filtered_by_category": category,
            "missing_docs_filter": missing_docs,
        }
        console.print(json.dumps(output, indent=2))
        raise typer.Exit(0)

    # Pretty display
    console.print(
        Panel.fit(
            f"[bold]Skill Analytics Report[/]\n\n"
            f"Total Tools: [cyan]{total_tools}[/]\n"
            f"Categories: [cyan]{len(categories)}[/]\n"
            f"Missing Documentation: [red]{missing_count}[/]"
            if missing_count > 0
            else f"Missing Documentation: [green]{missing_count}[/]",
            title="Analytics",
            border_style="blue",
        )
    )

    # Category distribution table
    if categories:
        cat_table = Table(title="Category Distribution", show_header=True)
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Tools", justify="right", style="green")
        cat_table.add_column("Percentage", justify="right", style="yellow")

        sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
        for cat, count in sorted_cats:
            pct = (count / total_tools * 100) if total_tools > 0 else 0
            cat_table.add_row(cat, str(count), f"{pct:.1f}%")

        console.print(cat_table)

    # Show tools without documentation if requested
    if missing_docs and missing_count > 0 and table is not None:
        doc_table = Table(title="Tools Missing Documentation", show_header=True)
        doc_table.add_column("Tool ID", style="cyan")
        doc_table.add_column("Skill", style="blue")

        try:
            ids = table["id"].to_pylist()
            skill_names = (
                table["skill_name"].to_pylist()
                if "skill_name" in table.column_names
                else [""] * len(ids)
            )

            for id_, skill in zip(ids, skill_names):
                doc_table.add_row(id_, skill)

            console.print(doc_table)
        except Exception:
            pass

    # Top categories visualization
    if len(categories) > 5:
        sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
        top5 = list(sorted_cats[:5])
        console.print("\n[bold]Top 5 Categories:[/]")
        max_count = top5[0][1] if top5 else 1
        for cat, count in top5:
            bar_len = int(count / max_count * 30)
            bar = "█" * bar_len
            console.print(f"  {cat:<20} {bar} {count}")


@skill_app.command("stats")
def skill_stats() -> None:
    """Quick skill database statistics."""
    try:
        from omni.core.skills.analyzer import get_category_distribution
    except ImportError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)

    categories = get_category_distribution()

    console.print(
        Panel.fit(
            f"[bold]Skill Database Stats[/]\n\n"
            f"Total Categories: [cyan]{len(categories)}[/]\n"
            f"Total Tools: [cyan]{sum(categories.values())}[/]",
            title="Quick Stats",
            border_style="green",
        )
    )


@skill_app.command("context")
def skill_context(
    limit: int = typer.Option(50, "-n", "--number", help="Max tools to include"),
) -> None:
    """Generate system context for LLM prompts.

    Uses Arrow vectorized operations for efficient context generation.
    Outputs formatted tool list: @omni("tool.name") - description
    """
    try:
        from omni.core.skills.analyzer import generate_system_context
    except ImportError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)

    try:
        context = generate_system_context(limit=limit)
    except Exception as e:
        console.print(f"[red]Error generating context: {e}[/]")
        raise typer.Exit(1)

    if not context:
        console.print("[yellow]No tools found in the database.[/]")
        console.print("[cyan]Tip: Run 'omni skill reindex' to index your skills.[/]")
        raise typer.Exit(0)

    console.print(
        Panel.fit(Text(context, style="cyan"), title="System Context", border_style="blue")
    )
