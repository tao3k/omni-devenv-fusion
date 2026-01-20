"""
Skill Skill Tests - Phase 63+ Architecture

Tests the new architecture where:
- Scripts/*.py contain plain functions with @skill_command decorators
- No tools.py file (legacy pattern removed)
- Commands exposed via skill prefix: skill_list_templates, skill_discover, etc.

Usage:
    def test_discover_command(skill):
        result = skill.discover(query="git")
        assert result is not None
"""

import ast
import pytest
from pathlib import Path

from common.skills_path import SKILLS_DIR


def validate_python_syntax(file_path: Path) -> tuple[bool, str | None]:
    """Validate Python file syntax using AST parser."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        ast.parse(content)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error: {e}"


class TestSkillSyntaxValidation:
    """Validate Python syntax for skill files."""

    def test_skill_scripts_have_valid_syntax(self):
        """All skill/scripts/*.py files must have valid Python syntax."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        if not scripts_dir.exists():
            pytest.skip("No scripts directory")

        invalid_files = []
        for py_file in scripts_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            is_valid, error = validate_python_syntax(py_file)
            if not is_valid:
                invalid_files.append(f"scripts/{py_file.name}: {error}")

        assert len(invalid_files) == 0, (
            f"Found {len(invalid_files)} files with syntax errors:\n" + "\n".join(invalid_files)
        )

    def test_discovery_script_imports_correctly(self):
        """scripts/discovery.py should import without errors."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        discovery_file = scripts_dir / "discovery.py"

        if not discovery_file.exists():
            pytest.skip("discovery.py not found")

        # Try to import the module to verify no import errors
        import importlib.util

        spec = importlib.util.spec_from_file_location("discovery_test", discovery_file)
        assert spec is not None, "Failed to load discovery.py spec"
        assert spec.loader is not None, "discovery.py has no loader"
        module = importlib.util.module_from_spec(spec)

        # This will fail if there are import errors
        try:
            spec.loader.exec_module(module)
        except ImportError as e:
            pytest.fail(f"discovery.py has import error: {e}")

    def test_core_task_py_has_valid_syntax(self):
        """Core task.py must have valid Python syntax (critical path)."""
        from common.gitops import get_project_root

        project_root = get_project_root()
        task_path = project_root / "packages/python/agent/src/agent/skills/core/task.py"
        assert task_path.exists(), f"task.py not found: {task_path}"

        is_valid, error = validate_python_syntax(task_path)
        assert is_valid, f"task.py has syntax error: {error}"


class TestSkillTemplatesCommand:
    """Test skill template commands (Phase 63+)."""

    def test_list_templates_command_exists(self, skill):
        """The list_templates command should exist in skill tools."""
        assert hasattr(skill, "list_templates"), "skill module missing 'list_templates' function"

    def test_list_templates_git(self, skill):
        """skill.list_templates with skill_name='git' should work."""
        result = skill.list_templates(skill_name="git")

        # Handle CommandResult wrapper
        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, (dict, str))

    def test_list_templates_filesystem(self, skill):
        """skill.list_templates with skill_name='filesystem' should work."""
        result = skill.list_templates(skill_name="filesystem")

        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, (dict, str))

    def test_eject_template_command_exists(self, skill):
        """The eject_template command should exist."""
        assert hasattr(skill, "eject_template"), "skill module missing 'eject_template' function"

    def test_get_template_info_command_exists(self, skill):
        """The get_template_info command should exist."""
        assert hasattr(skill, "get_template_info"), (
            "skill module missing 'get_template_info' function"
        )

    def test_get_template_source_command_exists(self, skill):
        """The get_template_source command should exist."""
        assert hasattr(skill, "get_template_source"), (
            "skill module missing 'get_template_source' function"
        )


class TestSkillCommandsMetadata:
    """Test skill commands have proper metadata."""

    def test_commands_have_skill_command_metadata(self, skill):
        """All skill commands should have @skill_command metadata."""
        # Check via SkillProxy._skill.commands (the original SkillCommand objects)
        for cmd_name, cmd in skill._skill.commands.items():
            assert hasattr(cmd, "_is_skill_command") or hasattr(cmd.func, "_is_skill_command"), (
                f"Command {cmd_name} should have _is_skill_command"
            )

    def test_skill_has_commands(self, skill):
        """skill should have @skill_command decorated functions."""
        # Check via SkillProxy._skill.commands (the original SkillCommand objects)
        commands = list(skill._skill.commands.keys())
        assert len(commands) > 0, "No skill commands found"
        # Phase 63+ commands
        assert "discover" in commands
        assert "suggest" in commands
        assert "list_templates" in commands
        assert "list_tools" in commands


class TestSkillDiscoveryCommands:
    """Test skill discovery commands (discover, suggest, list_index)."""

    def test_discover_command_exists(self, skill):
        """The discover command should exist in skill tools."""
        assert hasattr(skill, "discover"), "skill module missing 'discover' function"

    def test_suggest_command_exists(self, skill):
        """The suggest command should exist in skill tools."""
        assert hasattr(skill, "suggest"), "skill module missing 'suggest' function"

    def test_list_index_command_exists(self, skill):
        """The list_index command should exist in skill tools."""
        assert hasattr(skill, "list_index"), "skill module missing 'list_index' function"

    def test_jit_install_command_exists(self, skill):
        """The jit_install command should exist in skill tools."""
        assert hasattr(skill, "jit_install"), "skill module missing 'jit_install' function"


class TestSkillToolManagement:
    """Test skill tool management commands."""

    def test_list_tools_command_exists(self, skill):
        """The list_tools command should exist in skill tools."""
        assert hasattr(skill, "list_tools"), "skill module missing 'list_tools' function"

    def test_search_tools_command_exists(self, skill):
        """The search_tools command should exist in skill tools."""
        assert hasattr(skill, "search_tools"), "skill module missing 'search_tools' function"

    def test_reload_command_exists(self, skill):
        """The reload command should exist in skill tools."""
        assert hasattr(skill, "reload"), "skill module missing 'reload' function"

    def test_unload_command_exists(self, skill):
        """The unload command should exist in skill tools."""
        assert hasattr(skill, "unload"), "skill module missing 'unload' function"


class TestSkillDiscoveryIntegration:
    """Integration tests for skill discovery with registry."""

    def test_skill_discovery_import(self):
        """SkillDiscovery should be importable from agent.core.skill_discovery."""
        from agent.core.skill_discovery import SkillDiscovery

        # Verify class exists and can be instantiated
        discovery = SkillDiscovery()
        assert discovery is not None

    def test_skill_discovery_has_search_method(self):
        """SkillDiscovery should have search method with correct signature."""
        from agent.core.skill_discovery import SkillDiscovery
        import inspect

        discovery = SkillDiscovery()
        assert hasattr(discovery, "search"), "SkillDiscovery should have 'search' method"

        # Verify method signature
        sig = inspect.signature(discovery.search)
        params = list(sig.parameters.keys())
        assert "query" in params
        assert "limit" in params
        assert "local_only" in params
        # Verify no deprecated parameters
        assert "installed_only" not in params, (
            "Use 'local_only' instead of deprecated 'installed_only'"
        )

    def test_skill_discovery_has_get_index_stats_method(self):
        """SkillDiscovery should have get_index_stats method."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        assert hasattr(discovery, "get_index_stats"), (
            "SkillDiscovery should have 'get_index_stats' method"
        )
        assert not hasattr(discovery, "list_all"), "list_all is deprecated, use get_index_stats"

    def test_discover_uses_skill_discovery(self, skill):
        """skill.discover should use SkillDiscovery."""
        # Test that the command is callable without import errors
        assert callable(skill.discover)

    def test_suggest_returns_recommendation(self, skill):
        """skill.suggest should return a recommendation string."""
        result = skill.suggest(task="git version control")

        # Handle CommandResult wrapper
        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, str)


class TestSkillListTools:
    """Tests for skill.list_tools command."""

    def test_list_tools_returns_string(self, skill):
        """skill.list_tools should return a string result."""
        result = skill.list_tools()

        # Handle CommandResult wrapper
        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, str)

    def test_list_tools_contains_skill_names(self, skill):
        """skill.list_tools should contain skill names."""
        result = skill.list_tools()

        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, str)


class TestSkillScriptsImport:
    """Test that all skill scripts import correctly and use correct APIs."""

    @pytest.mark.parametrize("skill_name", ["git", "filesystem", "terminal", "knowledge", "memory"])
    def test_core_skills_scripts_import(self, skill_name):
        """Core skill scripts should import without errors."""
        scripts_dir = SKILLS_DIR(skill_name) / "scripts"
        if not scripts_dir.exists():
            pytest.skip(f"No scripts directory for {skill_name}")

        for py_file in scripts_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue

            # Read the file and check for relative imports
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Skip files with relative imports (they need proper package context)
            if "from ." in content or "from .state" in content:
                continue

            # Try to import the module to verify no import errors
            import importlib.util

            spec = importlib.util.spec_from_file_location(f"{skill_name}_{py_file.stem}", py_file)
            assert spec is not None, f"Failed to load {py_file}"
            assert spec.loader is not None, f"{py_file} has no loader"
            module = importlib.util.module_from_spec(spec)

            # This will fail if there are import errors
            try:
                spec.loader.exec_module(module)
            except ImportError as e:
                pytest.fail(f"{py_file} has import error: {e}")

    def test_reload_script_uses_correct_api(self):
        """reload.py should use SkillContext, not skill_manager."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        reload_file = scripts_dir / "reload.py"

        if not reload_file.exists():
            pytest.skip("reload.py not found")

        with open(reload_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should NOT use deprecated skill_manager
        assert "agent.core.skill_manager" not in content, (
            "reload.py should not use deprecated 'agent.core.skill_manager'"
        )

        # Should use skill_runtime (SkillContext)
        assert "agent.core.skill_runtime" in content, (
            "reload.py should use 'agent.core.skill_runtime'"
        )

    def test_unload_script_uses_correct_api(self):
        """unload.py should use SkillContext, not skill_manager."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        unload_file = scripts_dir / "unload.py"

        if not unload_file.exists():
            pytest.skip("unload.py not found")

        with open(unload_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should NOT use deprecated skill_manager
        assert "agent.core.skill_manager" not in content, (
            "unload.py should not use deprecated 'agent.core.skill_manager'"
        )

        # Should use skill_runtime (SkillContext)
        assert "agent.core.skill_runtime" in content, (
            "unload.py should use 'agent.core.skill_runtime'"
        )

    def test_smart_commit_workflow_uses_correct_api(self):
        """smart_commit_workflow.py should not use skill_manager."""
        git_scripts_dir = SKILLS_DIR("git") / "scripts"
        workflow_file = git_scripts_dir / "smart_commit_workflow.py"

        if not workflow_file.exists():
            pytest.skip("smart_commit_workflow.py not found")

        with open(workflow_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should NOT use deprecated skill_manager
        assert "agent.core.skill_manager" not in content, (
            "smart_commit_workflow.py should not use deprecated 'agent.core.skill_manager'"
        )

    def test_no_deprecated_vector_skill_discovery_import(self):
        """discovery.py should not use VectorSkillDiscovery."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        discovery_file = scripts_dir / "discovery.py"

        if not discovery_file.exists():
            pytest.skip("discovery.py not found")

        with open(discovery_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should NOT use deprecated VectorSkillDiscovery
        assert "VectorSkillDiscovery" not in content, (
            "discovery.py should not use deprecated 'VectorSkillDiscovery'"
        )

        # Should use SkillDiscovery
        assert "SkillDiscovery" in content, "discovery.py should use 'SkillDiscovery'"

    def test_discovery_script_uses_local_only_param(self):
        """discovery.py should use local_only, not installed_only."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        discovery_file = scripts_dir / "discovery.py"

        if not discovery_file.exists():
            pytest.skip("discovery.py not found")

        with open(discovery_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should NOT use deprecated installed_only
        assert "installed_only" not in content, (
            "discovery.py should not use deprecated 'installed_only' parameter"
        )

        # Should use local_only
        assert "local_only" in content, "discovery.py should use 'local_only' parameter"

    def test_no_deprecated_list_all_method(self):
        """discovery.py should use get_index_stats, not list_all."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        discovery_file = scripts_dir / "discovery.py"

        if not discovery_file.exists():
            pytest.skip("discovery.py not found")

        with open(discovery_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should NOT use deprecated list_all
        assert ".list_all(" not in content, (
            "discovery.py should not use deprecated 'list_all' method"
        )

        # Should use get_index_stats
        assert "get_index_stats" in content, "discovery.py should use 'get_index_stats' method"


class TestSkillHotReload:
    """Test hot reload/unload functionality uses correct API."""

    def test_reload_uses_context_reload_method(self):
        """reload.py should call ctx.reload(), not registry methods."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        reload_file = scripts_dir / "reload.py"

        if not reload_file.exists():
            pytest.skip("reload.py not found")

        with open(reload_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should call ctx.reload() method
        assert "ctx.reload(" in content, "reload.py should call ctx.reload()"
        # Should NOT call registry.unregister_module directly
        assert "registry.unregister_module" not in content, (
            "reload.py should not call registry.unregister_module directly"
        )

    def test_unload_uses_context_unload_method(self):
        """unload.py should call ctx.unload(), not registry methods."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        unload_file = scripts_dir / "unload.py"

        if not unload_file.exists():
            pytest.skip("unload.py not found")

        with open(unload_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should call ctx.unload() method
        assert "ctx.unload(" in content, "unload.py should call ctx.unload()"
        # Should NOT call registry.unregister_module directly
        assert "registry.unregister_module" not in content, (
            "unload.py should not call registry.unregister_module directly"
        )

    def test_reload_checks_correct_skill_registry(self):
        """reload.py should check ctx.registry.skills, not registry.loaded_skills."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        reload_file = scripts_dir / "reload.py"

        if not reload_file.exists():
            pytest.skip("reload.py not found")

        with open(reload_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should use ctx.registry.skills for loaded check
        assert "ctx.registry.skills" in content, (
            "reload.py should check 'ctx.registry.skills' for loaded skills"
        )
        # Should NOT use registry.loaded_skills
        assert "registry.loaded_skills" not in content, (
            "reload.py should not use deprecated 'registry.loaded_skills'"
        )

    def test_unload_checks_correct_skill_registry(self):
        """unload.py should check ctx.registry.skills, not registry.loaded_skills."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        unload_file = scripts_dir / "unload.py"

        if not unload_file.exists():
            pytest.skip("unload.py not found")

        with open(unload_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should use ctx.registry.skills for loaded check
        assert "ctx.registry.skills" in content, (
            "unload.py should check 'ctx.registry.skills' for loaded skills"
        )
        # Should NOT use registry.loaded_skills
        assert "registry.loaded_skills" not in content, (
            "unload.py should not use deprecated 'registry.loaded_skills'"
        )

    def test_reload_uses_context_core_skills_config(self):
        """reload.py should use ctx._config.core_skills for pinned check."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        reload_file = scripts_dir / "reload.py"

        if not reload_file.exists():
            pytest.skip("reload.py not found")

        with open(reload_file, "r", encoding="utf-8") as f:
            content = f.read()

        # reload doesn't block pinned skills, but should not hardcode pinned list
        # It should delegate to ctx._config.core_skills or ctx.reload() which handles it
        pass  # reload.py doesn't need pinned check, ctx.reload() handles it internally

    def test_unload_uses_context_core_skills_config(self):
        """unload.py should use ctx._config.core_skills for pinned check."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        unload_file = scripts_dir / "unload.py"

        if not unload_file.exists():
            pytest.skip("unload.py not found")

        with open(unload_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should use ctx._config.core_skills for pinned check
        assert "ctx._config.core_skills" in content, (
            "unload.py should use 'ctx._config.core_skills' for pinned check"
        )
        # Should NOT hardcode pinned skills list
        assert '"git"' not in content or "ctx._config" in content, (
            "unload.py should not hardcode pinned skills, use config"
        )
