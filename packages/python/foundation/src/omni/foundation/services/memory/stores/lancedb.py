# stores/lancedb.py
"""
LanceDB-based memory storage implementation.

Provides efficient structured data storage using LanceDB.
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

# Availability check
_LANCE_DB_AVAILABLE = True
try:
    import lancedb
    import pyarrow as pa

    LANCE_DB_AVAILABLE = True
except ImportError:
    LANCE_DB_AVAILABLE = False
    lancedb = None  # type: ignore
    pa = None  # type: ignore


# =============================================================================
# Schema Definitions
# =============================================================================

DECISIONS_SCHEMA = [
    ("id", "string"),
    ("title", "string"),
    ("content", "string"),
    ("problem", "string"),
    ("solution", "string"),
    ("rationale", "string"),
    ("status", "string"),
    ("author", "string"),
    ("date", "string"),
    ("metadata", "string"),
]

TASKS_SCHEMA = [
    ("id", "string"),
    ("title", "string"),
    ("content", "string"),
    ("status", "string"),
    ("assignee", "string"),
    ("created", "string"),
    ("metadata", "string"),
]

CONTEXT_SCHEMA = [
    ("id", "string"),
    ("timestamp", "string"),
    ("data", "string"),
    ("metadata", "string"),
]

ACTIVE_CONTEXT_SCHEMA = [
    ("id", "string"),
    ("type", "string"),
    ("content", "string"),
    ("updated", "string"),
    ("metadata", "string"),
]


# =============================================================================
# LanceDB Store Implementation
# =============================================================================


class LanceDBMemoryStore(MemoryStore):
    """LanceDB-based storage for project memory.

    Provides efficient structured data storage with ACID guarantees.
    """

    def __init__(self, db_path: str | None = None):
        """Initialize the LanceDB memory store.

        Args:
            db_path: Path to the LanceDB database. Defaults to memory.lance.
        """
        if not LANCE_DB_AVAILABLE:
            raise RuntimeError("LanceDB not installed. Run: pip install lancedb")

        if db_path is None:
            from omni.foundation.config.dirs import get_memory_db_path

            db_path = str(get_memory_db_path())

        self._db_path = db_path
        self._db: lancedb.DBConnection = lancedb.connect(db_path)
        self._initialized = False

    def _ensure_tables(self) -> None:
        """Ensure all tables exist."""
        if self._initialized:
            return

        def _create_table_if_needed(name: str, schema: list[tuple[str, str]]) -> None:
            """Create a table if it doesn't exist."""
            try:
                self._db.open_table(name)
            except Exception:
                try:
                    arrays = {}
                    for field_name, field_type in schema:
                        arrays[field_name] = pa.array([], type=pa.string())
                    empty_table = pa.table(arrays)
                    self._db.create_table(name, empty_table)
                except Exception:
                    log.debug(f"Table {name} may already exist")

        _create_table_if_needed("decisions", DECISIONS_SCHEMA)
        _create_table_if_needed("tasks", TASKS_SCHEMA)
        _create_table_if_needed("context", CONTEXT_SCHEMA)
        _create_table_if_needed("active_context", ACTIVE_CONTEXT_SCHEMA)

        self._initialized = True
        log.info("memory.lance_db_initialized", path=self._db_path)

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
        author: str = "Claude",
    ) -> dict[str, Any]:
        """Add a new architectural decision."""
        self._ensure_tables()

        decision_id = title.lower().replace(" ", "_")
        timestamp = datetime.now().isoformat()

        data = {
            "id": decision_id,
            "title": title,
            "content": content,
            "problem": problem,
            "solution": solution,
            "rationale": rationale,
            "status": status,
            "author": author,
            "date": timestamp,
            "metadata": "{}",
        }

        try:
            tbl = self._db.open_table("decisions")
            tbl.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(
                [data]
            )
            log.info("memory.decision_added", title=title)
            return {"success": True, "id": decision_id, "error": ""}
        except Exception as e:
            log.error("memory.decision_add_failed", error=str(e))
            return {"success": False, "id": None, "error": str(e)}

    def list_decisions(self) -> list[dict[str, Any]]:
        """List all recorded decisions."""
        self._ensure_tables()

        try:
            tbl = self._db.open_table("decisions")
            df = tbl.to_pandas()
            if df.empty:
                return []
            records = df.to_dict(orient="records")
            for record in records:
                if isinstance(record.get("metadata"), str):
                    try:
                        record["metadata"] = json.loads(record["metadata"])
                    except json.JSONDecodeError:
                        record["metadata"] = {}
            return records
        except Exception as e:
            log.error("memory.list_decisions_failed", error=str(e))
            return []

    def get_decision(self, title: str) -> dict[str, Any] | None:
        """Get a specific decision by title."""
        decisions = self.list_decisions()
        decision_id = title.lower().replace(" ", "_")
        for d in decisions:
            if d.get("id") == decision_id or d.get("title") == title:
                return d
        return None

    def delete_decision(self, title: str) -> bool:
        """Delete a decision by title."""
        # LanceDB doesn't support direct delete, so we mark as deleted
        decision_id = title.lower().replace(" ", "_")
        result = self.add_decision(title=title, content="", status="deleted", author="")
        return result["success"]

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
        self._ensure_tables()

        task_id = title.lower().replace(" ", "_")
        timestamp = datetime.now().isoformat()

        data = {
            "id": task_id,
            "title": title,
            "content": content,
            "status": status,
            "assignee": assignee,
            "created": timestamp,
            "metadata": "{}",
        }

        try:
            tbl = self._db.open_table("tasks")
            tbl.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(
                [data]
            )
            log.info("memory.task_added", title=title)
            return {"success": True, "id": task_id, "error": ""}
        except Exception as e:
            log.error("memory.task_add_failed", error=str(e))
            return {"success": False, "id": None, "error": str(e)}

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        """List all tasks, optionally filtered by status."""
        self._ensure_tables()

        try:
            tbl = self._db.open_table("tasks")
            df = tbl.to_pandas()
            if df.empty:
                return []
            records = df.to_dict(orient="records")
            for record in records:
                if isinstance(record.get("metadata"), str):
                    try:
                        record["metadata"] = json.loads(record["metadata"])
                    except json.JSONDecodeError:
                        record["metadata"] = {}
            if status:
                records = [r for r in records if r.get("status") == status]
            return records
        except Exception as e:
            log.error("memory.list_tasks_failed", error=str(e))
            return []

    def get_task(self, title: str) -> dict[str, Any] | None:
        """Get a specific task by title."""
        tasks = self.list_tasks()
        task_id = title.lower().replace(" ", "_")
        for t in tasks:
            if t.get("id") == task_id or t.get("title") == title:
                return t
        return None

    def delete_task(self, title: str) -> bool:
        """Delete a task by title."""
        task_id = title.lower().replace(" ", "_")
        result = self.add_task(title=title, content="", status="deleted", assignee="")
        return result["success"]

    # =====================================================================
    # Context Operations
    # =====================================================================

    def save_context(self, context_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Save a snapshot of current project context."""
        self._ensure_tables()

        if context_data is None:
            context_data = {}

        context_id = datetime.now().isoformat()
        timestamp = datetime.now().isoformat()

        full_context = {
            "timestamp": timestamp,
            "files_tracked": 0,
            "cwd": str(Path.cwd()),
            **context_data,
        }

        data = {
            "id": context_id,
            "timestamp": timestamp,
            "data": json.dumps(full_context, ensure_ascii=False),
            "metadata": "{}",
        }

        try:
            tbl = self._db.open_table("context")
            tbl.add([data])
            log.info("memory.context_saved")
            return {"success": True, "id": context_id, "error": ""}
        except Exception as e:
            log.error("memory.context_save_failed", error=str(e))
            return {"success": False, "id": None, "error": str(e)}

    def get_latest_context(self) -> dict[str, Any] | None:
        """Get the latest context snapshot."""
        self._ensure_tables()

        try:
            tbl = self._db.open_table("context")
            df = tbl.to_pandas()
            if df.empty:
                return None
            row = df.iloc[-1]
            data_str = row.get("data", "{}")
            if isinstance(data_str, str):
                return json.loads(data_str)
            return data_str
        except Exception as e:
            log.error("memory.get_latest_context_failed", error=str(e))
            return None

    # =====================================================================
    # Active Context Operations
    # =====================================================================

    def update_status(
        self,
        phase: str,
        focus: str,
        blockers: str = "None",
        sentiment: str = "Neutral",
    ) -> dict[str, Any]:
        """Update the global project status (The 'RAM')."""
        self._ensure_tables()

        timestamp = datetime.now().isoformat()
        content = f"""# Active Project Context
> Last Updated: {timestamp}

## Current Status
- Phase: {phase}
- Focus: {focus}
- Blockers: {blockers}
- Sentiment: {sentiment}
"""

        data = {
            "id": "status",
            "type": "status",
            "content": content,
            "updated": timestamp,
            "metadata": json.dumps(
                {"phase": phase, "focus": focus, "blockers": blockers, "sentiment": sentiment}
            ),
        }

        try:
            tbl = self._db.open_table("active_context")
            tbl.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(
                [data]
            )
            log.info("memory.status_updated", phase=phase, focus=focus)
            return {"success": True, "id": "status", "error": ""}
        except Exception as e:
            log.error("memory.status_update_failed", error=str(e))
            return {"success": False, "id": None, "error": str(e)}

    def get_status(self) -> str:
        """Read the current project status."""
        self._ensure_tables()

        try:
            tbl = self._db.open_table("active_context")
            df = tbl.to_pandas()
            if df.empty:
                return "No active context found. System is idle."
            status_rows = df[df["type"] == "status"]
            if status_rows.empty:
                return "No active context found. System is idle."
            return status_rows.iloc[0].get("content", "No active context found. System is idle.")
        except Exception as e:
            log.error("memory.get_status_failed", error=str(e))
            return "Error reading status."

    def log_scratchpad(self, entry: str, source: str = "Note") -> dict[str, Any]:
        """Append a thought, observation, or COMMAND LOG to the scratchpad."""
        self._ensure_tables()

        timestamp = datetime.now().strftime("%H:%M:%S")

        if source == "System":
            entry_text = f"\n> `[{timestamp}]` **EXEC**: {entry}\n"
        else:
            entry_text = f"\n### [{timestamp}] {source}\n{entry}\n"

        scratchpad_id = "scratchpad"
        timestamp_full = datetime.now().isoformat()

        existing_content = ""
        try:
            tbl = self._db.open_table("active_context")
            df = tbl.to_pandas()
            scratchpad_rows = df[df["id"] == scratchpad_id]
            if not scratchpad_rows.empty:
                existing_content = scratchpad_rows.iloc[0].get("content", "")
        except Exception:
            pass

        new_content = existing_content + entry_text

        data = {
            "id": scratchpad_id,
            "type": "scratchpad",
            "content": new_content,
            "updated": timestamp_full,
            "metadata": "{}",
        }

        try:
            tbl = self._db.open_table("active_context")
            tbl.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(
                [data]
            )
            log.info("memory.scratchpad_logged", source=source)
            return {"success": True, "id": scratchpad_id, "error": ""}
        except Exception as e:
            log.error("memory.scratchpad_log_failed", error=str(e))
            return {"success": False, "id": None, "error": str(e)}

    # =====================================================================
    # Migration & Mode
    # =====================================================================

    def migrate_from_file(self, file_memory_dir: Path) -> dict[str, Any]:
        """Migrate decisions and tasks from file-based storage."""
        self._ensure_tables()

        migrated = {"decisions": 0, "tasks": 0, "errors": []}

        from omni.foundation.services.memory.core.utils import parse_decision

        # Migrate decisions
        decisions_dir = file_memory_dir / "decisions"
        if decisions_dir.exists():
            for f in decisions_dir.glob("*.md"):
                try:
                    content = f.read_text(encoding="utf-8")
                    decision = parse_decision(content)
                    self.add_decision(
                        title=decision.get("title", f.stem),
                        content=content,
                        problem=decision.get("problem", ""),
                        solution=decision.get("solution", ""),
                        rationale=decision.get("rationale", ""),
                        status=decision.get("status", "open"),
                        author=decision.get("author", "Claude"),
                    )
                    migrated["decisions"] += 1
                except Exception as e:
                    migrated["errors"].append(f"Decision {f.name}: {e}")

        # Migrate tasks
        tasks_dir = file_memory_dir / "tasks"
        if tasks_dir.exists():
            for f in tasks_dir.glob("*.md"):
                try:
                    content = f.read_text(encoding="utf-8")
                    lines = content.split("\n")
                    task = {"title": f.stem, "status": "pending", "assignee": "Claude"}
                    for line in lines:
                        if line.startswith("Status:"):
                            task["status"] = line.replace("Status:", "").strip()
                        elif line.startswith("Assignee:"):
                            task["assignee"] = line.replace("Assignee:", "").strip()
                    self.add_task(
                        title=task.get("title", f.stem),
                        content=content,
                        status=task.get("status", "pending"),
                        assignee=task.get("assignee", "Claude"),
                    )
                    migrated["tasks"] += 1
                except Exception as e:
                    migrated["errors"].append(f"Task {f.name}: {e}")

        log.info("memory.migration_complete", **migrated)
        return migrated

    def get_storage_mode(self) -> str:
        """Get the storage mode."""
        return STORAGE_MODE_LANCE
