# core/project_memory.py
"""
ProjectMemory - Unified memory interface.

Provides a unified interface for project memory operations backed by LanceDB.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from omni.foundation.services.memory.core.interface import (
    STORAGE_MODE_LANCE,
    MemoryStore,
)

log = structlog.get_logger("mcp-core.memory")


# =============================================================================
# Directory Configuration
# =============================================================================


# Default memory directory (from PRJ_CACHE + "memory")
def _get_memory_dir() -> Path:
    """Get memory directory from PRJ_CACHE."""
    try:
        from omni.foundation import prj_dirs

        return prj_dirs.PRJ_CACHE("memory")
    except Exception:
        # Fallback for edge cases
        return Path(".cache/omni-dev-fusion/memory")


MEMORY_DIR = _get_memory_dir()


def init_memory_dir(dir_path: Path | None = None) -> bool:
    """Initialize the memory directory structure."""
    if dir_path is None:
        dir_path = MEMORY_DIR

    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "decisions").mkdir(exist_ok=True)
        (dir_path / "tasks").mkdir(exist_ok=True)
        (dir_path / "context").mkdir(exist_ok=True)
        (dir_path / "active_context").mkdir(exist_ok=True)
        return True
    except Exception as e:
        log.info("memory.init_failed", error=str(e))
        return False


# =============================================================================
# Memory Store Factory
# =============================================================================

# Lazy imports for optional dependencies
try:
    from omni.foundation.services.memory.stores.lancedb import LanceDBMemoryStore

    LANCE_DB_AVAILABLE = True
except ImportError:
    LANCE_DB_AVAILABLE = False
    LanceDBMemoryStore = None  # type: ignore


def _create_store(dir_path: Path) -> MemoryStore:
    """Create the LanceDB-backed memory store."""
    if not (LANCE_DB_AVAILABLE and LanceDBMemoryStore):
        raise RuntimeError("LanceDB memory backend is required but unavailable")
    db_path = str(dir_path / "memory.lance")
    return LanceDBMemoryStore(db_path=db_path)


# =============================================================================
# ProjectMemory - Main Interface
# =============================================================================


class ProjectMemory:
    """Provides unified interface for project memory operations.

    Uses LanceDB as the single storage backend.
    """

    def __init__(
        self,
        dir_path: Path | None = None,
    ):
        """Initialize ProjectMemory.

        Args:
            dir_path: Base directory for LanceDB files and local context artifacts.
        """
        self._storage_mode = STORAGE_MODE_LANCE
        self._file_dir_path = dir_path or MEMORY_DIR

        self._store: MemoryStore = _create_store(self._file_dir_path)

        # Initialize local context directories used by spec-path helpers.
        init_memory_dir(self._file_dir_path)

    @property
    def storage_mode(self) -> StorageMode:
        """Get the current storage mode."""
        return self._storage_mode

    @property
    def is_lance_mode(self) -> bool:
        """Check if using LanceDB storage."""
        return self._storage_mode == STORAGE_MODE_LANCE

    # =====================================================================
    # Decision Operations
    # =====================================================================

    def add_decision(
        self,
        title: str,
        content: str = "",
        problem: str = "",
        solution: str = "",
        rationale: str = "",
        status: str = "open",
    ) -> dict[str, Any]:
        """Add a new architectural decision."""
        if not title.strip():
            return {"success": False, "id": None, "error": "Title is required"}
        if content and not (problem or solution or rationale):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    problem = str(parsed.get("problem", problem))
                    solution = str(parsed.get("solution", solution))
                    rationale = str(parsed.get("rationale", rationale))
            except Exception:
                pass
        return self._store.add_decision(
            title=title,
            content=content,
            problem=problem,
            solution=solution,
            rationale=rationale,
            status=status,
        )

    def list_decisions(self) -> list[dict[str, Any]]:
        """List all recorded decisions."""
        return self._store.list_decisions()

    def get_decision(self, title: str) -> dict[str, Any] | None:
        """Get a specific decision by title."""
        return self._store.get_decision(title)

    # =====================================================================
    # Task Operations
    # =====================================================================

    def add_task(
        self,
        title: str,
        content: str = "",
        status: str = "pending",
        assignee: str = "Claude",
    ) -> dict[str, Any]:
        """Add a new task to the backlog."""
        if not title.strip():
            return {"success": False, "id": None, "error": "Title is required"}
        return self._store.add_task(
            title=title,
            content=content,
            status=status,
            assignee=assignee,
        )

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        """List all tasks, optionally filtered by status."""
        return self._store.list_tasks(status)

    # =====================================================================
    # Context Operations
    # =====================================================================

    def save_context(self, context_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Save a snapshot of current project context."""
        return self._store.save_context(context_data)

    def get_latest_context(self) -> dict[str, Any] | None:
        """Get the latest context snapshot."""
        return self._store.get_latest_context()

    # =====================================================================
    # Formatting Methods
    # =====================================================================

    def format_decisions_list(self) -> str:
        """Format decisions as a readable list."""
        decisions = self.list_decisions()
        if not decisions:
            return "No decisions recorded yet."

        lines = ["--- Architectural Decisions ---"]
        for d in decisions:
            status = d.get("status", "open")
            title = d.get("title", "Untitled")
            lines.append(f"- {title} [{status}]")
        return "\n".join(lines)

    def format_tasks_list(self, status: str | None = None) -> str:
        """Format tasks as a readable list."""
        tasks = self.list_tasks(status)
        if not tasks:
            return "No tasks found."

        lines = ["--- Tasks ---"]
        for t in tasks:
            task_status = t.get("status", "pending")
            assignee = t.get("assignee", "unassigned")
            lines.append(f"- {t.get('title', 'Untitled')} [{task_status}] @{assignee}")
        return "\n".join(lines)

    # =====================================================================
    # Active Context Management
    # =====================================================================

    def update_status(
        self, phase: str, focus: str, blockers: str = "None", sentiment: str = "Neutral"
    ) -> dict[str, Any]:
        """Update the global project status (The 'RAM')."""
        return self._store.update_status(
            phase=phase,
            focus=focus,
            blockers=blockers,
            sentiment=sentiment,
        )

    def get_status(self) -> str:
        """Read the current project status."""
        return self._store.get_status()

    def log_scratchpad(self, entry: str, source: str = "Note") -> dict[str, Any]:
        """Append a thought, observation, or COMMAND LOG to the scratchpad."""
        return self._store.log_scratchpad(entry, source)

    # =====================================================================
    # Spec Path Management
    # =====================================================================

    def set_spec_path(self, spec_path: str) -> dict[str, Any]:
        """Store the current spec path for the legislation workflow."""
        spec_file = self._file_dir_path / "active_context" / "current_spec.json"
        data = {"spec_path": spec_path, "timestamp": datetime.now().isoformat()}
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("memory.spec_path_set", spec_path=spec_path)
        return {"success": True, "file": str(spec_file)}

    def get_spec_path(self) -> str | None:
        """Get the current spec path stored by start_spec."""
        spec_file = self._file_dir_path / "active_context" / "current_spec.json"
        if not spec_file.exists():
            return None
        try:
            data = json.loads(spec_file.read_text(encoding="utf-8"))
            return data.get("spec_path")
        except (OSError, json.JSONDecodeError):
            return None

    # =====================================================================
    # Migration
    # =====================================================================

    def migrate_from_file(self, source_dir: Path | None = None) -> dict[str, Any]:
        """Import records from markdown export directories into LanceDB.

        Args:
            source_dir: Source directory containing `decisions/*.md` and `tasks/*.md`.

        Returns:
            Dict with import statistics.
        """
        source = source_dir or self._file_dir_path
        return self._store.migrate_from_file(source)
