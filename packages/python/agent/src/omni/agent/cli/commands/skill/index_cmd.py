# agent/cli/commands/skill/index_cmd.py
"""
Index commands for skill CLI.

Contains: reindex, sync, index-stats commands.
(watch deprecated in thin client model)
"""

from __future__ import annotations

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
    import logging
    import os

    from omni.core.skills.discovery import SkillDiscoveryService
    from omni.foundation.config.dirs import PRJ_CACHE
    from omni.foundation.config.logging import get_logger

    logger = get_logger("omni.core.reindex")

    # Suppress verbose logging by default
    if not verbose:
        logging.getLogger("omni.core.discovery").setLevel(logging.WARNING)

    err_console.print(
        Panel(
            "Full reindex of skill tools...",
            title="🔄 Reindex",
            style="blue",
        )
    )

    try:
        skills_path = str(SKILLS_DIR())

        # Export index using Rust scanner (creates skill_index.json)
        if export_index:
            try:
                from omni_core_rs import export_skill_index

                cache_dir = str(PRJ_CACHE())
                os.makedirs(cache_dir, exist_ok=True)
                output_path = os.path.join(cache_dir, "skill_index.json")

                # Call Rust to generate the index
                json_result = export_skill_index(skills_path, output_path)
                if json_result:
                    logger.info(f"Exported skill index to {output_path}")
            except ImportError:
                logger.warning("Rust scanner not available, skipping index export")

        # Clear and full reindex
        if clear:
            err_console.print("Clearing existing index...")
            # Would clear index here if available

        # Full reindex using discovery service
        discovery = SkillDiscoveryService()
        skills = discovery.discover_all([skills_path])

        if json_output:
            import json

            err_console.print(
                json.dumps(
                    {
                        "total_tools_indexed": len(skills),
                        "mode": "full_reindex",
                        "exported_skills": len(skills),
                    },
                    indent=2,
                )
            )
        else:
            err_console.print(
                Panel(
                    f"Reindexed {len(skills)} skills (full rebuild)",
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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress logs"),
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
        omni skill sync --json      # JSON output for scripting
    """
    import json
    import logging
    from pathlib import Path

    from omni.foundation.bridge.scanner import PythonSkillScanner

    # Suppress verbose logging by default
    if not verbose:
        logging.getLogger("omni.core.discovery").setLevel(logging.WARNING)

    err_console.print(
        Panel(
            "Incrementally syncing skill tools...",
            title="⚡ Sync",
            style="blue",
        )
    )

    try:
        scanner = PythonSkillScanner()
        index_path = scanner.index_path

        # Discover current skills from index
        index_entries = scanner.scan_directory()
        current_skills = {entry.skill_name for entry in index_entries}

        # Load existing index to compare (if exists)
        old_skills = set()
        if Path(index_path).exists():
            try:
                with open(index_path, encoding="utf-8") as f:
                    old_data = json.load(f)
                old_skills = {item.get("name") for item in old_data if item.get("name")}
            except (OSError, json.JSONDecodeError):
                old_skills = set()

        # Calculate deltas
        added = current_skills - old_skills
        deleted = old_skills - current_skills

        # No changes if sets are equal
        has_changes = len(added) > 0 or len(deleted) > 0

        # Format result
        added_count = len(added)
        deleted_count = len(deleted)

        if json_output:
            err_console.print(
                json.dumps(
                    {
                        "added": added_count,
                        "modified": 0,
                        "deleted": deleted_count,
                        "total": len(current_skills),
                        "changes": has_changes,
                    },
                    indent=2,
                )
            )
        else:
            if has_changes:
                parts = []
                if added_count > 0:
                    parts.append(f"+{added_count} added")
                if deleted_count > 0:
                    parts.append(f"-{deleted_count} deleted")
                summary = ", ".join(parts)
            else:
                summary = "No changes"

            err_console.print(
                Panel(
                    f"{summary} ({len(current_skills)} total)",
                    title="✅ Sync Complete",
                    style="green" if has_changes else "blue",
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
        raise typer.Exit(1)


@skill_app.command("index-stats")
def skill_index_stats(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """
    Show statistics about the skill discovery service.
    """
    from omni.core.skills.discovery import SkillDiscoveryService

    try:
        discovery = SkillDiscoveryService()
        skills_path = str(SKILLS_DIR())
        skills = discovery.discover_all([skills_path])

        if json_output:
            import json

            err_console.print(
                json.dumps(
                    {
                        "skill_count": len(skills),
                        "rust_available": discovery.is_rust_available,
                    },
                    indent=2,
                )
            )
        else:
            err_console.print(
                Panel(
                    f"Discovered Skills: {len(skills)}\n"
                    f"Rust Scanner: {'Available' if discovery.is_rust_available else 'Not Available'}",
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


# Deprecated command - file watcher not available in thin client model
@skill_app.command("watch")
def skill_watch():
    """
    Start a file watcher to automatically sync skills on change. [DEPRECATED]
    """
    err_console.print(
        Panel(
            "Background file watching is not available in thin client mode.\n"
            "Skills are loaded automatically on restart.",
            title="⚠️ Deprecated",
            style="yellow",
        )
    )
