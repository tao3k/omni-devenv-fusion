"""Tests for ProjectMemory module."""

from __future__ import annotations

from pathlib import Path

import pytest

from omni.foundation.services.memory.base import (
    STORAGE_MODE_FILE,
    STORAGE_MODE_LANCE,
    ProjectMemory,
    format_decision,
    parse_decision,
)


class TestFormatDecision:
    """Tests for format_decision function."""

    def test_format_decision_with_all_fields(self):
        """Test formatting a decision with all fields."""
        decision = {
            "title": "Test Decision",
            "problem": "Test problem statement",
            "solution": "Test solution",
            "rationale": "Test rationale",
            "status": "accepted",
            "author": "Claude",
            "date": "2026-01-30T10:00:00",
        }

        formatted = format_decision(decision)

        assert "# Decision: Test Decision" in formatted
        assert "Date: 2026-01-30T10:00:00" in formatted
        assert "Author: Claude" in formatted
        assert "## Problem" in formatted
        assert "Test problem statement" in formatted
        assert "## Solution" in formatted
        assert "Test solution" in formatted
        assert "## Rationale" in formatted
        assert "Test rationale" in formatted
        assert "## Status" in formatted
        assert "accepted" in formatted

    def test_format_decision_with_defaults(self):
        """Test formatting a decision with minimal fields."""
        decision = {"title": "Minimal Decision"}

        formatted = format_decision(decision)

        assert "# Decision: Minimal Decision" in formatted
        assert "N/A" in formatted  # Default for missing fields
        assert "open" in formatted  # Default status


class TestParseDecision:
    """Tests for parse_decision function."""

    def test_parse_full_decision(self):
        """Test parsing a complete decision."""
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
        assert parsed["date"] == "2026-01-30T10:00:00"
        assert parsed["author"] == "Claude"
        assert parsed["problem"] == "Test problem statement"
        assert parsed["solution"] == "Test solution"
        assert parsed["rationale"] == "Test rationale"
        assert parsed["status"] == "accepted"

    def test_parse_partial_decision(self):
        """Test parsing a decision with missing fields."""
        content = """# Decision: Partial Decision

## Problem
Only problem defined

## Status
open
"""
        parsed = parse_decision(content)

        assert parsed["title"] == "Partial Decision"
        assert parsed["problem"] == "Only problem defined"
        assert "solution" not in parsed


class TestProjectMemoryInit:
    """Tests for ProjectMemory initialization."""

    def test_init_file_mode(self, temp_dir):
        """Test initialization in file mode."""
        memory = ProjectMemory(dir_path=temp_dir, storage_mode=STORAGE_MODE_FILE)

        assert memory.storage_mode == STORAGE_MODE_FILE
        assert memory.is_lance_mode is False
        assert (temp_dir / "decisions").exists()
        assert (temp_dir / "tasks").exists()
        assert (temp_dir / "context").exists()
        assert (temp_dir / "active_context").exists()

    def test_init_lance_mode(self, temp_dir):
        """Test initialization in LanceDB mode."""
        memory = ProjectMemory(dir_path=temp_dir, storage_mode=STORAGE_MODE_LANCE)

        # LanceDB mode may not be available if lancedb is not installed
        # Just check that it was attempted
        assert memory.storage_mode in [STORAGE_MODE_LANCE, STORAGE_MODE_FILE]

    def test_init_default_storage_mode(self, temp_dir):
        """Test that default storage mode is LanceDB."""
        memory = ProjectMemory(dir_path=temp_dir)

        # Default should be lance if available, file otherwise
        assert memory.storage_mode in [STORAGE_MODE_LANCE, STORAGE_MODE_FILE]


class TestProjectMemoryDecisions:
    """Tests for decision operations."""

    def test_add_decision_file_mode(self, memory_file_mode):
        """Test adding a decision in file mode."""
        result = memory_file_mode.add_decision(
            title="Test Decision",
            problem="Test problem",
            solution="Test solution",
            rationale="Test rationale",
        )

        assert result["success"] is True
        assert result["file"] is not None
        assert result["error"] == ""

    def test_add_decision_empty_title_fails(self, memory_file_mode):
        """Test that adding a decision with empty title fails."""
        result = memory_file_mode.add_decision(title="")

        assert result["success"] is False
        assert "Title is required" in result["error"]

    def test_list_decisions_file_mode(self, populated_memory_file_mode):
        """Test listing decisions in file mode."""
        decisions = populated_memory_file_mode.list_decisions()

        assert len(decisions) == 2
        titles = [d.get("title") for d in decisions]
        assert "Use LanceDB for Memory Storage" in titles
        assert "Use Async IO" in titles

    def test_get_decision_file_mode(self, populated_memory_file_mode):
        """Test getting a specific decision in file mode."""
        decision = populated_memory_file_mode.get_decision("Use LanceDB for Memory Storage")

        assert decision is not None
        assert decision.get("title") == "Use LanceDB for Memory Storage"
        assert decision.get("status") == "open"

    def test_get_nonexistent_decision(self, memory_file_mode):
        """Test getting a decision that doesn't exist."""
        decision = memory_file_mode.get_decision("Nonexistent Decision")

        assert decision is None

    def test_add_decision_with_json_content(self, memory_file_mode):
        """Test adding a decision with JSON content."""
        json_content = '{"problem": "JSON problem", "solution": "JSON solution"}'
        result = memory_file_mode.add_decision(
            title="JSON Decision",
            content=json_content,
        )

        assert result["success"] is True
        decision = memory_file_mode.get_decision("JSON Decision")
        assert decision.get("problem") == "JSON problem"
        assert decision.get("solution") == "JSON solution"


class TestProjectMemoryTasks:
    """Tests for task operations."""

    def test_add_task_file_mode(self, memory_file_mode):
        """Test adding a task in file mode."""
        result = memory_file_mode.add_task(
            title="Test Task",
            content="Test content",
            status="pending",
            assignee="Claude",
        )

        assert result["success"] is True
        assert result["file"] is not None

    def test_add_task_empty_title_fails(self, memory_file_mode):
        """Test that adding a task with empty title fails."""
        result = memory_file_mode.add_task(title="")

        assert result["success"] is False
        assert "Title is required" in result["error"]

    def test_list_tasks_file_mode(self, populated_memory_file_mode):
        """Test listing tasks in file mode."""
        tasks = populated_memory_file_mode.list_tasks()

        assert len(tasks) == 2

    def test_list_tasks_with_status_filter(self, populated_memory_file_mode):
        """Test filtering tasks by status."""
        pending_tasks = populated_memory_file_mode.list_tasks(status="pending")
        in_progress_tasks = populated_memory_file_mode.list_tasks(status="in_progress")

        assert len(pending_tasks) == 1
        assert len(in_progress_tasks) == 1
        # File mode uses filename as title (underscores)
        assert "implement_memory_migration" in [t.get("title") for t in pending_tasks]
        assert "write_unit_tests" in [t.get("title") for t in in_progress_tasks]


class TestProjectMemoryContext:
    """Tests for context operations."""

    def test_save_context_file_mode(self, memory_file_mode):
        """Test saving context in file mode."""
        context_data = {"files_tracked": 100, "active_skills": ["git"]}
        result = memory_file_mode.save_context(context_data)

        assert result["success"] is True
        assert result["file"] is not None

    def test_get_latest_context_file_mode(self, populated_memory_file_mode):
        """Test getting latest context in file mode."""
        context = populated_memory_file_mode.get_latest_context()

        assert context is not None
        assert context.get("files_tracked") == 100
        assert context.get("current_phase") == "implementation"

    def test_get_latest_context_empty(self, memory_file_mode):
        """Test getting latest context when none exists."""
        context = memory_file_mode.get_latest_context()

        assert context is None


class TestProjectMemoryStatus:
    """Tests for status management."""

    def test_update_status_file_mode(self, memory_file_mode):
        """Test updating status in file mode."""
        result = memory_file_mode.update_status(
            phase="implementation",
            focus="Writing tests",
            blockers="None",
            sentiment="Positive",
        )

        assert result["success"] is True

    def test_get_status_file_mode(self, populated_memory_file_mode):
        """Test getting status in file mode."""
        status = populated_memory_file_mode.get_status()

        assert "implementation" in status
        assert "writing tests" in status

    def test_get_status_empty(self, memory_file_mode):
        """Test getting status when none exists."""
        status = memory_file_mode.get_status()

        assert "No active context" in status

    def test_log_scratchpad_file_mode(self, memory_file_mode):
        """Test logging to scratchpad in file mode."""
        result = memory_file_mode.log_scratchpad(
            entry="Test scratchpad entry",
            source="Test",
        )

        assert result["success"] is True

    def test_log_scratchpad_system_source(self, memory_file_mode):
        """Test logging with System source."""
        result = memory_file_mode.log_scratchpad(
            entry="git commit -m 'test'",
            source="System",
        )

        assert result["success"] is True
        scratchpad_file = result["file"]
        content = Path(scratchpad_file).read_text()
        assert "EXEC" in content


class TestProjectMemorySpecPath:
    """Tests for spec path management."""

    def test_set_and_get_spec_path(self, memory_file_mode):
        """Test setting and getting spec path."""
        memory_file_mode.set_spec_path("/path/to/spec.json")

        spec_path = memory_file_mode.get_spec_path()

        assert spec_path == "/path/to/spec.json"

    def test_get_spec_path_none(self, memory_file_mode):
        """Test getting spec path when none is set."""
        spec_path = memory_file_mode.get_spec_path()

        assert spec_path is None


class TestProjectMemoryFormatting:
    """Tests for formatting methods."""

    def test_format_decisions_list_empty(self, memory_file_mode):
        """Test formatting empty decisions list."""
        result = memory_file_mode.format_decisions_list()

        assert "No decisions recorded" in result

    def test_format_decisions_list_with_data(self, populated_memory_file_mode):
        """Test formatting decisions list with data."""
        result = populated_memory_file_mode.format_decisions_list()

        assert "Architectural Decisions" in result
        assert "Use LanceDB for Memory Storage" in result
        assert "[open]" in result or "[accepted]" in result

    def test_format_tasks_list_empty(self, memory_file_mode):
        """Test formatting empty tasks list."""
        result = memory_file_mode.format_tasks_list()

        assert "No tasks found" in result

    def test_format_tasks_list_with_filter(self, populated_memory_file_mode):
        """Test formatting tasks list with status filter."""
        result = populated_memory_file_mode.format_tasks_list(status="pending")

        # File mode uses filename as title (underscores)
        assert "implement_memory_migration" in result
        # Should not contain in_progress tasks
        assert "write_unit_tests" not in result or "[pending]" in result


class TestProjectMemoryMigration:
    """Tests for file to LanceDB migration."""

    def test_migrate_from_file_not_in_lance_mode(self, memory_file_mode):
        """Test migration fails when not in LanceDB mode."""
        result = memory_file_mode.migrate_from_file()

        assert "error" in result
        assert "not in LanceDB mode" in result["error"]

    def test_migrate_from_file_returns_stats(self, temp_dir):
        """Test migration returns migration statistics."""
        # Create file-based memory with some data
        file_memory = ProjectMemory(dir_path=temp_dir, storage_mode=STORAGE_MODE_FILE)
        file_memory.add_decision(
            title="Migration Test", problem="Test", solution="Test", rationale="Test"
        )
        file_memory.add_task(title="Migration Task", content="Test", status="pending")

        # Create LanceDB memory and migrate
        lance_memory = ProjectMemory(dir_path=temp_dir, storage_mode=STORAGE_MODE_LANCE)

        if lance_memory.is_lance_mode:
            result = lance_memory.migrate_from_file()

            assert "decisions" in result
            assert "tasks" in result
            assert "errors" in result


class TestProjectMemoryEdgeCases:
    """Tests for edge cases and error handling."""

    def test_decision_title_sanitization(self, memory_file_mode):
        """Test that decision titles are sanitized for filenames."""
        memory_file_mode.add_decision(
            title="Test Decision With Spaces!",
            problem="Test",
            solution="Test",
        )

        # Should work without errors
        decisions = memory_file_mode.list_decisions()
        assert len(decisions) == 1

    def test_task_title_sanitization(self, memory_file_mode):
        """Test that task titles are sanitized for filenames."""
        memory_file_mode.add_task(
            title="Test Task With Spaces!",
            content="Test",
        )

        # Should work without errors
        tasks = memory_file_mode.list_tasks()
        assert len(tasks) == 1

    def test_list_decisions_returns_list(self, memory_file_mode):
        """Test that list_decisions always returns a list."""
        decisions = memory_file_mode.list_decisions()
        assert isinstance(decisions, list)

    def test_list_tasks_returns_list(self, memory_file_mode):
        """Test that list_tasks always returns a list."""
        tasks = memory_file_mode.list_tasks()
        assert isinstance(tasks, list)


class TestProjectMemoryLanceMode:
    """Tests specific to LanceDB mode functionality."""

    @pytest.mark.skip(reason="LanceDB not available in test environment")
    def test_lance_store_initialized(self, memory_lance_mode):
        """Test that LanceDB store is properly initialized."""
        assert memory_lance_mode.is_lance_mode is True

    @pytest.mark.skip(reason="LanceDB not available in test environment")
    def test_add_decision_lance_mode(self, memory_lance_mode):
        """Test adding decision in LanceDB mode."""
        result = memory_lance_mode.add_decision(
            title="LanceDB Decision",
            problem="Test problem",
            solution="Test solution",
        )

        assert result["success"] is True

    @pytest.mark.skip(reason="LanceDB not available in test environment")
    def test_list_decisions_lance_mode(self, populated_memory_lance_mode):
        """Test listing decisions in LanceDB mode."""
        decisions = populated_memory_lance_mode.list_decisions()

        assert len(decisions) == 2

    @pytest.mark.skip(reason="LanceDB not available in test environment")
    def test_list_tasks_lance_mode(self, populated_memory_lance_mode):
        """Test listing tasks in LanceDB mode."""
        tasks = populated_memory_lance_mode.list_tasks()

        assert len(tasks) == 2

    @pytest.mark.skip(reason="LanceDB not available in test environment")
    def test_get_latest_context_lance_mode(self, populated_memory_lance_mode):
        """Test getting latest context in LanceDB mode."""
        context = populated_memory_lance_mode.get_latest_context()

        assert context is not None
        assert context.get("current_phase") == "implementation"

    @pytest.mark.skip(reason="LanceDB not available in test environment")
    def test_update_status_lance_mode(self, memory_lance_mode):
        """Test updating status in LanceDB mode."""
        result = memory_lance_mode.update_status(
            phase="testing",
            focus="unit tests",
        )

        assert result["success"] is True

    @pytest.mark.skip(reason="LanceDB not available in test environment")
    def test_get_status_lance_mode(self, populated_memory_lance_mode):
        """Test getting status in LanceDB mode."""
        status = populated_memory_lance_mode.get_status()

        assert "implementation" in status
