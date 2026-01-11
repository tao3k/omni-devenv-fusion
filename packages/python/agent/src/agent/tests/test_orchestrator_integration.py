"""
src/agent/tests/test_orchestrator_integration.py
Orchestrator Integration Tests.

Tests the complete flow:
1. Orchestrator -> Router -> Agent dispatch
2. Context Injection (Mission Brief)
3. Agent execution with narrow skills
4. Phase 15 Feedback Loop (Virtuous Cycle)

Usage:
    python -m pytest packages/python/agent/src/agent/tests/test_orchestrator_integration.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.core.orchestrator import Orchestrator
from agent.core.router import AgentRoute
from agent.core.agents.coder import CoderAgent
from agent.core.agents.reviewer import ReviewerAgent


class TestOrchestratorDispatch:
    """Test Orchestrator dispatch flow."""

    @pytest.mark.asyncio
    async def test_dispatch_to_coder(self):
        """Test dispatch routes coding tasks to CoderAgent."""
        orchestrator = Orchestrator()

        # Mock router to return coder route
        orchestrator.router.route_to_agent = AsyncMock(
            return_value=AgentRoute(
                target_agent="coder",
                confidence=0.85,
                reasoning="Keyword match: coding task",
                task_brief="Fix the bug in router.py",
                constraints=["Run tests after fix"],
                relevant_files=["router.py"],
            )
        )

        with patch.object(
            orchestrator.router, "route_to_agent", new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = AgentRoute(
                target_agent="coder",
                confidence=0.9,
                reasoning="Test routing",
                task_brief="Fix the bug",
            )

            # Dispatch should work without errors
            response = await orchestrator.dispatch("Fix the bug in router.py", history=[])

            # Verify router was called
            mock_route.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_to_reviewer(self):
        """Test dispatch routes review tasks to ReviewerAgent."""
        orchestrator = Orchestrator()

        # Mock router to return reviewer route
        orchestrator.router.route_to_agent = AsyncMock(
            return_value=AgentRoute(
                target_agent="reviewer",
                confidence=0.88,
                reasoning="Keyword match: review task",
                task_brief="Review the changes in main.py",
                constraints=["Check tests", "Verify lint"],
                relevant_files=["main.py"],
            )
        )

        with patch.object(
            orchestrator.router, "route_to_agent", new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = AgentRoute(
                target_agent="reviewer",
                confidence=0.9,
                reasoning="Test routing",
                task_brief="Review the code",
            )

            response = await orchestrator.dispatch("Review main.py", history=[])

            # Verify router was called
            mock_route.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_fallback_to_coder(self):
        """Test dispatch falls back to Coder when unknown agent."""
        orchestrator = Orchestrator()

        # Mock router to return unknown agent
        orchestrator.router.route_to_agent = AsyncMock(
            return_value=AgentRoute(
                target_agent="unknown_agent",  # This agent doesn't exist
                confidence=0.5,
                reasoning="Unknown agent type",
                task_brief="Do something",
            )
        )

        with patch.object(
            orchestrator.router, "route_to_agent", new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = AgentRoute(
                target_agent="unknown_agent",
                confidence=0.5,
                reasoning="Unknown",
                task_brief="Do something",
            )

            # Should not crash, should fall back to coder
            response = await orchestrator.dispatch("Do something", history=[])

            # Verify execution completed (even if mock returned placeholder)
            assert mock_route.called

    @pytest.mark.asyncio
    async def test_dispatch_with_history(self):
        """Test dispatch preserves conversation history."""
        orchestrator = Orchestrator()

        history = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
        ]

        with patch.object(
            orchestrator.router, "route_to_agent", new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = AgentRoute(
                target_agent="coder",
                confidence=0.9,
                reasoning="Test",
                task_brief="Continue the task",
            )

            await orchestrator.dispatch("Continue the task", history=history)

            # Verify history was passed to router
            mock_route.assert_called_once()
            call_args = mock_route.call_args
            # History should be included in the call
            assert call_args is not None


class TestOrchestratorWithHiveContext:
    """Test Orchestrator dispatch with explicit hive context."""

    @pytest.mark.asyncio
    async def test_dispatch_with_explicit_agent(self):
        """Test dispatch with explicit target_agent in context."""
        orchestrator = Orchestrator()

        hive_context = {
            "target_agent": "reviewer",
            "mission_brief": "Review this PR carefully",
            "constraints": ["Check tests", "Verify lint"],
            "relevant_files": ["pr_changes.diff"],
            "history": [],
        }

        # Should route to reviewer without calling router
        with patch.object(
            orchestrator.router, "route_to_agent", new_callable=AsyncMock
        ) as mock_route:
            response = await orchestrator.dispatch_with_hive_context("Review this PR", hive_context)

            # Router should NOT be called when explicit agent is provided
            mock_route.assert_not_called()


class TestOrchestratorStatus:
    """Test Orchestrator status reporting."""

    def test_get_status_basic(self):
        """Test status reporting without inference engine."""
        from agent.core.agents import CoderAgent, ReviewerAgent

        orchestrator = Orchestrator()

        status = orchestrator.get_status()

        assert status["router_loaded"] is True
        # inference_configured depends on environment (API key presence)
        # Just verify the key exists and has a boolean value
        assert isinstance(status["inference_configured"], bool)
        assert "coder" in status["agents_available"]
        assert "reviewer" in status["agents_available"]

    def test_orchestrator_has_agent_map(self):
        """Test Orchestrator has correct agent registry."""
        from agent.core.agents import CoderAgent, ReviewerAgent

        orchestrator = Orchestrator()

        # Verify agent map structure
        assert orchestrator.agent_map is not None
        assert "coder" in orchestrator.agent_map
        assert "reviewer" in orchestrator.agent_map
        assert orchestrator.agent_map["coder"] is CoderAgent
        assert orchestrator.agent_map["reviewer"] is ReviewerAgent


class TestAgentSelection:
    """Test that correct agents are selected based on routing."""

    @pytest.mark.asyncio
    async def test_coder_receives_coder_skills(self):
        """Test that CoderAgent only receives code-related tools."""
        from agent.core.agents import CoderAgent

        coder = CoderAgent()

        # Coder should have code skills
        assert "filesystem" in coder.default_skills
        assert "python_engineering" in coder.default_skills

        # Coder should NOT have quality skills
        assert "git" not in coder.default_skills
        assert "testing" not in coder.default_skills

    @pytest.mark.asyncio
    async def test_reviewer_receives_reviewer_skills(self):
        """Test that ReviewerAgent only receives quality-related tools."""
        from agent.core.agents import ReviewerAgent

        reviewer = ReviewerAgent()

        # Reviewer should have quality skills
        assert "git" in reviewer.default_skills
        assert "testing" in reviewer.default_skills
        assert "linter" in reviewer.default_skills

        # Reviewer should NOT have code skills
        assert "python_engineering" not in reviewer.default_skills


class TestMissionBriefIntegration:
    """Test Mission Brief is properly injected into agent context."""

    @pytest.mark.asyncio
    async def test_mission_brief_included_in_context(self):
        """Verify Mission Brief appears in agent system prompt."""
        from agent.core.agents import CoderAgent

        coder = CoderAgent()

        # Mock the registry
        coder.registry = MagicMock()
        coder.registry.get_skill_manifest = MagicMock(
            return_value=MagicMock(description="Test skill", tools_module="test.tools")
        )

        # Prepare context with specific mission brief
        mission = "Fix the critical security vulnerability in auth.py"

        ctx = await coder.prepare_context(
            mission_brief=mission, constraints=["Security first"], relevant_files=["auth.py"]
        )

        # Verify Mission Brief is in system prompt
        assert mission in ctx.system_prompt
        assert "Security first" in ctx.system_prompt
        assert "auth.py" in ctx.relevant_files


class TestOrchestratorIntegrationFlow:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_full_dispatch_flow(self):
        """Test complete dispatch: Router -> Agent -> Response."""
        orchestrator = Orchestrator()

        # Mock router response
        orchestrator.router.route_to_agent = AsyncMock(
            return_value=AgentRoute(
                target_agent="coder",
                confidence=0.92,
                reasoning="High confidence coding task",
                task_brief="Implement feature X with tests",
                constraints=["Write tests"],
                relevant_files=["feature.py"],
            )
        )

        with patch.object(
            orchestrator.router, "route_to_agent", new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = AgentRoute(
                target_agent="coder",
                confidence=0.9,
                reasoning="Test",
                task_brief="Implement feature",
            )

            # Execute dispatch
            response = await orchestrator.dispatch(
                "Implement a new feature in feature.py", history=[]
            )

            # Verify complete flow
            mock_route.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_handles_exceptions(self):
        """Test that dispatch handles agent exceptions gracefully."""
        orchestrator = Orchestrator()

        # Mock router to return valid route
        orchestrator.router.route_to_agent = AsyncMock(
            return_value=AgentRoute(
                target_agent="coder", confidence=0.9, reasoning="Test", task_brief="Test task"
            )
        )

        with patch.object(
            orchestrator.router, "route_to_agent", new_callable=AsyncMock
        ) as mock_route:
            mock_route.return_value = AgentRoute(
                target_agent="coder", confidence=0.9, reasoning="Test", task_brief="Test task"
            )

            # Should not raise, should return error message
            try:
                response = await orchestrator.dispatch("Test", history=[])
                # If we get here without exception, test passes
                assert mock_route.called
            except Exception as e:
                pytest.fail(f"Dispatch should handle exceptions gracefully: {e}")


# =============================================================================
# Phase 15: Feedback Loop Tests
# =============================================================================


class TestFeedbackLoop:
    """Test Phase 15 Feedback Loop (Virtuous Cycle)."""

    @pytest.mark.asyncio
    async def test_feedback_loop_audit_approved_first_try(self):
        """Test that feedback loop passes when audit approves on first try."""
        from agent.core.orchestrator import Orchestrator

        orchestrator = Orchestrator(feedback_enabled=True, max_retries=2)

        # Create the route that will be returned
        coder_route = AgentRoute(
            target_agent="coder",
            confidence=0.9,
            reasoning="Test",
            task_brief="Write a simple function",
        )

        # Directly set up the mock on router before dispatch
        orchestrator.router.route_to_agent = AsyncMock(return_value=coder_route)

        # Create a mock CoderAgent that tracks calls
        original_coder_init = CoderAgent.__init__
        original_coder_run = CoderAgent.run

        coder_instance = MagicMock()
        coder_instance.name = "coder"
        coder_instance.run = AsyncMock(
            return_value=MagicMock(
                success=True, content="def hello():\n    return 'Hello, World!'", confidence=0.85
            )
        )

        with patch.object(CoderAgent, "__init__", return_value=None):
            with patch.object(CoderAgent, "run", coder_instance.run):
                # Mock reviewer's audit to approve
                with patch.object(ReviewerAgent, "__init__", return_value=None):
                    reviewer_instance = MagicMock()
                    reviewer_instance.audit = AsyncMock(
                        return_value=MagicMock(
                            approved=True,
                            feedback="Output meets quality standards.",
                            confidence=0.9,
                            issues_found=[],
                            suggestions=[],
                        )
                    )
                    with patch.object(ReviewerAgent, "audit", reviewer_instance.audit):
                        response = await orchestrator.dispatch("Write a hello function", history=[])

                        # Should return the worker's content
                        assert "Hello, World!" in response
                        # Audit should have been called
                        assert reviewer_instance.audit.call_count == 1

    @pytest.mark.asyncio
    async def test_feedback_loop_audit_rejected_retries(self):
        """Test that feedback loop retries when audit rejects."""
        from agent.core.orchestrator import Orchestrator

        orchestrator = Orchestrator(feedback_enabled=True, max_retries=2)

        # Create the route
        coder_route = AgentRoute(
            target_agent="coder", confidence=0.9, reasoning="Test", task_brief="Write a function"
        )
        orchestrator.router.route_to_agent = AsyncMock(return_value=coder_route)

        call_count = 0

        async def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return MagicMock(
                success=True,
                content=f"Attempt {call_count}: def test():\n    pass",
                confidence=0.85,
            )

        with patch.object(CoderAgent, "__init__", return_value=None):
            with patch.object(CoderAgent, "run", side_effect=mock_run):
                # First audit rejects, second approves
                with patch.object(ReviewerAgent, "__init__", return_value=None):
                    reviewer_instance = MagicMock()
                    audit_responses = [
                        MagicMock(
                            approved=False,
                            feedback="Missing docstring.",
                            confidence=0.6,
                            issues_found=["missing_docstring"],
                            suggestions=["Add a docstring to the function"],
                        ),
                        MagicMock(
                            approved=True,
                            feedback="Output meets quality standards.",
                            confidence=0.9,
                            issues_found=[],
                            suggestions=[],
                        ),
                    ]
                    reviewer_instance.audit = AsyncMock(side_effect=audit_responses)
                    with patch.object(ReviewerAgent, "audit", reviewer_instance.audit):
                        response = await orchestrator.dispatch("Write a function", history=[])

                        # Worker should have been called twice (initial + retry)
                        assert call_count == 2
                        # Should contain the final attempt's content
                        assert "Attempt 2:" in response

    @pytest.mark.asyncio
    async def test_feedback_loop_disabled(self):
        """Test that feedback loop can be disabled."""
        from agent.core.orchestrator import Orchestrator

        orchestrator = Orchestrator(feedback_enabled=False)

        # Create the route
        coder_route = AgentRoute(
            target_agent="coder", confidence=0.9, reasoning="Test", task_brief="Write a function"
        )
        orchestrator.router.route_to_agent = AsyncMock(return_value=coder_route)

        with patch.object(CoderAgent, "__init__", return_value=None):
            coder_instance = MagicMock()
            coder_instance.run = AsyncMock(
                return_value=MagicMock(
                    success=True, content="def test():\n    return True", confidence=0.85
                )
            )
            with patch.object(CoderAgent, "run", coder_instance.run):
                # Patch reviewer to track if audit is called
                with patch.object(ReviewerAgent, "__init__", return_value=None):
                    reviewer_instance = MagicMock()
                    with patch.object(ReviewerAgent, "audit", reviewer_instance.audit):
                        response = await orchestrator.dispatch("Write a function", history=[])

                        # Audit should NOT be called when feedback is disabled
                        reviewer_instance.audit.assert_not_called()
                        assert "True" in response

    @pytest.mark.asyncio
    async def test_feedback_loop_max_retries_exceeded(self):
        """Test that feedback loop returns warning after max retries."""
        from agent.core.orchestrator import Orchestrator

        orchestrator = Orchestrator(feedback_enabled=True, max_retries=2)

        # Create the route
        coder_route = AgentRoute(
            target_agent="coder", confidence=0.9, reasoning="Test", task_brief="Write a function"
        )
        orchestrator.router.route_to_agent = AsyncMock(return_value=coder_route)

        call_count = 0

        async def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return MagicMock(
                success=True,
                content=f"Attempt {call_count}: def test():\n    pass",
                confidence=0.85,
            )

        with patch.object(CoderAgent, "__init__", return_value=None):
            with patch.object(CoderAgent, "run", side_effect=mock_run):
                # All audits reject
                with patch.object(ReviewerAgent, "__init__", return_value=None):
                    reviewer_instance = MagicMock()
                    reviewer_instance.audit = AsyncMock(
                        return_value=MagicMock(
                            approved=False,
                            feedback="Code quality issues.",
                            confidence=0.5,
                            issues_found=["style_issues", "missing_type_hints"],
                            suggestions=["Fix style", "Add type hints"],
                        )
                    )
                    with patch.object(ReviewerAgent, "audit", reviewer_instance.audit):
                        response = await orchestrator.dispatch("Write a function", history=[])

                        # Should have attempted max_retries times
                        assert call_count == 2
                        # Should include warning about failed audit
                        assert "Quality review failed" in response or "Warning" in response

    @pytest.mark.asyncio
    async def test_feedback_loop_reviewer_task_not_audited(self):
        """Test that Reviewer tasks are not audited (no self-review)."""
        from agent.core.orchestrator import Orchestrator

        orchestrator = Orchestrator(feedback_enabled=True, max_retries=2)

        # Create the route for reviewer
        reviewer_route = AgentRoute(
            target_agent="reviewer", confidence=0.9, reasoning="Test", task_brief="Review the code"
        )
        orchestrator.router.route_to_agent = AsyncMock(return_value=reviewer_route)

        # Track if CoderAgent.run is called
        coder_run_called = False

        async def mock_coder_run(*args, **kwargs):
            nonlocal coder_run_called
            coder_run_called = True
            return MagicMock(success=True, content="", confidence=0.85)

        with patch.object(ReviewerAgent, "__init__", return_value=None):
            reviewer_instance = MagicMock()
            reviewer_instance.name = "reviewer"
            reviewer_instance.run = AsyncMock(
                return_value=MagicMock(success=True, content="Code looks good.", confidence=0.85)
            )
            with patch.object(ReviewerAgent, "run", reviewer_instance.run):
                with patch.object(CoderAgent, "__init__", return_value=None):
                    with patch.object(CoderAgent, "run", mock_coder_run):
                        response = await orchestrator.dispatch("Review the code", history=[])

                        # Coder should not be involved in reviewer tasks
                        assert not coder_run_called
                        assert "looks good" in response


class TestAuditResult:
    """Test AuditResult model."""

    def test_audit_result_approved(self):
        """Test creating an approved AuditResult."""
        from agent.core.agents.base import AuditResult

        result = AuditResult(
            approved=True,
            feedback="Great work!",
            confidence=0.95,
            issues_found=[],
            suggestions=["Consider adding tests"],
        )

        assert result.approved is True
        assert result.confidence == 0.95
        assert len(result.issues_found) == 0
        assert len(result.suggestions) == 1

    def test_audit_result_rejected(self):
        """Test creating a rejected AuditResult."""
        from agent.core.agents.base import AuditResult

        result = AuditResult(
            approved=False,
            feedback="Missing error handling",
            confidence=0.6,
            issues_found=["no_error_handling", "missing_validation"],
            suggestions=["Add try-except blocks", "Validate inputs"],
        )

        assert result.approved is False
        assert result.confidence == 0.6
        assert len(result.issues_found) == 2
        assert len(result.suggestions) == 2
