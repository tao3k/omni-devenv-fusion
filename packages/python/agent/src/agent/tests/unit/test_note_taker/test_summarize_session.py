"""
test_summarize_session.py
Phase 63: Tests for Session Summarizer.
"""

import importlib.util
from pathlib import Path

from common.skills_path import SKILLS_DIR


def load_script_module(script_path: Path):
    """Dynamically load a Python module from assets/skills."""
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSummarizeSession:
    """Tests for summarize_session function."""

    def test_summarize_empty_trajectory(self):
        """Test summarizing an empty trajectory."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/summarize_session.py")
        summarize_mod = load_script_module(script_path)
        summarize_session = summarize_mod.summarize_session

        result = summarize_session("empty_session", [], include_failures=True)

        assert result["success"] is True
        assert result["session_id"] == "empty_session"
        assert result["decisions_count"] == 0
        assert result["failures_count"] == 0

        # Verify file was created
        output_path = Path(result["path"])
        assert output_path.exists()

        content = output_path.read_text()
        assert "Session: empty_session" in content

    def test_summarize_with_decisions(self):
        """Test summarizing a trajectory with decisions."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/summarize_session.py")
        summarize_mod = load_script_module(script_path)
        summarize_session = summarize_mod.summarize_session

        trajectory = [
            {
                "type": "goal",
                "content": "Fix the bug in runner.py",
            },
            {
                "type": "decision",
                "title": "Approach Selection",
                "context": "Need to fix subprocess handling",
                "choice": "Use asyncio.create_subprocess_exec",
                "rationale": "Better async support",
                "alternatives": ["subprocess.run", "os.system"],
            },
        ]

        result = summarize_session("test_session", trajectory, include_failures=True)

        assert result["success"] is True
        assert result["decisions_count"] == 1

        output_path = Path(result["path"])
        content = output_path.read_text()

        assert "Approach Selection" in content
        assert "asyncio.create_subprocess_exec" in content

    def test_summarize_with_failures(self):
        """Test summarizing a trajectory with failures."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/summarize_session.py")
        summarize_mod = load_script_module(script_path)
        summarize_session = summarize_mod.summarize_session

        trajectory = [
            {
                "type": "failure",
                "approach": "Used subprocess.run",
                "reason": "Doesn't support async timeout properly",
                "lesson": "Use asyncio subprocess functions for async code",
            },
        ]

        result = summarize_session("fail_session", trajectory, include_failures=True)

        assert result["success"] is True
        assert result["failures_count"] == 1

        content = Path(result["path"]).read_text()
        assert "Failed Approaches" in content
        assert "subprocess.run" in content

    def test_summarize_exclude_failures(self):
        """Test that failures can be excluded."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/summarize_session.py")
        summarize_mod = load_script_module(script_path)
        summarize_session = summarize_mod.summarize_session

        trajectory = [
            {
                "type": "failure",
                "approach": "Failed approach",
                "reason": "Some reason",
            },
        ]

        result = summarize_session("no_fail_session", trajectory, include_failures=False)

        assert result["success"] is True
        assert result["failures_count"] == 0

    def test_summarize_with_files(self):
        """Test summarizing file modifications."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/summarize_session.py")
        summarize_mod = load_script_module(script_path)
        summarize_session = summarize_mod.summarize_session

        trajectory = [
            {
                "type": "file_change",
                "path": "packages/python/agent/src/agent/core/runner.py",
                "description": "Added subprocess timeout handling",
            },
        ]

        result = summarize_session("file_session", trajectory, include_failures=False)

        assert result["success"] is True
        assert result["files_count"] == 1

        content = Path(result["path"]).read_text()
        assert "Files Modified" in content
        assert "runner.py" in content

    def test_summarize_with_insights(self):
        """Test summarizing insights."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/summarize_session.py")
        summarize_mod = load_script_module(script_path)
        summarize_session = summarize_mod.summarize_session

        trajectory = [
            {
                "type": "insight",
                "content": "Always use asyncio for async operations",
            },
        ]

        result = summarize_session("insight_session", trajectory, include_failures=False)

        assert result["success"] is True

        content = Path(result["path"]).read_text()
        assert "Key Insights" in content
        assert "asyncio" in content

    def test_extract_goal(self):
        """Test goal extraction."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/summarize_session.py")
        summarize_mod = load_script_module(script_path)
        _extract_goal = summarize_mod._extract_goal

        trajectory = [
            {"type": "goal", "content": "Test goal"},
            {"type": "other", "content": "Other"},
        ]

        assert _extract_goal(trajectory) == "Test goal"

    def test_extract_goal_not_found(self):
        """Test goal extraction when not found."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/summarize_session.py")
        summarize_mod = load_script_module(script_path)
        _extract_goal = summarize_mod._extract_goal

        trajectory = [{"type": "other", "content": "No goal here"}]

        assert _extract_goal(trajectory) == "Goal not explicitly recorded"

    def test_extract_decisions(self):
        """Test decision extraction."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/summarize_session.py")
        summarize_mod = load_script_module(script_path)
        _extract_decisions = summarize_mod._extract_decisions

        trajectory = [
            {
                "type": "decision",
                "title": "Test Decision",
                "context": "Test context",
                "choice": "Test choice",
                "rationale": "Test rationale",
            }
        ]

        decisions = _extract_decisions(trajectory)
        assert len(decisions) == 1
        assert decisions[0]["title"] == "Test Decision"

    def test_extract_failures(self):
        """Test failure extraction."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/summarize_session.py")
        summarize_mod = load_script_module(script_path)
        _extract_failures = summarize_mod._extract_failures

        trajectory = [
            {
                "type": "failure",
                "approach": "Test approach",
                "reason": "Test reason",
                "lesson": "Test lesson",
            }
        ]

        failures = _extract_failures(trajectory)
        assert len(failures) == 1
        assert failures[0]["approach"] == "Test approach"
