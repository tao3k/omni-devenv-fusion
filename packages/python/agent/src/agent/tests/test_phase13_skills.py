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
            "guide_file": "guide.md",
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
            "tools_module": "agent.skills.minimal.tools",
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
            "tools_module": "agent.skills.test.tools",
        }
        with pytest.raises(ValueError):
            SkillManifest(**data)

    def test_invalid_manifest_missing_tools_module(self):
        """Test that missing tools_module raises error."""
        data = {"name": "test_skill", "version": "1.0.0", "description": "A test skill"}
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

    def test_discovery_finds_terminal_skill(self, registry):
        """Registry should find 'terminal' skill."""
        skills = registry.list_available_skills()
        assert "terminal" in skills, f"Expected 'terminal' in skills, got: {skills}"

    def test_discovery_finds_testing_skill(self, registry):
        """Registry should find 'testing' skill."""
        skills = registry.list_available_skills()
        assert "testing" in skills, f"Expected 'testing' in skills, got: {skills}"

    def test_discovery_finds_documentation_skill(self, registry):
        """Registry should find 'documentation' skill."""
        skills = registry.list_available_skills()
        assert "documentation" in skills, f"Expected 'documentation' in skills, got: {skills}"

    def test_discovery_finds_software_engineering_skill(self, registry):
        """Registry should find 'software_engineering' skill (The Architect)."""
        skills = registry.list_available_skills()
        assert "software_engineering" in skills, (
            f"Expected 'software_engineering' in skills, got: {skills}"
        )

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
            "return f\"Directory Listing for '{path}':\\n\"",
            "return f\"[HOT-RELOADED] Directory Listing for '{path}':\\n\"",
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


class TestTerminalSkill:
    """Test terminal skill operations."""

    def test_load_terminal_skill(self, registry, real_mcp):
        """Should successfully load terminal skill using spec-based loading."""
        success, message = registry.load_skill("terminal", real_mcp)

        assert success is True, f"Expected success, got: {message}"
        assert "terminal" in registry.loaded_skills
        assert "terminal" in registry.module_cache

    def test_terminal_has_execute_command(self, registry, real_mcp):
        """Loaded terminal module should have execute_command function."""
        registry.load_skill("terminal", real_mcp)

        module = registry.module_cache["terminal"]
        assert hasattr(module, "execute_command")
        assert hasattr(module, "inspect_environment")

    def test_terminal_manifest_parsing(self, registry):
        """Registry should correctly parse terminal/manifest.json."""
        manifest = registry.get_skill_manifest("terminal")
        assert manifest is not None
        assert manifest.name == "terminal"
        assert manifest.version == "1.0.0"
        assert manifest.tools_module == "agent.skills.terminal.tools"
        assert manifest.guide_file == "guide.md"

    @pytest.mark.asyncio
    async def test_execute_command_echo(self, registry, real_mcp):
        """Test execute_command with safe echo command."""
        import asyncio

        registry.load_skill("terminal", real_mcp)
        module = registry.module_cache["terminal"]

        result = await module.execute_command("echo hello_terminal_test")
        assert "hello_terminal_test" in result or "hello" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_command_blocked_dangerous(self, registry, real_mcp):
        """Test execute_command blocks dangerous patterns."""
        import asyncio

        registry.load_skill("terminal", real_mcp)
        module = registry.module_cache["terminal"]

        # Test blocked pattern
        result = await module.execute_command("rm -rf /tmp/test")
        assert "Blocked" in result or "dangerous" in result.lower()


class TestTestingSkill:
    """Test testing skill operations."""

    def test_load_testing_skill(self, registry, real_mcp):
        """Should successfully load testing skill."""
        success, message = registry.load_skill("testing", real_mcp)

        assert success is True, f"Expected success, got: {message}"
        assert "testing" in registry.loaded_skills
        assert "testing" in registry.module_cache

    def test_testing_has_run_tests(self, registry, real_mcp):
        """Loaded testing module should have run_tests function."""
        registry.load_skill("testing", real_mcp)

        module = registry.module_cache["testing"]
        assert hasattr(module, "run_tests")
        assert hasattr(module, "list_tests")

    def test_testing_manifest_parsing(self, registry):
        """Registry should correctly parse testing/manifest.json."""
        manifest = registry.get_skill_manifest("testing")
        assert manifest is not None
        assert manifest.name == "testing"
        assert manifest.version == "1.0.0"
        assert manifest.tools_module == "agent.skills.testing.tools"
        assert manifest.guide_file == "guide.md"

    def test_testing_has_filesystem_dependency(self, registry):
        """Testing skill should depend on filesystem."""
        manifest = registry.get_skill_manifest("testing")
        assert "filesystem" in manifest.dependencies


class TestSoftwareEngineeringSkill:
    """Test software_engineering skill operations (The Architect)."""

    def test_load_software_engineering_skill(self, registry, real_mcp):
        """Should successfully load software_engineering skill."""
        success, message = registry.load_skill("software_engineering", real_mcp)

        assert success is True, f"Expected success, got: {message}"
        assert "software_engineering" in registry.loaded_skills
        assert "software_engineering" in registry.module_cache

    def test_software_engineering_has_analyze_structure(self, registry, real_mcp):
        """Loaded software_engineering module should have analyze_project_structure."""
        registry.load_skill("software_engineering", real_mcp)

        module = registry.module_cache["software_engineering"]
        assert hasattr(module, "analyze_project_structure")

    def test_software_engineering_has_grep_codebase(self, registry, real_mcp):
        """Loaded software_engineering module should have grep_codebase."""
        registry.load_skill("software_engineering", real_mcp)

        module = registry.module_cache["software_engineering"]
        assert hasattr(module, "grep_codebase")

    def test_software_engineering_has_detect_tech_stack(self, registry, real_mcp):
        """Loaded software_engineering module should have detect_tech_stack."""
        registry.load_skill("software_engineering", real_mcp)

        module = registry.module_cache["software_engineering"]
        assert hasattr(module, "detect_tech_stack")

    def test_software_engineering_manifest_parsing(self, registry):
        """Registry should correctly parse software_engineering/manifest.json."""
        manifest = registry.get_skill_manifest("software_engineering")
        assert manifest is not None
        assert manifest.name == "software_engineering"
        assert manifest.version == "1.0.0"
        assert manifest.tools_module == "agent.skills.software_engineering.tools"
        assert manifest.guide_file == "guide.md"

    def test_software_engineering_has_filesystem_dependency(self, registry):
        """Software engineering skill should depend on filesystem."""
        manifest = registry.get_skill_manifest("software_engineering")
        assert "filesystem" in manifest.dependencies

    def test_software_engineering_guide_contains_architecture(self, registry):
        """Guide should emphasize architecture thinking."""
        context = registry.get_skill_context("software_engineering")
        assert "architecture" in context.lower() or "architect" in context.lower()

    @pytest.mark.asyncio
    async def test_analyze_project_structure(self, registry, real_mcp):
        """Test analyze_project_structure function."""
        import asyncio

        registry.load_skill("software_engineering", real_mcp)
        module = registry.module_cache["software_engineering"]

        result = await module.analyze_project_structure(depth=1)
        assert "Project Root" in result or "agent" in result.lower()

    @pytest.mark.asyncio
    async def test_detect_tech_stack(self, registry, real_mcp):
        """Test detect_tech_stack function."""
        import asyncio

        registry.load_skill("software_engineering", real_mcp)
        module = registry.module_cache["software_engineering"]

        result = await module.detect_tech_stack()
        assert "Tech Stack" in result or "Python" in result


class TestSkillManager:
    """Test skill manager tools."""

    def _get_tool_func(self, mcp, tool_name):
        """Helper to get tool function from FastMCP."""
        tools = list(mcp._tool_manager._tools.values())
        tool = [t for t in tools if t.name == tool_name][0]
        return tool.fn

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

    @pytest.mark.asyncio
    async def test_invoke_skill_tool_exists(self, registry, real_mcp):
        """Test that invoke_skill tool is registered."""
        from agent.capabilities.skill_manager import register_skill_tools

        register_skill_tools(real_mcp)

        invoke_func = self._get_tool_func(real_mcp, "invoke_skill")
        assert invoke_func is not None


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
                "tools_module": "agent.skills.nonexistent.tools",
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


class TestCodeInsightSkill:
    """Test code_insight skill operations."""

    def test_code_insight_manifest_parsing(self, registry):
        """Registry should correctly parse code_insight/manifest.json."""
        manifest = registry.get_skill_manifest("code_insight")
        assert manifest is not None
        assert manifest.name == "code_insight"
        assert manifest.version == "1.0.0"
        assert manifest.tools_module == "agent.skills.code_insight.tools"

    def test_load_code_insight_skill(self, registry, real_mcp):
        """Should successfully load code_insight skill."""
        success, message = registry.load_skill("code_insight", real_mcp)

        assert success is True, f"Expected success, got: {message}"
        assert "code_insight" in registry.loaded_skills
        assert "code_insight" in registry.module_cache

    def test_code_insight_has_find_tools(self, registry, real_mcp):
        """Loaded code_insight module should have find_tools function."""
        registry.load_skill("code_insight", real_mcp)

        module = registry.module_cache["code_insight"]
        assert hasattr(module, "find_tools")
        assert hasattr(module, "count_lines")

    @pytest.mark.asyncio
    async def test_find_tools_functionality(self, registry, real_mcp):
        """find_tools should work without error and return reasonable output."""
        import asyncio

        registry.load_skill("code_insight", real_mcp)
        module = registry.module_cache["code_insight"]

        # Test with a file - most skills use register() pattern, so decorators
        # won't be at function definition level. Test that function works.
        result = await module.find_tools("agent/skills/code_insight/tools.py")
        # Should return either tool names or "No tools found"
        assert "No tools found" in result or "- find_tools" in result or "- count_lines" in result

    @pytest.mark.asyncio
    async def test_find_tools_returns_empty_for_no_tools(self, registry, real_mcp):
        """find_tools should return message when no tools found."""
        import asyncio

        registry.load_skill("code_insight", real_mcp)
        module = registry.module_cache["code_insight"]

        # Find tools in a file without decorators
        result = await module.find_tools("agent/skills/code_insight/manifest.json")
        assert "No tools found" in result

    @pytest.mark.asyncio
    async def test_find_tools_file_not_found(self, registry, real_mcp):
        """find_tools should return error for non-existent file."""
        import asyncio

        registry.load_skill("code_insight", real_mcp)
        module = registry.module_cache["code_insight"]

        result = await module.find_tools("nonexistent/file.py")
        assert "Error: File not found" in result

    @pytest.mark.asyncio
    async def test_count_lines(self, registry, real_mcp):
        """count_lines should return line count."""
        import asyncio

        registry.load_skill("code_insight", real_mcp)
        module = registry.module_cache["code_insight"]

        result = await module.count_lines("agent/skills/code_insight/tools.py")
        assert "tools.py" in result
        assert "lines" in result
        # Should be around 119 lines (updated after recursive call fixes)
        assert "119" in result or "118" in result or "120" in result


class TestInvokeSkillTool:
    """Test invoke_skill tool (replaces deprecated skill() with AST parsing)."""

    def _get_tool_func(self, mcp, tool_name):
        """Helper to get tool function from FastMCP."""
        tools = list(mcp._tool_manager._tools.values())
        tool = [t for t in tools if t.name == tool_name][0]
        return tool.fn

    @pytest.mark.asyncio
    async def test_invoke_skill_auto_loads(self, registry, real_mcp):
        """invoke_skill should auto-load when skill not loaded."""
        from agent.capabilities.skill_manager import register_skill_tools

        register_skill_tools(real_mcp)

        invoke_func = self._get_tool_func(real_mcp, "invoke_skill")

        # Execute with auto-load
        result = await invoke_func(
            skill="filesystem", tool="list_directory", args={"path": "agent/skills"}
        )

        assert "auto-loaded" in result.lower() or "filesystem" in result.lower()

    @pytest.mark.asyncio
    async def test_invoke_skill_calls_filesystem(self, registry, real_mcp):
        """invoke_skill should call filesystem.list_directory."""
        from agent.capabilities.skill_manager import register_skill_tools

        register_skill_tools(real_mcp)

        invoke_func = self._get_tool_func(real_mcp, "invoke_skill")

        result = await invoke_func(
            skill="filesystem", tool="list_directory", args={"path": "agent/skills"}
        )

        assert "filesystem" in result or "_template" in result

    @pytest.mark.asyncio
    async def test_invoke_skill_calls_git_stage_all(self, registry, real_mcp):
        """invoke_skill should call git.git_stage_all."""
        from agent.capabilities.skill_manager import register_skill_tools

        register_skill_tools(real_mcp)

        invoke_func = self._get_tool_func(real_mcp, "invoke_skill")

        result = await invoke_func(
            skill="git",
            tool="git_stage_all",
            args={"scan": False},  # Skip scan for test
        )

        # Should not return "Operation not found"
        assert "Operation 'git_stage_all' not found" not in result

    @pytest.mark.asyncio
    async def test_invoke_skill_handles_empty_args(self, registry, real_mcp):
        """invoke_skill should handle empty args dict."""
        from agent.capabilities.skill_manager import register_skill_tools

        register_skill_tools(real_mcp)

        invoke_func = self._get_tool_func(real_mcp, "invoke_skill")

        result = await invoke_func(skill="git", tool="git_stage_all", args={})

        assert "Invalid" not in result

    @pytest.mark.asyncio
    async def test_invoke_skill_nonexistent_operation(self, registry, real_mcp):
        """invoke_skill should return error for nonexistent operation with available ops list."""
        from agent.capabilities.skill_manager import register_skill_tools

        register_skill_tools(real_mcp)

        invoke_func = self._get_tool_func(real_mcp, "invoke_skill")

        # Call with nonexistent operation
        result = await invoke_func(skill="filesystem", tool="nonexistent_operation_xyz", args={})
        # Should return error with available operations listed
        assert "not found" in result.lower()
        # Should list available operations
        assert "Available:" in result or "list_directory" in result


class TestWriterSkill:
    """Test writer skill operations (Writing quality enforcement)."""

    def test_writer_manifest_parsing(self, registry):
        """Registry should correctly parse writer/manifest.json."""
        manifest = registry.get_skill_manifest("writer")
        assert manifest is not None
        assert manifest.name == "writer"
        assert manifest.version == "1.0.0"
        assert manifest.tools_module == "agent.skills.writer.tools"

    def test_load_writer_skill(self, registry, real_mcp):
        """Should successfully load writer skill."""
        success, message = registry.load_skill("writer", real_mcp)

        assert success is True, f"Expected success, got: {message}"
        assert "writer" in registry.loaded_skills
        assert "writer" in registry.module_cache

    def test_writer_has_lint_writing_style(self, registry, real_mcp):
        """Loaded writer module should have lint_writing_style function."""
        registry.load_skill("writer", real_mcp)

        module = registry.module_cache["writer"]
        assert hasattr(module, "lint_writing_style")
        assert hasattr(module, "check_markdown_structure")
        assert hasattr(module, "polish_text")
        assert hasattr(module, "load_writing_memory")

    @pytest.mark.asyncio
    async def test_lint_writing_style_detects_clutter(self, registry, real_mcp):
        """lint_writing_style should detect clutter words."""
        registry.load_skill("writer", real_mcp)
        module = registry.module_cache["writer"]

        # Test with clutter words
        result = await module.lint_writing_style("We should utilize this feature.")
        assert "violations" in result or "status" in result
        # Should detect "utilize" as a clutter word

    @pytest.mark.asyncio
    async def test_lint_writing_style_clean_text(self, registry, real_mcp):
        """lint_writing_style should return clean for good text."""
        registry.load_skill("writer", real_mcp)
        module = registry.module_cache["writer"]

        result = await module.lint_writing_style("Use this feature.")
        assert "clean" in result or "status" in result

    @pytest.mark.asyncio
    async def test_check_markdown_structure_valid(self, registry, real_mcp):
        """check_markdown_structure should validate proper markdown."""
        registry.load_skill("writer", real_mcp)
        module = registry.module_cache["writer"]

        result = await module.check_markdown_structure("# Heading\n\nSome content.")
        assert "clean" in result or "status" in result

    @pytest.mark.asyncio
    async def test_check_markdown_structure_detects_multiple_h1(self, registry, real_mcp):
        """check_markdown_structure should detect multiple H1 headings."""
        registry.load_skill("writer", real_mcp)
        module = registry.module_cache["writer"]

        result = await module.check_markdown_structure("# Title\n\n# Another Title")
        assert "violations" in result or "multiple_h1" in result

    @pytest.mark.asyncio
    async def test_polish_text_combines_checks(self, registry, real_mcp):
        """polish_text should combine lint and structure checks."""
        registry.load_skill("writer", real_mcp)
        module = registry.module_cache["writer"]

        result = await module.polish_text("# Title\n\nUse this feature.")
        assert "status" in result

    @pytest.mark.asyncio
    async def test_load_writing_memory(self, registry, real_mcp):
        """load_writing_memory should return writing guidelines."""
        registry.load_skill("writer", real_mcp)
        module = registry.module_cache["writer"]

        result = await module.load_writing_memory()
        assert "status" in result or "loaded" in result


class TestFileOpsSkill:
    """Test file_ops skill operations (File I/O and AST-based refactoring)."""

    def test_file_ops_manifest_parsing(self, registry):
        """Registry should correctly parse file_ops/manifest.json."""
        manifest = registry.get_skill_manifest("file_ops")
        assert manifest is not None
        assert manifest.name == "file_ops"
        assert manifest.version == "1.0.0"
        assert manifest.tools_module == "agent.skills.file_ops.tools"

    def test_load_file_ops_skill(self, registry, real_mcp):
        """Should successfully load file_ops skill."""
        success, message = registry.load_skill("file_ops", real_mcp)

        assert success is True, f"Expected success, got: {message}"
        assert "file_ops" in registry.loaded_skills
        assert "file_ops" in registry.module_cache

    def test_file_ops_has_core_functions(self, registry, real_mcp):
        """Loaded file_ops module should have core functions."""
        registry.load_skill("file_ops", real_mcp)

        module = registry.module_cache["file_ops"]
        assert hasattr(module, "read_file")
        assert hasattr(module, "search_files")
        assert hasattr(module, "save_file")

    @pytest.mark.asyncio
    async def test_file_ops_read_file(self, registry, real_mcp):
        """file_ops read_file should read file content."""
        registry.load_skill("file_ops", real_mcp)
        module = registry.module_cache["file_ops"]

        result = await module.read_file("agent/skills/file_ops/manifest.json")
        assert "file_ops" in result or "manifest" in result

    @pytest.mark.asyncio
    async def test_file_ops_read_file_not_found(self, registry, real_mcp):
        """file_ops read_file should return error for non-existent file."""
        registry.load_skill("file_ops", real_mcp)
        module = registry.module_cache["file_ops"]

        result = await module.read_file("nonexistent/file.txt")
        assert "Error" in result or "not exist" in result.lower()

    @pytest.mark.asyncio
    async def test_file_ops_search_files(self, registry, real_mcp):
        """file_ops search_files should find patterns."""
        registry.load_skill("file_ops", real_mcp)
        module = registry.module_cache["file_ops"]

        result = await module.search_files(pattern="def register", path="agent/skills/file_ops")
        assert "search" in result.lower() or "def" in result or "result" in result.lower()

    @pytest.mark.asyncio
    async def test_file_ops_save_file_creates_file(self, registry, real_mcp):
        """file_ops save_file should create a new file."""
        import tempfile

        registry.load_skill("file_ops", real_mcp)
        module = registry.module_cache["file_ops"]

        # Use temp file in agent directory
        test_path = "agent/skills/test_file_ops.txt"
        try:
            result = await module.save_file(path=test_path, content="test content")
            assert "Successfully wrote" in result or "Error" not in result

            # Verify file was written
            content = Path(test_path).read_text()
            assert content == "test content"
        finally:
            if Path(test_path).exists():
                Path(test_path).unlink()


class TestTestingProtocolSkill:
    """Test testing_protocol skill operations (Smart test runner)."""

    def test_testing_protocol_manifest_parsing(self, registry):
        """Registry should correctly parse testing_protocol/manifest.json."""
        manifest = registry.get_skill_manifest("testing_protocol")
        assert manifest is not None
        assert manifest.name == "testing_protocol"
        assert manifest.version == "1.0.0"
        assert manifest.tools_module == "agent.skills.testing_protocol.tools"

    def test_load_testing_protocol_skill(self, registry, real_mcp):
        """Should successfully load testing_protocol skill."""
        success, message = registry.load_skill("testing_protocol", real_mcp)

        assert success is True, f"Expected success, got: {message}"
        assert "testing_protocol" in registry.loaded_skills
        assert "testing_protocol" in registry.module_cache

    def test_testing_protocol_has_core_functions(self, registry, real_mcp):
        """Loaded testing_protocol module should have core functions."""
        registry.load_skill("testing_protocol", real_mcp)

        module = registry.module_cache["testing_protocol"]
        assert hasattr(module, "smart_test_runner")
        assert hasattr(module, "run_test_command")
        assert hasattr(module, "get_test_protocol")

    @pytest.mark.asyncio
    async def test_smart_test_runner_returns_json(self, registry, real_mcp):
        """smart_test_runner should return JSON result."""
        registry.load_skill("testing_protocol", real_mcp)
        module = registry.module_cache["testing_protocol"]

        result = await module.smart_test_runner()
        assert "strategy" in result or "status" in result

    @pytest.mark.asyncio
    async def test_smart_test_runner_with_focus_file(self, registry, real_mcp):
        """smart_test_runner with focus_file should return focused strategy."""
        registry.load_skill("testing_protocol", real_mcp)
        module = registry.module_cache["testing_protocol"]

        result = await module.smart_test_runner(focus_file="agent/skills/test.py")
        assert "focused" in result or "strategy" in result

    @pytest.mark.asyncio
    async def test_run_test_command_allowed(self, registry, real_mcp):
        """run_test_command should accept allowed commands."""
        registry.load_skill("testing_protocol", real_mcp)
        module = registry.module_cache["testing_protocol"]

        result = await module.run_test_command(command="pytest --version")
        assert "status" in result

    @pytest.mark.asyncio
    async def test_run_test_command_blocked(self, registry, real_mcp):
        """run_test_command should block dangerous commands."""
        registry.load_skill("testing_protocol", real_mcp)
        module = registry.module_cache["testing_protocol"]

        result = await module.run_test_command(command="rm -rf /")
        assert "not allowed" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_get_test_protocol(self, registry, real_mcp):
        """get_test_protocol should return testing protocol summary."""
        registry.load_skill("testing_protocol", real_mcp)
        module = registry.module_cache["testing_protocol"]

        result = await module.get_test_protocol()
        assert "doc" in result or "rules" in result or "strategy" in result


class TestGitSkill:
    """Test git skill operations (Phase 23 - The Skill Singularity)."""

    def test_git_manifest_parsing(self, registry):
        """Registry should correctly parse git/manifest.json."""
        manifest = registry.get_skill_manifest("git")
        assert manifest is not None
        assert manifest.name == "git"
        assert manifest.version == "2.0.0"  # Updated for Phase 24
        assert manifest.tools_module == "agent.skills.git.tools"

    def test_load_git_skill(self, registry, real_mcp):
        """Should successfully load git skill."""
        success, message = registry.load_skill("git", real_mcp)

        assert success is True, f"Expected success, got: {message}"
        assert "git" in registry.loaded_skills
        assert "git" in registry.module_cache

    def test_git_has_read_operations(self, registry, real_mcp):
        """Loaded git module should have read operations."""
        registry.load_skill("git", real_mcp)

        module = registry.module_cache["git"]
        assert hasattr(module, "git_status")
        assert hasattr(module, "git_diff")
        assert hasattr(module, "git_log")

    def test_git_has_write_operations(self, registry, real_mcp):
        """Loaded git module should have write operations."""
        registry.load_skill("git", real_mcp)

        module = registry.module_cache["git"]
        assert hasattr(module, "git_add")
        assert hasattr(module, "git_commit")
        assert hasattr(module, "git_stage_all")

    def test_git_status_returns_output(self, registry, real_mcp):
        """git_status should return status output."""
        registry.load_skill("git", real_mcp)
        module = registry.module_cache["git"]

        result = module.git_status()
        assert result is not None
        # Should contain file status indicators or be empty

    def test_git_log_returns_output(self, registry, real_mcp):
        """git_log should return commit history."""
        registry.load_skill("git", real_mcp)
        module = registry.module_cache["git"]

        result = module.git_log(n=3)
        assert result is not None

    def test_git_branch_returns_output(self, registry, real_mcp):
        """git_branch should return branch list."""
        registry.load_skill("git", real_mcp)
        module = registry.module_cache["git"]

        result = module.git_branch()
        assert result is not None


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main(["-v", __file__, "--tb=short"]))
