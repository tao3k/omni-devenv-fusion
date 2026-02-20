# agent/cli/commands/skill/query.py
"""
Query commands for skill CLI.

Contains: list, info, query commands.
(discover/search unavailable in thin client model)
"""

from __future__ import annotations

import json
import re
import sys

import typer
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .base import err_console, skill_app

_CANONICAL_COMMAND_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$")


@skill_app.command("query")
def skill_query(
    query: str = typer.Argument(..., help="Search query (e.g., 'commit changes', 'read file')"),
    limit: int = typer.Option(5, "--limit", "-n", help="Maximum number of results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Search for tools matching the given intent.

    Shows tool name, description, and smart usage template with parameters.
    """
    from omni.core.skills.discovery import SkillDiscoveryService

    service = SkillDiscoveryService()
    matches = service.search_tools(query=query, limit=limit)

    if not matches:
        err_console.print(
            Panel(
                f"No tools found matching '{query}'",
                title="🔍 Search Results",
                style="yellow",
            )
        )
        return

    if json_output:
        output = [
            {
                "name": m.name,
                "skill_name": m.skill_name,
                "description": m.description,
                "score": round(m.score, 3),
                "usage_template": m.usage_template,
            }
            for m in matches
        ]
        err_console.print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        # Create table with results
        table = Table(title=f"🔍 Search Results: '{query}'", show_header=True)
        table.add_column("Tool", style="bold cyan")
        table.add_column("Usage Template", style="green")
        table.add_column("Score", justify="right")

        for m in matches:
            table.add_row(
                f"[bold]{m.name}[/bold]\n[muted]{m.description[:60]}...[/muted]",
                f"[green]{m.usage_template}[/green]",
                f"{m.score:.2f}",
            )

        err_console.print(table)

        # Show hint
        err_console.print(
            Panel(
                "💡 Copy the usage_template above to call the tool with @omni()",
                title="Tip",
                style="blue",
            )
        )


def _build_index_from_list_all_tools(tools: list[dict]) -> dict[str, dict]:
    """Group list_all_tools output by skill_name into index_by_name format."""
    index_by_name: dict[str, dict] = {}
    for t in tools:
        skill_name = t.get("skill_name") or ""
        tool_name = t.get("tool_name") or ""
        if not skill_name or not tool_name:
            continue
        if "." in tool_name:
            full_name = tool_name
        else:
            full_name = f"{skill_name}.{tool_name}"
        full_name = full_name.strip()
        if not _CANONICAL_COMMAND_PATTERN.fullmatch(full_name):
            continue

        normalized_skill = full_name.split(".", 1)[0]
        if normalized_skill not in index_by_name:
            index_by_name[normalized_skill] = {"name": normalized_skill, "tools": []}
        index_by_name[normalized_skill]["tools"].append(
            {
                "name": full_name,
                "description": t.get("description", ""),
                "category": t.get("category", ""),
            }
        )
    return index_by_name


@skill_app.command("list")
def skill_list(
    compact: bool = typer.Option(False, "--compact", "-c", help="Show compact view (names only)"),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output all skills info as JSON (from Rust DB)"
    ),
):
    """
    List installed skills and their commands.

    Displays a hierarchical inventory of all available capabilities,
    including command aliases defined in settings (system: packages/conf/settings.yaml, user: $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml).

    Uses Rust DB (LanceDB) only - no filesystem scan, no kernel/sniffer/watcher init.
    Use --json to get machine-readable output. Run 'omni sync' first if index is empty.
    """
    from rich.tree import Tree
    from rich.text import Text
    from omni.core.config.loader import load_command_overrides, is_filtered
    from omni.foundation.config.skills import SKILLS_DIR
    from omni.foundation.bridge import RustVectorStore

    # Light path: list_all_tools reads from LanceDB (fast); avoid get_skill_index_sync (filesystem scan can hang)
    skills_dir = SKILLS_DIR()
    overrides = load_command_overrides()
    try:
        store = RustVectorStore()
        tools = store.list_all_tools()
    except Exception as e:
        err_console.print(
            Panel(
                f"Failed to load skill index: {e}. Run 'omni sync' to index skills.",
                title="Error",
                style="red",
            )
        )
        raise typer.Exit(1)

    index_by_name = _build_index_from_list_all_tools(tools)
    available_skills = sorted(index_by_name.keys()) if index_by_name else []

    # JSON output mode - from LanceDB (same as tree view)
    if json_output:
        output = [
            {
                "name": name,
                "tools": [
                    {
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "category": t.get("category", ""),
                    }
                    for t in data.get("tools", [])
                    if not is_filtered(t.get("name", ""))
                ],
            }
            for name, data in sorted(index_by_name.items())
            if any(not is_filtered(t.get("name", "")) for t in data.get("tools", []))
        ]
        sys.stdout.write(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
        return

    if not available_skills and skills_dir.exists():
        available_skills = sorted(
            [d.name for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
        )

    tree = Tree("📦 [bold]Skill Inventory[/bold]", guide_style="dim")

    for skill_name in available_skills:
        skill_data = index_by_name.get(skill_name, {})
        all_tools = skill_data.get("tools", [])
        tools = [tool for tool in all_tools if not is_filtered(tool.get("name", ""))]
        if not tools:
            continue
        is_indexed = bool(tools)
        status_color = "green" if is_indexed else "dim white"
        status_icon = "🟢" if is_indexed else "⚪"

        skill_node = tree.add(f"{status_icon} [bold {status_color}]{skill_name}[/]")

        if is_indexed and not compact:
            prefix = f"{skill_name}."
            for tool in tools:
                full_cmd = tool.get("name", "")
                if not full_cmd:
                    continue
                cmd_short = full_cmd[len(prefix) :] if full_cmd.startswith(prefix) else full_cmd

                override = overrides.commands.get(full_cmd)
                alias = override.alias if override else None
                append_doc = override.append_doc if override else None

                cmd_text = Text()
                if alias:
                    cmd_text.append("⭐ ", style="yellow")
                    cmd_text.append(alias, style="bold cyan")
                    cmd_text.append(f" (Canon: {full_cmd})", style="dim")
                else:
                    cmd_text.append("🔧 ", style="dim")
                    cmd_text.append(cmd_short, style="white")

                desc = tool.get("description", "") or ""
                if append_doc:
                    desc = f"{desc} {append_doc}"
                desc = desc.strip().split("\n")[0]
                if len(desc) > 60:
                    desc = desc[:57] + "..."

                if desc:
                    cmd_text.append(f" - {desc}", style="dim italic")

                skill_node.add(cmd_text)

            if not skill_node.children:
                skill_node.add("[dim italic]No public commands[/]")

    err_console.print(tree)
    err_console.print(
        Panel(
            'Use [bold cyan]omni run "intent"[/] to execute a task.\n'
            "Use [bold cyan]omni run skill.discover[/] to find specific tools.",
            title="💡 Tip",
            style="blue",
            expand=False,
        )
    )


@skill_app.command("info")
def skill_info(name: str = typer.Argument(..., help="Skill name")):
    """Show information about a skill."""
    import logging

    import yaml

    from omni.foundation.bridge import RustVectorStore
    from omni.foundation.config.skills import SKILLS_DIR

    # Suppress logging for cleaner CLI output
    logging.getLogger("omni.foundation.scanner").setLevel(logging.WARNING)

    skills_dir = SKILLS_DIR()
    skill_path = skills_dir / name
    info_path = skill_path / "SKILL.md"

    if not info_path.exists():
        err_console.print(Panel(f"Skill '{name}' not found", title="❌ Error", style="red"))
        raise typer.Exit(1)

    # Get commands from LanceDB (avoid get_skill_index_sync filesystem scan)
    commands = []
    try:
        store = RustVectorStore()
        tools = store.list_all_tools()
        for t in tools:
            if (t.get("skill_name") or "") != name:
                continue
            tool_name = t.get("tool_name") or ""
            if tool_name:
                commands.append(tool_name)
    except Exception:
        pass  # Silently fail - commands will show 0

    # Parse SKILL.md frontmatter
    content = info_path.read_text()
    info = {"version": "unknown", "description": "", "authors": [], "keywords": []}
    if content.startswith("---"):
        _, frontmatter, _ = content.split("---", 2)
        data = yaml.safe_load(frontmatter) or {}
        info = {
            "version": data.get("version", "unknown"),
            "description": data.get("description", ""),
            "authors": data.get("authors", []),
            "keywords": data.get("routing_keywords", []),
        }

    lines = [f"**Version:** {info['version']}  "]
    lines.append(f"**Commands:** {len(commands)}")

    if info["description"]:
        lines.extend(["", f"> {info['description']}"])

    if info["authors"]:
        lines.extend(["", f"**Authors:** {', '.join(info['authors'])}"])

    if commands:
        lines.extend(["", "### Commands"])
        for cmd in commands[:10]:
            lines.append(f"- `{cmd}`")
        if len(commands) > 10:
            lines.append(f"- ... and {len(commands) - 10} more")

    markdown_content = "\n".join(lines)
    err_console.print(Panel(Markdown(markdown_content), title=f"ℹ️ {name}", expand=False))


# Remote discovery/search are intentionally unavailable in thin client mode.
@skill_app.command("discover")
def skill_discover(query: str = typer.Argument(..., help="Search query")):
    """Discover skills from remote index (unavailable in thin client mode)."""
    err_console.print(
        Panel(
            "Remote skill discovery is not available in thin client mode.\n"
            "Skills are loaded from assets/skills/ automatically.",
            title="Unavailable",
            style="blue",
        )
    )


@skill_app.command("search")
def skill_search(
    query: str = typer.Argument(..., help="Semantic search query"),
    limit: int = typer.Option(5, "--limit", "-n", help="Maximum number of results"),
):
    """Search skills (unavailable in thin client mode)."""
    err_console.print(
        Panel(
            "Semantic skill search is not available in thin client mode.\n"
            "Use 'omni skill list' to see all available skills.",
            title="Unavailable",
            style="blue",
        )
    )


@skill_app.command("schema")
def skill_schema(
    tool_name: str = typer.Argument(..., help="Tool name (e.g., 'git.commit' or 'commit')"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Show schema for a specific tool.

    Displays the MCP Tool Schema including parameters, annotations, and variants.
    """
    from omni.core.skills.schema_gen import generate_tool_schemas

    # Load all skills first to register their commands
    from omni.core.kernel import get_kernel

    kernel = get_kernel()

    # Ensure skills are loaded so commands are registered
    try:
        kernel.skill_context.load_all_skills()
    except Exception:
        pass  # Continue anyway - some skills might fail to load

    # Generate schemas (this will scan registered commands)
    schemas = generate_tool_schemas()

    # Try to find the tool
    tool_schema = None

    # Search by full name (e.g., "git.commit")
    if tool_name in schemas.get("tools", []):
        for tool in schemas["tools"]:
            if tool.get("name") == tool_name:
                tool_schema = tool
                break

    # If not found, try partial match (e.g., "commit" matches "git.commit")
    if tool_schema is None:
        for tool in schemas.get("tools", []):
            tool_name_lower = tool.get("name", "").lower()
            # Match if tool name ends with the search term
            if (
                tool_name_lower.endswith(f".{tool_name.lower()}")
                or tool_name_lower == tool_name.lower()
            ):
                tool_schema = tool
                break

    if tool_schema is None:
        err_console.print(
            Panel(
                f"Tool '{tool_name}' not found.\n"
                f"Available tools: {', '.join([t.get('name', '') for t in schemas.get('tools', [])[:20]])}...\n"
                f"Use 'omni skill list' to see all available skills.",
                title="🔍 Tool Not Found",
                style="red",
            )
        )
        raise typer.Exit(1)

    if json_output:
        # Output JSON to stdout
        sys.stdout.write(json.dumps(tool_schema, indent=2, ensure_ascii=False) + "\n")
        return

    # Pretty print the schema
    from rich.json import JSON
    from rich.columns import Columns

    err_console.print(Panel(f"[bold]Tool Schema: {tool_schema.get('name', '')}[/]", style="cyan"))

    # Show key info
    err_console.print(f"[bold]Description:[/] {tool_schema.get('description', 'N/A')}")
    err_console.print(f"[bold]Category:[/] {tool_schema.get('category', 'N/A')}")

    # Annotations - show all MCP hints even if False (important for LLM guidance)
    annotations = tool_schema.get("annotations", {})
    if annotations:
        err_console.print("\n[bold]MCP Annotations:[/]")
        annotation_strs = []
        for key, value in annotations.items():
            # Show all hints including False (important for LLM behavior guidance)
            annotation_strs.append(f"{key}: {value}")
        if annotation_strs:
            err_console.print("  " + " | ".join(annotation_strs))
        else:
            err_console.print("  [dim]None[/]")

    # Parameters
    params = tool_schema.get("parameters", {})
    props = params.get("properties", {})
    required = params.get("required", [])

    if props:
        err_console.print("\n[bold]Parameters:[/]")
        param_table = Table(show_header=True, header_style="bold magenta")
        param_table.add_column("Name")
        param_table.add_column("Type")
        param_table.add_column("Required")
        param_table.add_column("Description")

        for param_name, param_def in props.items():
            is_required = "[green]Yes[/green]" if param_name in required else "[dim]No[/dim]"
            param_type = param_def.get("type", "unknown")
            param_desc = param_def.get("description", "")
            param_table.add_row(param_name, param_type, is_required, param_desc)

        err_console.print(param_table)

    # Variants
    variants = tool_schema.get("variants", [])
    if variants:
        err_console.print("\n[bold]Variants:[/]")
        variant_table = Table(show_header=True, header_style="bold green")
        variant_table.add_column("Name")
        variant_table.add_column("Priority")
        variant_table.add_column("Status")
        variant_table.add_column("Description")

        for var in variants:
            status = var.get("status", "unknown")
            status_style = "green" if status == "available" else "yellow"
            variant_table.add_row(
                var.get("name", ""),
                str(var.get("priority", 100)),
                f"[{status_style}]{status}[/{status_style}]",
                var.get("description", ""),
            )

        err_console.print(variant_table)

    # Show usage hint
    tool_name = tool_schema.get("name", "")
    params_str = ", ".join(
        [f'{p}="value"' for p in (required[:2] if required else list(props.keys())[:2])]
    )
    usage_text = f'[bold]Usage:[/] @omni("{tool_name}", {params_str})'

    err_console.print(
        Panel(
            usage_text,
            title="💡 Usage",
            style="blue",
        )
    )
