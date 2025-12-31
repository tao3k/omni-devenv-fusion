# mcp-core/memory.py
"""
Project Memory Persistence Module

Provides long-term memory storage for project context using file-based ADR pattern.
This module wraps project memory operations for both orchestrator.py and coder.py.

Features:
- Architectural Decision Records (ADRs)
- Task tracking (backlog-md compatible)
- Context snapshots

Follows numtide/prj-spec with .memory/ directory structure:
    .memory/
        decisions/  - ADRs
        tasks/      - Task tracking
        context/    - Project snapshots
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger("mcp-core.memory")

# Default memory directory
MEMORY_DIR = Path(".memory")


# =============================================================================
# Directory Management
# =============================================================================

def init_memory_dir(dir_path: Path = None) -> bool:
    """
    Initialize the memory directory structure.

    Args:
        dir_path: Custom memory directory path

    Returns:
        True if successful, False otherwise
    """
    if dir_path is None:
        dir_path = MEMORY_DIR

    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "decisions").mkdir(exist_ok=True)
        (dir_path / "tasks").mkdir(exist_ok=True)
        (dir_path / "context").mkdir(exist_ok=True)
        return True
    except Exception as e:
        log.info("memory.init_failed", error=str(e))
        return False


# =============================================================================
# Decision Management (ADRs)
# =============================================================================

def format_decision(decision: Dict[str, Any]) -> str:
    """
    Format a decision for storage as Markdown ADR.

    Args:
        decision: Decision dict with keys: title, problem, solution, rationale, status, author, date

    Returns:
        Formatted Markdown string
    """
    lines = [
        f"# Decision: {decision.get('title', 'Untitled')}",
        f"Date: {decision.get('date', datetime.now().isoformat())}",
        f"Author: {decision.get('author', 'Claude')}",
        "",
        f"## Problem",
        decision.get("problem", "N/A"),
        "",
        f"## Solution",
        decision.get("solution", "N/A"),
        "",
        f"## Rationale",
        decision.get("rationale", "N/A"),
        "",
        f"## Status",
        decision.get("status", "open"),
    ]
    return "\n".join(lines)


def parse_decision(content: str) -> Dict[str, Any]:
    """
    Parse a Markdown ADR back to a dict.

    Args:
        content: Markdown content

    Returns:
        Decision dict
    """
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


# =============================================================================
# ProjectMemory Class
# =============================================================================

class ProjectMemory:
    """
    Provides unified interface for project memory operations.

    Ensures both orchestrator.py and coder.py use the same memory system.

    Usage:
        memory = ProjectMemory()
        memory.add_decision(title="dual_mcp", content=...)
        decisions = memory.list_decisions()
        memory.add_task(title="Fix bug", content="...")
    """

    def __init__(self, dir_path: Path = None):
        """
        Initialize ProjectMemory.

        Args:
            dir_path: Custom memory directory path
        """
        self.dir_path = dir_path or MEMORY_DIR
        self.decisions_dir = self.dir_path / "decisions"
        self.tasks_dir = self.dir_path / "tasks"
        self.context_dir = self.dir_path / "context"

        # Ensure directories exist
        init_memory_dir(self.dir_path)

    # =============================================================================
    # Decision Operations
    # =============================================================================

    def add_decision(
        self,
        title: str,
        content: str = "",
        problem: str = "",
        solution: str = "",
        rationale: str = "",
        status: str = "open",
    ) -> Dict[str, Any]:
        """
        Add a new architectural decision.

        Args:
            title: Decision title
            content: Raw content (JSON or markdown)
            problem: Problem statement
            solution: Solution description
            rationale: Rationale explanation
            status: Decision status

        Returns:
            Dict with keys: success (bool), file (Path), error (str)
        """
        if not title:
            return {"success": False, "file": None, "error": "Title is required"}

        # Extract fields from content if it's JSON
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

    def list_decisions(self) -> List[Dict[str, Any]]:
        """
        List all recorded decisions.

        Returns:
            List of decision dicts with keys: title, date, author, status
        """
        decisions = []
        for f in self.decisions_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            parsed = parse_decision(content)
            parsed["file"] = str(f)
            decisions.append(parsed)

        return decisions

    def get_decision(self, title: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific decision by title.

        Args:
            title: Decision title

        Returns:
            Decision dict or None if not found
        """
        filename = self.decisions_dir / f"{title.lower().replace(' ', '_')}.md"
        if not filename.exists():
            return None

        content = filename.read_text(encoding="utf-8")
        return parse_decision(content)

    # =============================================================================
    # Task Operations
    # =============================================================================

    def add_task(
        self,
        title: str,
        content: str = "",
        status: str = "pending",
        assignee: str = "Claude",
    ) -> Dict[str, Any]:
        """
        Add a new task to the backlog.

        Args:
            title: Task title
            content: Task description
            status: Task status
            assignee: Task assignee

        Returns:
            Dict with keys: success (bool), file (Path), error (str)
        """
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

    def list_tasks(self, status: str = None) -> List[Dict[str, Any]]:
        """
        List all tasks, optionally filtered by status.

        Args:
            status: Filter by status (e.g., "pending", "completed")

        Returns:
            List of task dicts
        """
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

    # =============================================================================
    # Context Operations
    # =============================================================================

    def save_context(self, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Save a snapshot of current project context.

        Args:
            context_data: Custom context data

        Returns:
            Dict with keys: success (bool), file (Path), error (str)
        """
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

    def get_latest_context(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest context snapshot.

        Returns:
            Context dict or None if no snapshots exist
        """
        contexts = sorted(self.context_dir.glob("context_*.json"), key=lambda f: f.stat().st_mtime)
        if not contexts:
            return None

        latest = contexts[-1]
        try:
            return json.loads(latest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    # =============================================================================
    # Formatting Methods (for MCP tool output)
    # =============================================================================

    def format_decisions_list(self) -> str:
        """Format decisions as a readable list."""
        decisions = self.list_decisions()
        if not decisions:
            return "No decisions recorded yet."

        lines = ["--- Architectural Decisions ---"]
        for d in decisions:
            status = d.get("status", "open")
            lines.append(f"- {d.get('title', 'Untitled')} [{status}]")

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
