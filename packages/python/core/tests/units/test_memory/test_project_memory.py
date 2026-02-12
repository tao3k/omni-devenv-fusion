"""Tests for LanceDB-backed ProjectMemory."""

from __future__ import annotations

import json
from pathlib import Path

from omni.foundation.services.memory.base import (
    STORAGE_MODE_LANCE,
    ProjectMemory,
    format_decision,
    parse_decision,
)


def test_format_decision_with_all_fields():
    decision = {
        "title": "Test Decision",
        "problem": "Problem statement",
        "solution": "Solution body",
        "rationale": "Rationale body",
        "status": "accepted",
        "author": "Claude",
        "date": "2026-01-30T10:00:00",
    }
    formatted = format_decision(decision)
    assert "# Decision: Test Decision" in formatted
    assert "Problem statement" in formatted
    assert "Solution body" in formatted
    assert "accepted" in formatted


def test_parse_decision_roundtrip():
    content = """# Decision: Test Decision
Date: 2026-01-30T10:00:00
Author: Claude

## Problem
Test problem statement

## Solution
Test solution

## Rationale
Test rationale

## Status
accepted
"""
    parsed = parse_decision(content)
    assert parsed["title"] == "Test Decision"
    assert parsed["status"] == "accepted"
    assert parsed["problem"] == "Test problem statement"


def test_project_memory_init_lance_only(temp_dir):
    memory = ProjectMemory(dir_path=temp_dir)
    assert memory.storage_mode == STORAGE_MODE_LANCE
    assert memory.is_lance_mode is True
    assert (temp_dir / "active_context").exists()


def test_add_decision_requires_title(memory_store):
    result = memory_store.add_decision(title="")
    assert result["success"] is False
    assert "Title is required" in result["error"]


def test_add_and_get_decision(memory_store):
    result = memory_store.add_decision(
        title="Use Structured Logging",
        problem="Logs are inconsistent",
        solution="Use structlog across services",
        rationale="Consistency and machine parsing",
    )
    assert result["success"] is True
    assert result["id"] is not None

    decision = memory_store.get_decision("Use Structured Logging")
    assert decision is not None
    assert decision.get("title") == "Use Structured Logging"


def test_add_decision_with_json_content(memory_store):
    result = memory_store.add_decision(
        title="JSON Decision",
        content='{"problem":"JSON problem","solution":"JSON solution"}',
    )
    assert result["success"] is True
    decision = memory_store.get_decision("JSON Decision")
    assert decision.get("problem") == "JSON problem"
    assert decision.get("solution") == "JSON solution"


def test_list_decisions(populated_memory_store):
    decisions = populated_memory_store.list_decisions()
    assert len(decisions) == 2
    titles = [d.get("title") for d in decisions]
    assert "Use LanceDB for Memory Storage" in titles
    assert "Use Async IO" in titles


def test_add_task_requires_title(memory_store):
    result = memory_store.add_task(title="")
    assert result["success"] is False
    assert "Title is required" in result["error"]


def test_add_and_list_tasks(populated_memory_store):
    tasks = populated_memory_store.list_tasks()
    assert len(tasks) == 2
    pending = populated_memory_store.list_tasks(status="pending")
    in_progress = populated_memory_store.list_tasks(status="in_progress")
    assert len(pending) == 1
    assert len(in_progress) == 1
    assert pending[0].get("title") == "Implement Memory Migration"
    assert in_progress[0].get("title") == "Write Unit Tests"


def test_save_and_get_latest_context(memory_store):
    result = memory_store.save_context({"files_tracked": 42, "current_phase": "implementation"})
    assert result["success"] is True
    assert result["id"] is not None

    context = memory_store.get_latest_context()
    assert context is not None
    assert context.get("files_tracked") == 42
    assert context.get("current_phase") == "implementation"


def test_status_and_scratchpad(memory_store):
    status_result = memory_store.update_status(
        phase="implementation",
        focus="writing tests",
        blockers="None",
        sentiment="Positive",
    )
    assert status_result["success"] is True

    status = memory_store.get_status()
    assert "implementation" in status
    assert "writing tests" in status

    scratch = memory_store.log_scratchpad("git commit -m 'test'", source="System")
    assert scratch["success"] is True
    assert scratch["id"] == "scratchpad"


def test_set_and_get_spec_path(memory_store):
    memory_store.set_spec_path("/path/to/spec.json")
    assert memory_store.get_spec_path() == "/path/to/spec.json"


def test_formatters(populated_memory_store, temp_dir):
    empty_store = ProjectMemory(dir_path=temp_dir / "empty")
    assert "No decisions recorded" in empty_store.format_decisions_list()
    assert "No tasks found" in empty_store.format_tasks_list()

    decisions_text = populated_memory_store.format_decisions_list()
    assert "Architectural Decisions" in decisions_text
    assert "Use LanceDB for Memory Storage" in decisions_text

    tasks_text = populated_memory_store.format_tasks_list(status="pending")
    assert "Implement Memory Migration" in tasks_text
    assert "Write Unit Tests" not in tasks_text


def test_migrate_from_file_markdown_source(memory_store, temp_dir):
    decisions_dir = temp_dir / "decisions"
    tasks_dir = temp_dir / "tasks"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir.mkdir(parents=True, exist_ok=True)

    (decisions_dir / "migration_test.md").write_text(
        """# Decision: Migration Test
Date: 2026-01-30T10:00:00
Author: Claude

## Problem
Legacy markdown record

## Solution
Import to LanceDB

## Rationale
Consolidate storage

## Status
accepted
""",
        encoding="utf-8",
    )
    (tasks_dir / "migration_task.md").write_text(
        "Status: pending\nAssignee: Claude\n",
        encoding="utf-8",
    )

    result = memory_store.migrate_from_file(source_dir=temp_dir)
    assert "decisions" in result
    assert "tasks" in result
    assert "errors" in result
    assert result["decisions"] >= 1
    assert result["tasks"] >= 1


def test_spec_file_is_json(memory_store, temp_dir):
    memory_store.set_spec_path("/tmp/spec.md")
    spec_file = temp_dir / "active_context" / "current_spec.json"
    payload = json.loads(spec_file.read_text(encoding="utf-8"))
    assert payload["spec_path"] == "/tmp/spec.md"


def test_title_with_spaces_and_symbols(memory_store):
    memory_store.add_decision(
        title="Test Decision With Spaces!",
        problem="Test",
        solution="Test",
    )
    memory_store.add_task(
        title="Test Task With Spaces!",
        content="Test",
    )
    assert len(memory_store.list_decisions()) == 1
    assert len(memory_store.list_tasks()) == 1
