# agent/cli/commands/skill/index_cmd.py
"""
Index commands for skill CLI.

Contains: reindex, sync, index-stats, watch commands.
"""

from __future__ import annotations

import typer

from rich.panel import Panel

from .base import skill_app, err_console, SKILLS_DIR


@skill_app.command("reindex")
def skill_reindex(
    clear: bool = typer.Option(
        False, "--clear", "-c", help="Clear existing index before reindexing"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress logs"),
    export_index: bool = typer.Option(
        True,
        "--export-index/--no-export-index",
        help="Export skill_index.json after reindex (default: true)",
    ),
):
    """
    [Heavy] Wipe and rebuild the entire skill tool index.

    This command drops the existing table and re-indexes all skills from scratch.
    Use when:
    - The index is corrupted or inconsistent
    - Schema has changed and needs migration
    - You want a fresh start

    For incremental updates, use 'omni skill sync' instead.

    Example:
        omni skill reindex           # Full reindex all skills
        omni skill reindex --no-export-index  # Skip exporting skill_index.json
        omni skill reindex --json    # JSON output for scripting
    """
    import asyncio
    import logging

    from agent.core.vector_store import get_vector_memory

    # Suppress verbose logging by default
    if not verbose:
        logging.getLogger("agent.core.vector_store").setLevel(logging.WARNING)

    err_console.print(
        Panel(
            "Full reindex of skill tools...",
            title="🔄 Reindex",
            style="blue",
        )
    )

    try:
        vm = get_vector_memory()
        skills_path = str(SKILLS_DIR())

        # Clear the table first (heavy operation)
        if clear:
            vm.store.drop_table("skills")

        # Full reindex
        count = asyncio.run(vm.index_skill_tools_with_schema(skills_path, "skills"))

        # Export skill_index.json if requested
        exported_skills = 0
        exported_tools = 0
        if export_index and count > 0:
            export_result = asyncio.run(vm.export_skill_index())
            exported_skills = export_result.get("skills_exported", 0)
            exported_tools = export_result.get("tools_exported", 0)

        if json_output:
            import json

            err_console.print(
                json.dumps(
                    {
                        "total_tools_indexed": count,
                        "mode": "full_reindex",
                        "exported_skills": exported_skills,
                        "exported_tools": exported_tools,
                    },
                    indent=2,
                )
            )
        else:
            err_console.print(
                Panel(
                    f"Reindexed {count} tools (full rebuild)",
                    title="✅ Complete",
                    style="green",
                )
            )
            if export_index and exported_skills > 0:
                err_console.print(
                    f"[dim]Exported {exported_skills} skills to skill_index.json[/dim]"
                )

    except Exception as e:
        err_console.print(
            Panel(
                f"Reindex failed: {e}",
                title="❌ Error",
                style="red",
            )
        )
        raise typer.Exit(1)


@skill_app.command("sync")
def skill_sync(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress logs"),
    export_index: bool = typer.Option(
        True,
        "--export-index/--no-export-index",
        help="Export skill_index.json after sync (default: true)",
    ),
):
    """
    [Fast] Incrementally sync skill tools based on file changes.

    Compares file hashes between the database and filesystem to detect:
    - Added: New tool files
    - Modified: Files with changed content
    - Deleted: Files removed from filesystem

    This is fast (~0.1-0.2s) compared to reindex (~1-2s).

    Example:
        omni skill sync             # Fast incremental sync
        omni skill sync --no-export-index  # Skip exporting skill_index.json
        omni skill sync --json      # JSON output for scripting
    """
    import asyncio
    import logging

    from agent.core.vector_store import get_vector_memory

    # Suppress verbose logging by default
    if not verbose:
        logging.getLogger("agent.core.vector_store").setLevel(logging.WARNING)

    err_console.print(
        Panel(
            "Incrementally syncing skill tools...",
            title="⚡ Sync",
            style="blue",
        )
    )

    try:
        vm = get_vector_memory()
        skills_path = str(SKILLS_DIR())

        result = asyncio.run(vm.sync_skills(skills_path, "skills"))

        # Export skill_index.json if requested
        if export_index:
            export_result = asyncio.run(vm.export_skill_index())
            result["exported_skills"] = export_result.get("skills_exported", 0)
            result["exported_tools"] = export_result.get("tools_exported", 0)
            result["index_path"] = export_result.get("output_path", "")

        # Format result
        added = result.get("added", 0)
        modified = result.get("modified", 0)
        deleted = result.get("deleted", 0)
        total = added + modified + deleted

        if json_output:
            import json

            err_console.print(json.dumps(result, indent=2))
        else:
            # Build summary
            parts = []
            if added:
                parts.append(f"+{added} added")
            if modified:
                parts.append(f"~{modified} modified")
            if deleted:
                parts.append(f"-{deleted} deleted")

            summary = ", ".join(parts) if parts else "no changes"

            err_console.print(
                Panel(
                    f"{summary} ({total} total)",
                    title="✅ Sync Complete",
                    style="green" if total > 0 else "blue",
                )
            )

            # Show export info if enabled
            if export_index:
                exported = result.get("exported_skills", 0)
                err_console.print(f"[dim]Exported {exported} skills to skill_index.json[/dim]")

            # Show timing if available
            if "duration_ms" in result:
                err_console.print(f"[dim]Completed in {result['duration_ms']:.0f}ms[/dim]")

    except Exception as e:
        err_console.print(
            Panel(
                f"Sync failed: {e}",
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

    from agent.core.skill_discovery import SkillDiscovery

    async def get_stats():
        return await SkillDiscovery().get_index_stats()

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


@skill_app.command("watch")
def skill_watch():
    """
    Start a file watcher to automatically sync skills on change.

    Watches assets/skills/ for .py file changes and automatically
    triggers incremental sync. Use during development for live updates.

    Example:
        omni skill watch        # Start watching (Ctrl+C to stop)
    """
    from agent.core.skill_runtime.watcher import BackgroundWatcher
    from agent.core.vector_store import get_vector_memory

    err_console.print(
        Panel(
            "Starting Skill Watcher...",
            title="👀 Watch",
            style="blue",
        )
    )

    # Initial sync to ensure we're up to date
    skills_path = str(SKILLS_DIR())
    try:
        import asyncio

        vm = get_vector_memory()
        asyncio.run(vm.sync_skills(skills_path, "skills"))
        err_console.print("Initial sync complete")
    except Exception as e:
        err_console.print(Panel(f"Initial sync failed: {e}", title="⚠️ Warning", style="yellow"))

    # Start the watcher
    watcher = BackgroundWatcher()

    try:
        err_console.print(
            Panel(
                "Watching for file changes...",
                title="👀 Skill Watcher Active",
                style="blue",
            )
        )
        watcher.run(skills_path)
    except KeyboardInterrupt:
        watcher.stop()
        err_console.print(Panel("Skill Watcher stopped", title="🛑 Stopped", style="blue"))
