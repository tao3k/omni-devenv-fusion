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
from pathlib import Path


def load_skill_module(skill_name: str):
    """Load a skill module for testing."""
    from common.skills_path import SKILLS_DIR

    skills_dir = SKILLS_DIR()
    tools_path = skills_dir / skill_name / "tools.py"

    import importlib.util

    spec = importlib.util.spec_from_file_location(f"{skill_name}_tools", str(tools_path))
    module = importlib.util.module_from_spec(spec)
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


class TestGitSkillDecorators:
    """Test Git skill @skill_command decorators."""

    @pytest.fixture
    def git_module(self):
        """Load git skill module."""
        return load_skill_module("git")

    def test_git_commands_registered(self):
        """Git commands should be registered without skill prefix."""
        commands = get_command_names("git")
        # Git uses new naming convention (no prefix)
        assert "status" in commands, f"status not in {commands}"
        assert "branch" in commands
        assert "commit" in commands
        assert "log" in commands
        assert "diff" in commands
        assert "add" in commands

    def test_git_status_has_marker(self, git_module):
        """status should have _is_skill_command marker."""
        assert hasattr(git_module.status, "_is_skill_command")
        assert git_module.status._is_skill_command is True

    def test_git_status_has_config(self, git_module):
        """status should have _skill_config."""
        assert hasattr(git_module.status, "_skill_config")
        config = git_module.status._skill_config
        assert config["name"] == "status"
        assert config["category"] == "read"

    def test_git_branch_has_config(self, git_module):
        """branch should have _skill_config."""
        assert hasattr(git_module.branch, "_skill_config")
        config = git_module.branch._skill_config
        assert config["name"] == "branch"

    def test_git_commit_has_config(self, git_module):
        """commit should have _skill_config."""
        assert hasattr(git_module.commit, "_skill_config")
        config = git_module.commit._skill_config
        assert config["name"] == "commit"
        assert config["category"] == "write"

    def test_git_status_report_has_view_category(self, git_module):
        """status_report should have view category."""
        assert hasattr(git_module.status_report, "_skill_config")
        config = git_module.status_report._skill_config
        assert config["name"] == "status_report"
        assert config["category"] == "view"

    def test_git_hotfix_has_workflow_category(self, git_module):
        """hotfix should have workflow category."""
        assert hasattr(git_module.hotfix, "_skill_config")
        config = git_module.hotfix._skill_config
        assert config["name"] == "hotfix"
        assert config["category"] == "workflow"

    def test_git_read_backlog_has_evolution_category(self, git_module):
        """read_backlog should have evolution category."""
        assert hasattr(git_module.read_backlog, "_skill_config")
        config = git_module.read_backlog._skill_config
        assert config["name"] == "read_backlog"
        assert config["category"] == "evolution"


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


class TestSkillDirectCalls:
    """Test skill functions directly (without MCP registration)."""

    def _unwrap(self, result):
        """Unwrap CommandResult if needed."""
        from agent.skills.decorators import CommandResult

        if isinstance(result, CommandResult):
            return result.data if result.success else result.error
        return result

    def test_git_status_returns_output(self):
        """status should return status output."""
        module = load_skill_module("git")
        result = self._unwrap(module.status())
        assert isinstance(result, str)

    def test_git_log_returns_output(self):
        """log should return commit history."""
        module = load_skill_module("git")
        result = self._unwrap(module.log(n=3))
        assert isinstance(result, str)

    def test_git_branch_returns_output(self):
        """branch should return branch list."""
        module = load_skill_module("git")
        result = self._unwrap(module.branch())
        assert isinstance(result, str)

    def test_git_hotfix_returns_plan(self):
        """hotfix should return a plan."""
        module = load_skill_module("git")
        result = self._unwrap(module.hotfix(issue_id="TEST-123"))
        assert isinstance(result, str)
        assert "TEST-123" in result or "Hotfix" in result

    def test_git_read_backlog_returns_content(self):
        """read_backlog should return backlog content."""
        module = load_skill_module("git")
        result = self._unwrap(module.read_backlog())
        assert isinstance(result, str)
        assert "Backlog" in result


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
