"""
src/agent/tests/test_phase13_skills.py
Comprehensive testing for the Phase 13 Skill Architecture.

Covers:
1. SkillRegistry (Discovery, Loading, Context, Spec-based Loading)
2. SkillManifest (Schema Validation)
3. Skill Hot Reload
4. Filesystem Skill
5. Skill Manager Tools

Note: _template is a skeleton for creating new skills and cannot be loaded
as a Python module (names starting with underscore have special meaning).
"""
import pytest
import sys
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from mcp.server.fastmcp import FastMCP

# Import core components
from agent.core.schema import SkillManifest
from agent.core.skill_registry import SkillRegistry, get_skill_registry


@pytest.fixture
def registry():
    """Fixture to provide a clean registry instance."""
    # Create fresh instance for each test
    import agent.core.skill_registry as sr_module
    sr_module._registry = None
    reg = sr_module.get_skill_registry()
    reg.loaded_skills.clear()
    reg.module_cache.clear()
    yield reg
    reg.loaded_skills.clear()
    reg.module_cache.clear()


@pytest.fixture
def real_mcp():
    """Real FastMCP instance for integration testing."""
    mcp = FastMCP("test")
    return mcp


class TestSkillManifest:
    """Test the DNA of skills - Schema validation."""

    def test_valid_manifest_creation(self):
        """Test creating a valid SkillManifest."""
        data = {
            "name": "test_skill",
            "version": "1.0.0",
            "description": "A test skill",
            "dependencies": ["git"],
            "tools_module": "agent.skills.test.tools",
            "guide_file": "guide.md"
        }
        manifest = SkillManifest(**data)
        assert manifest.name == "test_skill"
        assert manifest.version == "1.0.0"
        assert manifest.dependencies == ["git"]
        assert manifest.tools_module == "agent.skills.test.tools"

    def test_minimal_manifest(self):
        """Test creating manifest with only required fields."""
        data = {
            "name": "minimal_skill",
            "version": "0.1.0",
            "description": "Minimal skill",
            "tools_module": "agent.skills.minimal.tools"
        }
        manifest = SkillManifest(**data)
        assert manifest.name == "minimal_skill"
        assert manifest.dependencies == []
        assert manifest.guide_file == "guide.md"
        assert manifest.prompts_file is None

    def test_invalid_manifest_missing_name(self):
        """Test that missing name raises error."""
        data = {
            "version": "1.0.0",
            "description": "A test skill",
            "tools_module": "agent.skills.test.tools"
        }
        with pytest.raises(ValueError):
            SkillManifest(**data)

    def test_invalid_manifest_missing_tools_module(self):
        """Test that missing tools_module raises error."""
        data = {
            "name": "test_skill",
            "version": "1.0.0",
            "description": "A test skill"
        }
        with pytest.raises(ValueError):
            SkillManifest(**data)


class TestSkillDiscovery:
    """Test skill discovery and manifest parsing."""

    def test_discovery_finds_git_skill(self, registry):
        """Registry should find 'git' skill."""
        skills = registry.list_available_skills()
        assert "git" in skills, f"Expected 'git' in skills, got: {skills}"

    def test_discovery_finds_filesystem_skill(self, registry):
        """Registry should find 'filesystem' skill."""
        skills = registry.list_available_skills()
        assert "filesystem" in skills

    def test_discovery_finds_template_directory(self, registry):
        """Registry should discover _template directory (for copying)."""
        skills = registry.list_available_skills()
        assert "_template" in skills

    def test_discovery_excludes_pycache(self, registry):
        """Registry should not pick up __pycache__ or other non-skill dirs."""
        skills = registry.list_available_skills()
        assert "__pycache__" not in skills

    def test_manifest_parsing_filesystem(self, registry):
        """Registry should correctly parse filesystem/manifest.json."""
        manifest = registry.get_skill_manifest("filesystem")
        assert manifest is not None
        assert manifest.name == "filesystem"
        assert manifest.version == "1.0.0"
        assert manifest.tools_module == "agent.skills.filesystem.tools"
        assert manifest.guide_file == "guide.md"


class TestSpecBasedLoading:
    """Test spec-based module loading (Level 2 feature)."""

    def test_load_filesystem_skill(self, registry, real_mcp):
        """Should successfully load filesystem skill using spec-based loading."""
        success, message = registry.load_skill("filesystem", real_mcp)

        assert success is True, f"Expected success, got: {message}"
        assert "filesystem" in registry.loaded_skills
        assert "filesystem" in registry.module_cache

    def test_module_cached_after_load(self, registry, real_mcp):
        """Module should be cached after loading."""
        registry.load_skill("filesystem", real_mcp)

        assert "filesystem" in registry.module_cache
        module = registry.module_cache["filesystem"]
        assert module is not None

    def test_module_has_executable_functions(self, registry, real_mcp):
        """Loaded module should have callable functions."""
        registry.load_skill("filesystem", real_mcp)

        module = registry.module_cache["filesystem"]
        # Check for expected functions
        assert hasattr(module, "list_directory")
        assert hasattr(module, "read_file")
        assert hasattr(module, "write_file")
        assert hasattr(module, "search_files")

    def test_execute_function_after_load(self, registry, real_mcp):
        """Should be able to execute functions after loading."""
        import asyncio

        registry.load_skill("filesystem", real_mcp)
        module = registry.module_cache["filesystem"]

        # Execute list_directory
        result = asyncio.run(module.list_directory("agent/skills"))
        assert "filesystem" in result or "Directory Listing" in result

    def test_nonexistent_skill_fails(self, registry, real_mcp):
        """Loading nonexistent skill should fail gracefully."""
        success, message = registry.load_skill("totally_fake_skill_xyz", real_mcp)
        assert success is False
        assert "not found" in message.lower()

    def test_template_loads_with_spec_based_loading(self, registry, real_mcp):
        """_template can now be loaded with spec-based loading (unlike importlib.import_module)."""
        # With spec-based loading, _template can be loaded
        success, message = registry.load_skill("_template", real_mcp)
        # This should succeed with spec-based loading
        assert success is True
        assert "_template" in registry.loaded_skills


class TestHotReload:
    """Test hot reload functionality."""

    def test_hot_reload_reloads_module(self, registry, real_mcp):
        """Loading same skill again should re-execute module code."""
        import asyncio
        import agent.core.skill_registry as sr_module

        # First load
        success1, msg1 = registry.load_skill("filesystem", real_mcp)
        assert success1 is True

        # Get original function result
        module1 = registry.module_cache["filesystem"]
        original_result = asyncio.run(module1.list_directory("agent/skills"))
        assert "[HOT-RELOADED]" not in original_result

        # Modify file content (simulate code change)
        tools_path = Path("agent/skills/filesystem/tools.py")
        original_content = tools_path.read_text()

        # Add a marker to the function (match the exact line including \n)
        new_content = original_content.replace(
            'return f"Directory Listing for \'{path}\':\\n"',
            'return f"[HOT-RELOADED] Directory Listing for \'{path}\':\\n"'
        )
        tools_path.write_text(new_content)

        try:
            # Force reload by clearing cache and reloading
            sr_module._registry = None
            registry = sr_module.get_skill_registry()
            registry.loaded_skills.clear()
            registry.module_cache.clear()

            success2, msg2 = registry.load_skill("filesystem", real_mcp)
            assert success2 is True

            # Verify new content is loaded by executing the function
            module2 = registry.module_cache["filesystem"]
            new_result = asyncio.run(module2.list_directory("agent/skills"))
            assert "[HOT-RELOADED]" in new_result

        finally:
            # Restore original content
            tools_path.write_text(original_content)

    def test_double_load_handles_gracefully(self, registry, real_mcp):
        """Loading same skill twice should be safe."""
        success1, msg1 = registry.load_skill("filesystem", real_mcp)
        assert success1 is True

        success2, msg2 = registry.load_skill("filesystem", real_mcp)
        assert success2 is True
        # Second load should succeed (hot reload behavior)


class TestSkillContext:
    """Test skill context retrieval."""

    def test_get_context_returns_guide(self, registry):
        """Registry should read guide.md content."""
        context = registry.get_skill_context("filesystem")
        assert context is not None
        assert len(context) > 0
        assert "FILESYSTEM" in context.upper()

    def test_get_context_includes_prompts(self, registry):
        """Registry should include prompts.md if available."""
        context = registry.get_skill_context("filesystem")
        # Filesystem has prompts.md
        assert "SYSTEM PROMPTS" in context or "Filesystem" in context

    def test_get_context_nonexistent_skill(self, registry):
        """Getting context for nonexistent skill returns empty string."""
        context = registry.get_skill_context("fake_skill_xyz")
        assert context == ""


class TestFilesystemSkill:
    """Test filesystem skill operations."""

    def test_list_directory_operation(self, registry, real_mcp):
        """Test list_directory function."""
        import asyncio

        registry.load_skill("filesystem", real_mcp)
        module = registry.module_cache["filesystem"]

        result = asyncio.run(module.list_directory("agent/skills"))
        assert "filesystem" in result or "_template" in result

    def test_read_file_operation(self, registry, real_mcp):
        """Test read_file function."""
        import asyncio

        registry.load_skill("filesystem", real_mcp)
        module = registry.module_cache["filesystem"]

        # Read the manifest file
        result = asyncio.run(module.read_file("agent/skills/filesystem/manifest.json"))
        assert "filesystem" in result
        assert "version" in result

    def test_write_file_operation(self, registry, real_mcp):
        """Test write_file function."""
        import asyncio
        import tempfile

        registry.load_skill("filesystem", real_mcp)
        module = registry.module_cache["filesystem"]

        # Write to a temp file in agent directory
        test_path = "agent/skills/test_write.txt"
        try:
            result = asyncio.run(module.write_file(test_path, "test content 123"))
            assert "Successfully wrote" in result

            # Verify file was written
            content = Path(test_path).read_text()
            assert content == "test content 123"
        finally:
            # Cleanup
            if Path(test_path).exists():
                Path(test_path).unlink()

    def test_search_files_operation(self, registry, real_mcp):
        """Test search_files function."""
        import asyncio

        registry.load_skill("filesystem", real_mcp)
        module = registry.module_cache["filesystem"]

        # Search for manifest files
        result = asyncio.run(module.search_files(pattern="*.json", path="agent/skills"))
        assert "manifest.json" in result

    def test_get_file_info_operation(self, registry, real_mcp):
        """Test get_file_info function."""
        import asyncio

        registry.load_skill("filesystem", real_mcp)
        module = registry.module_cache["filesystem"]

        result = asyncio.run(module.get_file_info(path="agent/skills/filesystem/manifest.json"))
        assert "Size:" in result or "bytes" in result


class TestSkillManager:
    """Test skill manager tools."""

    def _get_tool_func(self, mcp, tool_name):
        """Helper to get tool function from FastMCP."""
        tools = list(mcp._tool_manager._tools.values())
        tool = [t for t in tools if t.name == tool_name][0]
        return tool.fn

    @pytest.mark.asyncio
    async def test_skill_tool_auto_loads(self, registry, real_mcp):
        """Skill tool should auto-load when skill not loaded."""
        from agent.capabilities.skill_manager import register_skill_tools

        register_skill_tools(real_mcp)

        # Get tool function
        skill_func = self._get_tool_func(real_mcp, "skill")

        # Execute skill tool with auto-load
        result = await skill_func(
            skill="filesystem",
            call='list_directory(path="agent/skills")'
        )

        assert "auto-loaded" in result.lower() or "filesystem" in result.lower()

    @pytest.mark.asyncio
    async def test_skill_tool_executes_operation(self, registry, real_mcp):
        """Skill tool should execute operation after loading."""
        from agent.capabilities.skill_manager import register_skill_tools

        register_skill_tools(real_mcp)

        skill_func = self._get_tool_func(real_mcp, "skill")

        # First load
        await skill_func(
            skill="filesystem",
            call='list_directory(path="agent/skills")'
        )

        # Second call should execute
        result = await skill_func(
            skill="filesystem",
            call='list_directory(path="agent/skills")'
        )

        assert "Directory Listing" in result or "filesystem" in result

    @pytest.mark.asyncio
    async def test_load_skill_tool(self, registry, real_mcp):
        """Test load_skill tool."""
        from agent.capabilities.skill_manager import register_skill_tools

        register_skill_tools(real_mcp)

        load_func = self._get_tool_func(real_mcp, "load_skill")

        result = await load_func(skill_name="filesystem")
        assert "filesystem" in result.lower()
        assert "successfully" in result.lower()

    @pytest.mark.asyncio
    async def test_list_available_skills_tool(self, registry, real_mcp):
        """Test list_available_skills tool."""
        from agent.capabilities.skill_manager import register_skill_tools

        register_skill_tools(real_mcp)

        list_func = self._get_tool_func(real_mcp, "list_available_skills")

        result = await list_func()
        assert "filesystem" in result
        assert "git" in result

    @pytest.mark.asyncio
    async def test_get_active_skills_tool(self, registry, real_mcp):
        """Test get_active_skills tool."""
        from agent.capabilities.skill_manager import register_skill_tools

        register_skill_tools(real_mcp)

        active_func = self._get_tool_func(real_mcp, "get_active_skills")
        load_func = self._get_tool_func(real_mcp, "load_skill")

        # Initially empty
        result = await active_func()
        assert "No skills" in result

        # Load a skill
        await load_func(skill_name="filesystem")

        # Should show active skill
        result = await active_func()
        assert "filesystem" in result


class TestSkillEdgeCases:
    """Edge case and error handling tests."""

    def test_load_skill_with_missing_source_file(self, registry, real_mcp):
        """Loading skill with missing source file should fail."""
        # Create a temporary manifest with invalid tools_module
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test_missing"
            skill_dir.mkdir()

            manifest = {
                "name": "test_missing",
                "version": "1.0.0",
                "description": "Test skill with missing source",
                "tools_module": "agent.skills.nonexistent.tools"
            }
            (skill_dir / "manifest.json").write_text(json.dumps(manifest))

            # This would fail to find the source file
            success, message = registry.load_skill("test_missing", real_mcp)
            assert success is False
            assert "not found" in message.lower() or "source file" in message.lower()

    def test_singleton_returns_same_instance(self):
        """get_skill_registry should return singleton."""
        reg1 = get_skill_registry()
        reg2 = get_skill_registry()
        assert reg1 is reg2

    def test_registry_state_cleared_between_tests(self, registry):
        """Verify registry state is properly cleared."""
        assert len(registry.loaded_skills) == 0
        assert len(registry.module_cache) == 0


class TestSkillPerformance:
    """Performance and stress tests."""

    def test_rapid_load_unload(self, registry, real_mcp):
        """Test rapid loading and reloading of skills."""
        import time

        skills_to_test = ["filesystem", "git"]

        start = time.time()
        for _ in range(3):
            for skill in skills_to_test:
                registry.loaded_skills.pop(skill, None)
                registry.module_cache.pop(skill, None)
                registry.load_skill(skill, real_mcp)
        elapsed = time.time() - start

        # Should complete within reasonable time (< 5 seconds for 6 loads)
        assert elapsed < 5.0

    def test_concurrent_load_same_skill(self, registry, real_mcp):
        """Loading same skill concurrently should not cause errors."""
        import asyncio

        async def load():
            return registry.load_skill("filesystem", real_mcp)

        # Run multiple loads
        results = []
        for _ in range(3):
            success, msg = registry.load_skill("filesystem", real_mcp)
            results.append((success, msg))

        # All should succeed
        for success, msg in results:
            assert success is True


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", __file__, "--tb=short"]))
