"""
Agent Tests - Decorator Validation Tests

公共测试库：验证 @skill_command 装饰器正确性

Usage:
    # 直接运行
    python -m pytest packages/python/foundation/tests/unit/api/test_decorators.py -v

Note:
    Tests actual skill modules (filesystem, terminal) which use
    omni.core.skills.script_loader.skill_command decorator.
    This decorator sets individual attributes (_command_name, _category, etc.)
    not the _skill_config dict used by omni.foundation.api.decorators.skill_command.
"""

import sys
import types
from pathlib import Path

import pytest


def _setup_skill_package_context(skill_name: str, skills_root: Path):
    """Set up package context for skill module loading."""
    from importlib import util

    from omni.foundation.runtime.gitops import get_project_root

    project_root = get_project_root()

    # Ensure 'agent' package exists
    if "agent" not in sys.modules:
        agent_src = project_root / "packages/python/agent/src/agent"
        agent_pkg = types.ModuleType("agent")
        agent_pkg.__path__ = [str(agent_src)]
        agent_pkg.__file__ = str(agent_src / "__init__.py")
        sys.modules["agent"] = agent_pkg

    # Ensure 'agent.skills' package exists
    if "agent.skills" not in sys.modules:
        skills_pkg = types.ModuleType("agent.skills")
        skills_pkg.__path__ = [str(skills_root)]
        skills_pkg.__file__ = str(skills_root / "__init__.py")
        sys.modules["agent.skills"] = skills_pkg
        sys.modules["agent"].skills = skills_pkg

    # Ensure 'agent.skills.{skill_name}' package exists
    skill_pkg_name = f"agent.skills.{skill_name}"
    if skill_pkg_name not in sys.modules:
        skill_pkg = types.ModuleType(skill_pkg_name)
        skill_pkg.__path__ = [str(skills_root / skill_name)]
        skill_pkg.__file__ = str(skills_root / skill_name / "__init__.py")
        sys.modules[skill_pkg_name] = skill_pkg


def load_skill_module(skill_name: str):
    """Load a skill module for testing with proper package context.

    Loads from scripts/ instead of tools.py.
    Handles both __init__.py and scripts/*.py files.
    """
    from omni.foundation.config.skills import SKILLS_DIR

    skills_dir = SKILLS_DIR()
    scripts_dir = skills_dir / skill_name / "scripts"

    # Set up package context BEFORE loading (enables agent.skills.git.scripts imports)
    _setup_skill_package_context(skill_name, skills_dir)

    import importlib.util

    # Check if __init__.py has content, otherwise look for scripts/*.py
    init_path = scripts_dir / "__init__.py" if scripts_dir.exists() else None

    if init_path and init_path.exists():
        init_content = init_path.read_text()
        # Check if __init__.py has actual code (not just docstring)
        # Strip docstring and check for real code
        lines = init_content.split("\n")
        code_lines = []
        in_docstring = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = not in_docstring
            elif not in_docstring and stripped and not stripped.startswith("#"):
                code_lines.append(line)

        if code_lines:
            # __init__.py has actual code, load it
            tools_path = init_path
            module_name = f"{skill_name}_scripts"
        else:
            # __init__.py is empty or only has docstring, use io.py
            script_files = list(scripts_dir.glob("*.py"))
            script_files = [f for f in script_files if f.name not in ("__init__.py", "__pycache__")]

            if script_files:
                tools_path = script_files[0]
                module_name = f"{skill_name}_{script_files[0].stem}"
            else:
                raise FileNotFoundError(f"No script files found in {scripts_dir}")
    elif scripts_dir.exists():
        # No __init__.py, look for script files
        script_files = list(scripts_dir.glob("*.py"))
        script_files = [f for f in script_files if f.name not in ("__init__.py", "__pycache__")]

        if script_files:
            tools_path = script_files[0]
            module_name = f"{skill_name}_{script_files[0].stem}"
        else:
            raise FileNotFoundError(f"No script files found in {scripts_dir}")
    else:
        # Fallback to tools.py (legacy support for git skill)
        tools_path = skills_dir / skill_name / "tools.py"
        module_name = f"{skill_name}_tools"

    if not tools_path.exists():
        raise FileNotFoundError(f"Skill module not found: {tools_path}")

    # Determine module name based on file
    script_stem = tools_path.stem
    if script_stem == "__init__":
        module_name = f"{skill_name}_scripts"
    else:
        module_name = f"{skill_name}_{script_stem}"

    # Clear any cached version
    if module_name in sys.modules:
        del sys.modules[module_name]
    scripts_alias = f"{skill_name}_scripts"
    if scripts_alias in sys.modules:
        del sys.modules[scripts_alias]

    spec = importlib.util.spec_from_file_location(module_name, str(tools_path))
    module = importlib.util.module_from_spec(spec)
    module.__package__ = f"agent.skills.{skill_name}"
    spec.loader.exec_module(module)

    # Register with consistent alias for testing
    sys.modules[scripts_alias] = module

    return module


class TestSkillScriptDecorators:
    """Test @skill_command decorator functionality.

    Note: Tests both:
    - omni.core.skills.script_loader.skill_command (terminal skill)
      Sets: _is_skill_command, _command_name, _category, etc.
    - omni.foundation.api.decorators.skill_command (filesystem skill)
      Sets: _is_skill_command, _skill_config dict
    """

    @pytest.fixture
    def terminal_module(self):
        """Load terminal skill module (commands.py specifically)."""
        from omni.foundation.config.skills import SKILLS_DIR
        from importlib import util
        import types
        import sys

        skills_dir = SKILLS_DIR()
        scripts_dir = skills_dir / "terminal" / "scripts"
        commands_path = scripts_dir / "commands.py"

        # Set up package context
        _setup_skill_package_context("terminal", skills_dir)

        # Load commands.py specifically
        spec = util.spec_from_file_location("terminal_commands", commands_path)
        if spec and spec.loader:
            module = types.ModuleType("terminal_commands")
            module.__package__ = "omni.skills.terminal.scripts"
            sys.modules["terminal_commands"] = spec.loader.exec_module(module)
            return module

        raise RuntimeError(f"Failed to load terminal commands.py")

    @pytest.fixture
    def filesystem_module(self):
        """Load filesystem skill module."""
        # Force fresh load by clearing any cached module
        module_name = "filesystem_scripts"
        if module_name in sys.modules:
            del sys.modules[module_name]
        return load_skill_module("filesystem")

    def test_run_task_has_marker(self, terminal_module):
        """run_task should have _is_skill_command marker."""
        assert hasattr(terminal_module.run_task, "_is_skill_command")
        assert terminal_module.run_task._is_skill_command is True

    def test_run_task_has_command_name(self, terminal_module):
        """run_task should have _skill_config with name."""
        assert hasattr(terminal_module.run_task, "_skill_config")
        assert terminal_module.run_task._skill_config["name"] == "run_task"

    def test_run_task_has_category(self, terminal_module):
        """run_task should have _skill_config with category."""
        assert hasattr(terminal_module.run_task, "_skill_config")
        assert terminal_module.run_task._skill_config["category"] == "workflow"

    def test_read_file_has_marker(self, filesystem_module):
        """read_file should have _is_skill_command marker."""
        assert hasattr(filesystem_module.read_file, "_is_skill_command")
        assert filesystem_module.read_file._is_skill_command is True

    def test_read_file_has_command_name(self, filesystem_module):
        """read_file should have _skill_config with name."""
        assert hasattr(filesystem_module.read_file, "_skill_config")
        assert filesystem_module.read_file._skill_config["name"] == "read_file"

    def test_read_file_has_category(self, filesystem_module):
        """read_file should have _skill_config with category."""
        assert hasattr(filesystem_module.read_file, "_skill_config")
        assert filesystem_module.read_file._skill_config["category"] == "read"

    def test_write_file_has_command_name(self, filesystem_module):
        """write_file should have _skill_config with name."""
        assert hasattr(filesystem_module.write_file, "_skill_config")
        assert filesystem_module.write_file._skill_config["name"] == "write_file"

    def test_write_file_has_category(self, filesystem_module):
        """write_file should have _skill_config with category."""
        assert hasattr(filesystem_module.write_file, "_skill_config")
        assert filesystem_module.write_file._skill_config["category"] == "write"

    def test_list_directory_has_command_name(self, filesystem_module):
        """list_directory should have _skill_config with name."""
        assert hasattr(filesystem_module.list_directory, "_skill_config")
        assert filesystem_module.list_directory._skill_config["name"] == "list_directory"

    def test_list_directory_has_category(self, filesystem_module):
        """list_directory should have _skill_config with category."""
        assert hasattr(filesystem_module.list_directory, "_skill_config")
        assert filesystem_module.list_directory._skill_config["category"] == "read"

    def test_get_file_info_has_command_name(self, filesystem_module):
        """get_file_info should have _skill_config with name."""
        assert hasattr(filesystem_module.get_file_info, "_skill_config")
        assert filesystem_module.get_file_info._skill_config["name"] == "get_file_info"

    def test_get_file_info_has_category(self, filesystem_module):
        """get_file_info should have _skill_config with category."""
        assert hasattr(filesystem_module.get_file_info, "_skill_config")
        assert filesystem_module.get_file_info._skill_config["category"] == "read"
