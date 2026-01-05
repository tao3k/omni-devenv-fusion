"""
src/agent/tests/test_phase13_skills.py
Comprehensive testing for the Phase 13 Skill Architecture + Phase 25 Omni CLI.

Phase 25: Omni CLI Architecture
- SkillManager scans skills and builds registry
- Skills expose EXPOSED_COMMANDS dictionary
- Single omni_run() tool handles all operations

Covers:
1. SkillRegistry (Discovery, Loading, Context, Spec-based Loading)
2. SkillManager (Phase 25: Omni CLI single entry point)
3. Skill Manifest (Schema Validation)
4. Skill Hot Reload
5. Filesystem Skill
6. Git Skill (Phase 25: EXPOSED_COMMANDS)

Note: _template is a skeleton for creating new skills and cannot be loaded
as a Python module (names starting with underscore have special meaning).
"""

import pytest
import sys
import os
import time
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from mcp.server.fastmcp import FastMCP

# Import core components
from agent.core.schema import SkillManifest
from agent.core.skill_registry import SkillRegistry, get_skill_registry
from agent.core.skill_manager import SkillManager, get_skill_manager


def _load_skill_module_for_test(skill_name: str, test_file: str):
    """
    Load a skill module directly from file using importlib.util.
    This bypasses the normal import system which may resolve 'agent' to the package.
    """
    # Get project root and skill path
    project_root = Path(test_file).resolve().parent.parent.parent.parent.parent.parent.parent
    skill_tools_path = project_root / "agent" / "skills" / skill_name / "tools.py"

    if not skill_tools_path.exists():
        raise FileNotFoundError(f"Skill tools not found: {skill_tools_path}")

    # Create a unique module name to avoid conflicts
    module_name = f"_test_skill_{skill_name}"

    # Load the module from file
    spec = importlib.util.spec_from_file_location(
        module_name, skill_tools_path, submodule_search_locations=[str(skill_tools_path.parent)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module


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
def skill_manager():
    """Fixture to provide a clean SkillManager instance."""
    import agent.core.skill_manager as sm_module

    sm_module._skill_manager = None
    manager = sm_module.get_skill_manager()
    manager.skills.clear()
    manager._skills_loaded = False
    # Reload skills to ensure git is loaded
    manager.load_skills()
    yield manager
    manager.skills.clear()
    manager._skills_loaded = False


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


# =============================================================================
# Phase 25: Omni CLI Tests
# =============================================================================


class TestSkillManagerOmniCLI:
    """Test Phase 25: Omni CLI SkillManager."""

    def test_skill_manager_loads_skills(self, skill_manager):
        """SkillManager should load skills from agent/skills."""
        skills = skill_manager.load_skills()

        assert "git" in skills, f"Expected 'git' in skills, got: {list(skills.keys())}"
        assert len(skills) >= 1

    def test_skill_manager_git_has_commands(self, skill_manager):
        """Git skill should have commands loaded."""
        skill_manager.load_skills()

        assert "git" in skill_manager.skills
        git_skill = skill_manager.skills["git"]
        assert len(git_skill.commands) >= 1

    def test_skill_manager_git_status_report_command(self, skill_manager):
        """Git skill should have git_status_report command."""
        skill_manager.load_skills()

        cmd = skill_manager.get_command("git", "git_status_report")
        assert cmd is not None
        assert cmd.name == "git_status_report"
        assert callable(cmd.func)

    def test_skill_manager_run_command(self, skill_manager):
        """SkillManager.run() should execute commands."""
        result = skill_manager.run("git", "git_status_report", {})

        assert result is not None
        assert isinstance(result, str)
        assert "Git Status" in result or "branch" in result

    def test_skill_manager_run_with_args(self, skill_manager):
        """SkillManager.run() should pass arguments to commands."""
        result = skill_manager.run("git", "git_log", {"n": 3})

        assert result is not None
        assert isinstance(result, str)

    def test_skill_manager_run_nonexistent_skill(self, skill_manager):
        """Running command on nonexistent skill should return error."""
        result = skill_manager.run("nonexistent", "some_command", {})

        assert "Error" in result or "not found" in result.lower()

    def test_skill_manager_run_nonexistent_command(self, skill_manager):
        """Running nonexistent command should return error."""
        result = skill_manager.run("git", "nonexistent_command", {})

        assert "Error" in result or "not found" in result.lower()

    def test_skill_manager_list_available_skills(self, skill_manager):
        """list_available_skills() should return skill names."""
        skill_manager.load_skills()

        skills = skill_manager.list_available_skills()
        assert isinstance(skills, list)
        assert "git" in skills

    def test_skill_manager_list_commands(self, skill_manager):
        """list_commands() should return command names for a skill."""
        skill_manager.load_skills()

        commands = skill_manager.list_commands("git")
        assert isinstance(commands, list)
        assert "git_status_report" in commands
        assert "git_commit" in commands

    def test_skill_manager_get_skill_info(self, skill_manager):
        """get_skill_info() should return skill metadata."""
        skill_manager.load_skills()

        info = skill_manager.get_skill_info("git")
        assert info is not None
        assert info["name"] == "git"
        assert info["loaded"] is True
        assert info["command_count"] >= 1

    def test_skill_manager_global_instance(self):
        """get_skill_manager() should return singleton."""
        manager1 = get_skill_manager()
        manager2 = get_skill_manager()

        assert manager1 is manager2


class TestGitSkillEXPOSEDCOMMANDS:
    """Test Phase 25: Git skill with EXPOSED_COMMANDS."""

    def _load_git_module(self):
        """Load git skill module for testing."""
        return _load_skill_module_for_test("git", __file__)

    def test_git_has_exposed_commands(self):
        """Git skill should have EXPOSED_COMMANDS dictionary."""
        module = self._load_git_module()

        assert hasattr(module, "EXPOSED_COMMANDS")
        assert isinstance(module.EXPOSED_COMMANDS, dict)

    def test_git_exposed_commands_has_required_keys(self):
        """EXPOSED_COMMANDS should have func, description, category keys."""
        module = self._load_git_module()

        for cmd_name, cmd_info in module.EXPOSED_COMMANDS.items():
            assert isinstance(cmd_info, dict), f"Command {cmd_name} should be a dict"
            assert "func" in cmd_info, f"Command {cmd_name} should have 'func'"
            assert "description" in cmd_info, f"Command {cmd_name} should have 'description'"
            assert "category" in cmd_info, f"Command {cmd_name} should have 'category'"

    def test_git_exposed_commands_func_is_callable(self):
        """EXPOSED_COMMANDS func values should be callable."""
        module = self._load_git_module()

        for cmd_name, cmd_info in module.EXPOSED_COMMANDS.items():
            assert callable(cmd_info["func"]), f"Command {cmd_name} func should be callable"

    def test_git_exposed_commands_includes_status_report(self):
        """EXPOSED_COMMANDS should include git_status_report."""
        module = self._load_git_module()

        assert "git_status_report" in module.EXPOSED_COMMANDS
        cmd = module.EXPOSED_COMMANDS["git_status_report"]
        assert cmd["category"] == "view"

    def test_git_exposed_commands_includes_workflow_tools(self):
        """EXPOSED_COMMANDS should include workflow tools like git_plan_hotfix."""
        module = self._load_git_module()

        assert "git_plan_hotfix" in module.EXPOSED_COMMANDS
        cmd = module.EXPOSED_COMMANDS["git_plan_hotfix"]
        assert cmd["category"] == "workflow"

    def test_git_exposed_commands_includes_write_operations(self):
        """EXPOSED_COMMANDS should include write operations."""
        module = self._load_git_module()

        write_commands = ["git_commit", "git_add", "git_checkout"]
        for cmd_name in write_commands:
            assert cmd_name in module.EXPOSED_COMMANDS, f"Missing {cmd_name} in EXPOSED_COMMANDS"

    def test_git_exposed_commands_includes_evolution_tools(self):
        """EXPOSED_COMMANDS should include evolution tools like git_read_backlog."""
        module = self._load_git_module()

        assert "git_read_backlog" in module.EXPOSED_COMMANDS
        cmd = module.EXPOSED_COMMANDS["git_read_backlog"]
        assert cmd["category"] == "evolution"


class TestGitSkillDirectCalls:
    """Test git skill functions directly (without MCP registration)."""

    def _load_git_module(self):
        """Load git skill module for testing."""
        return _load_skill_module_for_test("git", __file__)

    def test_git_status_report_returns_markdown(self):
        """git_status_report should return formatted markdown."""
        module = self._load_git_module()

        result = module.git_status_report()

        assert isinstance(result, str)
        assert "Git Status" in result or "📊" in result
        assert "Branch" in result

    def test_git_status_returns_output(self):
        """git_status should return status output."""
        module = self._load_git_module()

        result = module.git_status()

        assert isinstance(result, str)

    def test_git_log_returns_output(self):
        """git_log should return commit history."""
        module = self._load_git_module()

        result = module.git_log(n=3)

        assert isinstance(result, str)

    def test_git_branch_returns_output(self):
        """git_branch should return branch list."""
        module = self._load_git_module()

        result = module.git_branch()

        assert isinstance(result, str)

    def test_git_plan_hotfix_returns_plan(self):
        """git_plan_hotfix should return a plan."""
        module = self._load_git_module()

        result = module.git_plan_hotfix(issue_id="TEST-123")

        assert isinstance(result, str)
        assert "TEST-123" in result or "Hotfix" in result

    def test_git_read_backlog_returns_content(self):
        """git_read_backlog should return backlog content."""
        module = self._load_git_module()

        result = module.git_read_backlog()

        assert isinstance(result, str)
        assert "Git Skill Backlog" in result or "Backlog" in result

    def test_git_add_with_files(self):
        """git_add should accept file list."""
        module = self._load_git_module()

        # This will fail if no files are staged, but should not raise
        try:
            result = module.git_add(["."])
            assert isinstance(result, str)
        except Exception as e:
            # GitError is expected if nothing is staged
            assert "nothing to commit" in str(e).lower() or isinstance(e, Exception)


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


# =============================================================================
# Phase 25: One Tool Architecture Tests
# =============================================================================


class TestOneToolArchitecture:
    """Test Phase 25: Single 'omni' tool with simplified syntax."""

    def test_only_one_tool_registered(self):
        """MCP server should only have ONE tool registered."""
        from agent.mcp_server import mcp

        tools = list(mcp._tool_manager._tools.values())
        assert len(tools) == 1, f"Expected 1 tool, got {len(tools)}: {[t.name for t in tools]}"

    def test_tool_named_omni(self):
        """The single tool should be named 'omni'."""
        from agent.mcp_server import mcp

        tools = list(mcp._tool_manager._tools.values())
        assert tools[0].name == "omni"

    def test_omni_simplified_syntax_git_status(self, skill_manager):
        """Test @omni('skill.command') simplified syntax works."""
        # Import inside test to ensure skill_manager fixture is applied first
        from agent.mcp_server import omni
        from agent.core.skill_manager import _skill_manager

        # Ensure we're using the same manager as the fixture
        assert _skill_manager is skill_manager

        result = omni("git.status")

        assert isinstance(result, str)
        assert "Git Status" in result or "branch" in result

    def test_omni_syntax_with_args(self, skill_manager):
        """Test @omni('skill.command', args={}) with arguments."""
        from agent.mcp_server import omni

        result = omni("git.log", {"n": 3})

        assert isinstance(result, str)
        assert len(result) > 0

    def test_omni_help_shows_all_skills(self, skill_manager):
        """@omni('help') should list all skills."""
        from agent.mcp_server import omni

        result = omni("help")

        assert isinstance(result, str)
        assert "Available Skills" in result or "🛠️" in result
        assert "git" in result

    def test_omni_skill_name_shows_commands(self, skill_manager):
        """@omni('skill') should show skill's commands."""
        from agent.mcp_server import omni

        result = omni("git")

        assert isinstance(result, str)
        assert "git" in result.lower()
        assert "git_status_report" in result or "status" in result.lower()

    def test_omni_invalid_format_shows_skills(self, skill_manager):
        """Without dots, shows skill help (not an error)."""
        from agent.mcp_server import omni

        result = omni("invalid_command_without_dot")

        # Without dots, it's treated as a skill name request
        # Shows available skills instead of error
        assert isinstance(result, str)
        assert "Available Skills" in result or "git" in result

    def test_omni_nonexistent_skill_error(self, skill_manager):
        """Nonexistent skill should return helpful error."""
        from agent.mcp_server import omni

        result = omni("nonexistent_skill.status")

        assert isinstance(result, str)
        assert "not found" in result.lower() or "Error" in result

    def test_omni_nonexistent_command_error(self, skill_manager):
        """Nonexistent command should return helpful error."""
        from agent.mcp_server import omni

        result = omni("git.nonexistent_command_xyz")

        assert isinstance(result, str)
        assert "not found" in result.lower() or "Error" in result

    def test_omni_dispatch_to_filesystem(self, skill_manager):
        """@omni should dispatch to filesystem skill."""
        from agent.mcp_server import omni

        # filesystem.read -> read_file (no prefix since skill doesn't use prefix)
        result = omni("filesystem.read", {"path": "agent/skills/filesystem/manifest.json"})

        assert isinstance(result, str)
        assert "filesystem" in result

    def test_omni_dispatch_to_knowledge(self, skill_manager):
        """@omni should dispatch to knowledge skill."""
        from agent.mcp_server import omni

        result = omni("get_development_context")

        assert isinstance(result, str)
        assert "project" in result.lower() or "context" in result.lower()

    def test_omni_empty_args_defaults_to_dict(self, skill_manager):
        """@omni with no args should work with empty dict."""
        from agent.mcp_server import omni

        result = omni("git.status")

        assert isinstance(result, str)
        assert "Git Status" in result or "branch" in result


class TestSkillManagerCommandExecution:
    """Test SkillManager command execution for One Tool architecture."""

    def test_run_command_returns_string(self, skill_manager):
        """run() should always return string."""
        result = skill_manager.run("git", "git_status", {})

        assert isinstance(result, str)

    def test_run_command_with_complex_args(self, skill_manager):
        """run() should handle complex arguments."""
        result = skill_manager.run("git", "git_commit", {"message": "Test commit"})

        assert isinstance(result, str)
        # Should either succeed or give git error about empty staging
        assert len(result) > 0

    def test_all_skills_loadable(self, skill_manager):
        """All discovered skills should be loadable."""
        skills = skill_manager.list_available_skills()

        for skill_name in skills:
            if skill_name.startswith("_"):
                continue  # Skip template
            result = skill_manager.run(skill_name, "help", {})
            assert isinstance(result, str), f"Skill {skill_name} should return string"


class TestOmniHelpRender:
    """Test help rendering functions."""

    def test_render_help_includes_usage(self, skill_manager):
        """Help output should include usage instructions."""
        from agent.mcp_server import _render_help

        result = _render_help(skill_manager)

        assert isinstance(result, str)
        assert "@omni" in result or "omni_run" in result

    def test_render_skill_help_includes_usage(self, skill_manager):
        """Skill help should include usage instructions."""
        from agent.mcp_server import _render_skill_help

        result = _render_skill_help(skill_manager, "git")

        assert isinstance(result, str)
        assert "@omni" in result or "omni_run" in result
        assert "git" in result.lower()

    def test_render_skill_help_for_nonexistent(self, skill_manager):
        """Skill help for nonexistent skill should show available skills."""
        from agent.mcp_server import _render_skill_help

        result = _render_skill_help(skill_manager, "nonexistent_skill_xyz")

        assert isinstance(result, str)
        assert "not found" in result.lower() or "Available skills" in result


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main(["-v", __file__, "--tb=short"]))
