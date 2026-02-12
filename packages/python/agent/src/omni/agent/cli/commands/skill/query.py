# agent/cli/commands/skill/query.py
"""
Query commands for skill CLI.

Contains: list, info, query commands.
(discover/search unavailable in thin client model)
"""

from __future__ import annotations

import json
import sys

import typer
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .base import err_console, skill_app


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
    including command aliases defined in settings.yaml.

    Use --json to get machine-readable output of all skills from the Rust DB index.
    """
    import asyncio

    from rich.tree import Tree
    from rich.text import Text
    from omni.core.kernel import get_kernel
    from omni.core.config.loader import load_command_overrides, is_filtered
    from omni.foundation.config.skills import SKILLS_DIR
    from omni.foundation.bridge import RustVectorStore

    # JSON output mode - dump all skills from Rust DB with full metadata
    if json_output:
        try:
            store = RustVectorStore()
            skills_dir = SKILLS_DIR()
            skills = store.get_skill_index_sync(str(skills_dir))

            output = []
            for skill in skills:
                skill_path = skill.get("path", "")
                docs_path = f"{skill_path}/SKILL.md" if skill_path else ""

                # Extract docs_available subfields
                docs_avail = skill.get("docs_available", {})
                docs_status = {
                    "skill_md": docs_avail.get("skill_md", False)
                    if isinstance(docs_avail, dict)
                    else False,
                    "readme": docs_avail.get("readme", False)
                    if isinstance(docs_avail, dict)
                    else False,
                    "tests": docs_avail.get("tests", False)
                    if isinstance(docs_avail, dict)
                    else False,
                }

                # Convert require_refs to list of strings
                require_refs = skill.get("require_refs", [])
                if require_refs and isinstance(require_refs[0], dict):
                    require_refs = [
                        r.get("path", r) if isinstance(r, dict) else r for r in require_refs
                    ]
                elif require_refs and isinstance(require_refs[0], str):
                    pass  # Already strings
                else:
                    require_refs = []

                # Convert sniffing_rules to simplified format
                sniffing_rules = skill.get("sniffing_rules", [])
                if sniffing_rules and isinstance(sniffing_rules[0], dict):
                    sniffing_rules = [
                        {
                            "type": r.get("type", ""),
                            "pattern": r.get("pattern", ""),
                        }
                        for r in sniffing_rules
                    ]

                skill_data = {
                    "name": skill.get("name", ""),
                    "path": skill_path,
                    "docs_path": docs_path,
                    "description": skill.get("description", ""),
                    "version": skill.get("version", "unknown"),
                    "repository": skill.get("repository", ""),
                    "routing_keywords": skill.get("routing_keywords", []),
                    "intents": skill.get("intents", []),
                    "authors": skill.get("authors", []),
                    "permissions": skill.get("permissions", []),
                    "require_refs": require_refs,
                    "oss_compliant": skill.get("oss_compliant", []),
                    "compliance_details": skill.get("compliance_details", []),
                    "sniffing_rules": sniffing_rules,
                    "docs_available": docs_status,
                    "has_extensions": bool(skill.get("tools")),
                    "tools": [
                        {
                            "name": t.get("name", ""),
                            "description": t.get("description", ""),
                            "category": t.get("category", ""),
                            "input_schema": t.get("input_schema", ""),
                            "file_hash": t.get("file_hash", ""),
                        }
                        for t in skill.get("tools", [])
                    ],
                }
                output.append(skill_data)

            # Output JSON to stdout (for piping) instead of stderr
            sys.stdout.write(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
            return
        except Exception as e:
            err_console.print(
                Panel(
                    f"Failed to load skill index: {e}",
                    title="Error",
                    style="red",
                )
            )
            raise typer.Exit(1)

    skills_dir = SKILLS_DIR()
    kernel = get_kernel()
    ctx = kernel.skill_context
    overrides = load_command_overrides()

    # Get available skills from filesystem
    available_skills = []
    if skills_dir.exists():
        available_skills = sorted(
            [d.name for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
        )

    loaded_skills = ctx.list_skills()

    # Build Tree
    tree = Tree("📦 [bold]Skill Inventory[/bold]", guide_style="dim")

    for skill_name in available_skills:
        is_loaded = skill_name in loaded_skills
        status_color = "green" if is_loaded else "dim white"
        status_icon = "🟢" if is_loaded else "⚪"

        skill_node = tree.add(f"{status_icon} [bold {status_color}]{skill_name}[/]")

        if is_loaded and not compact:
            skill_obj = ctx.get_skill(skill_name)
            commands = skill_obj.list_commands() if skill_obj else []

            # Sort commands: Aliased first, then others
            commands.sort(key=lambda c: (c not in overrides.commands, c))

            for full_cmd in commands:
                # Filter hidden commands
                if is_filtered(full_cmd):
                    continue

                # Handle Alias
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
                    cmd_text.append(full_cmd, style="white")

                # Handle Description
                cmd_obj = ctx.get_command(full_cmd)
                desc = getattr(cmd_obj, "description", "") or ""
                if append_doc:
                    desc = f"{desc} {append_doc}"

                # Truncate description for clean display
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

    # Get commands from index (works even if skill is not loaded)
    commands = []
    try:
        store = RustVectorStore()
        skill_index = store.get_skill_index_sync(str(skills_dir))
        for skill in skill_index:
            if skill.get("name") != name:
                continue
            prefix = f"{name}."
            for tool in skill.get("tools", []):
                cmd_name = tool.get("name", "")
                if cmd_name.startswith(prefix):
                    cmd_name = cmd_name[len(prefix) :]
                if cmd_name:
                    commands.append(cmd_name)
            break
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
