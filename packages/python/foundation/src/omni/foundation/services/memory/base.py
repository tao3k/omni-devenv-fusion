# memory/base.py
"""
Project Memory - Long-term memory storage using ADR pattern.

Modularized.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger("mcp-core.memory")


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


def init_memory_dir(dir_path: Path = None) -> bool:
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


def parse_decision(content: str) -> dict[str, Any]:
    """Parse a Markdown ADR back to a dict."""
    decision = {}
    lines = content.split("\n")
    current_section = None

    for line in lines:
        if line.startswith("# Decision:"):
            decision["title"] = line.replace("# Decision:", "").strip()
        elif line.startswith("Date:"):
            decision["date"] = line.replace("Date:", "").strip()
        elif line.startswith("Author:"):
            decision["author"] = line.replace("Author:", "").strip()
        elif line.startswith("## "):
            current_section = line.replace("## ", "").lower().strip()
        elif current_section in ["problem", "solution", "rationale", "status"]:
            decision[current_section] = line.strip()

    return decision


class ProjectMemory:
    """Provides unified interface for project memory operations."""

    def __init__(self, dir_path: Path = None):
        """Initialize ProjectMemory."""
        self.dir_path = dir_path or MEMORY_DIR
        self.decisions_dir = self.dir_path / "decisions"
        self.tasks_dir = self.dir_path / "tasks"
        self.context_dir = self.dir_path / "context"
        self.active_dir = self.dir_path / "active_context"

        init_memory_dir(self.dir_path)
        self.active_dir.mkdir(exist_ok=True)

    # Decision Operations
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
            "author": "Claude",
            "date": datetime.now().isoformat(),
        }

        filename = self.decisions_dir / f"{title.lower().replace(' ', '_')}.md"
        filename.write_text(format_decision(decision), encoding="utf-8")

        log.info("memory.decision_added", title=title, file=str(filename))
        return {"success": True, "file": str(filename), "error": ""}

    def list_decisions(self) -> list[dict[str, Any]]:
        """List all recorded decisions."""
        decisions = []
        for f in self.decisions_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            parsed = parse_decision(content)
            parsed["file"] = str(f)
            decisions.append(parsed)
        return decisions

    def get_decision(self, title: str) -> dict[str, Any] | None:
        """Get a specific decision by title."""
        filename = self.decisions_dir / f"{title.lower().replace(' ', '_')}.md"
        if not filename.exists():
            return None
        content = filename.read_text(encoding="utf-8")
        return parse_decision(content)

    # Task Operations
    def add_task(
        self,
        title: str,
        content: str = "",
        status: str = "pending",
        assignee: str = "Claude",
    ) -> dict[str, Any]:
        """Add a new task to the backlog."""
        if not title:
            return {"success": False, "file": None, "error": "Title is required"}

        task_content = f"# Task: {title}\n\n"
        task_content += f"Status: {status}\n"
        task_content += f"Assignee: {assignee}\n"
        task_content += f"Created: {datetime.now().isoformat()}\n\n"
        task_content += content

        filename = self.tasks_dir / f"{title.lower().replace(' ', '_')}.md"
        filename.write_text(task_content, encoding="utf-8")

        log.info("memory.task_added", title=title, file=str(filename))
        return {"success": True, "file": str(filename), "error": ""}

    def list_tasks(self, status: str = None) -> list[dict[str, Any]]:
        """List all tasks, optionally filtered by status."""
        tasks = []
        for f in self.tasks_dir.glob("*.md"):
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

    # Context Operations
    def save_context(self, context_data: dict[str, Any] = None) -> dict[str, Any]:
        """Save a snapshot of current project context."""
        if context_data is None:
            context_data = {}

        context = {
            "timestamp": datetime.now().isoformat(),
            "files_tracked": len(list(Path.cwd().rglob("*"))),
            "cwd": str(Path.cwd()),
            **context_data,
        }

        index = len(list(self.context_dir.glob("context_*.json")))
        filename = self.context_dir / f"context_{index}.json"
        filename.write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8")

        log.info("memory.context_saved", file=str(filename))
        return {"success": True, "file": str(filename), "error": ""}

    def get_latest_context(self) -> dict[str, Any] | None:
        """Get the latest context snapshot."""
        contexts = sorted(self.context_dir.glob("context_*.json"), key=lambda f: f.stat().st_mtime)
        if not contexts:
            return None
        latest = contexts[-1]
        try:
            return json.loads(latest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    # Formatting Methods
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

    def format_tasks_list(self, status: str = None) -> str:
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

    # Active Context Management
    def update_status(
        self, phase: str, focus: str, blockers: str = "None", sentiment: str = "Neutral"
    ) -> dict[str, Any]:
        """Update the global project status (The 'RAM')."""
        status_file = self.active_dir / "STATUS.md"
        timestamp = datetime.now().isoformat()

        content = f"""# 🧠 Active Project Context
> Last Updated: {timestamp}

## 📍 Current Status
- **Phase**: {phase}
- **Focus**: {focus}
- **Blockers**: {blockers}
- **Sentiment**: {sentiment}

## 📝 Scratchpad (Latest Thoughts)
*(Agent should update this via `log_scratchpad` tool)*
"""
        status_file.write_text(content, encoding="utf-8")

        log_file = self.active_dir / "history.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{phase}] {focus} (Blockers: {blockers})\n")

        return {"success": True, "file": str(status_file)}

    def get_status(self) -> str:
        """Read the current project status."""
        status_file = self.active_dir / "STATUS.md"
        if not status_file.exists():
            return "No active context found. System is idle."
        return status_file.read_text(encoding="utf-8")

    def log_scratchpad(self, entry: str, source: str = "Note") -> dict[str, Any]:
        """Append a thought, observation, or COMMAND LOG to the scratchpad."""
        scratchpad_file = self.active_dir / "SCRATCHPAD.md"
        timestamp = datetime.now().strftime("%H:%M:%S")

        if not scratchpad_file.exists():
            scratchpad_file.write_text(
                f"# 📝 Scratchpad (Session Log)\nStarted: {datetime.now()}\n\n", encoding="utf-8"
            )

        if source == "System":
            entry_text = f"\n> `[{timestamp}]` **EXEC**: {entry}\n"
        else:
            entry_text = f"\n### [{timestamp}] {source}\n{entry}\n"

        with open(scratchpad_file, "a", encoding="utf-8") as f:
            f.write(entry_text)

        return {"success": True, "file": str(scratchpad_file)}

    # Spec Path Management
    def set_spec_path(self, spec_path: str) -> dict[str, Any]:
        """Store the current spec path for the legislation workflow."""
        spec_file = self.active_dir / "current_spec.json"
        data = {"spec_path": spec_path, "timestamp": datetime.now().isoformat()}
        spec_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("memory.spec_path_set", spec_path=spec_path)
        return {"success": True, "file": str(spec_file)}

    def get_spec_path(self) -> str | None:
        """Get the current spec path stored by start_spec."""
        spec_file = self.active_dir / "current_spec.json"
        if not spec_file.exists():
            return None
        try:
            data = json.loads(spec_file.read_text(encoding="utf-8"))
            return data.get("spec_path")
        except (OSError, json.JSONDecodeError):
            return None


__all__ = ["MEMORY_DIR", "ProjectMemory", "format_decision", "init_memory_dir", "parse_decision"]
