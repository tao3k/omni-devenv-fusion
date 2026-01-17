"""
Agent Tests - Decorator Validation Tests (Phase 36)

公共测试库：验证 @skill_command 装饰器正确性

Usage:
    # 直接运行
    python -m pytest packages/python/agent/src/agent/tests/test_decorators.py -v

    # 被其他测试引用
    from agent.tests.test_decorators import TestSkillCommandDecorators
"""

import sys
import pytest
import types
from pathlib import Path


def _setup_skill_package_context(skill_name: str, skills_root: Path):
    """Set up package context for skill module loading."""
    from importlib import util
    from common.gitops import get_project_root

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

    # Pre-load decorators module (required for @skill_command)
    if "agent.skills.decorators" not in sys.modules:
        decorators_path = project_root / "packages/python/agent/src/agent/skills/decorators.py"
        if decorators_path.exists():
            spec = util.spec_from_file_location("agent.skills.decorators", decorators_path)
            if spec and spec.loader:
                module = util.module_from_spec(spec)
                sys.modules["agent.skills.decorators"] = module
                sys.modules["agent.skills"].decorators = module
                spec.loader.exec_module(module)

    # Ensure 'agent.skills.{skill_name}' package exists
    skill_pkg_name = f"agent.skills.{skill_name}"
    if skill_pkg_name not in sys.modules:
        skill_pkg = types.ModuleType(skill_pkg_name)
        skill_pkg.__path__ = [str(skills_root / skill_name)]
        skill_pkg.__file__ = str(skills_root / skill_name / "__init__.py")
        sys.modules[skill_pkg_name] = skill_pkg


def load_skill_module(skill_name: str):
    """Load a skill module for testing with proper package context.

    Phase 63: Loads from scripts/ instead of tools.py.
    Handles both __init__.py and scripts/*.py files.
    """
    from common.skills_path import SKILLS_DIR

    skills_dir = SKILLS_DIR()
    scripts_dir = skills_dir / skill_name / "scripts"

    # Set up package context BEFORE loading (enables agent.skills.git.scripts imports)
    _setup_skill_package_context(skill_name, skills_dir)

    import importlib.util

    # Phase 63: Check if __init__.py has content, otherwise look for scripts/*.py
    init_path = scripts_dir / "__init__.py" if scripts_dir.exists() else None

    if init_path and init_path.exists():
        init_content = init_path.read_text().strip()
        if init_content:
            # __init__.py has content, load it
            tools_path = init_path
            module_name = f"{skill_name}_scripts"
        else:
            # __init__.py is empty, try to find the main script file
            # Look for a script file that matches the skill name or has the main functions
            script_files = list(scripts_dir.glob("*.py"))
            script_files = [f for f in script_files if f.name not in ("__init__.py", "__pycache__")]

            if script_files:
                # Use the first non-init script file as the main module
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

    spec = importlib.util.spec_from_file_location(module_name, str(tools_path))
    module = importlib.util.module_from_spec(spec)
    # Set __package__ for proper import resolution
    module.__package__ = f"agent.skills.{skill_name}"
    spec.loader.exec_module(module)
    return module


class TestSkillScriptDecorators:
    """Test @skill_command decorator functionality (Phase 63).

    Note: Uses _is_skill_command marker and _skill_config.
    """

    @pytest.fixture
    def terminal_module(self):
        """Load terminal skill module."""
        return load_skill_module("terminal")

    @pytest.fixture
    def filesystem_module(self):
        """Load filesystem skill module."""
        return load_skill_module("filesystem")

    def test_run_task_has_marker(self, terminal_module):
        """run_task should have _is_skill_command marker."""
        assert hasattr(terminal_module.run_task, "_is_skill_command")
        assert terminal_module.run_task._is_skill_command is True

    def test_run_task_has_config(self, terminal_module):
        """run_task should have _skill_config."""
        assert hasattr(terminal_module.run_task, "_skill_config")
        config = terminal_module.run_task._skill_config
        assert config["name"] == "run_task"
        assert config["category"] == "workflow"

    def test_read_file_has_marker(self, filesystem_module):
        """read_file should have _is_skill_command marker."""
        assert hasattr(filesystem_module.read_file, "_is_skill_command")
        assert filesystem_module.read_file._is_skill_command is True

    def test_read_file_has_config(self, filesystem_module):
        """read_file should have _skill_config."""
        assert hasattr(filesystem_module.read_file, "_skill_config")
        config = filesystem_module.read_file._skill_config
        assert config["name"] == "read_file"
        assert config["category"] == "read"

    def test_write_file_has_config(self, filesystem_module):
        """write_file should have _skill_config."""
        assert hasattr(filesystem_module.write_file, "_skill_config")
        config = filesystem_module.write_file._skill_config
        assert config["name"] == "write_file"
        assert config["category"] == "write"

    def test_list_directory_has_config(self, filesystem_module):
        """list_directory should have _skill_config."""
        assert hasattr(filesystem_module.list_directory, "_skill_config")
        config = filesystem_module.list_directory._skill_config
        assert config["name"] == "list_directory"
        assert config["category"] == "read"

    def test_get_file_info_has_config(self, filesystem_module):
        """get_file_info should have _skill_config."""
        assert hasattr(filesystem_module.get_file_info, "_skill_config")
        config = filesystem_module.get_file_info._skill_config
        assert config["name"] == "get_file_info"
        assert config["category"] == "read"
