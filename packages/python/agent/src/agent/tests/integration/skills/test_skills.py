"""
src/agent/tests/test_phase13_skills.py
Comprehensive testing for the Phase 13 Skill Architecture + Phase 25 Omni CLI.

Phase 25.1: Macro System with @skill_command Decorators
- @skill_command decorator marks functions with metadata and DI support
- SkillManager scans skills and builds registry from decorated functions
- Single omni() tool handles all operations

Phase 34: CommandResult wrapper for structured output

Covers:
1. SkillRegistry (Discovery, Loading, Context, Spec-based Loading)
2. SkillManager (Phase 25: Omni CLI single entry point)
3. Skill Manifest (Schema Validation)
4. Skill Hot Reload
5. Filesystem Skill
6. Git Skill (Phase 25.1: @skill_command decorators)

Note: _template is a skeleton for creating new skills and cannot be loaded
as a Python module (names starting with underscore have special meaning).
"""

import pytest
import sys
import asyncio
import os
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from mcp.server.fastmcp import FastMCP


# =============================================================================
# Test Helper: Handle CommandResult from @skill_command decorator
# =============================================================================


def unwrap_command_result(result):
    """
    Unwrap CommandResult from @skill_command decorated functions.

    Phase 34: @skill_command now returns CommandResult for structured output.
    Tests should use this helper to extract the actual data.
    """
    from agent.skills.decorators import CommandResult

    if isinstance(result, CommandResult):
        if result.success:
            return result.data
        else:
            raise AssertionError(f"Command failed: {result.error}")
    return result


# =============================================================================
# Test Helper: omni function (Phase 35.3 - Pure MCP Server)
# =============================================================================


async def omni(command: str, args: dict | None = None) -> str:
    """
    Execute a skill command. Mimics old FastMCP @tool omni behavior.

    Phase 35.3: Uses SkillManager.run() directly instead of FastMCP.

    Special commands:
    - "help": Shows all available skills
    - "skill": Shows skill's commands (e.g., omni("git") shows git commands)
    - "skill.command": Executes a specific command (e.g., omni("git.status"))
    """
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()
    args = args or {}

    # Special case: "help" shows all skills
    if command == "help":
        # Get list of available skills and format as help
        available = manager.list_available()
        loaded = manager.list_loaded()
        lines = ["# Available Skills", ""]
        for skill in sorted(available):
            status = "loaded" if skill in loaded else "unloaded"
            lines.append(f"- **{skill}** ({status})")
        return "\n".join(lines)

    if "." in command:
        parts = command.split(".", 1)
        skill_name = parts[0]
        command_name = parts[1]
    else:
        # Just skill name - show skill's commands
        skill_name = command
        command_name = "help"

    return await manager.run(skill_name, command_name, args)


def async_unwrap_command_result(coro):
    """Async wrapper for unwrap_command_result."""

    async def wrapper():
        result = await coro
        return unwrap_command_result(result)

    return wrapper()


# Import core components
from agent.core.schema import SkillManifest
from agent.core.registry import SkillRegistry, get_skill_registry
from agent.core.skill_manager import SkillManager, get_skill_manager

# Use new SKILLS_DIR API from common.skills_path
from common.skills_path import SKILLS_DIR, load_skill_module


def _load_skill_module_for_test(skill_name: str):
    """Load a skill module using module_loader for proper import setup.

    This is optimized for tests - uses module_loader context manager
    which pre-loads decorators and handles parent packages.
    """
    from agent.core.module_loader import module_loader

    skill_tools_path = SKILLS_DIR(skill=skill_name, filename="tools.py")

    if not skill_tools_path.exists():
        raise FileNotFoundError(f"Skill tools not found: {skill_tools_path}")

    module_name = f"agent.skills.{skill_name}.tools"

    # Use module_loader context manager for proper import setup (pre-loads decorators)
    with module_loader(SKILLS_DIR()) as loader:
        module = loader.load_module(module_name, skill_tools_path)

    return module


@pytest.fixture
def real_mcp():
    """Real FastMCP instance for integration testing."""
    mcp = FastMCP("test")
    return mcp


class TestSkillManifest:
    """Test the DNA of skills - Schema validation."""

    def test_valid_manifest_creation(self):
        """Test creating a valid SkillManifest with v2.0 format."""
        data = {
            "name": "test_skill",
            "version": "1.0.0",
            "description": "A test skill",
            "dependencies": {"skills": {"git": ">=1.0.0"}},
            "tools_module": "assets.skills.test.tools",
            "guide_file": "README.md",
        }
        manifest = SkillManifest(**data)
        assert manifest.name == "test_skill"
        assert manifest.version == "1.0.0"
        assert manifest.dependencies.skills == {"git": ">=1.0.0"}
        assert manifest.tools_module == "assets.skills.test.tools"

    def test_minimal_manifest(self):
        """Test creating manifest with only required fields."""
        data = {
            "name": "minimal_skill",
            "version": "0.1.0",
            "description": "Minimal skill",
            "tools_module": "assets.skills.minimal.tools",
        }
        manifest = SkillManifest(**data)
        assert manifest.name == "minimal_skill"
        assert manifest.dependencies.skills == {}
        assert manifest.dependencies.python == {}
        assert manifest.guide_file == "README.md"
        assert manifest.prompts_file is None

    def test_invalid_manifest_missing_name(self):
        """Test that missing name raises error."""
        data = {
            "version": "1.0.0",
            "description": "A test skill",
            "tools_module": "assets.skills.test.tools",
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

    def test_discovery_finds_git_skill(self, registry_fixture):
        """Registry should find 'git' skill."""
        skills = registry_fixture.list_available_skills()
        assert "git" in skills, f"Expected 'git' in skills, got: {skills}"

    def test_discovery_finds_filesystem_skill(self, registry_fixture):
        """Registry should find 'filesystem' skill."""
        skills = registry_fixture.list_available_skills()
        assert "filesystem" in skills

    def test_discovery_finds_terminal_skill(self, registry_fixture):
        """Registry should find 'terminal' skill."""
        skills = registry_fixture.list_available_skills()
        assert "terminal" in skills, f"Expected 'terminal' in skills, got: {skills}"

    def test_discovery_finds_testing_skill(self, registry_fixture):
        """Registry should find 'testing' skill."""
        skills = registry_fixture.list_available_skills()
        assert "testing" in skills, f"Expected 'testing' in skills, got: {skills}"

    def test_discovery_finds_documentation_skill(self, registry_fixture):
        """Registry should find 'documentation' skill."""
        skills = registry_fixture.list_available_skills()
        assert "documentation" in skills, f"Expected 'documentation' in skills, got: {skills}"

    def test_discovery_finds_software_engineering_skill(self, registry_fixture):
        """Registry should find 'software_engineering' skill (The Architect)."""
        skills = registry_fixture.list_available_skills()
        assert "software_engineering" in skills, (
            f"Expected 'software_engineering' in skills, got: {skills}"
        )

    def test_discovery_finds_template_directory(self, registry_fixture):
        """Registry should discover _template directory (for copying)."""
        skills = registry_fixture.list_available_skills()
        assert "_template" in skills

    def test_discovery_excludes_pycache(self, registry_fixture):
        """Registry should not pick up __pycache__ or other non-skill dirs."""
        skills = registry_fixture.list_available_skills()
        assert "__pycache__" not in skills

    def test_manifest_parsing_filesystem(self, registry_fixture):
        """Registry should correctly parse filesystem/SKILL.md."""
        manifest = registry_fixture.get_skill_manifest("filesystem")
        assert manifest is not None
        assert manifest.name == "filesystem"
        assert manifest.version == "1.0.0"
        assert manifest.tools_module == "agent.skills.filesystem.tools"
        assert manifest.guide_file == "README.md"


class TestSpecBasedLoading:
    """Test spec-based module loading (Level 2 feature)."""

    def test_load_filesystem_skill(self, registry_fixture, real_mcp):
        """Should successfully load filesystem skill using spec-based loading."""
        success, message = registry_fixture.load_skill("filesystem", real_mcp)

        assert success is True, f"Expected success, got: {message}"
        assert "filesystem" in registry_fixture.loaded_skills
        assert "filesystem" in registry_fixture.module_cache

    def test_module_cached_after_load(self, registry_fixture, real_mcp):
        """Module should be cached after loading."""
        registry_fixture.load_skill("filesystem", real_mcp)

        assert "filesystem" in registry_fixture.module_cache
        module = registry_fixture.module_cache["filesystem"]
        assert module is not None

    def test_module_has_executable_functions(self, registry_fixture, real_mcp):
        """Loaded module should have callable functions."""
        registry_fixture.load_skill("filesystem", real_mcp)

        module = registry_fixture.module_cache["filesystem"]
        # Check for expected functions
        assert hasattr(module, "list_directory")
        assert hasattr(module, "read_file")
        assert hasattr(module, "write_file")
        assert hasattr(module, "search_files")

    def test_execute_function_after_load(self, registry_fixture, real_mcp):
        """Should be able to execute functions after loading."""
        import asyncio

        registry_fixture.load_skill("filesystem", real_mcp)
        module = registry_fixture.module_cache["filesystem"]

        # Execute list_directory
        result = asyncio.run(module.list_directory("assets/skills"))

        # @skill_command now returns CommandResult
        from agent.skills.decorators import CommandResult

        if isinstance(result, CommandResult):
            result_str = result.data if result.success else result.error
        else:
            result_str = result

        assert "filesystem" in result_str or "Directory Listing" in result_str

    def test_nonexistent_skill_fails(self, registry_fixture, real_mcp):
        """Loading nonexistent skill should fail gracefully."""
        success, message = registry_fixture.load_skill("totally_fake_skill_xyz", real_mcp)
        assert success is False
        assert "not found" in message.lower()

    def test_template_loads_with_spec_based_loading(self, registry_fixture, real_mcp):
        """_template can now be loaded with spec-based loading (unlike importlib.import_module)."""
        # With spec-based loading, _template can be loaded
        success, message = registry_fixture.load_skill("_template", real_mcp)
        # This should succeed with spec-based loading
        assert success is True
        assert "_template" in registry_fixture.loaded_skills


class TestHotReload:
    """Test hot reload functionality."""

    def test_hot_reload_reloads_module(self, registry_fixture, real_mcp):
        """Loading same skill again should re-execute module code."""
        import asyncio
        import agent.core.registry as sr_module
        from common.skills_path import SKILLS_DIR

        # First load
        success1, msg1 = registry_fixture.load_skill("filesystem", real_mcp)
        assert success1 is True

        # Get original function result
        module1 = registry_fixture.module_cache["filesystem"]
        original_result = unwrap_command_result(
            asyncio.run(module1.list_directory("assets/skills"))
        )
        assert "[HOT-RELOADED]" not in original_result

        # Modify file content (simulate code change)
        tools_path = SKILLS_DIR(skill="filesystem", filename="tools.py")
        original_content = tools_path.read_text()

        # Add a marker to the function (match the exact line including \n)
        new_content = original_content.replace(
            "return f\"Directory Listing for '{path}':\\n\"",
            "return f\"[HOT-RELOADED] Directory Listing for '{path}':\\n\"",
        )
        tools_path.write_text(new_content)

        try:
            # Force reload by clearing cache and reloading
            sr_module.SkillRegistry._instance = None
            registry = sr_module.get_skill_registry()
            registry_fixture.loaded_skills.clear()
            registry_fixture.module_cache.clear()

            success2, msg2 = registry_fixture.load_skill("filesystem", real_mcp)
            assert success2 is True

            # Verify new content is loaded by executing the function
            module2 = registry_fixture.module_cache["filesystem"]
            new_result = unwrap_command_result(asyncio.run(module2.list_directory("assets/skills")))
            assert "[HOT-RELOADED]" in new_result

        finally:
            # Restore original content
            tools_path.write_text(original_content)

    def test_double_load_handles_gracefully(self, registry_fixture, real_mcp):
        """Loading same skill twice should be safe."""
        success1, msg1 = registry_fixture.load_skill("filesystem", real_mcp)
        assert success1 is True

        success2, msg2 = registry_fixture.load_skill("filesystem", real_mcp)
        assert success2 is True
        # Second load should succeed (hot reload behavior)


class TestSkillContext:
    """Test skill context retrieval."""

    def test_get_context_returns_guide(self, registry_fixture):
        """Registry should read README.md content."""
        context = registry_fixture.get_skill_context("filesystem")
        assert context is not None
        assert len(context) > 0
        assert "FILESYSTEM" in context.upper()

    def test_get_context_includes_definition(self, registry_fixture):
        """Registry should include SKILL.md definition if available."""
        context = registry_fixture.get_skill_context("filesystem")
        # Filesystem has SKILL.md
        assert "FILESYSTEM" in context.upper()

    def test_get_context_nonexistent_skill(self, registry_fixture):
        """Getting context for nonexistent skill returns empty string."""
        context = registry_fixture.get_skill_context("fake_skill_xyz")
        assert context == ""


# =============================================================================
# Phase 25: Omni CLI Tests
# =============================================================================


class TestSkillManagerOmniCLI:
    """Test Phase 25: Omni CLI SkillManager."""

    def test_skill_manager_fixture_loads_skills(self, skill_manager_fixture):
        """SkillManager should load skills from agent/skills."""
        skills = skill_manager_fixture.load_skills()

        assert "git" in skills, f"Expected 'git' in skills, got: {list(skills.keys())}"
        assert len(skills) >= 1

    def test_skill_manager_fixture_git_has_commands(self, skill_manager_fixture):
        """Git skill should have commands loaded."""
        skill_manager_fixture.load_skills()

        assert "git" in skill_manager_fixture.skills
        git_skill = skill_manager_fixture.skills["git"]
        assert len(git_skill.commands) >= 1

    @pytest.mark.asyncio
    async def test_skill_manager_fixture_run_with_args(self, skill_manager_fixture):
        """SkillManager.run() should pass arguments to commands."""
        # git.log tests migrated to assets/skills/git/tests/
        pass

    @pytest.mark.asyncio
    async def test_skill_manager_fixture_run_nonexistent_skill(self, skill_manager_fixture):
        """Running command on nonexistent skill should return error."""
        result = await skill_manager_fixture.run("nonexistent", "some_command", {})

        assert "Error" in result or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_skill_manager_fixture_run_nonexistent_command(self, skill_manager_fixture):
        """Running nonexistent command should return error."""
        result = await skill_manager_fixture.run("git", "nonexistent_command", {})

        assert "Error" in result or "not found" in result.lower()

    def test_skill_manager_fixture_list_available_skills(self, skill_manager_fixture):
        """list_available_skills() should return skill names."""
        skill_manager_fixture.load_skills()

        skills = skill_manager_fixture.list_available_skills()
        assert isinstance(skills, list)
        assert "git" in skills

    def test_skill_manager_fixture_get_skill_info(self, skill_manager_fixture):
        """get_skill_info() should return skill metadata."""
        skill_manager_fixture.load_skills()

        info = skill_manager_fixture.get_skill_info("git")
        assert info is not None
        assert info["name"] == "git"
        assert info["loaded"] is True
        assert info["command_count"] >= 1

    def test_skill_manager_fixture_global_instance(self):
        """get_skill_manager() should return singleton."""
        manager1 = get_skill_manager()
        manager2 = get_skill_manager()

        assert manager1 is manager2


# Import decorator tests from common test library (Phase 35.1)
# Note: TestFilesystemSkillDecorators removed (Phase 36) - tests migrated to skills/filesystem/tests/


class TestFilesystemSkill:
    """Test filesystem skill operations."""

    @pytest.mark.asyncio
    async def test_list_directory_operation(self, isolated_registry, mock_mcp_server):
        """Test list_directory function."""
        isolated_registry.load_skill("filesystem", mock_mcp_server)
        module = isolated_registry.module_cache["filesystem"]

        result = await module.list_directory("assets/skills")
        result = unwrap_command_result(result)
        assert "filesystem" in result or "_template" in result

    @pytest.mark.asyncio
    async def test_read_file_operation(self, isolated_registry, mock_mcp_server):
        """Test read_file function."""
        isolated_registry.load_skill("filesystem", mock_mcp_server)
        module = isolated_registry.module_cache["filesystem"]

        # Read the SKILL.md file
        result = await module.read_file("assets/skills/filesystem/SKILL.md")
        result = unwrap_command_result(result)
        assert "filesystem" in result
        assert "version" in result

    @pytest.mark.asyncio
    async def test_write_file_operation(self, isolated_registry, mock_mcp_server, temp_dir):
        """Test write_file function."""
        isolated_registry.load_skill("filesystem", mock_mcp_server)
        module = isolated_registry.module_cache["filesystem"]

        # Write to a temp file
        test_path = temp_dir / "test_write.txt"
        result = await module.write_file(str(test_path), "test content 123")
        result = unwrap_command_result(result)
        assert "Successfully wrote" in result

        # Verify file was written
        content = test_path.read_text()
        assert content == "test content 123"

    @pytest.mark.asyncio
    async def test_search_files_operation(self, isolated_registry, mock_mcp_server):
        """Test search_files function."""
        isolated_registry.load_skill("filesystem", mock_mcp_server)
        module = isolated_registry.module_cache["filesystem"]

        # Search for SKILL.md files
        result = await module.search_files(pattern="SKILL.md", path="assets/skills")
        result = unwrap_command_result(result)
        assert "SKILL.md" in result

    @pytest.mark.asyncio
    async def test_get_file_info_operation(self, isolated_registry, mock_mcp_server):
        """Test get_file_info function."""
        isolated_registry.load_skill("filesystem", mock_mcp_server)
        module = isolated_registry.module_cache["filesystem"]

        result = await module.get_file_info(path="assets/skills/filesystem/SKILL.md")
        result = unwrap_command_result(result)
        assert "Size:" in result or "bytes" in result


class TestSkillEdgeCases:
    """Edge case and error handling tests."""

    def test_load_skill_with_missing_source_file(self, registry_fixture, real_mcp):
        """Loading skill with missing source file should fail."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test_missing"
            skill_dir.mkdir()

            # Create SKILL.md instead of manifest.json
            skill_md = """\
---
name: "test_missing"
version: "1.0.0"
description: "Test skill with missing source"
routing_keywords: ["test"]
"""
            (skill_dir / "SKILL.md").write_text(skill_md)

            # This would fail to find the source file
            success, message = registry_fixture.load_skill("test_missing", real_mcp)
            assert success is False
            assert "not found" in message.lower() or "source file" in message.lower()

    def test_singleton_returns_same_instance(self):
        """get_skill_registry should return singleton."""
        reg1 = get_skill_registry()
        reg2 = get_skill_registry()
        assert reg1 is reg2

    def test_registry_state_cleared_between_tests(self, registry_fixture):
        """Verify registry state is properly cleared."""
        assert len(registry_fixture.loaded_skills) == 0
        assert len(registry_fixture.module_cache) == 0

    def test_concurrent_load_same_skill(self, registry_fixture, real_mcp):
        """Loading same skill concurrently should not cause errors."""
        import asyncio

        async def load():
            return registry_fixture.load_skill("filesystem", real_mcp)

        # Run multiple loads
        results = []
        for _ in range(3):
            success, msg = registry_fixture.load_skill("filesystem", real_mcp)
            results.append((success, msg))

        # All should succeed
        for success, msg in results:
            assert success is True


# =============================================================================
# Phase 25: One Tool Architecture Tests
# =============================================================================


class TestOneToolArchitecture:
    """Test Phase 25: Single 'omni' tool with simplified syntax."""

    def test_omni_is_callable(self, skill_manager_fixture):
        """omni function should be callable."""
        assert callable(omni), "omni should be callable"

    @pytest.mark.asyncio
    async def test_omni_simplified_syntax_git_status(self, skill_manager_fixture):
        """Test @omni('skill.command') simplified syntax works."""
        from agent.core.skill_manager import _skill_manager

        # Ensure we're using the same manager as the fixture
        assert _skill_manager is skill_manager_fixture

    @pytest.mark.asyncio
    async def test_omni_syntax_with_args(self, skill_manager_fixture):
        """Test @omni('skill.command', args={}) with arguments."""
        # git.status and git.log tests migrated to assets/skills/git/tests/
        pass

    @pytest.mark.asyncio
    async def test_omni_help_shows_all_skills(self, skill_manager_fixture):
        """@omni('help') should list all skills."""
        result = await omni("help")

        assert isinstance(result, str)
        assert "Available Skills" in result or "🛠️" in result
        assert "git" in result

    @pytest.mark.asyncio
    async def test_omni_skill_name_shows_commands(self, skill_manager_fixture):
        """@omni('skill') should show skill info or available commands."""
        result = await omni("git")

        assert isinstance(result, str)
        assert "git" in result.lower()
        # Result may be "No context available for 'git'" if context cache not initialized
        # or actual help content with commands

    @pytest.mark.asyncio
    async def test_omni_invalid_format_shows_skills(self, skill_manager_fixture):
        """Without dots, shows skill help or error message."""
        result = await omni("invalid_command_without_dot")

        # Without dots, it's treated as a skill name request
        # Result is either available skills or "not found" error
        assert isinstance(result, str)
        assert "not found" in result.lower() or "Available Skills" in result or "git" in result

    @pytest.mark.asyncio
    async def test_omni_nonexistent_skill_error(self, skill_manager_fixture):
        """Nonexistent skill should return helpful error."""
        result = await omni("nonexistent_skill.status")

        assert isinstance(result, str)
        assert "not found" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_omni_nonexistent_command_error(self, skill_manager_fixture):
        """Nonexistent command should return helpful error."""
        result = await omni("help.nonexistent_command")

        assert isinstance(result, str)
        assert "not found" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_omni_dispatch_to_filesystem(self, skill_manager_fixture):
        """@omni should dispatch to filesystem skill."""
        # filesystem tests migrated to assets/skills/filesystem/tests/
        pass

    @pytest.mark.asyncio
    async def test_omni_dispatch_to_knowledge(self, skill_manager_fixture):
        """@omni should dispatch to knowledge skill."""
        # knowledge tests migrated to assets/skills/knowledge/tests/
        pass

    @pytest.mark.asyncio
    async def test_omni_empty_args_defaults_to_dict(self, skill_manager_fixture):
        """@omni with no args should work with empty dict."""
        # git.status tests migrated to assets/skills/git/tests/
        pass


class TestSkillManagerCommandExecution:
    """Test SkillManager command execution for One Tool architecture."""

    @pytest.mark.asyncio
    async def test_run_command_returns_string(self, skill_manager_fixture):
        """run() should always return string."""
        # git tests migrated to assets/skills/git/tests/
        pass

    @pytest.mark.asyncio
    async def test_run_command_with_complex_args(self, skill_manager_fixture):
        """run() should handle complex arguments."""
        # git tests migrated to assets/skills/git/tests/
        pass

    @pytest.mark.asyncio
    async def test_all_skills_loadable(self, skill_manager_fixture):
        """All discovered skills should be loadable."""
        skills = skill_manager_fixture.list_available_skills()

        for skill_name in skills:
            if skill_name.startswith("_"):
                continue  # Skip template
            result = await skill_manager_fixture.run(skill_name, "help", {})
            assert isinstance(result, str), f"Skill {skill_name} should return string"


# =============================================================================
# Phase 25+: Performance & Multimodal Tests
# =============================================================================
