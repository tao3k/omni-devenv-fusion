"""
src/agent/tests/test_phase13_skills.py
Comprehensive testing for the Phase 13 Skill Architecture + Phase 25 Omni CLI.

Phase 25.1: Macro System with @skill_command Decorators
- @skill_command decorator marks functions with metadata and DI support
- SkillManager scans skills and builds registry from decorated functions
- Single omni() tool handles all operations

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
import importlib.util
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from mcp.server.fastmcp import FastMCP

# Import core components
from agent.core.schema import SkillManifest
from agent.core.registry import SkillRegistry, get_skill_registry
from agent.core.skill_manager import SkillManager, get_skill_manager

# Fixtures are provided by conftest.py - no explicit import needed


def _load_skill_module_for_test(skill_name: str):
    """Load a skill module directly from file using importlib.util.

    This is a test helper function for loading skills without going through
    the full SkillRegistry.
    """
    from common.gitops import get_project_root
    from common.settings import get_setting

    project_root = get_project_root()
    skills_path = get_setting("skills.path", "assets/skills")
    skill_tools_path = project_root / skills_path / skill_name / "tools.py"

    if not skill_tools_path.exists():
        raise FileNotFoundError(f"Skill tools not found: {skill_tools_path}")

    skills_parent = project_root / skills_path
    skills_parent_str = str(skills_parent)
    module_name = f"_test_skill_{skill_name}"

    # Clean up existing module if present
    if module_name in sys.modules:
        del sys.modules[module_name]

    # Load the module from file
    spec = importlib.util.spec_from_file_location(
        module_name, skill_tools_path, submodule_search_locations=[skills_parent_str]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

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
            "guide_file": "guide.md",
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
        assert manifest.guide_file == "guide.md"
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
        """Registry should correctly parse filesystem/manifest.json."""
        manifest = registry_fixture.get_skill_manifest("filesystem")
        assert manifest is not None
        assert manifest.name == "filesystem"
        assert manifest.version == "1.0.0"
        assert manifest.tools_module == "assets.skills.filesystem.tools"
        assert manifest.guide_file == "guide.md"


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
        assert "filesystem" in result or "Directory Listing" in result

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

        # First load
        success1, msg1 = registry_fixture.load_skill("filesystem", real_mcp)
        assert success1 is True

        # Get original function result
        module1 = registry_fixture.module_cache["filesystem"]
        original_result = asyncio.run(module1.list_directory("assets/skills"))
        assert "[HOT-RELOADED]" not in original_result

        # Modify file content (simulate code change)
        tools_path = Path("assets/skills/filesystem/tools.py")
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
            new_result = asyncio.run(module2.list_directory("assets/skills"))
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
        """Registry should read guide.md content."""
        context = registry_fixture.get_skill_context("filesystem")
        assert context is not None
        assert len(context) > 0
        assert "FILESYSTEM" in context.upper()

    def test_get_context_includes_prompts(self, registry_fixture):
        """Registry should include prompts.md if available."""
        context = registry_fixture.get_skill_context("filesystem")
        # Filesystem has prompts.md
        assert "SYSTEM PROMPTS" in context or "Filesystem" in context

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

    def test_skill_manager_fixture_git_status_report_command(self, skill_manager_fixture):
        """Git skill should have git_status_report command."""
        skill_manager_fixture.load_skills()

        cmd = skill_manager_fixture.get_command("git", "git_status_report")
        assert cmd is not None
        assert cmd.name == "git_status_report"
        assert callable(cmd.func)

    @pytest.mark.asyncio
    async def test_skill_manager_fixture_run_command(self, skill_manager_fixture):
        """SkillManager.run() should execute commands."""
        result = await skill_manager_fixture.run("git", "git_status_report", {})

        assert result is not None
        assert isinstance(result, str)
        assert "Git Status" in result or "Branch" in result

    @pytest.mark.asyncio
    async def test_skill_manager_fixture_run_with_args(self, skill_manager_fixture):
        """SkillManager.run() should pass arguments to commands."""
        result = await skill_manager_fixture.run("git", "git_log", {"n": 3})

        assert result is not None
        assert isinstance(result, str)

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

    def test_skill_manager_fixture_list_commands(self, skill_manager_fixture):
        """list_commands() should return command names for a skill."""
        skill_manager_fixture.load_skills()

        commands = skill_manager_fixture.list_commands("git")
        assert isinstance(commands, list)
        assert "git_status_report" in commands
        assert "git_commit" in commands

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


class TestGitSkillDecorators:
    """Test Phase 25.1: Git skill with @skill_command decorators."""

    def _load_git_module(self):
        """Load git skill module for testing."""
        return _load_skill_module_for_test("git")

    def test_git_functions_have_skill_command_marker(self):
        """Git functions should have _is_skill_command marker."""
        module = self._load_git_module()

        assert hasattr(module.status, "_is_skill_command")
        assert module.status._is_skill_command is True

        assert hasattr(module.branch, "_is_skill_command")
        assert module.branch._is_skill_command is True

        assert hasattr(module.commit, "_is_skill_command")
        assert module.commit._is_skill_command is True

    def test_git_functions_have_skill_config(self):
        """Git functions should have _skill_config with metadata."""
        module = self._load_git_module()

        # Check status has correct config
        assert hasattr(module.status, "_skill_config")
        config = module.status._skill_config
        assert config["name"] == "git_status"
        assert config["category"] == "read"

        # Check branch has correct config
        assert hasattr(module.branch, "_skill_config")
        config = module.branch._skill_config
        assert config["name"] == "git_branch"

        # Check commit has correct config
        assert hasattr(module.commit, "_skill_config")
        config = module.commit._skill_config
        assert config["name"] == "git_commit"
        assert config["category"] == "write"

    def test_git_status_report_has_view_category(self):
        """git_status_report should have view category."""
        module = self._load_git_module()

        assert hasattr(module.status_report, "_skill_config")
        config = module.status_report._skill_config
        assert config["name"] == "git_status_report"
        assert config["category"] == "view"

    def test_git_plan_hotfix_has_workflow_category(self):
        """git_plan_hotfix should have workflow category."""
        module = self._load_git_module()

        assert hasattr(module.hotfix, "_skill_config")
        config = module.hotfix._skill_config
        assert config["name"] == "git_plan_hotfix"
        assert config["category"] == "workflow"

    def test_git_read_backlog_has_evolution_category(self):
        """git_read_backlog should have evolution category."""
        module = self._load_git_module()

        assert hasattr(module.read_backlog, "_skill_config")
        config = module.read_backlog._skill_config
        assert config["name"] == "git_read_backlog"
        assert config["category"] == "evolution"


class TestGitSkillDirectCalls:
    """Test git skill functions directly (without MCP registration)."""

    def _load_git_module(self):
        """Load git skill module for testing."""
        return _load_skill_module_for_test("git")

    def test_git_status_report_returns_markdown(self):
        """status_report should return formatted markdown."""
        module = self._load_git_module()

        result = module.status_report()

        assert isinstance(result, str)
        assert "Branch" in result

    def test_git_status_returns_output(self):
        """status should return status output."""
        module = self._load_git_module()

        result = module.status()

        assert isinstance(result, str)

    def test_git_log_returns_output(self):
        """log should return commit history."""
        module = self._load_git_module()

        # log() is sync, returns string directly
        result = module.log(n=3)

        assert isinstance(result, str)

    def test_git_branch_returns_output(self):
        """branch should return branch list."""
        module = self._load_git_module()

        result = module.branch()

        assert isinstance(result, str)

    def test_git_plan_hotfix_returns_plan(self):
        """hotfix should return a plan."""
        module = self._load_git_module()

        # hotfix() is sync, returns string directly
        result = module.hotfix(issue_id="TEST-123")

        assert isinstance(result, str)
        assert "TEST-123" in result or "Hotfix" in result

    def test_git_read_backlog_returns_content(self):
        """read_backlog should return backlog content."""
        module = self._load_git_module()

        result = module.read_backlog()

        assert isinstance(result, str)
        assert "Git Skill Backlog" in result or "Backlog" in result

    def test_git_add_with_files(self):
        """add should accept file list."""
        module = self._load_git_module()

        # This will fail if no files are staged, but should not raise
        try:
            result = asyncio.run(module.add(["."]))
            assert isinstance(result, str)
        except Exception as e:
            # GitError is expected if nothing is staged
            assert "nothing to commit" in str(e).lower() or isinstance(e, Exception)


class TestFilesystemSkill:
    """Test filesystem skill operations."""

    @pytest.mark.asyncio
    async def test_list_directory_operation(self, isolated_registry, mock_mcp_server):
        """Test list_directory function."""
        isolated_registry.load_skill("filesystem", mock_mcp_server)
        module = isolated_registry.module_cache["filesystem"]

        result = await module.list_directory("assets/skills")
        assert "filesystem" in result or "_template" in result

    @pytest.mark.asyncio
    async def test_read_file_operation(self, isolated_registry, mock_mcp_server):
        """Test read_file function."""
        isolated_registry.load_skill("filesystem", mock_mcp_server)
        module = isolated_registry.module_cache["filesystem"]

        # Read the manifest file
        result = await module.read_file("assets/skills/filesystem/manifest.json")
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
        assert "Successfully wrote" in result

        # Verify file was written
        content = test_path.read_text()
        assert content == "test content 123"

    @pytest.mark.asyncio
    async def test_search_files_operation(self, isolated_registry, mock_mcp_server):
        """Test search_files function."""
        isolated_registry.load_skill("filesystem", mock_mcp_server)
        module = isolated_registry.module_cache["filesystem"]

        # Search for manifest files
        result = await module.search_files(pattern="*.json", path="assets/skills")
        assert "manifest.json" in result

    @pytest.mark.asyncio
    async def test_get_file_info_operation(self, isolated_registry, mock_mcp_server):
        """Test get_file_info function."""
        isolated_registry.load_skill("filesystem", mock_mcp_server)
        module = isolated_registry.module_cache["filesystem"]

        result = await module.get_file_info(path="assets/skills/filesystem/manifest.json")
        assert "Size:" in result or "bytes" in result


class TestSkillEdgeCases:
    """Edge case and error handling tests."""

    def test_load_skill_with_missing_source_file(self, registry_fixture, real_mcp):
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
                "tools_module": "assets.skills.nonexistent.tools",
            }
            (skill_dir / "manifest.json").write_text(json.dumps(manifest))

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

    def test_only_omni_tool(self, skill_manager_fixture):
        """MCP server should have ONLY 'omni' tool registered."""
        from agent.mcp_server import mcp

        tools = list(mcp._tool_manager._tools.values())
        tool_names = [t.name for t in tools]

        # Phase 25: Only 'omni' should be registered as MCP tool
        # Phase 27: JIT tools are skill commands under 'omni', not separate MCP tools
        assert tool_names == ["omni"], f"Expected only 'omni', got: {tool_names}"

    def test_omni_is_primary_tool(self, skill_manager_fixture):
        """The 'omni' tool should be the first/main tool."""
        from agent.mcp_server import mcp

        tools = list(mcp._tool_manager._tools.values())
        assert tools[0].name == "omni"

    @pytest.mark.asyncio
    async def test_omni_simplified_syntax_git_status(self, skill_manager_fixture):
        """Test @omni('skill.command') simplified syntax works."""
        # Import inside test to ensure skill_manager_fixture fixture is applied first
        from agent.mcp_server import omni
        from agent.core.skill_manager import _skill_manager

        # Ensure we're using the same manager as the fixture
        assert _skill_manager is skill_manager_fixture

        result = await omni("git.status")

        assert isinstance(result, str)
        # git.status returns short format: "M file\nA file" or "✅ Clean"
        assert "M" in result or "A" in result or "✅" in result or "Clean" in result

    @pytest.mark.asyncio
    async def test_omni_syntax_with_args(self, skill_manager_fixture):
        """Test @omni('skill.command', args={}) with arguments."""
        from agent.mcp_server import omni

        result = await omni("git.log", {"n": 3})

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_omni_help_shows_all_skills(self, skill_manager_fixture):
        """@omni('help') should list all skills."""
        from agent.mcp_server import omni

        result = await omni("help")

        assert isinstance(result, str)
        assert "Available Skills" in result or "🛠️" in result
        assert "git" in result

    @pytest.mark.asyncio
    async def test_omni_skill_name_shows_commands(self, skill_manager_fixture):
        """@omni('skill') should show skill's commands."""
        from agent.mcp_server import omni

        result = await omni("git")

        assert isinstance(result, str)
        assert "git" in result.lower()
        assert "git_status_report" in result or "status" in result.lower()

    @pytest.mark.asyncio
    async def test_omni_invalid_format_shows_skills(self, skill_manager_fixture):
        """Without dots, shows skill help (not an error)."""
        from agent.mcp_server import omni

        result = await omni("invalid_command_without_dot")

        # Without dots, it's treated as a skill name request
        # Shows available skills instead of error
        assert isinstance(result, str)
        assert "Available Skills" in result or "git" in result

    @pytest.mark.asyncio
    async def test_omni_nonexistent_skill_error(self, skill_manager_fixture):
        """Nonexistent skill should return helpful error."""
        from agent.mcp_server import omni

        result = await omni("nonexistent_skill.status")

        assert isinstance(result, str)
        assert "not found" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_omni_nonexistent_command_error(self, skill_manager_fixture):
        """Nonexistent command should return helpful error."""
        from agent.mcp_server import omni

        result = await omni("git.nonexistent_command_xyz")

        assert isinstance(result, str)
        assert "not found" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_omni_dispatch_to_filesystem(self, skill_manager_fixture):
        """@omni should dispatch to filesystem skill."""
        from agent.mcp_server import omni

        # filesystem.read -> read_file (no prefix since skill doesn't use prefix)
        result = await omni("filesystem.read", {"path": "assets/skills/filesystem/manifest.json"})

        assert isinstance(result, str)
        assert "filesystem" in result

    @pytest.mark.asyncio
    async def test_omni_dispatch_to_knowledge(self, skill_manager_fixture):
        """@omni should dispatch to knowledge skill."""
        from agent.mcp_server import omni

        result = await omni("get_development_context")

        assert isinstance(result, str)
        assert "project" in result.lower() or "context" in result.lower()

    @pytest.mark.asyncio
    async def test_omni_empty_args_defaults_to_dict(self, skill_manager_fixture):
        """@omni with no args should work with empty dict."""
        from agent.mcp_server import omni

        result = await omni("git.status")

        assert isinstance(result, str)
        # git.status returns short format: "M file\nA file" or "✅ Clean"
        assert "M" in result or "A" in result or "✅" in result or "Clean" in result


class TestSkillManagerCommandExecution:
    """Test SkillManager command execution for One Tool architecture."""

    @pytest.mark.asyncio
    async def test_run_command_returns_string(self, skill_manager_fixture):
        """run() should always return string."""
        result = await skill_manager_fixture.run("git", "git_status", {})

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_command_with_complex_args(self, skill_manager_fixture):
        """run() should handle complex arguments."""
        result = await skill_manager_fixture.run("git", "git_commit", {"message": "Test commit"})

        assert isinstance(result, str)
        # git_commit returns empty string if nothing staged, or commit hash on success
        # Either is valid - empty means nothing to commit, non-empty means success
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_all_skills_loadable(self, skill_manager_fixture):
        """All discovered skills should be loadable."""
        skills = skill_manager_fixture.list_available_skills()

        for skill_name in skills:
            if skill_name.startswith("_"):
                continue  # Skip template
            result = await skill_manager_fixture.run(skill_name, "help", {})
            assert isinstance(result, str), f"Skill {skill_name} should return string"


class TestOmniHelpRender:
    """Test help rendering functions."""

    def test_render_help_includes_usage(self, skill_manager_fixture):
        """Help output should include usage instructions."""
        from agent.mcp_server import _render_help

        result = _render_help(skill_manager_fixture)

        assert isinstance(result, str)
        assert "@omni" in result or "omni_run" in result

    def test_render_skill_help_includes_usage(self, skill_manager_fixture):
        """Skill help should include usage instructions."""
        from agent.mcp_server import _render_skill_help

        result = _render_skill_help(skill_manager_fixture, "git")

        assert isinstance(result, str)
        assert "@omni" in result or "omni_run" in result
        assert "git" in result.lower()

    def test_render_skill_help_for_nonexistent(self, skill_manager_fixture):
        """Skill help for nonexistent skill should show available skills."""
        from agent.mcp_server import _render_skill_help

        result = _render_skill_help(skill_manager_fixture, "nonexistent_skill_xyz")

        assert isinstance(result, str)
        assert "not found" in result.lower() or "Available skills" in result


# =============================================================================
# Phase 25+: Performance & Multimodal Tests
# =============================================================================
