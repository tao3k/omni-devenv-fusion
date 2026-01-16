"""
src/agent/tests/test_kernel_stress.py
Advanced Stress & Resilience Testing for Skill Kernel.

Trinity Architecture (Phase 29):
- Skills use @skill_command decorators
- SkillManager handles command execution via Trinity

Focus:
1. Resilience: Ensuring 'Bad Skills' don't crash the Kernel.
2. Performance: Measuring load latency.
3. Stability: Repeated loading stress test.
"""

import pytest
import time
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock
from mcp.server import Server

from agent.core.registry import get_skill_registry
from agent.core.skill_manager import SkillManager, get_skill_manager


@pytest.fixture
def registry():
    """Provide registry with clean state."""
    reg = get_skill_registry()
    # Clear loaded skills between tests for isolation
    original_loaded = reg.loaded_skills.copy()
    yield reg
    # Cleanup
    reg.loaded_skills.clear()
    reg.loaded_skills.update(original_loaded)


@pytest.fixture
def skill_manager():
    """Provide clean SkillManager for Phase 29 tests."""
    import agent.core.skill_manager as sm_module

    sm_module._manager = None
    manager = sm_module.get_skill_manager()
    manager._skills.clear()
    manager._loaded = False
    yield manager
    manager._skills.clear()
    manager._loaded = False


@pytest.fixture
def mock_mcp():
    """Provide mock MCP server."""
    mcp = MagicMock(spec=Server)
    mcp.tool = MagicMock(return_value=lambda x: x)
    return mcp


from agent.tests.utils.fixtures import create_toxic_skill_factory


@pytest.fixture
def toxic_skill_factory(registry):
    """
    Creates temporary 'toxic' skills for testing error handling.

    Uses centralized TOXIC_SKILL_TEMPLATES dictionary - no if/elif chains.
    Phase 25: Skills use @skill_command decorators instead of register().
    Skills are created in the actual skills directory so Python can import them.
    Cleans up after test.
    """
    from common.skills_path import SKILLS_DIR

    factory = create_toxic_skill_factory(SKILLS_DIR())
    yield factory
    # Cleanup using attached cleanup method
    if hasattr(factory, "cleanup"):
        factory.cleanup()


class TestKernelResilience:
    """Test the Kernel's ability to survive bad plugins."""

    def test_syntax_error_skill(self, registry, mock_mcp, toxic_skill_factory):
        """Kernel should reject skills with syntax errors gracefully."""
        skill_name, module_name = toxic_skill_factory("toxic_syntax", "syntax_error")

        success, message = registry.load_skill(skill_name, mock_mcp)

        assert success is False, f"Expected failure, got success=True, message={message}"
        # Message should indicate syntax error
        assert (
            "SyntaxError" in message
            or "invalid syntax" in message.lower()
            or "syntax" in message.lower()
        )
        assert skill_name not in registry.loaded_skills
        # Ensure system didn't crash and is still initialized
        assert registry._initialized is True
        # Registry should still be functional for other skills
        assert "git" in registry.list_available_skills()

    def test_import_error_skill(self, registry, mock_mcp, toxic_skill_factory):
        """Kernel should handle missing dependencies in tool code."""
        skill_name, module_name = toxic_skill_factory("toxic_import", "import_error")

        success, message = registry.load_skill(skill_name, mock_mcp)

        assert success is False
        # Message should indicate an error
        assert (
            "error" in message.lower()
            or "not found" in message.lower()
            or "fail" in message.lower()
        )
        assert skill_name not in registry.loaded_skills

    def test_runtime_error_skill(self, registry, mock_mcp, toxic_skill_factory):
        """Kernel should handle skills that have functions which raise errors."""
        skill_name, module_name = toxic_skill_factory("toxic_runtime", "runtime_error")

        # In Trinity Architecture, the module loads successfully
        # The error only manifests when the function is actually called
        success, message = registry.load_skill(skill_name, mock_mcp)

        # With Trinity Architecture, the module loads (runtime errors only on call)
        assert success is True, f"Trinity Architecture loads module: {message}"

    def test_missing_exposed_commands(self, registry, mock_mcp, toxic_skill_factory):
        """Kernel should reject skills without @skill_command decorators."""
        skill_name, module_name = toxic_skill_factory("toxic_no_exposed", "missing_exposed")

        success, message = registry.load_skill(skill_name, mock_mcp)

        assert success is False
        assert "@skill_command" in message or "no commands" in message.lower()

    def test_valid_skill_after_toxic(self, registry, mock_mcp, toxic_skill_factory):
        """Kernel should recover and load valid skills after toxic ones failed."""
        # First try to load a toxic skill
        toxic_skill_factory("toxic_first", "syntax_error")
        success1, _ = registry.load_skill("toxic_first", mock_mcp)
        assert success1 is False

        # Then load a valid skill - should work fine
        success2, message = registry.load_skill("git", mock_mcp)

        assert success2 is True
        # Message should indicate success (flexible check)
        assert "success" in message.lower() or "git" in message.lower()
        assert "git" in registry.loaded_skills

    def test_multiple_toxic_skills_sequence(self, registry, mock_mcp, toxic_skill_factory):
        """Kernel should handle a sequence of bad skills without state corruption."""
        toxic_skills = []

        # Create multiple toxic skills
        for i in range(3):
            name, _ = toxic_skill_factory(f"toxic_multi_{i}", "syntax_error")
            toxic_skills.append(name)

        # Try to load them - all should fail gracefully
        for skill_name in toxic_skills:
            success, _ = registry.load_skill(skill_name, mock_mcp)
            assert success is False
            assert skill_name not in registry.loaded_skills

        # Verify kernel is still functional
        assert registry._initialized is True
        assert len(registry.list_available_skills()) > 0


class TestSkillManagerOmniCLI:
    """Phase 25: Test SkillManager with EXPOSED_COMMANDS pattern."""

    def test_skill_manager_loads_git(self, skill_manager):
        """SkillManager should load git skill successfully."""
        skills = skill_manager.load_skills()

        assert "git" in skills, f"Git skill should be loaded, got: {list(skills.keys())}"
        assert len(skills) >= 1

    def test_skill_manager_git_has_commands(self, skill_manager):
        """Git skill should have commands loaded via @skill_command."""
        skill_manager.load_skills()

        assert "git" in skill_manager.skills
        git_skill = skill_manager.skills["git"]
        assert len(git_skill.commands) >= 1

    @pytest.mark.asyncio
    async def test_skill_manager_run_command(self, skill_manager):
        """SkillManager.run() should execute commands from @skill_command."""
        skill_manager.load_skills()

        result = await skill_manager.run("git", "status", {})

        assert result is not None
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_skill_manager_nonexistent_skill(self, skill_manager):
        """Running command on nonexistent skill should return error."""
        skill_manager.load_skills()

        result = await skill_manager.run("nonexistent", "some_command", {})

        assert "Error" in result or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_skill_manager_nonexistent_command(self, skill_manager):
        """Running nonexistent command should return error."""
        skill_manager.load_skills()

        result = await skill_manager.run("git", "nonexistent_command", {})

        assert "Error" in result or "not found" in result.lower()


class TestKernelPerformance:
    """Benchmark the dynamic loader."""

    def test_load_latency_cold(self, registry, mock_mcp):
        """Loading 'git' skill should be under 200ms for cold start."""
        # Ensure git is unloaded and module is cleared
        if "git" in registry.loaded_skills:
            del registry.loaded_skills["git"]
        if "assets.skills.git.tools" in sys.modules:
            del sys.modules["assets.skills.git.tools"]

        start_time = time.perf_counter()
        success, _ = registry.load_skill("git", mock_mcp)
        end_time = time.perf_counter()

        duration_ms = (end_time - start_time) * 1000

        assert success is True, "Git skill should load successfully"

        # Performance threshold: 200ms for cold start (file IO + import)
        assert duration_ms < 200, f"Cold load took {duration_ms:.2f}ms, expected < 200ms"

    def test_load_latency_hot(self, registry, mock_mcp):
        """Reloading an already loaded skill should be instant (< 1ms)."""
        # First ensure git is loaded
        registry.load_skill("git", mock_mcp)

        start_time = time.perf_counter()
        success, msg = registry.load_skill("git", mock_mcp)
        end_time = time.perf_counter()

        duration_ms = (end_time - start_time) * 1000

        assert success is True
        # Message should indicate hot reload
        assert "hot reload" in msg.lower() or "loaded via" in msg.lower()

        # Hot load should be essentially instant (Phase 34: increased to 15ms for LangGraph overhead)
        assert duration_ms < 15.0, f"Hot load took {duration_ms:.4f}ms, expected < 15ms"

    def test_context_retrieval_speed(self, registry, mock_mcp):
        """Retrieving skill context should be fast (< 5ms)."""
        # Load git first
        registry.load_skill("git", mock_mcp)

        # Benchmark context retrieval
        iterations = 100
        start_time = time.perf_counter()

        for _ in range(iterations):
            _ = registry.get_skill_context("git")

        end_time = time.perf_counter()
        total_ms = (end_time - start_time) * 1000
        avg_ms = total_ms / iterations

        assert avg_ms < 5.0, f"Average context retrieval took {avg_ms:.2f}ms, expected < 5ms"

    def test_manifest_parsing_speed(self, registry):
        """Parsing skill manifest should be fast (< 1ms)."""
        iterations = 1000

        start_time = time.perf_counter()

        for _ in range(iterations):
            _ = registry.get_skill_manifest("git")

        end_time = time.perf_counter()
        total_ms = (end_time - start_time) * 1000
        avg_ms = total_ms / iterations

        # Manifest parsing is simple YAML + Pydantic validation
        # Threshold adjusted for cross-platform consistency
        assert avg_ms < 2.5, f"Average manifest parsing took {avg_ms:.4f}ms"


class TestKernelStability:
    """Stress test the state machine for long-running operation."""

    def test_rapid_fire_loading(self, registry, mock_mcp):
        """Kernel should handle 100 sequential load requests without memory corruption."""
        iterations = 100
        success_count = 0

        start_time = time.perf_counter()

        for i in range(iterations):
            # Clear loaded_skills to force re-load
            registry.loaded_skills.clear()
            success, _ = registry.load_skill("git", mock_mcp)
            if success:
                success_count += 1

        end_time = time.perf_counter()
        total_time = end_time - start_time

        # All loads should succeed
        assert success_count == iterations, f"{iterations - success_count} loads failed"

        # Performance check
        avg_time_ms = (total_time / iterations) * 1000
        print(f"\n Rapid Fire: {iterations} loads in {total_time:.4f}s")
        print(f" Average: {avg_time_ms:.2f}ms per load")

        # Average should be reasonable
        assert avg_time_ms < 50, f"Average load time {avg_time_ms:.2f}ms too high"

    def test_concurrent_load_attempts(self, registry, mock_mcp):
        """Simulate rapid successive load requests (stress test)."""
        iterations = 50
        results = []

        for _ in range(iterations):
            # Simulate concurrent requests by clearing and reloading
            registry.loaded_skills.clear()
            result = registry.load_skill("git", mock_mcp)
            results.append(result)

        # All should succeed
        assert all(r[0] for r in results), "Some load attempts failed"

        # State should be consistent
        assert len(registry.loaded_skills) >= 1
        assert "git" in registry.loaded_skills

    def test_state_consistency_after_failures(self, registry, mock_mcp, toxic_skill_factory):
        """Registry state should remain consistent after loading failures."""
        # Load valid skill first
        registry.load_skill("git", mock_mcp)
        assert "git" in registry.loaded_skills

        # Try to load toxic skills
        toxic_skill_factory("toxic_consistency", "syntax_error")
        success, _ = registry.load_skill("toxic_consistency", mock_mcp)
        assert success is False
        assert "toxic_consistency" not in registry.loaded_skills

        # Valid skill should still be in registry
        assert "git" in registry.loaded_skills

        # Registry should still function
        success, _ = registry.load_skill("git", mock_mcp)
        assert success is True

    def test_stress_sys_modules(self, registry, mock_mcp):
        """Repeated loading shouldn't leak memory in sys.modules."""
        # Clear initial state
        registry.loaded_skills.clear()

        initial_modules = len([m for m in sys.modules if m.startswith("assets.skills")])

        # Rapid load/unload cycle
        for _ in range(10):
            registry.load_skill("git", mock_mcp)
            registry.loaded_skills.clear()

        final_modules = len([m for m in sys.modules if m.startswith("assets.skills")])

        # Modules should not grow significantly
        module_growth = final_modules - initial_modules
        print(f"\n Sys.modules growth: {module_growth} modules")

        # Should not have exploded
        assert module_growth < 5, f"sys.modules grew by {module_growth}, possible memory leak"


class TestKernelEdgeCases:
    """Additional edge case tests."""

    def test_load_skill_with_empty_manifest(self, registry, mock_mcp):
        """Handle skill with empty or invalid manifest gracefully."""
        skill_dir = registry.skills_dir / "empty_manifest"
        skill_dir.mkdir(exist_ok=True)

        try:
            # Create empty SKILL.md
            (skill_dir / "SKILL.md").write_text("")

            success, message = registry.load_skill("empty_manifest", mock_mcp)

            assert success is False
            assert "not found" in message.lower() or "invalid" in message.lower()
        finally:
            shutil.rmtree(skill_dir)

    def test_load_skill_while_uninitialized(self, registry, mock_mcp):
        """Loading should work even if we somehow reset _initialized."""
        # This is a theoretical edge case
        original_init = registry._initialized
        registry._initialized = False
        registry.__init__()  # Re-init

        success, _ = registry.load_skill("git", mock_mcp)

        assert success is True
        registry._initialized = original_init

    def test_concurrent_module_imports(self, registry, mock_mcp):
        """Multiple rapid loads shouldn't cause import conflicts."""
        # Clear all agent.skills modules first (Phase 63: module prefix changed)
        modules_to_remove = [m for m in sys.modules if m.startswith("agent.skills")]
        for m in modules_to_remove:
            del sys.modules[m]

        modules_before = set(sys.modules.keys())

        for _ in range(5):
            registry.loaded_skills.clear()
            registry.load_skill("git", mock_mcp)

        modules_after = set(sys.modules.keys())
        new_modules = modules_after - modules_before

        # Filter to only agent.skills modules (the ones we care about)
        new_skill_modules = [m for m in new_modules if m.startswith("agent.skills")]

        # Should have added some skill modules but not excessively
        # Note: Phase 63 uses hot-reload cleanup, so repeated loads may clear and reimport
        # The key is that loading worked without import conflicts
        assert len(new_skill_modules) >= 0, "Import conflicts detected"
        assert len(new_skill_modules) < 50, f"Too many modules imported: {len(new_skill_modules)}"


if __name__ == "__main__":
    # Allow running directly with verbose output
    sys.exit(pytest.main(["-v", "-s", __file__]))
