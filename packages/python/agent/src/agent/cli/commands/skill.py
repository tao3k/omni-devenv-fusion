"""
skill.py - Skill Command Group

Phase 35.2: Modular CLI Architecture
Phase 36: Vector-Enhanced Discovery
Phase 37/38: Hybrid Search & Scoring

Provides full skill management commands:
- run: Run a skill command
- list: List installed skills
- discover: Discover skills from index
- search: Semantic vector search (Phase 37/38)
- info: Show skill information
- install: Install a skill from URL
- update: Update an installed skill
- test: Test skills (Phase 35.1)
- check: Validate skill structure (Phase 35.2)
- templates: Manage skill templates (Phase 35.2)
- create: Create a new skill from template (Phase 35.2)
- reindex: Reindex skills into vector store (Phase 36)
- index-stats: Show index statistics (Phase 36)
"""

from __future__ import annotations

import json
import typer
from typing import Optional
from pathlib import Path

from rich.panel import Panel
from rich.table import Table

from common.skills_path import SKILLS_DIR

from ..console import cli_log_handler, print_result, err_console
from ..runner import run_skills

skill_app = typer.Typer(help="Skill management commands")


@skill_app.command("run")
def skill_run(
    command: str = typer.Argument(..., help="Skill command in format 'skill.command'"),
    args_json: Optional[str] = typer.Argument(None, help="JSON arguments for the command"),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output raw JSON instead of markdown content"
    ),
):
    """Execute a skill command."""
    commands = [command]
    if args_json:
        commands.append(args_json)
    run_skills(commands, json_output=json_output, log_handler=cli_log_handler)


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


@skill_app.command("install")
def skill_install(
    url: str = typer.Argument(..., help="Git repository URL"),
    name: Optional[str] = typer.Argument(
        None, help="Skill name (derived from URL if not provided)"
    ),
    version: str = typer.Option("main", "--version", "-v", help="Git ref (default: main)"),
):
    """Install a skill from a remote repository."""
    from agent.core.registry import get_skill_registry

    if not name:
        name = url.rstrip("/").split("/")[-1].replace("-skill", "")

    registry = get_skill_registry()
    success, msg = registry.install_remote_skill(name, url, version)

    if success:
        err_console.print(Panel(f"Installed {name} from {url}", title="✅ Success", style="green"))
    else:
        err_console.print(Panel(msg, title="❌ Failed", style="red"))
        raise typer.Exit(1)


@skill_app.command("update")
def skill_update(
    name: str = typer.Argument(..., help="Skill name"),
    version: str = typer.Option("main", "--version", "-v", help="Git ref"),
):
    """Update an installed skill."""
    from agent.core.registry import get_skill_registry

    registry = get_skill_registry()
    success, msg = registry.update_skill(name, version)

    if success:
        err_console.print(Panel(f"Updated {name} to {version}", title="✅ Success", style="green"))
    else:
        err_console.print(Panel(msg, title="❌ Failed", style="red"))
        raise typer.Exit(1)


# =============================================================================
# Skill Testing (Phase 35.1)
# =============================================================================


@skill_app.command("test")
def skill_test(
    skill_name: Optional[str] = typer.Argument(
        None, help="Skill name to test (default: all skills)"
    ),
    all_skills: bool = typer.Option(False, "--all", help="Test all skills with tests/ directory"),
):
    """Test skills using the testing framework."""
    from agent.testing.context import TestContext

    ctx = TestContext()

    if all_skills:
        results = ctx.run_all_tests()
        ctx.print_summary(results)
    elif skill_name:
        result = ctx.run_skill_tests(skill_name)
        # Wrap single result in dict for print_summary
        ctx.print_summary({skill_name: result})
    else:
        err_console.print(
            Panel(
                "Specify a skill name or use --all to test all skills",
                title="ℹ️ Usage",
                style="blue",
            )
        )


# =============================================================================
# Skill Structure Validation (Phase 35.2)
# =============================================================================


@skill_app.command("check")
def skill_check(
    skill_name: Optional[str] = typer.Argument(
        None, help="Skill name to check (default: all skills)"
    ),
    examples: bool = typer.Option(False, "--examples", help="Check with structure examples"),
):
    """Validate skill structure."""
    from agent.testing.context import TestContext

    ctx = TestContext()

    if skill_name:
        ctx.validate_skill_structure(skill_name, check_examples=examples)
    else:
        # Check all skills
        skills_dir = SKILLS_DIR()
        for skill_path in sorted(skills_dir.iterdir()):
            if skill_path.is_dir() and not skill_path.name.startswith("_"):
                ctx.validate_skill_structure(skill_path.name, check_examples=examples)


# =============================================================================
# Skill Templates Management (Phase 35.2)
# =============================================================================


def _load_templates_module():
    """Load templates module directly from file."""
    import importlib.util
    from pathlib import Path

    templates_path = Path("assets/skills/skill/scripts/templates.py")
    if not templates_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("templates", templates_path)
    templates = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(templates)
    return templates


@skill_app.command("templates")
def skill_templates(
    skill_name: str = typer.Argument(..., help="Skill name"),
    list_templates: bool = typer.Option(False, "--list", "-l", help="List available templates"),
    eject: Optional[str] = typer.Option(
        None, "--eject", "-e", help="Copy template to user directory"
    ),
    info: Optional[str] = typer.Option(None, "--info", "-i", help="Show template content"),
):
    """Manage skill templates."""
    templates = _load_templates_module()

    if templates is None:
        err_console.print(Panel("Templates module not found", title="❌ Error", style="red"))
        return

    if list_templates:
        result = templates.format_template_list(skill_name)
        err_console.print(Panel(result, title=f"📋 Templates: {skill_name}", expand=False))
    elif eject:
        result = templates.format_eject_result(skill_name, eject)
        err_console.print(Panel(result, title="✅ Eject Result", expand=False))
    elif info:
        result = templates.format_info_result(skill_name, info)
        err_console.print(Panel(result, title=f"📄 Template Info", expand=False))
    else:
        err_console.print(
            Panel(
                "Use --list, --eject, or --info",
                title="ℹ️ Usage",
                style="blue",
            )
        )


# =============================================================================
# Create New Skill (Phase 35.2)
# =============================================================================


@skill_app.command("create")
def skill_create(
    skill_name: str = typer.Argument(..., help="New skill name (kebab-case)"),
    description: str = typer.Option(..., "--description", "-d", help="Skill description"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing skill"),
):
    """Create a new skill from template."""
    from agent.testing.context import TestContext

    ctx = TestContext()
    ctx.create_skill(skill_name, description, force=force)


@skill_app.command("reindex")
def skill_reindex(
    clear: bool = typer.Option(
        False, "--clear", "-c", help="Clear existing index before reindexing"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress logs"),
):
    """
    Reindex all skills into the vector store for semantic search.

    This command scans all installed skills and creates semantic embeddings
    in ChromaDB, enabling intelligent discovery even when keywords don't
    exactly match (e.g., "draw chart" → "visualization").

    Example:
        omni skill reindex           # Reindex all skills
        omni skill reindex --clear   # Clear and reindex
        omni skill reindex --json    # JSON output for scripting
        omni skill reindex -v        # Verbose output
    """
    import asyncio
    import logging

    from agent.core.skill_discovery import reindex_skills_from_manifests

    # Suppress verbose logging by default
    if not verbose:
        logging.getLogger("agent.core.vector_store").setLevel(logging.WARNING)
        logging.getLogger("agent.core.skill_discovery").setLevel(logging.WARNING)

    err_console.print(
        Panel(
            "Reindexing skills into vector store...",
            title="🔄 Skill Index",
            style="blue",
        )
    )

    try:
        result = asyncio.run(reindex_skills_from_manifests(clear_existing=clear))

        if json_output:
            import json

            err_console.print(json.dumps(result, indent=2))
        else:
            err_console.print(
                Panel(
                    f"Indexed {result['total_skills_indexed']} skills "
                    f"({result['local_skills_indexed']} local, {result['remote_skills_indexed']} remote)",
                    title="✅ Complete",
                    style="green",
                )
            )

            if result.get("errors"):
                error_panel = Panel(
                    "\n".join([f"- {e['skill']}: {e['error']}" for e in result["errors"]]),
                    title="⚠️ Errors",
                    style="yellow",
                )
                err_console.print(error_panel)

    except Exception as e:
        err_console.print(
            Panel(
                f"Reindex failed: {e}",
                title="❌ Error",
                style="red",
            )
        )
        raise typer.Exit(1)


@skill_app.command("index-stats")
def skill_index_stats(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """
    Show statistics about the skill vector index.

    Displays the number of indexed skills and collection information.
    """
    import asyncio

    from agent.core.skill_discovery import VectorSkillDiscovery

    async def get_stats():
        return await VectorSkillDiscovery().get_index_stats()

    try:
        result = asyncio.run(get_stats())

        if json_output:
            import json

            err_console.print(json.dumps(result, indent=2))
        else:
            err_console.print(
                Panel(
                    f"Collection: {result['collection']}\n"
                    f"Indexed Skills: {result['skill_count']}\n"
                    f"Available Collections: {', '.join(result.get('available_collections', []))}",
                    title="📊 Index Statistics",
                    style="blue",
                )
            )

    except Exception as e:
        err_console.print(
            Panel(
                f"Failed to get stats: {e}",
                title="❌ Error",
                style="red",
            )
        )
        raise typer.Exit(1)


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


def register_skill_command(app_instance: typer.Typer) -> None:
    """Register skill subcommand with the main app."""
    app_instance.add_typer(skill_app, name="skill")


__all__ = ["skill_app", "register_skill_command"]
