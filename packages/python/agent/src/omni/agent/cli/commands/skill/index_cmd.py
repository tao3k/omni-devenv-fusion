# agent/cli/commands/skill/index_cmd.py
"""
Index commands for skill CLI.

Contains: reindex, sync, index-stats commands.
Data is stored in LanceDB (.cache/omni-vector/).
"""

from __future__ import annotations

import asyncio
import json

import typer
from rich.panel import Panel

from .base import SKILLS_DIR, err_console, skill_app


@skill_app.command("reindex")
def skill_reindex(
    clear: bool = typer.Option(
        False, "--clear", "-c", help="Clear existing index before reindexing"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress logs"),
):
    """
    [Heavy] Wipe and rebuild the entire skill tool index in LanceDB.

    This command drops the existing table and re-indexes all skills from scratch.
    Use when:
    - The index is corrupted or inconsistent
    - Schema has changed and needs migration
    - You want a fresh start

    For incremental updates, use 'omni skill sync' instead.

    Example:
        omni skill reindex           # Full reindex all skills
        omni skill reindex --json    # JSON output for scripting
    """
    import logging

    from omni.foundation.bridge import RustVectorStore
    from omni.foundation.config.logging import get_logger

    logger = get_logger("omni.core.reindex")

    # Suppress verbose logging by default
    if not verbose:
        logging.getLogger("omni.core.discovery").setLevel(logging.WARNING)

    err_console.print(
        Panel(
            "Full reindex of skill tools to LanceDB...",
            title="🔄 Reindex",
            style="blue",
        )
    )

    try:
        skills_path = str(SKILLS_DIR())

        # Drop existing table for full reindex (always clear for consistency)
        err_console.print("Dropping existing index table...")
        try:
            store = RustVectorStore(dimension=384)
            asyncio.run(store.drop_table("skills"))
        except Exception:
            pass  # Table may not exist

        # Full reindex using Rust bindings (writes to LanceDB)
        store = RustVectorStore(dimension=384)
        indexed_count = asyncio.run(store.index_skill_tools(skills_path))

        if json_output:
            err_console.print(
                json.dumps(
                    {
                        "total_tools_indexed": indexed_count,
                        "mode": "full_reindex",
                        "storage": "lancedb",
                    },
                    indent=2,
                )
            )
        else:
            err_console.print(
                Panel(
                    f"Reindexed {indexed_count} tools to LanceDB (full rebuild)",
                    title="✅ Complete",
                    style="green",
                )
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
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed diff"),
):
    """
    [Fast] Incrementally sync skill tools to LanceDB.

    Uses file hashes to detect changes and update LanceDB.

    Example:
        omni skill sync             # Fast incremental sync
        omni skill sync --json      # JSON output for scripting
        omni skill sync --dry-run   # Preview changes without applying
    """
    import logging
    from pathlib import Path

    # Suppress verbose logging by default
    if not verbose:
        logging.getLogger("omni.core.discovery").setLevel(logging.WARNING)

    err_console.print(
        Panel(
            "Incrementally syncing skill tools to LanceDB...",
            title="⚡ Sync",
            style="blue",
        )
    )

    try:
        skills_path = str(SKILLS_DIR())

        # Use Rust scanner to detect changes
        try:
            from omni_core_rs import diff_skills, scan_skill_tools
        except ImportError as e:
            err_console.print(
                Panel(
                    f"Rust bindings not available: {e}",
                    title="❌ Error",
                    style="red",
                )
            )
            raise typer.Exit(1)

        # Scan current state
        scanned_tools = scan_skill_tools(skills_path)

        # Deduplicate tools by name
        seen_tools: dict[str, dict] = {}
        for t in scanned_tools:
            if t.tool_name not in seen_tools:
                seen_tools[t.tool_name] = {
                    "tool_name": t.tool_name,
                    "description": t.description,
                    "skill_name": t.skill_name,
                    "file_path": t.file_path,
                    "function_name": t.function_name,
                    "execution_mode": t.execution_mode,
                    "keywords": t.keywords,
                    "input_schema": t.input_schema,
                    "file_hash": t.file_hash,
                    "category": t.category,
                }
        scanned_data = list(seen_tools.values())
        scanned_data_str = json.dumps(scanned_data)

        # Get existing tools from LanceDB for comparison
        from omni.foundation.bridge import RustVectorStore

        store = RustVectorStore()
        try:
            existing_tools = asyncio.run(store.list_all_tools())
            # Transform to IndexToolEntry format: tool_name -> name
            existing_entries = []
            for tool in existing_tools:
                entry = {
                    "name": tool.get("tool_name", ""),
                    "description": tool.get("description", ""),
                    "category": tool.get("category", ""),
                    "input_schema": tool.get("input_schema", ""),
                    "file_hash": tool.get("file_hash", ""),
                }
                existing_entries.append(entry)
            existing_data_str = json.dumps(existing_entries)
        except Exception:
            existing_tools = []
            existing_data_str = "[]"

        # Calculate diff
        report = diff_skills(scanned_data_str, existing_data_str)

        added = [t.tool_name for t in report.added]
        updated = [t.tool_name for t in report.updated]
        deleted = report.deleted
        unchanged_count = report.unchanged_count

        has_changes = len(added) > 0 or len(updated) > 0 or len(deleted) > 0

        # Check if LanceDB is empty (needs initial population)
        lance_db_empty = len(existing_tools) == 0

        # Apply changes to LanceDB
        if has_changes and not dry_run:
            # If LanceDB is empty, auto-run reindex to populate
            if lance_db_empty and added:
                err_console.print(
                    Panel(
                        "LanceDB is empty. Running reindex to populate skills...",
                        title="🚀 Auto-populating",
                        style="blue",
                    )
                )
                # Index tools to LanceDB using Rust bindings
                asyncio.run(store.index_skill_tools(skills_path))
                # Reset the diff result since we just populated
                has_changes = False
                unchanged_count = len(scanned_data)
                added = []
                updated = []
                deleted = []
            else:
                # Delete removed tools
                for tool_name in deleted:
                    store.delete("skills", [tool_name])

                # Note: add/update would require embedding computation
                # For now, recommend reindex for significant changes
                if added or updated:
                    err_console.print(
                        Panel(
                            "Changes detected. Run 'omni skill reindex' to apply.",
                            title="⚠️ Action Required",
                            style="yellow",
                        )
                    )

        # Output results
        if json_output:
            output = {
                "added": added,
                "updated": updated,
                "deleted": deleted,
                "unchanged": unchanged_count,
                "total": len(scanned_data),
                "changes": has_changes,
                "dry_run": dry_run,
                "storage": "lancedb",
            }
            err_console.print(json.dumps(output, indent=2))
        else:
            if not has_changes:
                err_console.print(
                    Panel(
                        f"LanceDB is up to date ({unchanged_count} tools unchanged)",
                        title="✅ Sync Complete",
                        style="green",
                    )
                )
            else:
                parts = []
                if added:
                    parts.append(f"[green]+{len(added)} added[/]")
                if updated:
                    parts.append(f"[yellow]~{len(updated)} updated[/]")
                if deleted:
                    parts.append(f"[red]-{len(deleted)} deleted[/]")

                status_style = "yellow" if dry_run else "green"

                err_console.print(
                    Panel(
                        "\n".join(parts),
                        title="⚡ Sync Report" + (" (DRY RUN)" if dry_run else ""),
                        subtitle=f"Total Tools: {unchanged_count + len(added) + len(updated)}",
                        style=status_style,
                    )
                )

    except Exception as e:
        err_console.print(
            Panel(
                f"Sync failed: {e}",
                title="❌ Error",
                style="red",
            )
        )
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(1)


@skill_app.command("index-stats")
def skill_index_stats(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """
    Show statistics about the skill index in LanceDB.
    """
    try:
        from omni.foundation.bridge import RustVectorStore

        store = RustVectorStore()
        tools = asyncio.run(store.list_all_tools())

        # Group by skill
        skills_count = len(set(t.get("skill_name", "unknown") for t in tools))

        if json_output:
            err_console.print(
                json.dumps(
                    {
                        "skill_count": skills_count,
                        "tool_count": len(tools),
                        "storage": "lancedb",
                    },
                    indent=2,
                )
            )
        else:
            err_console.print(
                Panel(
                    f"Skills: {skills_count}\n"
                    f"Tools: {len(tools)}\n"
                    f"Storage: LanceDB (.cache/omni-vector/)",
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
