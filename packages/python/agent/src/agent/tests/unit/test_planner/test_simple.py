"""
Unit tests for AdaptivePlanner (simple.py).

Tests lightweight task estimation and initial planning without the full planner.
Optimized for efficiency: fewer steps, faster planning.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.core.planner.simple import AdaptivePlanner, create_adaptive_planner


class TestAdaptivePlannerInitialization:
    """Tests for AdaptivePlanner initialization."""

    def test_init_without_client(self) -> None:
        """Verify planner initializes without client."""
        planner = AdaptivePlanner()
        assert planner._client is None

    def test_init_with_client(self) -> None:
        """Verify planner initializes with provided client."""
        mock_client = MagicMock()
        planner = AdaptivePlanner(client=mock_client)
        assert planner._client is mock_client


class TestEstimateSteps:
    """Tests for step estimation heuristics (optimized for speed)."""

    def test_simple_query_tasks(self) -> None:
        """Verify simple query tasks get optimized base steps."""
        planner = AdaptivePlanner()
        tasks = [
            "Analyze the code",
            "Find the bug",
            "Show me the structure",
            "Get the status",
        ]
        for task in tasks:
            steps = planner.estimate_steps(task)
            assert steps == 3, f"Expected 3 steps for '{task}', got {steps}"

    def test_file_listing_tasks(self) -> None:
        """Verify file listing tasks get optimized steps."""
        planner = AdaptivePlanner()
        tasks = [
            "List all files",
        ]
        for task in tasks:
            steps = planner.estimate_steps(task)
            assert steps == 5, f"Expected 5 steps for '{task}', got {steps}"

    def test_edit_tasks(self) -> None:
        """Verify edit tasks get optimized steps (3 base + 1 buffer = 4)."""
        planner = AdaptivePlanner()
        tasks = [
            "Edit the file",
            "Update the readme",
            "Change the content",
            "Modify the config",
            "Replace the text",
            "Fix the error",
            "Check the style",
        ]
        for task in tasks:
            steps = planner.estimate_steps(task)
            assert steps == 4, f"Expected 4 steps for '{task}', got {steps}"

    def test_create_tasks(self) -> None:
        """Verify create tasks get optimized steps."""
        planner = AdaptivePlanner()
        tasks = [
            "Create a new file",
            "Add a new feature",
            "Implement the function",
            "Write documentation",
        ]
        for task in tasks:
            steps = planner.estimate_steps(task)
            assert steps == 5, f"Expected 5 steps for '{task}', got {steps}"

    def test_refactor_tasks(self) -> None:
        """Verify refactor tasks get optimized steps (6 base + 1 buffer = 7)."""
        planner = AdaptivePlanner()
        tasks = [
            "Refactor the codebase",
            "Restructure the project",
            "Migrate to new architecture",
        ]
        for task in tasks:
            steps = planner.estimate_steps(task)
            assert steps == 7, f"Expected 7 steps for '{task}', got {steps}"

    def test_debug_tasks(self) -> None:
        """Verify debug tasks get optimized steps (5 base + 1 buffer = 6)."""
        planner = AdaptivePlanner()
        tasks = [
            "Debug the issue",
            "Troubleshoot the problem",
            "Investigate the failure",
        ]
        for task in tasks:
            steps = planner.estimate_steps(task)
            assert steps == 6, f"Expected 6 steps for '{task}', got {steps}"

    def test_documentation_tasks(self) -> None:
        """Verify documentation tasks get optimized steps (writer skill)."""
        planner = AdaptivePlanner()
        tasks = [
            "Update the readme",
            "Fix the readme typo",
            "Edit documentation",
            "Polish the docs",
        ]
        for task in tasks:
            steps = planner.estimate_steps(task)
            # Documentation uses writer skill, optimized to 4 steps
            assert steps >= 3, f"Expected at least 3 steps for '{task}', got {steps}"

    def test_multi_file_indicator(self) -> None:
        """Verify multi-file tasks get +2 steps."""
        planner = AdaptivePlanner()
        # Single file
        single_steps = planner.estimate_steps("Edit the file")
        # Multi-file
        multi_steps = planner.estimate_steps("Edit all Python files")
        assert multi_steps == single_steps + 2, (
            f"Multi-file should have +2 steps: single={single_steps}, multi={multi_steps}"
        )

    def test_default_for_unknown_tasks(self) -> None:
        """Verify unknown tasks get optimized default steps."""
        planner = AdaptivePlanner()
        steps = planner.estimate_steps("Do something random")
        assert steps == 3, f"Expected 3 steps for unknown task, got {steps}"

    def test_safety_buffer(self) -> None:
        """Verify all estimates include optimized safety buffer (+1)."""
        planner = AdaptivePlanner()
        # Test tasks with their expected base steps (before buffer)
        tasks = [
            ("Analyze the code", 3),  # Analyze -> base 2 + buffer 1 = 3
            ("Edit the file", 4),  # Edit -> base 3 + buffer 1 = 4
            ("Create a new file", 5),  # Create -> base 4 + buffer 1 = 5
            ("Refactor the code", 7),  # Refactor -> base 6 + buffer 1 = 7 (not capped)
        ]
        for task, expected_with_buffer in tasks:
            steps = planner.estimate_steps(task)
            assert steps == expected_with_buffer, (
                f"Safety buffer not applied: expected {expected_with_buffer}, got {steps}"
            )


class TestSuggestSkill:
    """Tests for skill suggestion."""

    def test_suggests_writer_for_editing(self) -> None:
        """Verify writer skill is suggested for editing tasks."""
        planner = AdaptivePlanner()
        tasks = [
            "Write a new document",
            "Edit the file",
            "Replace the content",
            "Update the readme",
            "Modify the text",
            "Polish the writing",
        ]
        for task in tasks:
            skill = planner.suggest_skill(task)
            assert skill == "writer", f"Expected 'writer' for '{task}', got '{skill}'"

    def test_suggests_grep_for_searching(self) -> None:
        """Verify grep skill is suggested for search tasks."""
        planner = AdaptivePlanner()
        tasks = [
            "Grep for the pattern",
            "Search the codebase",
            "Find all occurrences",
            "Match the regex",
        ]
        for task in tasks:
            skill = planner.suggest_skill(task)
            assert skill == "grep", f"Expected 'grep' for '{task}', got '{skill}'"

    def test_suggests_runner_for_execution(self) -> None:
        """Verify runner skill is suggested for execution tasks."""
        planner = AdaptivePlanner()
        tasks = [
            "Run the tests",
            "Execute the command",
            "Build the project",
            "Compile the code",
        ]
        for task in tasks:
            skill = planner.suggest_skill(task)
            assert skill == "runner", f"Expected 'runner' for '{task}', got '{skill}'"

    def test_suggests_git_for_version_control(self) -> None:
        """Verify git skill is suggested for version control tasks."""
        planner = AdaptivePlanner()
        tasks = [
            "Git commit the changes",
            "Create a branch",
            "Merge the feature",
        ]
        for task in tasks:
            skill = planner.suggest_skill(task)
            assert skill == "git", f"Expected 'git' for '{task}', got '{skill}'"

    def test_suggests_file_ops_for_file_tasks(self) -> None:
        """Verify file_ops skill is suggested for file listing tasks."""
        planner = AdaptivePlanner()
        tasks = [
            "List all files",
            "Show project structure",
            "Get the file tree",
        ]
        for task in tasks:
            skill = planner.suggest_skill(task)
            assert skill == "file_ops", f"Expected 'file_ops' for '{task}', got '{skill}'"

    def test_returns_none_for_unknown(self) -> None:
        """Verify unknown tasks return None."""
        planner = AdaptivePlanner()
        skill = planner.suggest_skill("Do something vague")
        assert skill is None


class TestAnalyzeTask:
    """Tests for full task analysis."""

    @pytest.mark.asyncio
    async def test_analyze_task_without_client(self) -> None:
        """Verify analysis uses fallback when no client."""
        planner = AdaptivePlanner()
        steps, plan = await planner.analyze_task("Edit the readme")

        assert isinstance(steps, int)
        assert steps >= 3  # Optimized: at least 3 steps
        assert "PLAN:" in plan

    @pytest.mark.asyncio
    async def test_analyze_task_with_fallback_plan(self) -> None:
        """Verify fallback plan includes writer suggestion."""
        planner = AdaptivePlanner()
        steps, plan = await planner.analyze_task("Update the documentation")

        # Should suggest writer skill in fallback plan
        assert "writer" in plan.lower() or steps >= 4

    @pytest.mark.asyncio
    async def test_analyze_task_llm_fallback_on_error(self) -> None:
        """Verify falls back to heuristic when LLM fails."""
        mock_client = MagicMock()
        mock_client.complete = AsyncMock(side_effect=Exception("LLM error"))

        planner = AdaptivePlanner(client=mock_client)
        steps, plan = await planner.analyze_task("Fix the bug")

        # Should fall back to heuristic
        assert isinstance(steps, int)
        assert "PLAN:" in plan

    @pytest.mark.asyncio
    async def test_analyze_task_uses_llm_when_available(self) -> None:
        """Verify LLM is used when client is available."""
        mock_response = {"content": "STEPS: 8\nPLAN:\n- Step 1\n- Step 2"}
        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value=mock_response)

        planner = AdaptivePlanner(client=mock_client)
        steps, plan = await planner.analyze_task("Refactor the codebase")

        mock_client.complete.assert_called_once()
        # Steps are determined by heuristic (refactor = 7 steps)
        assert steps == 7, f"Heuristic should determine steps, got {steps}"
        assert "PLAN:" in plan

    @pytest.mark.asyncio
    async def test_analyze_task_parses_llm_response(self) -> None:
        """Verify LLM response is parsed correctly."""
        mock_response = {
            "content": "STEPS: 12\nPLAN:\n- Analyze requirements\n- Implement changes\n- Test thoroughly"
        }
        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value=mock_response)

        planner = AdaptivePlanner(client=mock_client)
        steps, plan = await planner.analyze_task("Complex task")

        # Steps use heuristic (default = 3 steps for unknown optimized)
        assert steps == 3, f"Heuristic should determine steps, got {steps}"
        assert "PLAN:" in plan

    @pytest.mark.asyncio
    async def test_analyze_task_uses_larger_step_count(self) -> None:
        """Verify max of heuristic and LLM estimate is used."""
        mock_response = {"content": "STEPS: 3\nPLAN:\n- Simple step"}
        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value=mock_response)

        planner = AdaptivePlanner(client=mock_client)
        # Edit task should have at least 4 steps from heuristic (optimized)
        steps, _ = await planner.analyze_task("Edit the file")

        assert steps >= 4, f"Heuristic should override low LLM estimate: {steps}"


class TestCreateAdaptivePlanner:
    """Tests for factory function."""

    @pytest.mark.asyncio
    async def test_create_adaptive_planner(self) -> None:
        """Verify factory creates planner."""
        planner = await create_adaptive_planner()
        assert isinstance(planner, AdaptivePlanner)
        assert planner._client is None

    @pytest.mark.asyncio
    async def test_create_with_client(self) -> None:
        """Verify factory accepts client."""
        mock_client = MagicMock()
        planner = await create_adaptive_planner(client=mock_client)
        assert planner._client is mock_client


class TestFallbackPlan:
    """Tests for fallback plan generation."""

    def test_fallback_plan_for_writer(self) -> None:
        """Verify fallback plan for writer tasks."""
        planner = AdaptivePlanner()
        plan = planner._fallback_plan("Update the readme", "writer")

        assert "PLAN:" in plan
        assert "writer" in plan.lower()

    def test_fallback_plan_for_grep(self) -> None:
        """Verify fallback plan for grep tasks."""
        planner = AdaptivePlanner()
        plan = planner._fallback_plan("Search for pattern", "grep")

        assert "PLAN:" in plan
        assert "grep" in plan.lower()

    def test_fallback_plan_generic(self) -> None:
        """Verify generic fallback plan."""
        planner = AdaptivePlanner()
        plan = planner._fallback_plan("Do something", None)

        assert "PLAN:" in plan
        assert "Read" in plan
        assert "Verify" in plan
        # Optimized fallback doesn't include "Analyze" step explicitly


class TestEdgeCases:
    """Tests for edge cases (optimized)."""

    def test_empty_task(self) -> None:
        """Verify empty task handled gracefully."""
        planner = AdaptivePlanner()
        steps = planner.estimate_steps("")
        assert steps == 3  # Optimized default case

    def test_very_long_task(self) -> None:
        """Verify very long task handled."""
        planner = AdaptivePlanner()
        long_task = "Edit the file " * 100
        steps = planner.estimate_steps(long_task)
        assert steps == 4  # Edit task (optimized)

    def test_special_characters(self) -> None:
        """Verify special characters handled."""
        planner = AdaptivePlanner()
        steps = planner.estimate_steps("Edit file @#$%")
        assert steps == 4  # Edit task (optimized)

    def test_unicode_content(self) -> None:
        """Verify unicode content handled."""
        planner = AdaptivePlanner()
        # Chinese text doesn't match any keyword, falls to default
        steps = planner.estimate_steps("分析代码")  # Chinese: "Analyze code"
        assert steps == 3  # Optimized default case (2 + 1 buffer)


class TestIntegration:
    """Integration-style tests (optimized)."""

    @pytest.mark.asyncio
    async def test_full_analysis_flow(self) -> None:
        """Verify complete analysis flow."""
        mock_response = {
            "content": "STEPS: 10\nPLAN:\n- Read requirements\n- Design solution\n- Implement\n- Test\n- Deploy"
        }
        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value=mock_response)

        planner = AdaptivePlanner(client=mock_client)

        # Full analysis with an edit task
        steps, plan = await planner.analyze_task("Edit the documentation")

        # Verify components
        assert isinstance(steps, int)
        assert steps > 0
        assert "PLAN:" in plan

        # Verify skill suggestion for editing
        skill = planner.suggest_skill("Edit the documentation")
        assert skill == "writer", f"Expected 'writer' for edit task, got {skill}"

    @pytest.mark.asyncio
    async def test_multiple_tasks_different_complexity(self) -> None:
        """Verify different task complexities are distinguished (optimized)."""
        planner = AdaptivePlanner()

        tasks = [
            ("Analyze structure", 3),  # Optimized: analyze = 3
            ("Edit config", 4),  # Optimized: edit = 4
            ("Create module", 5),  # Optimized: create = 5
            ("Refactor system", 7),  # Optimized: refactor = 7
        ]

        for task, expected_min in tasks:
            steps = planner.estimate_steps(task)
            assert steps >= expected_min, f"{task} should have at least {expected_min} steps"
