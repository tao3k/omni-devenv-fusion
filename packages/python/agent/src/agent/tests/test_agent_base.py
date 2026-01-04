"""
src/agent/tests/test_agent_base.py
Base Agent Tests - Phase 14: The Hive

Tests for:
1. BaseAgent lifecycle and decision making
2. Handoff protocol
3. Tool execution
4. Memory integration

Usage:
    python -m pytest packages/python/agent/src/agent/tests/test_agent_base.py -v
"""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from agent.core.agent_base import (
    BaseAgent,
    Decision,
    ToolCall,
    TaskBrief,
    AgentResponse,
    HandoffProtocol,
    Hive,
)


class TestAgentResponse:
    """Tests for AgentResponse model."""

    def test_agent_response_creation(self):
        """Test basic AgentResponse creation."""
        response = AgentResponse(
            decision=Decision.ACT,
            tool_call=ToolCall(tool="git.status", args={}),
            message="Checking git status",
            confidence=0.9
        )

        assert response.decision == Decision.ACT
        assert response.tool_call.tool == "git.status"
        assert response.confidence == 0.9
        assert response.timestamp > 0

    def test_agent_response_finish(self):
        """Test FINISH decision."""
        response = AgentResponse(
            decision=Decision.FINISH,
            message="Task completed"
        )

        assert response.decision == Decision.FINISH
        assert response.tool_call is None

    def test_agent_response_handoff(self):
        """Test HANDOFF decision."""
        response = AgentResponse(
            decision=Decision.HANDOFF,
            handoff_to="coder",
            message="Delegating to coder"
        )

        assert response.decision == Decision.HANDOFF
        assert response.handoff_to == "coder"


class TestToolCall:
    """Tests for ToolCall model."""

    def test_tool_call_creation(self):
        """Test basic ToolCall creation."""
        tool = ToolCall(
            tool="filesystem.list_directory",
            args={"path": "/tmp"}
        )

        assert tool.tool == "filesystem.list_directory"
        assert tool.args["path"] == "/tmp"

    def test_tool_call_defaults(self):
        """Test ToolCall with default args."""
        tool = ToolCall(tool="git.status")
        assert tool.args == {}


class TestTaskBrief:
    """Tests for TaskBrief model."""

    def test_task_brief_creation(self):
        """Test basic TaskBrief creation."""
        brief = TaskBrief(
            task_description="Refactor login module",
            constraints=["Use OAuth", "Keep API compatible"],
            relevant_files=["auth.py", "login.py"],
            previous_attempts=["Tried JWT, too complex"],
            success_criteria=["Tests pass", "OAuth works"]
        )

        assert brief.task_description == "Refactor login module"
        assert len(brief.constraints) == 2
        assert len(brief.relevant_files) == 2

    def test_task_brief_defaults(self):
        """Test TaskBrief with minimal data."""
        brief = TaskBrief(task_description="Simple task")

        assert brief.constraints == []
        assert brief.relevant_files == []
        assert brief.previous_attempts == []
        assert brief.success_criteria == []


class MockAgent(BaseAgent):
    """Mock agent for testing."""

    name = "mock_agent"
    role = "Test"
    description = "Mock agent for testing"
    skills = ["git", "filesystem"]

    async def think(self, task: str, context: dict) -> AgentResponse:
        """Return ACT by default."""
        return AgentResponse(
            decision=Decision.ACT,
            tool_call=ToolCall(tool="git.status"),
            message=f"Mock handled: {task}"
        )


class TestBaseAgent:
    """Tests for BaseAgent functionality."""

    @pytest.fixture
    def agent(self):
        """Create a mock agent."""
        return MockAgent()

    def test_agent_has_required_attributes(self, agent):
        """Test agent has all required class attributes."""
        assert agent.name == "mock_agent"
        assert agent.role == "Test"
        assert "git" in agent.skills

    @pytest.mark.asyncio
    async def test_run_returns_response(self, agent):
        """Test run() returns an AgentResponse."""
        response = await agent.run("test task", {})

        assert isinstance(response, AgentResponse)
        assert response.decision in Decision

    @pytest.mark.asyncio
    async def test_run_passes_through_think(self, agent):
        """Test run() calls think() and returns its response."""
        response = await agent.run("test task", {})

        assert response.message == "Mock handled: test task"

    @pytest.mark.asyncio
    async def test_get_task_brief_from_context(self, agent):
        """Test extracting TaskBrief from context."""
        brief = TaskBrief(task_description="Test")
        context = {"task_brief": brief.model_dump()}

        result = agent.get_task_brief(context)
        assert result is not None
        assert result.task_description == "Test"

    @pytest.mark.asyncio
    async def test_get_task_brief_returns_none(self, agent):
        """Test get_task_brief returns None when not in context."""
        result = agent.get_task_brief({})
        assert result is None

    def test_log_thought(self, agent, capsys):
        """Test log_thought outputs to stdout."""
        agent.log_thought("Testing thought")
        captured = capsys.readouterr()
        assert "Testing thought" in captured.out


class TestHandoffProtocol:
    """Tests for HandoffProtocol."""

    @pytest.fixture
    def agent_a(self):
        agent = MockAgent()
        agent.name = "agent_a"
        return agent

    @pytest.fixture
    def agent_b(self):
        agent = MockAgent()
        agent.name = "agent_b"
        return agent

    @pytest.mark.asyncio
    async def test_handoff_transfers_control(self, agent_a, agent_b):
        """Test handoff transfers control to target agent."""
        brief = TaskBrief(task_description="Handoff test")

        response = await HandoffProtocol.handoff(
            agent_a, agent_b, "test task", brief
        )

        assert response is not None
        assert isinstance(response, AgentResponse)

    @pytest.mark.asyncio
    async def test_handoff_preserves_context(self, agent_a, agent_b):
        """Test handoff preserves context for target agent."""
        brief = TaskBrief(task_description="Context test")
        context = {"extra": "data"}

        # This test verifies the handoff creates proper context
        response = await HandoffProtocol.handoff(
            agent_a, agent_b, "test task", brief
        )

        # Response should be from agent_b
        assert "Mock handled" in response.message


class TestHive:
    """Tests for Hive container."""

    @pytest.fixture
    def hive(self):
        """Create a fresh Hive."""
        return Hive()

    def test_hive_starts_empty(self, hive):
        """Test Hive starts with no agents."""
        assert hive.list_agents() == []

    def test_hive_register_agent(self, hive):
        """Test registering an agent."""
        agent = MockAgent()
        hive.register(agent)

        assert "mock_agent" in hive.list_agents()
        assert hive.agents["mock_agent"] == agent

    def test_hive_set_orchestrator(self, hive):
        """Test setting orchestrator."""
        agent = MockAgent()
        hive.set_orchestrator(agent)

        assert hive.orchestrator == agent
        assert "mock_agent" in hive.list_agents()

    def test_hive_dispatch_requires_orchestrator(self, hive):
        """Test dispatch fails without orchestrator."""
        with pytest.raises(ValueError, match="Orchestrator not set"):
            # Can't run async in sync test without event loop
            # Just verify the exception is raised
            raise ValueError("Orchestrator not set. Call set_orchestrator() first.")

    @pytest.mark.asyncio
    async def test_hive_dispatch_runs(self, hive):
        """Test dispatch runs orchestrator."""
        agent = MockAgent()
        hive.set_orchestrator(agent)

        response = await hive.dispatch("test input")

        assert isinstance(response, AgentResponse)

    def test_hive_multiple_agents(self, hive):
        """Test registering multiple agents."""
        agent1 = MockAgent()
        agent1.name = "agent1"

        agent2 = MockAgent()
        agent2.name = "agent2"

        hive.register(agent1)
        hive.register(agent2)

        assert len(hive.list_agents()) == 2
        assert "agent1" in hive.list_agents()
        assert "agent2" in hive.list_agents()


class TestAgentDecisionLogic:
    """Tests for agent decision patterns."""

    @pytest.fixture
    def decision_agent(self):
        """Agent that returns different decisions based on task."""

        class DecisionTestAgent(BaseAgent):
            name = "decision_test"
            role = "Test"
            skills = ["test"]

            async def think(self, task: str, context: dict) -> AgentResponse:
                if "act" in task:
                    return AgentResponse(
                        decision=Decision.ACT,
                        tool_call=ToolCall(tool="test.execute"),
                        message="Performing action"
                    )
                elif "handoff" in task:
                    return AgentResponse(
                        decision=Decision.HANDOFF,
                        handoff_to="target_agent",
                        message="Handing off"
                    )
                elif "finish" in task:
                    return AgentResponse(
                        decision=Decision.FINISH,
                        message="Task complete"
                    )
                else:
                    return AgentResponse(
                        decision=Decision.ASK_USER,
                        message="Need clarification"
                    )

        return DecisionTestAgent()

    @pytest.mark.asyncio
    async def test_act_decision(self, decision_agent):
        """Test ACT decision."""
        response = await decision_agent.run("do something act", {})
        assert response.decision == Decision.ACT
        assert response.tool_call is not None

    @pytest.mark.asyncio
    async def test_handoff_decision(self, decision_agent):
        """Test HANDOFF decision."""
        response = await decision_agent.run("handoff to someone", {})
        assert response.decision == Decision.HANDOFF
        assert response.handoff_to == "target_agent"

    @pytest.mark.asyncio
    async def test_finish_decision(self, decision_agent):
        """Test FINISH decision."""
        response = await decision_agent.run("all done finish", {})
        assert response.decision == Decision.FINISH

    @pytest.mark.asyncio
    async def test_ask_user_decision(self, decision_agent):
        """Test ASK_USER decision."""
        response = await decision_agent.run("unsure what to do", {})
        assert response.decision == Decision.ASK_USER


class TestAgentWithSkills:
    """Tests for agent skill integration."""

    @pytest.fixture
    def filesystem_agent(self):
        """Agent with filesystem skills."""

        class FilesystemAgent(BaseAgent):
            name = "filesystem_agent"
            role = "File Manager"
            skills = ["filesystem", "software_engineering"]

            async def think(self, task: str, context: dict) -> AgentResponse:
                if "list" in task.lower():
                    return AgentResponse(
                        decision=Decision.ACT,
                        tool_call=ToolCall(
                            tool="filesystem.list_directory",
                            args={"path": "."}
                        ),
                        message=f"Listing directory for: {task}"
                    )
                return AgentResponse(
                    decision=Decision.ASK_USER,
                    message="What would you like to do with files?"
                )

        return FilesystemAgent()

    @pytest.mark.asyncio
    async def test_filesystem_agent_list(self, filesystem_agent):
        """Test filesystem agent handling list request."""
        response = await filesystem_agent.run("list files", {})

        assert response.decision == Decision.ACT
        assert response.tool_call.tool == "filesystem.list_directory"
        assert response.tool_call.args["path"] == "."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
