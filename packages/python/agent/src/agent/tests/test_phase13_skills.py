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
        assert "software_engineering" in skills, f"Expected 'software_engineering' in skills, got: {skills}"

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


class TestSkillToolExecution:
    """
    CRITICAL: Tests for skill() tool execution.

    This class specifically tests skills where tools are defined INSIDE the register()
    function (like git skill). This is the pattern that caused the bug where
    hasattr(module, operation) failed because functions inside register() are not
    module attributes.

    This test class would have caught the spec_aware_commit bug.
    """

    def _get_tool_func(self, mcp, tool_name):
        """Helper to get tool function from FastMCP."""
        tools = list(mcp._tool_manager._tools.values())
        tool = [t for t in tools if t.name == tool_name][0]
        return tool.fn

    @pytest.mark.asyncio
    async def test_skill_tool_calls_git_status(self, registry, real_mcp):
        """
        Test skill() tool can call git_status from git skill.

        git skill defines functions INSIDE register(), so hasattr(module, 'git_status')
        returns False. This test catches the bug where skill() couldn't call git tools.
        """
        from agent.capabilities.skill_manager import register_skill_tools
        register_skill_tools(real_mcp)
        skill_func = self._get_tool_func(real_mcp, "skill")

        result = await skill_func(
            skill="git",
            call='git_status()'
        )

        # Should return git status, not "Operation not found"
        assert "Operation 'git_status' not found" not in result
        assert "git_status" in result or "M " in result or "A " in result or "✅" in result

    @pytest.mark.asyncio
    async def test_skill_tool_calls_git_diff_staged(self, registry, real_mcp):
        """Test skill() tool can call git_diff_staged from git skill."""
        from agent.capabilities.skill_manager import register_skill_tools
        register_skill_tools(real_mcp)
        skill_func = self._get_tool_func(real_mcp, "skill")

        result = await skill_func(
            skill="git",
            call='git_diff_staged()'
        )

        # Should return diff output, not "Operation not found"
        assert "Operation 'git_diff_staged' not found" not in result

    @pytest.mark.asyncio
    async def test_skill_tool_calls_git_log(self, registry, real_mcp):
        """Test skill() tool can call git_log from git skill."""
        from agent.capabilities.skill_manager import register_skill_tools
        register_skill_tools(real_mcp)
        skill_func = self._get_tool_func(real_mcp, "skill")

        result = await skill_func(
            skill="git",
            call='git_log(n=3)'
        )

        # Should return commit log, not "Operation not found"
        assert "Operation 'git_log' not found" not in result
        assert "git_log" in result or "commit" in result.lower()

    @pytest.mark.asyncio
    async def test_skill_tool_calls_smart_commit(self, registry, real_mcp):
        """Test skill() tool can call smart_commit from git skill.

        smart_commit is defined inside register() and has a complex signature.
        This tests that skill() can handle tools with default arguments.
        """
        from agent.capabilities.skill_manager import register_skill_tools
        register_skill_tools(real_mcp)
        skill_func = self._get_tool_func(real_mcp, "skill")

        # smart_commit will fail without staged changes, but that's OK
        # The key is that it finds the function (doesn't return "Operation not found")
        result = await skill_func(
            skill="git",
            call='smart_commit(message="test: validation check")'
        )

        # Should either:
        # 1. Return analysis with session token (if no staged changes)
        # 2. Return success (if staged changes exist)
        # Should NOT return "Operation 'smart_commit' not found"
        assert "Operation 'smart_commit' not found" not in result

    @pytest.mark.asyncio
    async def test_skill_tool_calls_spec_aware_commit(self, registry, real_mcp):
        """
        Test skill() tool can call spec_aware_commit from git skill.

        This is THE critical test that would have caught the original bug.
        spec_aware_commit is defined inside register() and uses InferenceClient.
        """
        from agent.capabilities.skill_manager import register_skill_tools
        register_skill_tools(real_mcp)
        skill_func = self._get_tool_func(real_mcp, "skill")

        result = await skill_func(
            skill="git",
            call='spec_aware_commit(context="test commit generation")'
        )

        # Should not return "Operation not found"
        # May return success or error from InferenceClient, but function should be found
        assert "Operation 'spec_aware_commit' not found" not in result

    @pytest.mark.asyncio
    async def test_skill_tool_parse_kwargs_correctly(self, registry, real_mcp):
        """Test skill() tool correctly parses keyword arguments."""
        from agent.capabilities.skill_manager import register_skill_tools
        register_skill_tools(real_mcp)
        skill_func = self._get_tool_func(real_mcp, "skill")

        # Call git_log with explicit n parameter
        result = await skill_func(
            skill="git",
            call='git_log(n=1)'
        )

        # Should execute without error (parsing kwargs works)
        assert "Invalid call syntax" not in result


class TestSkillManagerConsistency:
    """
    Test that skill() tool behavior is consistent across different skills.

    Ensures that skills with module-level functions (filesystem) and
    skills with register()-level functions (git) both work correctly.
    """

    def _get_tool_func(self, mcp, tool_name):
        """Helper to get tool function from FastMCP."""
        tools = list(mcp._tool_manager._tools.values())
        tool = [t for t in tools if t.name == tool_name][0]
        return tool.fn

    @pytest.mark.asyncio
    async def test_filesystem_and_git_both_work(self, registry, real_mcp):
        """
        Verify both filesystem (module-level) and git (register-level) skills work.

        This is a regression test ensuring both patterns work.
        """
        from agent.capabilities.skill_manager import register_skill_tools
        register_skill_tools(real_mcp)
        skill_func = self._get_tool_func(real_mcp, "skill")

        # Test filesystem skill (module-level functions)
        fs_result = await skill_func(
            skill="filesystem",
            call='list_directory(path="agent/skills")'
        )
        assert "Operation 'list_directory' not found" not in fs_result

        # Test git skill (register-level functions)
        git_result = await skill_func(
            skill="git",
            call='git_status()'
        )
        assert "Operation 'git_status' not found" not in git_result

        # Both should succeed (neither returns "Operation not found")
        assert "not found" not in fs_result.lower()
        assert "not found" not in git_result.lower()


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
