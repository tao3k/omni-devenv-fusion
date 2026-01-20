"""
src/agent/tests/test_agent_handoff.py
Agent Tests - Phase 14: The Hive

Tests for the new agents package:
1. BaseAgent with context injection and Mission Brief Protocol
2. CoderAgent (narrow skills - code focused)
3. ReviewerAgent (narrow skills - quality focused)

Usage:
    python -m pytest packages/python/agent/src/agent/tests/test_agent_handoff.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAgentContext:
    """Test AgentContext model."""

    def test_agent_context_creation(self):
        """Test AgentContext can be created with all fields."""
        from agent.core.agents.base import AgentContext

        ctx = AgentContext(
            system_prompt="You are a coder",
            tools=[{"name": "filesystem.list_directory"}],
            mission_brief="Fix the bug in main.py",
            constraints=["Run tests"],
            relevant_files=["main.py"],
        )

        assert ctx.system_prompt == "You are a coder"
        assert ctx.mission_brief == "Fix the bug in main.py"
        assert len(ctx.constraints) == 1
        assert "main.py" in ctx.relevant_files

    def test_agent_context_defaults(self):
        """Test AgentContext default values."""
        from agent.core.agents.base import AgentContext

        ctx = AgentContext(system_prompt="Test", tools=[], mission_brief="Test mission")

        assert ctx.constraints == []
        assert ctx.relevant_files == []


class TestAgentResult:
    """Test AgentResult model."""

    def test_agent_result_creation(self):
        """Test AgentResult can be created."""
        from agent.core.agents.base import AgentResult

        result = AgentResult(success=True, content="Task completed", confidence=0.85)

        assert result.success is True
        assert result.confidence == 0.85
        assert result.tool_calls == []

    def test_agent_result_defaults(self):
        """Test AgentResult default values."""
        from agent.core.agents.base import AgentResult

        result = AgentResult(success=True)

        assert result.content == ""
        assert result.confidence == 0.5
        assert result.message == ""


class TestBaseAgent:
    """Test BaseAgent core functionality."""

    @pytest.mark.asyncio
    async def test_prepare_context_basic(self):
        """Test BaseAgent.prepare_context generates system prompt."""
        from agent.core.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            name = "test"
            role = "Test Role"
            default_skills = ["filesystem"]

        agent = TestAgent()
        agent.registry = MagicMock()
        agent.registry.get_skill_metadata = MagicMock(
            return_value=MagicMock(description="Test skill", routing_keywords=["filesystem"])
        )

        ctx = await agent.prepare_context(
            mission_brief="Fix the bug in main.py",
            constraints=["Run tests after fix"],
            relevant_files=["main.py"],
        )

        # Verify context was created
        assert ctx is not None
        assert "Fix the bug in main.py" in ctx.system_prompt
        assert "Test Role" in ctx.system_prompt
        assert "Run tests after fix" in ctx.system_prompt
        assert "main.py" in ctx.relevant_files

    def test_build_system_prompt_structure(self):
        """Test _build_system_prompt creates properly structured prompt."""
        from agent.core.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            name = "test"
            role = "Test Role"
            default_skills = []

        agent = TestAgent()

        prompt = agent._build_system_prompt(
            mission_brief="Test mission",
            skill_prompts="- test_skill: Does things",
            constraints=["constraint1"],
            relevant_files=["file.py"],
        )

        # Verify structure
        assert "# ROLE: Test Role" in prompt
        assert "## 📋 CURRENT MISSION" in prompt
        assert "Test mission" in prompt
        assert "## 🛠️ YOUR CAPABILITIES" in prompt
        assert "## ⚠️ CONSTRAINTS" in prompt
        assert "constraint1" in prompt
        assert "## 📁 RELEVANT FILES" in prompt
        assert "file.py" in prompt
        assert "## 🎯 EXECUTION RULES" in prompt

    def test_get_skill_summary(self):
        """Test get_skill_summary returns agent metadata."""
        from agent.core.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            name = "test"
            role = "Test Role"
            default_skills = ["fs", "git"]

        agent = TestAgent()
        summary = agent.get_skill_summary()

        assert summary["name"] == "test"
        assert summary["role"] == "Test Role"
        assert summary["skills"] == ["fs", "git"]
        assert summary["skill_count"] == 2

    def test_get_skill_tools(self):
        """Test _get_skill_tools returns tool info from manifests."""
        from agent.core.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            name = "test"
            role = "Test Role"
            default_skills = ["filesystem"]

        agent = TestAgent()
        agent.registry = MagicMock()
        agent.registry.get_skill_metadata = MagicMock(
            return_value=MagicMock(
                description="File system operations", routing_keywords=["filesystem"]
            )
        )

        tools = agent._get_skill_tools()

        assert len(tools) == 1
        assert tools[0]["skill"] == "filesystem"
        assert "File system operations" in tools[0]["description"]

    def test_get_skill_capabilities(self):
        """Test _get_skill_capabilities returns formatted capabilities."""
        from agent.core.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            name = "test"
            role = "Test Role"
            default_skills = ["filesystem", "git"]

        agent = TestAgent()
        agent.registry = MagicMock()

        def get_metadata(skill_name):
            if skill_name == "filesystem":
                return MagicMock(description="File operations", routing_keywords=[])
            elif skill_name == "git":
                return MagicMock(description="Git operations", routing_keywords=[])
            return None

        agent.registry.get_skill_metadata = MagicMock(side_effect=get_metadata)

        capabilities = agent._get_skill_capabilities()

        assert "- [filesystem]:" in capabilities
        assert "- [git]:" in capabilities
        assert "File operations" in capabilities


class TestCoderAgent:
    """Test CoderAgent specific behavior."""

    def test_coder_has_coder_skills(self):
        """Test CoderAgent has code-related skills only."""
        from agent.core.agents import CoderAgent

        agent = CoderAgent()

        # Should have code skills
        assert "filesystem" in agent.default_skills
        assert "code_insight" in agent.default_skills
        assert "python_engineering" in agent.default_skills
        assert "terminal" in agent.default_skills

        # Should NOT have git/testing (Reviewer skills)
        assert "git" not in agent.default_skills
        assert "testing" not in agent.default_skills

    def test_coder_role_and_name(self):
        """Test CoderAgent has correct identity."""
        from agent.core.agents import CoderAgent

        agent = CoderAgent()

        assert agent.name == "coder"
        assert agent.role == "Senior Python Architect"

    @pytest.mark.asyncio
    async def test_coder_run_execution(self):
        """Test CoderAgent.run executes successfully."""
        from agent.core.agents import CoderAgent
        from agent.core.agents.base import AgentResult

        with patch.object(CoderAgent, "_execute_with_llm", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = AgentResult(success=True, content="Done")

            agent = CoderAgent()

            result = await agent.run(task="Fix bug", mission_brief="Fix the bug")

            mock_exec.assert_called_once()
            assert result.success is True


class TestReviewerAgent:
    """Test ReviewerAgent specific behavior."""

    def test_reviewer_has_reviewer_skills(self):
        """Test ReviewerAgent has quality-related skills only."""
        from agent.core.agents import ReviewerAgent

        agent = ReviewerAgent()

        # Should have quality skills
        assert "git" in agent.default_skills
        assert "testing" in agent.default_skills
        assert "documentation" in agent.default_skills
        assert "linter" in agent.default_skills
        assert "terminal" in agent.default_skills

        # Should NOT have code skills (Coder skills)
        assert "python_engineering" not in agent.default_skills

    def test_reviewer_role_and_name(self):
        """Test ReviewerAgent has correct identity."""
        from agent.core.agents import ReviewerAgent

        agent = ReviewerAgent()

        assert agent.name == "reviewer"
        assert agent.role == "Quality Assurance Lead"

    @pytest.mark.asyncio
    async def test_reviewer_run_execution(self):
        """Test ReviewerAgent.run executes successfully."""
        from agent.core.agents import ReviewerAgent
        from agent.core.agents.base import AgentResult

        with patch.object(ReviewerAgent, "_execute_with_llm", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = AgentResult(success=True, content="Done")

            agent = ReviewerAgent()

            result = await agent.run(task="Review changes", mission_brief="Review the code changes")

            mock_exec.assert_called_once()
            assert result.success is True


class TestAgentContextNarrowing:
    """Test that agents have narrow, focused skill sets."""

    def test_coder_skill_set_is_narrow(self):
        """Test Coder has minimal, focused skills."""
        from agent.core.agents import CoderAgent

        agent = CoderAgent()

        # Coder should have 5 skills max
        assert len(agent.default_skills) == 4

        # All skills should be code-related (file_ops consolidated into filesystem)
        code_related = {"filesystem", "code_insight", "python_engineering", "terminal"}
        assert set(agent.default_skills) == code_related

    def test_reviewer_skill_set_is_narrow(self):
        """Test Reviewer has minimal, focused skills."""
        from agent.core.agents import ReviewerAgent

        agent = ReviewerAgent()

        # Reviewer should have 5 skills max
        assert len(agent.default_skills) == 5

        # All skills should be quality-related
        quality_related = {"git", "testing", "documentation", "linter", "terminal"}
        assert set(agent.default_skills) == quality_related

    def test_agents_have_complementary_skills(self):
        """Test Coder and Reviewer skills are complementary, not overlapping."""
        from agent.core.agents import CoderAgent, ReviewerAgent

        coder = CoderAgent()
        reviewer = ReviewerAgent()

        # No overlap except terminal
        overlap = set(coder.default_skills) & set(reviewer.default_skills)
        assert overlap == {"terminal"}, f"Expected only 'terminal' overlap, got: {overlap}"


class TestMissionBriefProtocol:
    """Test Mission Brief Protocol implementation."""

    @pytest.mark.asyncio
    async def test_mission_brief_in_system_prompt(self):
        """Test that Mission Brief is prominently displayed in system prompt."""
        from agent.core.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            name = "test"
            role = "Test Role"
            default_skills = []

        agent = TestAgent()
        agent.registry = MagicMock()
        agent.registry.get_skill_metadata = MagicMock(return_value=None)

        ctx = await agent.prepare_context(
            mission_brief="Fix the critical bug in router.py immediately"
        )

        # Mission Brief should be in system prompt with markers
        assert "Fix the critical bug in router.py immediately" in ctx.system_prompt
        assert "CURRENT MISSION" in ctx.system_prompt
        assert "=" in ctx.system_prompt  # Section marker

    @pytest.mark.asyncio
    async def test_context_preserves_all_brief_fields(self):
        """Test that all brief fields are preserved in context."""
        from agent.core.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            name = "test"
            role = "Test Role"
            default_skills = []

        agent = TestAgent()
        agent.registry = MagicMock()
        agent.registry.get_skill_metadata = MagicMock(return_value=None)

        ctx = await agent.prepare_context(
            mission_brief="Complete the feature",
            constraints=["Constraint 1", "Constraint 2"],
            relevant_files=["file1.py", "file2.py"],
        )

        assert ctx.mission_brief == "Complete the feature"
        assert len(ctx.constraints) == 2
        assert "Constraint 1" in ctx.constraints
        assert "file1.py" in ctx.relevant_files
        assert "file2.py" in ctx.relevant_files

    def test_system_prompt_has_execution_rules(self):
        """Test that system prompt includes execution rules."""
        from agent.core.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            name = "test"
            role = "Test Role"
            default_skills = []

        agent = TestAgent()

        prompt = agent._build_system_prompt(
            mission_brief="Test mission", skill_prompts="", constraints=[], relevant_files=[]
        )

        # Verify execution rules are present
        assert "Focus ONLY on the mission above" in prompt
        assert "Use the provided tools precisely" in prompt
        assert "If unclear, ask for clarification" in prompt


class TestAgentsPackage:
    """Test the agents package exports."""

    def test_agents_package_exports(self):
        """Test that agents package exports correct classes."""
        from agent.core.agents import (
            BaseAgent,
            AgentContext,
            AgentResult,
            CoderAgent,
            ReviewerAgent,
        )

        assert BaseAgent is not None
        assert AgentContext is not None
        assert AgentResult is not None
        assert CoderAgent is not None
        assert ReviewerAgent is not None

    def test_coder_agent_is_base_agent(self):
        """Test CoderAgent inherits from BaseAgent."""
        from agent.core.agents import CoderAgent, BaseAgent

        assert issubclass(CoderAgent, BaseAgent)

    def test_reviewer_agent_is_base_agent(self):
        """Test ReviewerAgent inherits from BaseAgent."""
        from agent.core.agents import ReviewerAgent, BaseAgent

        assert issubclass(ReviewerAgent, BaseAgent)
