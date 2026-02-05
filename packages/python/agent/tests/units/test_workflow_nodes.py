"""
Unit tests for workflow nodes (clarify_node, plan_node).

Tests focus on:
- Hippocampus experience recall and formatting
- Context injection into LLM prompts
- Proper handling of Pydantic models vs dicts for ExecutionStep
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHippocampusExperienceFormatting:
    """Tests for formatting Hippocampus experiences into context strings."""

    def test_format_experience_with_pydantic_steps(self):
        """Test formatting experiences with Pydantic ExecutionStep models."""
        from omni.agent.core.memory.schemas import ExperienceRecallResult, ExecutionStep

        # Create mock experiences with Pydantic ExecutionStep
        experiences = [
            ExperienceRecallResult(
                trace_id="trace-1",
                task_description="Find Python files",
                similarity_score=0.85,
                domain="file_manipulation",
                nu_pattern="find|glob",
                tags=["python"],
                steps=[
                    ExecutionStep(command="find . -name '*.py'", success=True, output="file1.py"),
                    ExecutionStep(command="wc -l file1.py", success=True, output="42"),
                ],
            )
        ]

        # Format experiences (simulating the logic in clarify_node)
        exp_parts = ["# Relevant Past Experiences:\n"]
        for i, exp in enumerate(experiences[:3], 1):
            exp_parts.append(f"## Experience {i} (confidence: {exp.similarity_score:.2f})")
            exp_parts.append(f"Task: {exp.task_description}")
            if exp.nu_pattern:
                exp_parts.append(f"Approach: {exp.nu_pattern}")
            if exp.steps:
                steps_text = []
                for s in exp.steps[:3]:
                    # This is the key fix: handle Pydantic model vs dict
                    if hasattr(s, "command"):
                        cmd = s.command
                        out = s.output[:100] if s.output else ""
                    else:
                        cmd = s.get("command", str(s))
                        out = s.get("output", "")[:100]
                    steps_text.append(f"  - {cmd}: {out}")
                exp_parts.append("Steps:\n" + "\n".join(steps_text))
            exp_parts.append("")
        experience_context = "\n".join(exp_parts)

        # Verify formatting
        assert "# Relevant Past Experiences:" in experience_context
        assert "Experience 1 (confidence: 0.85)" in experience_context
        assert "Find Python files" in experience_context
        assert "find|glob" in experience_context
        assert "find . -name '*.py'" in experience_context
        assert "Steps:" in experience_context

    def test_format_experience_with_dict_steps(self):
        """Test formatting experiences with dict steps (legacy format)."""
        # Create mock experiences with dict steps (legacy format)
        experiences = [
            MagicMock(
                trace_id="trace-2",
                task_description="Git commit",
                similarity_score=0.92,
                domain="git",
                nu_pattern="git commit",
                tags=["git"],
                steps=[
                    {"command": "git status", "success": True, "output": "clean"},
                    {"command": "git add -A", "success": True, "output": ""},
                ],
            )
        ]

        # Format experiences (simulating the logic in clarify_node)
        exp_parts = ["# Relevant Past Experiences:\n"]
        for i, exp in enumerate(experiences[:3], 1):
            exp_parts.append(f"## Experience {i} (confidence: {exp.similarity_score:.2f})")
            exp_parts.append(f"Task: {exp.task_description}")
            if exp.nu_pattern:
                exp_parts.append(f"Approach: {exp.nu_pattern}")
            if exp.steps:
                steps_text = []
                for s in exp.steps[:3]:
                    # Handle dict format
                    if isinstance(s, dict):
                        cmd = s.get("command", str(s))
                        out = s.get("output", "")[:100]
                    else:
                        cmd = getattr(s, "command", str(s))
                        out = getattr(s, "output", "")[:100]
                    steps_text.append(f"  - {cmd}: {out}")
                exp_parts.append("Steps:\n" + "\n".join(steps_text))
            exp_parts.append("")
        experience_context = "\n".join(exp_parts)

        # Verify formatting
        assert "Experience 1 (confidence: 0.92)" in experience_context
        assert "Git commit" in experience_context
        assert "git status" in experience_context

    def test_format_experience_without_steps(self):
        """Test formatting experiences with no steps."""
        from omni.agent.core.memory.schemas import ExperienceRecallResult

        experiences = [
            ExperienceRecallResult(
                trace_id="trace-3",
                task_description="Simple task",
                similarity_score=0.75,
                steps=[],
            )
        ]

        # Format experiences
        exp_parts = ["# Relevant Past Experiences:\n"]
        for i, exp in enumerate(experiences[:3], 1):
            exp_parts.append(f"## Experience {i} (confidence: {exp.similarity_score:.2f})")
            exp_parts.append(f"Task: {exp.task_description}")
            if exp.steps:
                exp_parts.append("Steps exist")
            exp_parts.append("")
        experience_context = "\n".join(exp_parts)

        # Verify formatting without steps section
        assert "Simple task" in experience_context
        assert "Steps exist" not in experience_context

    def test_format_multiple_experiences(self):
        """Test formatting multiple experiences."""
        from omni.agent.core.memory.schemas import ExperienceRecallResult, ExecutionStep

        # Create 3 experiences
        experiences = [
            ExperienceRecallResult(
                trace_id=f"trace-{i}",
                task_description=f"Task {i}",  # Task 0, Task 1, Task 2
                similarity_score=0.9 - i * 0.1,
                steps=[ExecutionStep(command=f"cmd{i}", success=True)],
            )
            for i in range(3)
        ]

        # Format experiences
        exp_parts = ["# Relevant Past Experiences:\n"]
        for i, exp in enumerate(experiences[:3], 1):
            exp_parts.append(f"## Experience {i} (confidence: {exp.similarity_score:.2f})")
            exp_parts.append(f"Task: {exp.task_description}")
            exp_parts.append("")
        experience_context = "\n".join(exp_parts)

        # Verify all experiences are included
        assert "Experience 1" in experience_context
        assert "Experience 2" in experience_context
        assert "Experience 3" in experience_context
        # Task 0, Task 1, Task 2
        assert "Task 0" in experience_context
        assert "Task 1" in experience_context
        assert "Task 2" in experience_context


class TestExecutionStepAccess:
    """Tests for proper ExecutionStep access (Pydantic vs dict)."""

    def test_pydantic_step_access(self):
        """Test accessing attributes on Pydantic ExecutionStep."""
        from omni.agent.core.memory.schemas import ExecutionStep

        step = ExecutionStep(command="ls -la", output="file1 file2", success=True, duration_ms=10.0)

        # Direct attribute access should work
        assert step.command == "ls -la"
        assert step.output == "file1 file2"
        assert step.success is True
        assert step.duration_ms == 10.0

    def test_dict_step_access(self):
        """Test accessing keys on dict step."""
        step = {"command": "ls -la", "output": "file1 file2", "success": True}

        # Dict access should work
        assert step.get("command") == "ls -la"
        assert step.get("output") == "file1 file2"

    def test_mixed_access_function(self):
        """Test unified access function for both types."""
        from omni.agent.core.memory.schemas import ExecutionStep

        pydantic_step = ExecutionStep(command="ls", output="files", success=True)
        dict_step = {"command": "ls", "output": "files", "success": True}

        def get_command(step):
            if hasattr(step, "command"):
                return step.command
            return step.get("command", str(step))

        def get_output(step):
            if isinstance(step, dict):
                return step.get("output", "")[:100]
            return getattr(step, "output", "")[:100]

        # Both should return same values
        assert get_command(pydantic_step) == get_command(dict_step) == "ls"
        assert get_output(pydantic_step) == get_output(dict_step) == "files"


class TestMemoryContextCombination:
    """Tests for combining memory_context with experience_context."""

    def test_combine_memory_and_experience_context(self):
        """Test that memory_context and experience_context are combined correctly."""
        memory_context = "Previous knowledge retrieved from memory subgraph."
        experience_context = """# Relevant Past Experiences:

## Experience 1 (confidence: 0.85)
Task: Find Python files
Steps:
  - find . -name '*.py': file1.py

"""

        # Combine (as done in clarify_node)
        full_context = memory_context + "\n\n" + experience_context

        assert "Previous knowledge" in full_context
        assert "Relevant Past Experiences" in full_context
        assert "Experience 1" in full_context
        assert "Find Python files" in full_context

    def test_combine_with_empty_experience(self):
        """Test combining when experience_context is empty."""
        memory_context = "Previous knowledge."
        experience_context = ""

        full_context = memory_context
        if experience_context:
            full_context = f"{memory_context}\n\n{experience_context}"

        assert full_context == "Previous knowledge."


class TestClarifyNodeIntegration:
    """Integration tests for clarify_node with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_clarify_node_with_mocked_hippocampus(self):
        """Test clarify_node behavior when hippocampus is mocked at import source."""
        from omni.agent.core.memory.schemas import ExperienceRecallResult, ExecutionStep

        # Create mock experiences
        mock_experiences = [
            ExperienceRecallResult(
                trace_id="test-trace",
                task_description="Test task",
                similarity_score=0.85,
                steps=[ExecutionStep(command="ls", success=True)],
            )
        ]

        # Mock at the source where it's imported
        with patch("omni.agent.core.memory.hippocampus.Hippocampus") as MockHippo:
            mock_instance = MagicMock()
            mock_instance.recall_experience = AsyncMock(return_value=mock_experiences)
            MockHippo.return_value = mock_instance

            from omni.agent.workflows.robust_task.nodes import clarify_node
            from omni.agent.workflows.robust_task.state import RobustTaskState

            # Create minimal test state
            state: RobustTaskState = {
                "user_request": "test query",
                "discovered_tools": [],
                "memory_context": "",
                "retry_count": 0,
                "clarified_goal": "",
                "context_files": [],
                "last_thought": "",
                "trace": [],
                "user_feedback": "",
                "approval_status": "pending",
                "plan": {"steps": [], "current_step_index": 0},
                "execution_history": [],
                "status": "clarifying",
                "validation_result": {},
                "final_summary": "",
                "error": "",
            }

            result = await clarify_node(state)

            # Verify hippocampus was called
            mock_instance.recall_experience.assert_called_once()

            # Verify result structure
            assert "status" in result

    @pytest.mark.asyncio
    async def test_clarify_node_with_empty_experiences(self):
        """Test clarify_node handles empty experiences gracefully."""
        with patch("omni.agent.core.memory.hippocampus.Hippocampus") as MockHippo:
            mock_instance = MagicMock()
            mock_instance.recall_experience = AsyncMock(return_value=[])
            MockHippo.return_value = mock_instance

            from omni.agent.workflows.robust_task.nodes import clarify_node
            from omni.agent.workflows.robust_task.state import RobustTaskState

            state: RobustTaskState = {
                "user_request": "test query",
                "discovered_tools": [],
                "memory_context": "",
                "retry_count": 0,
                "clarified_goal": "",
                "context_files": [],
                "last_thought": "",
                "trace": [],
                "user_feedback": "",
                "approval_status": "pending",
                "plan": {"steps": [], "current_step_index": 0},
                "execution_history": [],
                "status": "clarifying",
                "validation_result": {},
                "final_summary": "",
                "error": "",
            }

            # Should not raise exception
            result = await clarify_node(state)
            assert "status" in result


class TestPlanNodeIntegration:
    """Integration tests for plan_node with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_plan_node_with_mocked_hippocampus(self):
        """Test plan_node behavior when hippocampus is mocked."""
        from omni.agent.core.memory.schemas import ExperienceRecallResult, ExecutionStep

        mock_experiences = [
            ExperienceRecallResult(
                trace_id="test-trace",
                task_description="Test task",
                similarity_score=0.85,
                steps=[ExecutionStep(command="ls", success=True)],
            )
        ]

        with patch("omni.agent.core.memory.hippocampus.Hippocampus") as MockHippo:
            mock_instance = MagicMock()
            mock_instance.recall_experience = AsyncMock(return_value=mock_experiences)
            MockHippo.return_value = mock_instance

            from omni.agent.workflows.robust_task.nodes import plan_node
            from omni.agent.workflows.robust_task.state import RobustTaskState

            state: RobustTaskState = {
                "user_request": "original request",
                "clarified_goal": "Execute test task",
                "discovered_tools": [],
                "memory_context": "",
                "user_feedback": "",
                "context_files": [],
                "last_thought": "",
                "trace": [],
                "user_feedback": "",
                "approval_status": "pending",
                "plan": {"steps": [], "current_step_index": 0},
                "execution_history": [],
                "status": "planning",
                "validation_result": {},
                "final_summary": "",
                "error": "",
                "retry_count": 0,
            }

            result = await plan_node(state)

            # Verify hippocampus was called
            mock_instance.recall_experience.assert_called_once()

            # Verify result has plan
            assert "plan" in result
            assert "status" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
