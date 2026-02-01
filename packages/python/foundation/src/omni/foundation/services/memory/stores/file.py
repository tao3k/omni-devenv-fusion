# stores/file.py
"""
File-based memory storage implementation.

Provides legacy file-based storage for backward compatibility.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from omni.foundation.services.memory.core.interface import (
    STORAGE_MODE_FILE,
    MemoryStore,
)

log = structlog.get_logger("mcp-core.memory")


# =============================================================================
# Formatting Utilities
# =============================================================================


def format_decision(decision: dict[str, Any]) -> str:
    """Format a decision for storage as Markdown ADR."""
    lines = [
        f"# Decision: {decision.get('title', 'Untitled')}",
        f"Date: {decision.get('date', datetime.now().isoformat())}",
        f"Author: {decision.get('author', 'Claude')}",
        "",
        "## Problem",
        decision.get("problem", "N/A"),
        "",
        "## Solution",
        decision.get("solution", "N/A"),
        "",
        "## Rationale",
        decision.get("rationale", "N/A"),
        "",
        "## Status",
        decision.get("status", "open"),
    ]
    return "\n".join(lines)


def parse_decision(content: str) -> dict[str, str]:
    """Parse a Markdown ADR back to a dict."""
    decision: dict[str, str] = {}
    lines = content.split("\n")
    current_section: str | None = None
    section_content: list[str] = []

    for line in lines:
        if line.startswith("# Decision:"):
            decision["title"] = line.replace("# Decision:", "").strip()
        elif line.startswith("Date:"):
            decision["date"] = line.replace("Date:", "").strip()
        elif line.startswith("Author:"):
            decision["author"] = line.replace("Author:", "").strip()
        elif line.startswith("## "):
            if current_section and section_content:
                decision[current_section] = "\n".join(section_content).strip()
            current_section = line.replace("## ", "").lower().strip()
            section_content = []
        elif current_section in ["problem", "solution", "rationale", "status"]:
            section_content.append(line)

    if current_section and section_content:
        decision[current_section] = "\n".join(section_content).strip()

    return decision


# =============================================================================
# File Store Implementation
# =============================================================================


class FileMemoryStore(MemoryStore):
    """File-based storage for project memory.

    Stores decisions, tasks, and context as Markdown and JSON files.
    """

    def __init__(self, dir_path: Path):
        """Initialize the file-based memory store.

        Args:
            dir_path: Path to the memory directory.
        """
        self._dir_path = dir_path
        self._decisions_dir = dir_path / "decisions"
        self._tasks_dir = dir_path / "tasks"
        self._context_dir = dir_path / "context"
        self._active_dir = dir_path / "active_context"

        # Create directories
        for d in [
            self._decisions_dir,
            self._tasks_dir,
            self._context_dir,
            self._active_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

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
        """Add a new decision."""
        if not title:
            return {"success": False, "file": None, "error": "Title is required"}

        if content.startswith("{"):
            try:
                data = json.loads(content)
                problem = problem or data.get("problem", "")
                solution = solution or data.get("solution", "")
                rationale = rationale or data.get("rationale", "")
            except json.JSONDecodeError:
                pass

        decision = {
            "title": title,
            "problem": problem,
            "solution": solution,
            "rationale": rationale,
            "status": status,
            "author": author,
            "date": datetime.now().isoformat(),
        }

        filename = self._decisions_dir / f"{title.lower().replace(' ', '_')}.md"
        filename.write_text(format_decision(decision), encoding="utf-8")

        log.info("memory.decision_added", title=title, file=str(filename))
        return {"success": True, "file": str(filename), "error": ""}

    def list_decisions(self) -> list[dict[str, Any]]:
        """List all decisions."""
        decisions = []
        for f in self._decisions_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            parsed = parse_decision(content)
            parsed["file"] = str(f)
            decisions.append(parsed)
        return decisions

    def get_decision(self, title: str) -> dict[str, Any] | None:
        """Get a specific decision."""
        filename = self._decisions_dir / f"{title.lower().replace(' ', '_')}.md"
        if not filename.exists():
            return None
        content = filename.read_text(encoding="utf-8")
        return parse_decision(content)

    def delete_decision(self, title: str) -> bool:
        """Delete a decision."""
        filename = self._decisions_dir / f"{title.lower().replace(' ', '_')}.md"
        if filename.exists():
            filename.unlink()
            return True
        return False

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
        """Add a new task."""
        if not title:
            return {"success": False, "file": None, "error": "Title is required"}

        task_content = f"# Task: {title}\n\n"
        task_content += f"Status: {status}\n"
        task_content += f"Assignee: {assignee}\n"
        task_content += f"Created: {datetime.now().isoformat()}\n\n"
        task_content += content

        filename = self._tasks_dir / f"{title.lower().replace(' ', '_')}.md"
        filename.write_text(task_content, encoding="utf-8")

        log.info("memory.task_added", title=title, file=str(filename))
        return {"success": True, "file": str(filename), "error": ""}

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        """List tasks, optionally filtered by status."""
        tasks = []
        for f in self._tasks_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            lines = content.split("\n")

            task = {"file": str(f), "title": f.stem}
            for line in lines:
                if line.startswith("Status:"):
                    task["status"] = line.replace("Status:", "").strip()
                elif line.startswith("Assignee:"):
                    task["assignee"] = line.replace("Assignee:", "").strip()

            if status is None or task.get("status") == status:
                tasks.append(task)
        return tasks

    def get_task(self, title: str) -> dict[str, Any] | None:
        """Get a specific task."""
        filename = self._tasks_dir / f"{title.lower().replace(' ', '_')}.md"
        if not filename.exists():
            return None
        content = filename.read_text(encoding="utf-8")
        lines = content.split("\n")
        task = {"title": title, "content": content}
        for line in lines:
            if line.startswith("Status:"):
                task["status"] = line.replace("Status:", "").strip()
            elif line.startswith("Assignee:"):
                task["assignee"] = line.replace("Assignee:", "").strip()
        return task

    def delete_task(self, title: str) -> bool:
        """Delete a task."""
        filename = self._tasks_dir / f"{title.lower().replace(' ', '_')}.md"
        if filename.exists():
            filename.unlink()
            return True
        return False

    # =====================================================================
    # Context Operations
    # =====================================================================

    def save_context(self, context_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Save a context snapshot."""
        if context_data is None:
            context_data = {}

        context = {
            "timestamp": datetime.now().isoformat(),
            "files_tracked": len(list(Path.cwd().rglob("*"))),
            "cwd": str(Path.cwd()),
            **context_data,
        }

        index = len(list(self._context_dir.glob("context_*.json")))
        filename = self._context_dir / f"context_{index}.json"
        filename.write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8")

        log.info("memory.context_saved", file=str(filename))
        return {"success": True, "file": str(filename), "error": ""}

    def get_latest_context(self) -> dict[str, Any] | None:
        """Get the latest context snapshot."""
        contexts = sorted(self._context_dir.glob("context_*.json"), key=lambda f: f.stat().st_mtime)
        if not contexts:
            return None
        latest = contexts[-1]
        try:
            return json.loads(latest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
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
        """Update the project status."""
        status_file = self._active_dir / "STATUS.md"
        timestamp = datetime.now().isoformat()

        content = f"""# Active Project Context
> Last Updated: {timestamp}

## Current Status
- **Phase**: {phase}
- **Focus**: {focus}
- **Blockers**: {blockers}
- **Sentiment**: {sentiment}

## Scratchpad
*(Agent should update this via `log_scratchpad` tool)*
"""
        status_file.write_text(content, encoding="utf-8")

        log_file = self._active_dir / "history.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{phase}] {focus} (Blockers: {blockers})\n")

        return {"success": True, "file": str(status_file)}

    def get_status(self) -> str:
        """Get the current project status."""
        status_file = self._active_dir / "STATUS.md"
        if not status_file.exists():
            return "No active context found. System is idle."
        return status_file.read_text(encoding="utf-8")

    def log_scratchpad(self, entry: str, source: str = "Note") -> dict[str, Any]:
        """Log an entry to the scratchpad."""
        scratchpad_file = self._active_dir / "SCRATCHPAD.md"
        timestamp = datetime.now().strftime("%H:%M:%S")

        if not scratchpad_file.exists():
            scratchpad_file.write_text(
                f"# Scratchpad (Session Log)\nStarted: {datetime.now()}\n\n", encoding="utf-8"
            )

        if source == "System":
            entry_text = f"\n> `[{timestamp}]` **EXEC**: {entry}\n"
        else:
            entry_text = f"\n### [{timestamp}] {source}\n{entry}\n"

        with open(scratchpad_file, "a", encoding="utf-8") as f:
            f.write(entry_text)

        return {"success": True, "file": str(scratchpad_file)}

    # =====================================================================
    # Migration & Mode
    # =====================================================================

    def migrate_from_file(self, source_dir: Path) -> dict[str, Any]:
        """Migrate from file-based storage (no-op for file store)."""
        return {"error": "Cannot migrate: already in file mode"}

    def get_storage_mode(self) -> str:
        """Get the storage mode."""
        return STORAGE_MODE_FILE
