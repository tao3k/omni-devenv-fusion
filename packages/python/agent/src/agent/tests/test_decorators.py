"""
Agent Tests - Decorator Validation Tests (Phase 35.1)

公共测试库：验证 @skill_command 装饰器正确性

Usage:
    # 直接运行
    python -m pytest packages/python/agent/src/agent/tests/test_decorators.py -v

    # 被其他测试引用
    from agent.tests.test_decorators import TestSkillCommandDecorators
"""

import pytest
import inspect
import sys
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
    """Load a skill module for testing with proper package context."""
    from common.skills_path import SKILLS_DIR

    skills_dir = SKILLS_DIR()
    tools_path = skills_dir / skill_name / "tools.py"

    # Set up package context BEFORE loading (enables agent.skills.git.scripts imports)
    _setup_skill_package_context(skill_name, skills_dir)

    import importlib.util

    spec = importlib.util.spec_from_file_location(f"{skill_name}_tools", str(tools_path))
    module = importlib.util.module_from_spec(spec)
    # Set __package__ for proper import resolution
    module.__package__ = f"agent.skills.{skill_name}"
    spec.loader.exec_module(module)
    return module


def get_command_names(skill_name: str) -> list[str]:
    """Get command names from a skill (as registered with SkillManager)."""
    from agent.core.skill_manager import get_skill_manager
    from common.skills_path import SKILLS_DIR

    manager = get_skill_manager()
    skill_path = SKILLS_DIR(skill=skill_name)
    if isinstance(skill_path, str):
        skill_path = Path(skill_path)
    manager.load_skill(skill_path)
    return manager.get_commands(skill_name)


class TestFilesystemSkillDecorators:
    """Test Filesystem skill @skill_command decorators."""

    @pytest.fixture
    def fs_module(self):
        """Load filesystem skill module."""
        return load_skill_module("filesystem")

    def test_fs_commands_registered(self):
        """Filesystem commands should be registered."""
        commands = get_command_names("filesystem")
        # Filesystem uses skill prefix naming
        assert "filesystem_list_directory" in commands, f"list_directory not in {commands}"
        assert "filesystem_read_file" in commands
        assert "filesystem_write_file" in commands

    def test_fs_list_directory_has_marker(self, fs_module):
        """list_directory should have _is_skill_command marker."""
        assert hasattr(fs_module.list_directory, "_is_skill_command")
        assert fs_module.list_directory._is_skill_command is True

    def test_fs_list_directory_has_config(self, fs_module):
        """list_directory should have _skill_config."""
        assert hasattr(fs_module.list_directory, "_skill_config")
        config = fs_module.list_directory._skill_config
        assert config["name"] == "filesystem_list_directory"
        assert config["category"] == "read"

    def test_fs_read_file_has_config(self, fs_module):
        """read_file should have _skill_config."""
        assert hasattr(fs_module.read_file, "_skill_config")
        config = fs_module.read_file._skill_config
        assert config["name"] == "filesystem_read_file"
        assert config["category"] == "read"

    def test_fs_write_file_has_config(self, fs_module):
        """write_file should have _skill_config."""
        assert hasattr(fs_module.write_file, "_skill_config")
        config = fs_module.write_file._skill_config
        assert config["name"] == "filesystem_write_file"
        assert config["category"] == "write"


class TestSkillsDirDiscovery:
    """Discover and run tests from skills_dirs/tests directories."""

    def get_skills_with_tests(self) -> list[tuple[str, Path]]:
        """Find all skills that have tests directories."""
        from common.skills_path import SKILLS_DIR

        skills_dir = Path(SKILLS_DIR())
        skills_with_tests = []
        if not skills_dir.exists():
            return skills_with_tests

        for skill_dir in sorted(skills_dir.iterdir()):
            if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
                tests_dir = skill_dir / "tests"
                if tests_dir.exists() and any(tests_dir.glob("test_*.py")):
                    skills_with_tests.append((skill_dir.name, tests_dir))
        return skills_with_tests

    def test_skills_with_tests_exist(self):
        """Verify skills have tests directories."""
        skills_with_tests = self.get_skills_with_tests()
        assert len(skills_with_tests) >= 2, (
            f"Expected at least 2 skills with tests, found: {skills_with_tests}"
        )
        skill_names = [name for name, _ in skills_with_tests]
        assert "git" in skill_names, "git skill should have tests"
        assert "knowledge" in skill_names, "knowledge skill should have tests"

    def test_git_tests_directory_exists(self):
        """Verify git skill tests directory exists."""
        from common.skills_path import SKILLS_DIR

        git_tests = Path(SKILLS_DIR()) / "git" / "tests"
        assert git_tests.exists(), "git/tests should exist"
        assert any(git_tests.glob("test_*.py")), "git/tests should have test files"

    def test_knowledge_tests_directory_exists(self):
        """Verify knowledge skill tests directory exists."""
        from common.skills_path import SKILLS_DIR

        knowledge_tests = Path(SKILLS_DIR()) / "knowledge" / "tests"
        assert knowledge_tests.exists(), "knowledge/tests should exist"
        assert any(knowledge_tests.glob("test_*.py")), "knowledge/tests should have test files"

    def test_knowledge_test_discovers_commands(self):
        """Knowledge tests should discover all commands."""
        from common.skills_path import SKILLS_DIR

        knowledge_tests = Path(SKILLS_DIR()) / "knowledge" / "tests"
        test_file = knowledge_tests / "test_knowledge_commands.py"
        assert test_file.exists(), "test_knowledge_commands.py should exist"

        # Verify test file has expected test functions (simplified format with @test decorator)
        import ast

        with open(test_file) as f:
            content = f.read()

        tree = ast.parse(content)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        # Check for key test functions in the simplified @test decorator format
        assert "test_get_development_context_exists" in func_names, (
            "Should have test_get_development_context_exists function"
        )
        assert "test_consult_architecture_doc_exists" in func_names, (
            "Should have test_consult_architecture_doc_exists function"
        )
