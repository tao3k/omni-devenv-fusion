"""
src/agent/tests/test_phase25_one_tool.py
Phase 25: One Tool Architecture Integration Tests.

Tests the complete flow:
1. omni tool registration and dispatch
2. Real LLM session feedback with omni commands
3. Skill loading and command execution
4. Multi-turn conversation with @omni syntax

Phase 35.3: Uses pure MCP Server with SkillContext.run()

Usage:
    python -m pytest packages/python/agent/src/agent/tests/test_phase25_one_tool.py -v -s

    # Run with real LLM session:
    python -m pytest packages/python/agent/src/agent/tests/test_phase25_one_tool.py::TestOmniRealLLMSession -v -s
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from agent.core.skill_runtime import get_skill_context, SkillContext
from agent.core.router import SemanticRouter, clear_routing_cache
from agent.skills.decorators import skill_command

# Import helper for unwrapping CommandResult and omni function
from agent.tests.integration.skills.test_skills import unwrap_command_result, omni


# =============================================================================
# Fixture: Real Skill Manager
# =============================================================================


@pytest.fixture(autouse=True)
def reset_skill_manager_singleton():
    """Reset SkillContext singleton before each test."""
    import agent.core.skill_runtime.context as manager_module

    # Reset the singleton
    manager_module._instance = None
    yield
    # Cleanup after test
    manager_module._instance = None


@pytest.fixture
def real_skill_manager():
    """Create a real skill manager with all skills loaded."""
    manager = get_skill_context()
    # Ensure all skills are loaded before tests run
    if not manager.skills:
        manager.load_all()
    return manager


# =============================================================================
# Test: One Tool Registration
# =============================================================================


class TestOmniToolRegistration:
    """Test that only one tool 'omni' is registered with MCP."""

    def test_omni_function_exists(self):
        """Verify the omni function can be imported from test_skills."""
        # omni is now imported from test_skills (Phase 35.3)
        assert callable(omni), "omni should be callable"


# =============================================================================
# Test: Omni Dispatch Logic
# =============================================================================


class TestOmniDispatch:
    """Test omni dispatch logic with real skill manager."""

    @pytest.mark.asyncio
    async def test_dispatch_git_help(self, real_skill_manager):
        """Test @omni('git') shows git commands or available skills."""
        result = await omni("git")

        assert isinstance(result, str)
        assert "git" in result.lower()

    @pytest.mark.asyncio
    async def test_dispatch_help_shows_all_skills(self, real_skill_manager):
        """Test @omni('help') shows all skills."""
        result = await omni("help")

        assert isinstance(result, str)
        assert "Available Skills" in result or "🛠️" in result
        assert "git" in result

    @pytest.mark.asyncio
    async def test_dispatch_with_args(self, real_skill_manager):
        """Test @omni with arguments."""
        # git.log and other skill commands tested in assets/skills/<skill>/tests/
        pass

    @pytest.mark.asyncio
    async def test_dispatch_knowledge_context(self, real_skill_manager):
        """Test @omni('knowledge.get_development_context') dispatch."""
        # Knowledge tests migrated to assets/skills/knowledge/tests/
        pass


# =============================================================================
# Test: Error Handling
# =============================================================================


class TestOmniErrorHandling:
    """Test omni error handling."""

    @pytest.mark.asyncio
    async def test_nonexistent_skill_error(self, real_skill_manager):
        """Test error for nonexistent skill."""
        result = await omni("nonexistent_skill.status")

        assert isinstance(result, str)
        assert "not found" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_nonexistent_command_error(self, real_skill_manager):
        """Test error for nonexistent command."""
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
        router = SemanticRouter(use_semantic_cache=False)  # Disable semantic cache for test

        if not router.inference:
            pytest.skip("No inference engine configured")

        # Route a git-related query
        result = await router.route("commit my changes with message feat: add new feature")

        # Should route to git skill
        assert "git" in result.selected_skills

        # Mission brief should be actionable (could be from LLM or vector fallback)
        assert len(result.mission_brief) > 0
        # If vector fallback was used, mission_brief might not contain "commit"
        # The key assertion is that git skill was selected
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

        # Clear any cached modules for fresh test (but preserve agent.skills.core)
        modules_to_clear = [
            k
            for k in sys.modules.keys()
            if k.startswith("agent.skills") and k != "agent.skills.core"
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]

        # Create fresh skill manager
        manager = SkillContext()

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

        # Verify function still works (now returns CommandResult)
        result = unwrap_command_result(test_func())
        assert result == "test_result"


class TestOmniCLISimulation:
    """
    Simulate the CLI interactive mode to test @omni in conversation context.
    """

    @pytest.mark.asyncio
    async def test_omni_syntax_variations(self):
        """
        Test different @omni syntax variations.

        - @omni("skill.command")
        - @omni("skill.command", args={})
        - @omni("skill")  # Show help

        Note: skill-specific tests migrated to assets/skills/<skill>/tests/
        """
        test_cases = [
            # (command, args, expected_in_result)
            ("help", None, "Available Skills"),
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


# =============================================================================
# Demo: SKILLS_DIR Attribute Access (for reference)
# =============================================================================


class TestSkillPathUtilities:
    """Demonstrate SKILLS_DIR callable using settings.yaml via git toplevel."""

    def test_skills_dir_callable(self):
        """Verify SKILLS_DIR(skill="git") returns correct path from settings.yaml using git toplevel.

        Phase 63: Tests scripts/ directory instead of tools.py.
        """
        from common.skills_path import SKILLS_DIR
        from common.gitops import get_project_root

        root = get_project_root()
        expected_git_path = root / "assets" / "skills" / "git"

        # Callable access with keyword args
        assert SKILLS_DIR(skill="git") == expected_git_path

        # Phase 63: Check for scripts/__init__.py instead of tools.py
        expected_scripts_path = expected_git_path / "scripts" / "__init__.py"
        assert SKILLS_DIR(skill="git", filename="scripts/__init__.py") == expected_scripts_path

        # Verify the path exists
        assert expected_scripts_path.exists()

    def test_skills_dir_base_path(self):
        """Verify SKILLS_DIR() returns base skills path from settings.yaml."""
        from common.skills_path import SKILLS_DIR
        from common.gitops import get_project_root

        root = get_project_root()
        expected_base = root / "assets" / "skills"

        assert SKILLS_DIR() == expected_base

    def test_gitops_get_project_root(self):
        """Verify common.gitops.get_project_root() uses git toplevel."""
        from common.gitops import get_project_root

        root = get_project_root()

        # Should have .git indicator
        assert (root / ".git").exists()
        # Should have pyproject.toml
        assert (root / "pyproject.toml").exists()

    def test_skill_path_builder(self):
        """Demonstrate SkillPathBuilder convenience methods."""
        from common.skills_path import SkillPathBuilder
        from common.gitops import get_project_root

        root = get_project_root()
        builder = SkillPathBuilder()

        # Convenience methods
        assert builder.git == root / "assets/skills/git"
        assert builder.skill("git") == root / "assets/skills/git"
        assert builder.tools("git") == root / "assets/skills/git/tools.py"
        assert builder.manifest("git") == root / "assets/skills/git/SKILL.md"
        # README.md exists in git skill (formerly guide.md)
        readme_path = root / "assets/skills/git/README.md"
        assert readme_path.exists(), f"README.md should exist at {readme_path}"


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--real":
        asyncio.run(run_real_session_test())
    else:
        # Run pytest
        pytest.main([__file__, "-v", "-s"])
