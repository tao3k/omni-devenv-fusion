"""sync.py - Unified Sync Protocol

The "One Ring" command to synchronize all vector indexes and system state.
Consolidates 'ingest knowledge', 'ingest skills', and memory indexing.

Usage:
    omni sync                # Sync EVERYTHING (Default)
    omni sync knowledge      # Sync documentation only
    omni sync skills         # Sync skill registry (Cortex) only
    omni sync router         # Sync router database (Hybrid Search) only
    omni sync memory         # Optimize memory index
    omni sync symbols        # Sync code symbols (Zero-Token Indexing)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.config.dirs import PRJ_CONFIG
from omni.foundation.runtime.gitops import get_project_root
from omni.foundation.utils.asyncio import run_async_blocking
from omni.foundation.utils.common import setup_import_paths

# Setup paths before importing omni modules
setup_import_paths()

console = Console()

# Sync-specific logger
sync_logger = logging.getLogger("omni.sync")
sync_logger.setLevel(logging.DEBUG)


class SyncLogger:
    """Structured logger for sync operations with timestamps and phases."""

    def __init__(self, name: str = "sync"):
        self.name = name
        self.start_times: dict[str, float] = {}
        self.phase_stack: list[str] = []

    def _now(self) -> str:
        """Get current timestamp."""
        return datetime.now().strftime("%H:%M:%S")

    def _format(self, level: str, phase: str, msg: str) -> str:
        """Format log message with timestamp and phase."""
        return f"[{self._now()}] [{level}] [{phase}] {msg}"

    def phase(self, name: str) -> None:
        """Mark the start of a phase."""
        self.phase_stack.append(name)
        self.start_times[name] = time.time()
        icon = ">>>" if len(self.phase_stack) == 1 else "..."
        console.print(f"\n{icon} [bold cyan]{name}[/bold cyan]")

    def end_phase(self, name: str, status: str = "done") -> float:
        """Mark the end of a phase and return elapsed time."""
        elapsed = time.time() - self.start_times.get(name, 0)
        if name in self.phase_stack:
            self.phase_stack.pop()
        icon = "<<<"
        status_color = {"done": "green", "skip": "yellow", "error": "red"}.get(status, "white")
        console.print(f"{icon} [bold {status_color}]{name}[/bold {status_color}] - {elapsed:.2f}s")
        return elapsed

    def info(self, msg: str, phase: str = "main") -> None:
        """Log info message."""
        console.print(self._format("INFO", phase, msg))

    def success(self, msg: str, phase: str = "main") -> None:
        """Log success message."""
        console.print(f"  [green]✓[/green] {msg}")

    def error(self, msg: str, phase: str = "main", exc: Exception | None = None) -> None:
        """Log error message with optional exception."""
        console.print(f"  [red]✗[/red] {msg}")
        if exc:
            console.print(f"     [dim]Exception: {type(exc).__name__}: {exc}[/dim]")

    def warn(self, msg: str, phase: str = "main") -> None:
        """Log warning message."""
        console.print(f"  [yellow]![/yellow] {msg}")

    def progress(self, current: int, total: int, msg: str = "") -> None:
        """Show progress."""
        percent = (current / total * 100) if total > 0 else 0
        bar = "█" * int(percent / 5) + "░" * (20 - int(percent / 5))
        console.print(f"  [{bar}] {current}/{total} {msg}", end="\r")


# Global sync logger instance
sync_log = SyncLogger()

sync_app = typer.Typer(
    name="sync",
    help="Synchronize system state and vector indexes (knowledge, skills, memory)",
    invoke_without_command=True,  # Allow 'omni sync' to run default action
)


def _resolve_references_config_path() -> str:
    """Resolve dependency references config path with canonical precedence.

    Order:
    1. Explicit env override: OMNI_REFERENCES_YAML
    2. Active config: $PRJ_CONFIG_HOME/omni-dev-fusion/references.yaml
    3. Repository default: <git-root>/assets/references.yaml
    """
    import os

    env_path = os.environ.get("OMNI_REFERENCES_YAML")
    if env_path:
        return env_path

    active_path = PRJ_CONFIG("omni-dev-fusion", "references.yaml")
    if active_path.exists():
        return str(active_path)

    try:
        return str(get_project_root() / "assets" / "references.yaml")
    except Exception:
        return "assets/references.yaml"


def _print_sync_report(
    title: str, stats: dict[str, Any], json_output: bool = False, elapsed: float = 0.0
):
    """Print a standardized sync report."""
    if json_output:
        print(json.dumps(stats, indent=2))
        return

    # Count successes and errors
    success_count = sum(
        1 for v in stats.values() if isinstance(v, dict) and v.get("status") == "success"
    )
    error_count = sum(
        1 for v in stats.values() if isinstance(v, dict) and v.get("status") == "error"
    )
    total_count = len(stats)

    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_row(f"[bold cyan]Sync Operation:[/bold cyan] {title}")
    grid.add_row(
        f"[dim]Completed in {elapsed:.2f}s | {success_count}/{total_count} successful[/dim]"
    )
    if error_count > 0:
        grid.add_row(f"[red]{error_count} errors encountered[/red]")
    grid.add_row("")

    metrics = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
    metrics.add_column("Component")
    metrics.add_column("Status", style="yellow")
    metrics.add_column("Details", style="dim")

    for component, info in stats.items():
        if not isinstance(info, dict):
            continue
        status = info.get("status", "unknown")
        icon = (
            "[green]✓[/green]"
            if status == "success"
            else "[red]✗[/red]"
            if status == "error"
            else "[yellow]⊘[/yellow]"
        )
        details = info.get("details", "")
        comp_elapsed = info.get("elapsed", 0)

        # Handle external_deps sub-info
        if component == "symbols" and "external_deps" in info:
            ext = info["external_deps"]
            ext_status = ext.get("status", "")
            ext_details = ext.get("details", "")
            ext_icon = "[green]✓[/green]" if ext_status == "success" else "[yellow]⊘[/yellow]"
            elapsed_str = f" ({comp_elapsed:.2f}s)" if comp_elapsed > 0 else ""
            metrics.add_row(f"{component.title()}{elapsed_str} {icon}", status, details)
            metrics.add_row(f"  External Deps", ext_icon, ext_details)
        else:
            elapsed_str = f" ({comp_elapsed:.2f}s)" if comp_elapsed > 0 else ""
            metrics.add_row(f"{component.title()}{elapsed_str} {icon}", status, str(details))

    grid.add_row(metrics)

    # Choose border style based on success
    border = "green" if error_count == 0 else "red" if error_count == total_count else "yellow"
    console.print(Panel(grid, title="✓ System Sync Complete", border_style=border))


def _find_markdown_files(directory: str) -> list[str]:
    """Find all markdown files recursively."""
    path = Path(directory)
    if not path.is_dir():
        return []

    files = []
    # Use walk if available (Python 3.12+), else rglob
    if hasattr(path, "walk"):
        for root, _, filenames in path.walk():
            for filename in filenames:
                if filename.endswith((".md", ".markdown")):
                    files.append(str(root / filename))
    else:
        for p in path.rglob("*"):
            if p.suffix in (".md", ".markdown") and p.is_file():
                files.append(str(p))
    return files


async def _sync_symbols(clear: bool = False, verbose: bool | None = None) -> dict[str, Any]:
    """Internal logic to sync code symbols using Zero-Token Indexing.

    Uses omni-tags (Rust) to extract symbols without LLM tokens.
    This replaces LLM-based summarization for code files.

    Also indexes external crate dependencies for API lookup.
    """
    from omni.core.knowledge.symbol_indexer import SymbolIndexer
    from omni.foundation.config.logging import is_verbose
    from omni_core_rs import PyDependencyIndexer

    # Use explicit verbose if provided, otherwise check global logging config
    if verbose is None:
        verbose = is_verbose()

    sync_log.phase("Symbols Indexing")

    try:
        # Get project root
        try:
            project_root = str(get_project_root())
        except Exception:
            project_root = "."

        sync_log.info(f"Project root: {project_root}")
        sync_log.info(f"Extensions: [py, rs, js, ts, go, java]")
        sync_log.info(f"Clear mode: {clear}")
        if verbose:
            sync_log.info("Verbose mode: enabled")

        # First sync external dependencies (crates)
        config_path = _resolve_references_config_path()
        ext_crates = 0
        ext_symbols = 0

        if os.path.exists(config_path):
            sync_log.info("Syncing external dependencies...")
            try:
                indexer = PyDependencyIndexer(project_root, config_path)
                result_json = indexer.build(clean=clear, verbose=verbose)
                result = json.loads(result_json)
                ext_crates = result.get("crates_indexed", 0)
                ext_symbols = result.get("total_symbols", 0)
                errors = result.get("errors", 0)
                if errors > 0:
                    sync_log.warn(f"External deps errors: {errors}")
                sync_log.success(f"External: {ext_crates} crates, {ext_symbols} symbols")
            except Exception as e:
                sync_log.warn(f"External deps skipped: {e}")
        else:
            sync_log.info("External deps: config not found")

        # Then sync project symbols
        indexer = SymbolIndexer(
            project_root=project_root,
            extensions=[".py", ".rs", ".js", ".ts", ".go", ".java"],
        )

        sync_log.info("Extracting project symbols...")
        result = indexer.build(clean=clear)

        sync_log.success(
            f"Project: {result['unique_symbols']} symbols in {result['indexed_files']} files"
        )

        elapsed = sync_log.end_phase("Symbols Indexing", "done")
        return {
            "status": "success",
            "details": f"Project: {result['unique_symbols']} | External: {ext_symbols}",
            "project_symbols": result["unique_symbols"],
            "project_files": result["indexed_files"],
            "external_crates": ext_crates,
            "external_symbols": ext_symbols,
            "elapsed": elapsed,
        }
    except Exception as e:
        sync_log.error(f"Symbol indexing failed: {e}", exc=e)
        sync_log.end_phase("Symbols Indexing", "error")
        return {"status": "error", "details": str(e)}


async def _sync_external_dependencies(clear: bool = False) -> dict[str, Any]:
    """Sync external crate dependency symbols for API lookup."""
    from omni_core_rs import PyDependencyIndexer
    import os

    sync_log.phase("External Dependencies")

    try:
        project_root = os.environ.get("OMNI_PROJECT_ROOT", ".")
        config_path = _resolve_references_config_path()

        sync_log.info(f"Project: {project_root}")
        sync_log.info(f"Config: {config_path}")

        if not os.path.exists(config_path):
            sync_log.warn(f"Config not found: {config_path}, skipping external deps")
            sync_log.end_phase("External Dependencies", "skip")
            return {"status": "skipped", "details": "config not found"}

        indexer = PyDependencyIndexer(project_root, config_path)

        sync_log.info("Building dependency index...")
        result_json = indexer.build(clean=clear)
        result = json.loads(result_json)

        crates = result.get("crates_indexed", 0)
        symbols = result.get("total_symbols", 0)
        errors = result.get("errors", 0)
        error_details = result.get("error_details", [])

        sync_log.success(f"Indexed {crates} crates, {symbols} symbols")
        if errors > 0:
            sync_log.warn(f"Errors during indexing: {errors}")
            for err in error_details:
                sync_log.warn(f"  - {err}")

        elapsed = sync_log.end_phase("External Dependencies", "done")
        return {
            "status": "success",
            "details": f"External deps: {crates} crates, {symbols} symbols",
            "elapsed": elapsed,
        }
    except ImportError:
        sync_log.warn("omni-core-rs not available")
        sync_log.end_phase("External Dependencies", "skip")
        return {"status": "skipped", "details": "omni-core-rs not available"}
    except Exception as e:
        sync_log.error(f"External deps failed: {e}", exc=e)
        sync_log.end_phase("External Dependencies", "error")
        return {"status": "error", "details": str(e)}


async def _sync_knowledge(clear: bool = False, include_code: bool = False) -> dict[str, Any]:
    """Internal logic to sync knowledge base (Librarian).

    By default, this only indexes documentation (markdown files).
    Code files are indexed via _sync_symbols (Zero-Token).

    Args:
        clear: Clear existing index first
        include_code: Also index code files (NOT recommended - use _sync_symbols instead)
    """
    from pathlib import Path

    from omni.core.knowledge.librarian import Librarian
    from omni.foundation.runtime.path_filter import should_skip_path, SKIP_DIRS

    try:
        librarian = Librarian()

        # Configure FileIngestor to use globs from knowledge_dirs config
        original_discover = librarian.ingestor.discover_files

        def knowledge_discover(project_root: Path, **kwargs):
            """Discover files using globs from knowledge_dirs config."""
            files = []
            for entry in librarian.config.knowledge_dirs:
                dir_path = project_root / entry.get("path", "")
                globs = entry.get("globs", [])

                # Support both single glob and list of globs
                if isinstance(globs, str):
                    globs = [globs]

                if not dir_path.exists():
                    continue

                for glob_pattern in globs:
                    for f in dir_path.glob(glob_pattern):
                        if f.is_file() and not should_skip_path(
                            f, skip_hidden=True, skip_dirs=SKIP_DIRS
                        ):
                            files.append(f)
            return sorted(set(files))

        librarian.ingestor.discover_files = knowledge_discover

        # Use ingest() which handles file discovery, chunking, and indexing
        result = librarian.ingest(clean=clear)

        # Restore original method
        librarian.ingestor.discover_files = original_discover

        return {
            "status": "success",
            "details": f"Indexed {result['files_processed']} docs, {result['chunks_indexed']} chunks (code: use 'omni sync symbols')",
        }
    except Exception as e:
        return {"status": "error", "details": str(e)}


async def _sync_skills() -> dict[str, Any]:
    """Internal logic to sync skill registry (Cortex) and skills table."""
    from omni.foundation.bridge import get_vector_store
    from omni.foundation.config.skills import SKILLS_DIR

    try:
        skills_path = str(SKILLS_DIR())
        if not Path(skills_path).exists():
            return {"status": "skipped", "details": "Skills dir not found"}

        # Index tools to skills table (for omni db search)
        store = get_vector_store()
        count = await store.index_skill_tools(skills_path, "skills")

        # Also update the skill discovery service
        from omni.core.skills.discovery import SkillDiscoveryService

        discovery = SkillDiscoveryService()
        skills = await discovery.discover_all()

        return {
            "status": "success",
            "details": f"Indexed {count} tools, registered {len(skills)} skills",
        }
    except Exception as e:
        return {"status": "error", "details": str(e)}


async def _sync_memory() -> dict[str, Any]:
    """Internal logic to optimize memory index."""
    # This usually just needs an optimization run
    from omni.foundation.services.vector import get_vector_store

    try:
        store = get_vector_store()
        # Create/Optimize index
        await store.create_index("memory")
        count = await store.count("memory")
        return {"status": "success", "details": f"Optimized index ({count} memories)"}
    except Exception as e:
        return {"status": "error", "details": str(e)}


async def _sync_router() -> dict[str, Any]:
    """Internal logic to sync router database from skills."""
    from omni.foundation.bridge import get_vector_store
    from omni.foundation.config import get_database_path
    from omni.foundation.config.skills import SKILLS_DIR

    try:
        router_path = get_database_path("router")
        skills_path = str(SKILLS_DIR())

        router_store = get_vector_store(router_path, enable_keyword_index=True)
        count = await router_store.index_skill_tools(skills_path, "router")

        return {"status": "success", "details": f"Synced {count} tools to router"}
    except Exception as e:
        return {"status": "error", "details": str(e)}


@sync_app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed logs"),
):
    """
    Synchronize system state and vector indexes.

    If no subcommand is provided, syncs EVERYTHING (Knowledge + Skills + Memory).
    """
    # If a subcommand is called (e.g. 'omni sync knowledge'), let it handle execution
    if ctx.invoked_subcommand is not None:
        return

    # Default action: Sync All
    from datetime import datetime

    sync_log.phase("FULL SYSTEM SYNC")
    start_time = datetime.now()

    async def run_sync_all():
        stats = {}

        # 1. Symbols (Zero-Token Code Index)
        sync_log.info("Starting symbols sync...")
        stats["symbols"] = await _sync_symbols()

        # 2. Skills (Cortex)
        sync_log.info("Starting skills sync...")
        stats["skills"] = await _sync_skills()

        # 3. Router (Hybrid Search Index)
        sync_log.info("Starting router sync...")
        stats["router"] = await _sync_router()

        # 4. Knowledge (Librarian - Docs only)
        sync_log.info("Starting knowledge sync...")
        stats["knowledge"] = await _sync_knowledge()

        # 5. Memory (Hippocampus)
        sync_log.info("Starting memory sync...")
        stats["memory"] = await _sync_memory()

        # Calculate total time
        total_elapsed = (datetime.now() - start_time).total_seconds()

        _print_sync_report("Full System Sync", stats, json_output, total_elapsed)

    run_async_blocking(run_sync_all())


@sync_app.command("knowledge")
def sync_knowledge_cmd(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing index first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Sync documentation into the knowledge base.
    """
    stats = {"knowledge": run_async_blocking(_sync_knowledge(clear))}
    _print_sync_report("Knowledge Base", stats, json_output)


@sync_app.command("skills")
def sync_skills_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Sync skill registry (Cortex).
    """
    stats = {"skills": run_async_blocking(_sync_skills())}
    _print_sync_report("Skill Cortex", stats, json_output)


@sync_app.command("memory")
def sync_memory_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Optimize and sync memory index.
    """
    stats = {"memory": run_async_blocking(_sync_memory())}
    _print_sync_report("Memory Index", stats, json_output)


@sync_app.command("router")
def sync_router_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Sync router database from skills (Hybrid Search Index).
    """
    stats = {"router": run_async_blocking(_sync_router())}
    _print_sync_report("Router Index", stats, json_output)


@sync_app.command("symbols")
def sync_symbols_cmd(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing symbol index first"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Sync code symbols using Zero-Token Indexing.

    This uses omni-tags (Rust AST extraction) to index functions,
    classes, and other symbols without using LLM tokens.

    Examples:
        omni sync symbols
        omni sync symbols --clear
        omni sync symbols --verbose
    """
    stats = {"symbols": run_async_blocking(_sync_symbols(clear, verbose))}
    _print_sync_report("Symbol Index (Zero-Token)", stats, json_output)


def register_sync_command(parent_app: typer.Typer) -> None:
    """Register the sync command with the parent app."""
    parent_app.add_typer(sync_app, name="sync")


__all__ = ["sync_app", "register_sync_command"]
