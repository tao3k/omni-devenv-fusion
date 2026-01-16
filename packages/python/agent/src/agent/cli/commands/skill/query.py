# agent/cli/commands/skill/query.py
"""
Query commands for skill CLI.

Contains: list, discover, info, search commands.
"""

from __future__ import annotations

import json
import typer
from typing import Optional

from rich.panel import Panel
from rich.table import Table

from .base import skill_app, err_console, print_result


@skill_app.command("list")
def skill_list():
    """List installed skills."""
    from agent.core.registry import get_skill_registry

    registry = get_skill_registry()
    skills = registry.list_available_skills()
    loaded = registry.list_loaded_skills()

    table = Table(title="📦 Installed Skills", show_header=True)
    table.add_column("Skill", style="bold")
    table.add_column("Status")
    table.add_column("Version")
    table.add_column("Dirty")

    for skill in sorted(skills):
        status = "loaded" if skill in loaded else "unloaded"
        status_style = "green" if status == "loaded" else "yellow"

        info = registry.get_skill_info(skill)
        version = info.get("version", "unknown") if info else "unknown"
        dirty = "📝" if info and info.get("dirty") else ""

        table.add_row(skill, f"[{status_style}]{status}[/{status_style}]", version, dirty)

    err_console.print(table)


@skill_app.command("discover")
def skill_discover(query: str = typer.Argument(..., help="Search query")):
    """Discover skills from remote index."""
    from agent.core.registry.jit import discover_skills

    result = discover_skills(query, limit=20)
    skills = result.get("skills", [])

    if skills:
        table = Table(title=f"🔍 Search Results for '{query}'", show_header=True)
        table.add_column("Name")
        table.add_column("Description")
        table.add_column("ID")

        for skill in skills:
            name = skill.get("name", skill.get("id", ""))
            desc = skill.get("description", "")[:60]
            skill_id = skill.get("id", "")
            table.add_row(name, desc + "..." if len(desc) > 60 else desc, skill_id)

        err_console.print(table)
    else:
        err_console.print(Panel(f"No skills found for '{query}'", title="🔍 Results"))


@skill_app.command("info")
def skill_info(name: str = typer.Argument(..., help="Skill name")):
    """Show detailed information about a skill from SKILL.md frontmatter."""
    from rich.markdown import Markdown
    from agent.core.registry import get_skill_registry

    registry = get_skill_registry()
    info = registry.get_skill_info(name)

    if not info or "error" in info:
        err_console.print(Panel(f"Skill '{name}' not found", title="❌ Error", style="red"))
        raise typer.Exit(1)

    # Build markdown content
    lines = [f"### 📦 {name}", ""]

    # Version and path
    version = info.get("version", "unknown")
    path = info.get("path", "unknown")
    lines.append(f"**Version:** {version}")
    lines.append(f"**Path:** `{path}`")

    # Description from frontmatter
    description = info.get("description", "")
    if description:
        lines.extend(["", f"> {description}"])

    # Routing keywords
    routing_keywords = info.get("routing_keywords", [])
    if routing_keywords:
        keywords_preview = routing_keywords[:15]
        keywords_str = ", ".join(str(k) for k in keywords_preview)
        if len(routing_keywords) > 15:
            keywords_str += f" (+{len(routing_keywords) - 15} more)"
        lines.extend(["", f"**Routing Keywords:** {keywords_str}"])

    # Intents
    intents = info.get("intents", [])
    if intents:
        intents_str = ", ".join(str(i) for i in intents)
        lines.extend(["", f"**Intents:** `{intents_str}`"])

    # Authors
    authors = info.get("authors", [])
    if authors:
        authors_str = ", ".join(str(a) for a in authors)
        lines.extend(["", f"**Authors:** {authors_str}"])

    # Render markdown in panel
    markdown_content = "\n".join(lines)
    err_console.print(Panel(Markdown(markdown_content), title=f"ℹ️ {name}", expand=False))


@skill_app.command("search")
def skill_search(
    query: str = typer.Argument(..., help="Semantic search query"),
    limit: int = typer.Option(5, "--limit", "-n", help="Maximum number of results"),
    all_skills: bool = typer.Option(
        False, "--all", "-a", help="Include remote (not installed) skills"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """
    Search skills using semantic vector search (Phase 37/38).

    Uses hybrid search with:
    - Vector similarity (ChromaDB embeddings)
    - Fuzzy keyword matching (substring, stemming)
    - Sigmoid score calibration

    Examples:
        omni skill search "write documentation"
        omni skill search "commit code" --limit 10
        omni skill search "git workflow" --all --json
    """
    import asyncio

    from agent.core.skill_discovery import VectorSkillDiscovery

    async def do_search():
        discovery = VectorSkillDiscovery()
        return await discovery.search(query, limit=limit, installed_only=not all_skills)

    try:
        results = asyncio.run(do_search())

        if json_output:
            print_result(json.dumps(results, indent=2))
        elif results:
            table = Table(title=f"🔍 Search: '{query}'", show_header=True)
            table.add_column("Skill", style="bold")
            table.add_column("Score", justify="right")
            table.add_column("Keywords")
            table.add_column("Installed")

            for skill in results:
                score = skill.get("score", 0)
                score_style = "green" if score >= 0.7 else "yellow" if score >= 0.5 else "red"
                keywords = ", ".join(skill.get("keywords", [])[:3])
                installed = "✅" if skill.get("installed") else "❌"

                table.add_row(
                    skill.get("name", skill.get("id", "")),
                    f"[{score_style}]{score:.2f}[/{score_style}]",
                    keywords[:30] + "..." if len(keywords) > 30 else keywords,
                    installed,
                )

            err_console.print(table)

            # Show scoring details for top result
            if results:
                top = results[0]
                verb_info = " +verb" if top.get("verb_matched") else ""
                feedback = top.get("feedback_bonus", 0.0)
                feedback_info = f", feedback={feedback:+.2f}" if feedback != 0 else ""
                err_console.print(
                    f"\n[dim]Top match scoring: "
                    f"vector={top.get('calibrated_vector', 0):.2f}, "
                    f"keyword_bonus=+{top.get('keyword_bonus', 0):.2f} "
                    f"({top.get('keyword_matches', 0)} matches){verb_info}{feedback_info}[/dim]"
                )
        else:
            err_console.print(
                Panel(f"No skills found for '{query}'", title="🔍 Results", style="yellow")
            )

    except Exception as e:
        err_console.print(
            Panel(
                f"Search failed: {e}",
                title="❌ Error",
                style="red",
            )
        )
        raise typer.Exit(1)
