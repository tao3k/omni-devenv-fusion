"""
src/agent/tests/test_phase25_one_tool.py
Phase 25: One Tool Architecture Integration Tests.

Tests the complete flow:
1. omni tool registration and dispatch
2. Real LLM session feedback with omni commands
3. Skill loading and command execution
4. Multi-turn conversation with @omni syntax

Usage:
    python -m pytest packages/python/agent/src/agent/tests/test_phase25_one_tool.py -v -s

    # Run with real LLM session:
    python -m pytest packages/python/agent/src/agent/tests/test_phase25_one_tool.py::TestOmniRealLLMSession -v -s
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from agent.core.skill_manager import get_skill_manager, SkillManager
from agent.core.router import SemanticRouter, clear_routing_cache


# =============================================================================
# Fixture: Real Skill Manager
# =============================================================================


@pytest.fixture
def real_skill_manager():
    """Create a real skill manager with all skills loaded."""
    manager = get_skill_manager()
    return manager


# =============================================================================
# Test: One Tool Registration
# =============================================================================


class TestOmniToolRegistration:
    """Test that only one tool 'omni' is registered with MCP."""

    def test_only_omni_tool_in_mcp_server(self):
        """Verify MCP server has ONLY 'omni' tool registered."""
        from agent.mcp_server import mcp

        tools = list(mcp._tool_manager._tools.values())
        tool_names = [t.name for t in tools]

        # Phase 25: Only 'omni' should be registered as MCP tool
        # Phase 27: JIT tools are skill commands under 'omni', not separate MCP tools
        assert tool_names == ["omni"], f"Expected only 'omni', got: {tool_names}"

    def test_omni_is_primary_tool(self):
        """Verify the 'omni' tool is the first/main tool."""
        from agent.mcp_server import mcp

        tools = list(mcp._tool_manager._tools.values())
        assert tools[0].name == "omni", f"Tool name is '{tools[0].name}', expected 'omni'"

    def test_omni_function_exists(self):
        """Verify the omni function can be imported."""
        from agent.mcp_server import omni

        assert callable(omni), "omni should be callable"


# =============================================================================
# Test: Omni Dispatch Logic
# =============================================================================


class TestOmniDispatch:
    """Test omni dispatch logic with real skill manager."""

    @pytest.mark.asyncio
    async def test_dispatch_git_status(self, real_skill_manager):
        """Test @omni('git.status') dispatch."""
        from agent.mcp_server import omni

        result = await omni("git.status")

        assert isinstance(result, str)
        # git.status returns staged files list or "Clean" message
        assert "assets/" in result or "M " in result or result == "✅ Clean"

    @pytest.mark.asyncio
    async def test_dispatch_git_help(self, real_skill_manager):
        """Test @omni('git') shows git commands."""
        from agent.mcp_server import omni

        result = await omni("git")

        assert isinstance(result, str)
        assert "git" in result.lower()
        assert "git_status" in result or "status" in result

    @pytest.mark.asyncio
    async def test_dispatch_help_shows_all_skills(self, real_skill_manager):
        """Test @omni('help') shows all skills."""
        from agent.mcp_server import omni

        result = await omni("help")

        assert isinstance(result, str)
        assert "Available Skills" in result or "🛠️" in result
        assert "git" in result

    @pytest.mark.asyncio
    async def test_dispatch_with_args(self, real_skill_manager):
        """Test @omni with arguments."""
        from agent.mcp_server import omni

        result = await omni("git.log", {"n": 3})

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_dispatch_filesystem_read(self, real_skill_manager):
        """Test @omni('filesystem.read') dispatch."""
        from agent.mcp_server import omni

        result = await omni("filesystem.read", {"path": "assets/skills/filesystem/manifest.json"})

        assert isinstance(result, str)
        assert "filesystem" in result or "manifest" in result

    @pytest.mark.asyncio
    async def test_dispatch_knowledge_context(self, real_skill_manager):
        """Test @omni('knowledge.get_development_context') dispatch."""
        from agent.mcp_server import omni

        result = await omni("knowledge.get_development_context")

        assert isinstance(result, str)
        assert "project" in result.lower() or "context" in result.lower()


# =============================================================================
# Test: Error Handling
# =============================================================================


class TestOmniErrorHandling:
    """Test omni error handling."""

    @pytest.mark.asyncio
    async def test_nonexistent_skill_error(self, real_skill_manager):
        """Test error for nonexistent skill."""
        from agent.mcp_server import omni

        result = await omni("nonexistent_skill.status")

        assert isinstance(result, str)
        assert "not found" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_nonexistent_command_error(self, real_skill_manager):
        """Test error for nonexistent command."""
        from agent.mcp_server import omni

        result = await omni("git.nonexistent_command_xyz")

        assert isinstance(result, str)
        assert "not found" in result.lower() or "Error" in result


# =============================================================================
# Test: Real LLM Session (Optional - requires API key)
# =============================================================================


class TestOmniRealLLMSession:
    """
    Integration test with real LLM session.

    This test actually opens an LLM session and tests
    the complete feedback loop with omni commands.

    Run with: pytest ... -s -v
    """

    @pytest.mark.asyncio
    async def test_conversation_with_omni_commands(self):
        """
        Test a multi-turn conversation that uses @omni commands.

        This tests:
        1. Router selects skills based on user intent
        2. Agent receives Mission Brief
        3. Agent can use @omni to execute skill commands
        4. Response is generated based on tool results
        """
        from agent.core.orchestrator import Orchestrator
        from agent.core.router import clear_routing_cache

        # Clear cache for fresh routing
        clear_routing_cache()

        # Create orchestrator with real LLM
        orchestrator = Orchestrator()

        # Check if inference is configured
        if not orchestrator.inference:
            pytest.skip("No inference engine configured (ANTHROPIC_API_KEY missing)")

        # Test query that should route to git skill
        query1 = "Show me the git status"
        response1 = await orchestrator.dispatch(query1, history=[])

        # Verify response
        assert isinstance(response1, str)
        assert len(response1) > 0

        # The response should mention git status or contain @omni command
        print(f"\n🤖 Response to '{query1}':\n{response1[:500]}...")

        # Second query about tests
        query2 = "Run the tests"
        response2 = await orchestrator.dispatch(query2, history=[])

        assert isinstance(response2, str)
        print(f"\n🤖 Response to '{query2}':\n{response2[:500]}...")

    @pytest.mark.asyncio
    async def test_router_suggests_omni_commands(self):
        """
        Test that router generates suggestions with @omni syntax.

        When routing a query, the router should suggest
        the appropriate @omni commands.
        """
        from agent.core.router import SemanticRouter, clear_routing_cache

        clear_routing_cache()
        router = SemanticRouter(use_semantic_cache=True)

        if not router.inference:
            pytest.skip("No inference engine configured")

        # Route a git-related query
        result = await router.route("commit my changes with message feat: add new feature")

        # Should route to git skill
        assert "git" in result.selected_skills

        # Mission brief should be actionable
        assert len(result.mission_brief) > 0
        assert "commit" in result.mission_brief.lower() or "git" in result.mission_brief.lower()

        print(f"\n🎯 Router Result:")
        print(f"   Skills: {result.selected_skills}")
        print(f"   Confidence: {result.confidence}")
        print(f"   Brief: {result.mission_brief[:100]}...")


# =============================================================================
# Test: Skill Manager Loading (Critical Path)
# =============================================================================


class TestSkillManagerLoading:
    """
    Test skill manager loading and command extraction.

    This is a CRITICAL path test - ensures skills load correctly with
    decorators.py properly resolved from the agent source directory,
    NOT from the assets/skills directory.

    Regression test for: "No module named 'agent.skills.decorators'"
    """

    def test_all_skills_load_with_decorators(self):
        """
        Verify ALL skills load successfully with decorators.

        This catches the bug where decorators.py path was calculated
        incorrectly (assets/skills/decorators.py instead of
        packages/python/agent/src/agent/skills/decorators.py).
        """
        import sys

        # Clear any cached modules for fresh test
        modules_to_clear = [k for k in sys.modules.keys() if k.startswith("agent.skills")]
        for mod in modules_to_clear:
            del sys.modules[mod]

        # Create fresh skill manager
        manager = SkillManager()

        # Load all skills
        skills = manager.load_skills()

        # Should load many skills (at least git, filesystem, knowledge)
        skill_names = list(skills.keys())
        print(f"\n✅ Loaded {len(skill_names)} skills: {skill_names}")

        # Critical assertions
        assert len(skill_names) > 10, f"Expected >10 skills, got {len(skill_names)}"

        # These must be present
        assert "git" in skill_names, "git skill must load"
        assert "filesystem" in skill_names, "filesystem skill must load"
        assert "knowledge" in skill_names, "knowledge skill must load"

    def test_git_skill_has_prepare_commit_command(self):
        """Verify git skill has the prepare_commit command loaded."""
        manager = get_skill_manager()

        # Check git skill commands
        commands = manager.list_commands("git")
        print(f"\n📦 Git commands: {len(commands)}")

        # Must have prepare_commit
        assert "git_prepare_commit" in commands, "git_prepare_commit must exist"
        assert "git_execute_commit" in commands, "git_execute_commit must exist"
        assert "git_status" in commands, "git_status must exist"

    def test_decorators_module_loaded(self):
        """Verify decorators.py was loaded from correct location."""
        import sys

        # Check decorators module exists
        assert "agent.skills.decorators" in sys.modules, "agent.skills.decorators must be loaded"

        decorators_module = sys.modules["agent.skills.decorators"]

        # Verify it has the skill_command decorator
        assert hasattr(decorators_module, "skill_command"), (
            "skill_command decorator must exist in decorators module"
        )

    def test_git_commands_are_skill_command_decorated(self):
        """Verify git commands were properly extracted from decorated functions."""
        manager = get_skill_manager()

        # Get git skill
        git_skill = manager.skills.get("git")
        assert git_skill is not None, "git skill must exist"

        # Check some commands exist and have proper attributes
        prepare_commit = git_skill.commands.get("git_prepare_commit")
        assert prepare_commit is not None, "git_prepare_commit command must exist"
        assert prepare_commit.category == "workflow", (
            "git_prepare_commit should be workflow category"
        )
        assert (
            "lefthook" in prepare_commit.description.lower()
            or "lefthook" in prepare_commit.description
            or "pre-commit" in prepare_commit.description
        ), "git_prepare_commit should mention lefthook or pre-commit"

    def test_skill_command_decorator_works(self):
        """Test that the skill_command decorator properly wraps functions."""
        from agent.skills.decorators import skill_command

        # Create a test function
        @skill_command(
            name="test_command",
            category="test",
            description="A test command",
        )
        def test_func():
            return "test_result"

        # Verify it has the marker
        assert hasattr(test_func, "_is_skill_command"), (
            "Decorated function must have _is_skill_command marker"
        )
        assert test_func._is_skill_command is True, "_is_skill_command must be True"

        # Verify config is stored
        assert hasattr(test_func, "_skill_config"), "Decorated function must have _skill_config"
        assert test_func._skill_config["name"] == "test_command"
        assert test_func._skill_config["category"] == "test"

        # Verify function still works
        assert test_func() == "test_result"

    @pytest.mark.asyncio
    async def test_prepare_commit_runs_successfully(self):
        """Test that prepare_commit command actually works."""
        from agent.mcp_server import omni

        # Run prepare_commit - should not raise
        result = await omni("git.prepare_commit")

        # Should return a valid result (not an error)
        assert isinstance(result, str)
        assert len(result) > 0

        # Should contain expected output markers
        assert (
            "Git Commit Preparation" in result
            or "Lefthook" in result
            or "Staged" in result
            or "commit" in result.lower()
        ), f"prepare_commit result should contain commit-related content"


class TestOmniCLISimulation:
    """
    Simulate the CLI interactive mode to test @omni in conversation context.
    """

    @pytest.mark.asyncio
    async def test_omni_in_conversation_context(self):
        """
        Test using @omni within a conversation-like context.

        This simulates how Claude would use @omni when
        it needs to execute skill commands during a conversation.
        """
        from agent.mcp_server import omni

        # Simulate conversation flow
        conversation_steps = [
            ("help", "User asks for help"),
            ("git.status", "User checks git status"),
            ("filesystem.read", "User reads a file"),
        ]

        for command, description in conversation_steps:
            result = await omni(command)
            print(f"\n📝 {description}: @omni('{command}')")
            print(f"   Result preview: {result[:150]}...")

            # Each result should be valid
            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_omni_syntax_variations(self):
        """
        Test different @omni syntax variations.

        - @omni("skill.command")
        - @omni("skill.command", args={})
        - @omni("skill")  # Show help

        Note: git commands are excluded as output is dynamic.
        """
        from agent.mcp_server import omni

        test_cases = [
            # (command, args, expected_in_result)
            ("help", None, "Available Skills"),
            ("git", None, "git"),
        ]

        for command, args, expected in test_cases:
            if args:
                result = await omni(command, args)
            else:
                result = await omni(command)

            assert expected in result, f"Expected '{expected}' in result for command '{command}'"
            print(f"✅ @omni('{command}', {args}) -> contains '{expected}'")


# =============================================================================
# Performance Benchmark
# =============================================================================


class TestOmniPerformance:
    """Performance benchmarks for Phase 25 One Tool architecture."""

    @pytest.mark.asyncio
    async def test_omni_dispatch_latency(self):
        """Measure @omni dispatch latency."""
        from agent.mcp_server import omni
        import time

        iterations = 5
        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()
            _ = await omni("git.status")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        print(f"\n⚡ Omni Dispatch Latency:")
        print(f"   Average: {avg_latency:.1f}ms")
        print(f"   Min: {min(latencies):.1f}ms")
        print(f"   Max: {max(latencies):.1f}ms")

        # Should be under 100ms for local commands
        assert avg_latency < 100, f"Average latency {avg_latency:.1f}ms exceeds 100ms threshold"


# =============================================================================
# Main Entry Point (for manual testing)
# =============================================================================


async def run_real_session_test():
    """
    Run a real LLM session test manually.

    Usage:
        python -c "from test_phase25_one_tool import run_real_session_test; asyncio.run(run_real_session_test())"
    """
    print("=" * 60)
    print("PHASE 25 ONE TOOL - REAL SESSION TEST")
    print("=" * 60)

    from agent.mcp_server import omni

    # Test 1: Help
    print("\n📋 Test 1: @omni('help')")
    result = omni("help")
    print(result[:300])

    # Test 2: Git status
    print("\n🔧 Test 2: @omni('git.status')")
    result = omni("git.status")
    print(result[:300])

    # Test 3: Knowledge context
    print("\n🧠 Test 3: @omni('knowledge.get_development_context')")
    result = omni("knowledge.get_development_context")
    print(result[:300])

    print("\n" + "=" * 60)
    print("✅ Real Session Test Complete")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--real":
        asyncio.run(run_real_session_test())
    else:
        # Run pytest
        pytest.main([__file__, "-v", "-s"])
