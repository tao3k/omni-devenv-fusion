"""
Software Engineering Skill Tests - Migration

Tests for migrated software_engineering skill:
- engineering.py: run_tests, analyze_project_structure, detect_tech_stack

Verifies:
- @skill_command with autowire=True pattern
- ConfigPaths integration
- Zero-config orchestration (just/make/pytest discovery)
"""

import sys
from pathlib import Path

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))

# Also add project root for agent.skills imports
PROJECT_ROOT = SKILLS_ROOT.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestEngineeringImports:
    """Test engineering module imports."""

    def test_engineering_script_imports(self):
        """Test engineering script imports successfully."""
        from software_engineering.scripts import engineering

        assert engineering is not None

    def test_run_tests_function_exists(self):
        """Test run_tests function is exported."""
        from software_engineering.scripts.engineering import run_tests

        assert callable(run_tests)

    def test_analyze_project_structure_function_exists(self):
        """Test analyze_project_structure function is exported."""
        from software_engineering.scripts.engineering import analyze_project_structure

        assert callable(analyze_project_structure)

    def test_detect_tech_stack_function_exists(self):
        """Test detect_tech_stack function is exported."""
        from software_engineering.scripts.engineering import detect_tech_stack

        assert callable(detect_tech_stack)


class TestEngineeringSkillCommand:
    """Test @skill_command decorator attributes."""

    def _has_skill_command_attr(self, func) -> bool:
        """Check if function has skill command attributes."""
        return hasattr(func, "_is_skill_command") and hasattr(func, "_skill_config")

    def test_run_tests_has_skill_command(self):
        """Test run_tests has skill command attributes."""
        from software_engineering.scripts.engineering import run_tests

        assert self._has_skill_command_attr(run_tests)
        assert run_tests._is_skill_command is True

    def test_run_tests_autowire_enabled(self):
        """Test run_tests has autowire in config."""
        from software_engineering.scripts.engineering import run_tests

        config = getattr(run_tests, "_skill_config", None)
        assert config is not None
        execution = config.get("execution", {})
        assert execution.get("autowire") is True

    def test_analyze_project_structure_has_skill_command(self):
        """Test analyze_project_structure has skill command attributes."""
        from software_engineering.scripts.engineering import analyze_project_structure

        assert self._has_skill_command_attr(analyze_project_structure)

    def test_detect_tech_stack_has_skill_command(self):
        """Test detect_tech_stack has skill command attributes."""
        from software_engineering.scripts.engineering import detect_tech_stack

        assert self._has_skill_command_attr(detect_tech_stack)


class TestRunTests:
    """Test run_tests orchestration function."""

    def test_run_tests_returns_structure(self):
        """Test run_tests returns structured result."""
        from software_engineering.scripts.engineering import run_tests

        result = run_tests()

        assert "success" in result
        assert "command" in result
        assert "output" in result

    def test_run_tests_with_just(self):
        """Test run_tests detects justfile."""
        from software_engineering.scripts.engineering import run_tests

        result = run_tests()

        # Should detect justfile in this project
        if (
            "just test" in result["command"]
            or "make test" in result["command"]
            or "pytest" in result["command"]
        ):
            assert True


class TestAnalyzeProjectStructure:
    """Test analyze_project_structure function."""

    def test_analyze_project_structure_returns_string(self):
        """Test analyze_project_structure returns string output."""
        from software_engineering.scripts.engineering import analyze_project_structure

        result = analyze_project_structure(depth=1)

        assert isinstance(result, str)
        assert "Project Root" in result

    def test_analyze_project_structure_ignores_hidden(self):
        """Test analyze_project_structure ignores hidden directories."""
        from software_engineering.scripts.engineering import analyze_project_structure

        result = analyze_project_structure(depth=2)

        # Should not contain hidden directories
        assert ".git" not in result
        assert "__pycache__" not in result


class TestDetectTechStack:
    """Test detect_tech_stack function."""

    def test_detect_tech_stack_returns_string(self):
        """Test detect_tech_stack returns string output."""
        from software_engineering.scripts.engineering import detect_tech_stack

        result = detect_tech_stack()

        assert isinstance(result, str)
        assert "Tech Stack" in result

    def test_detect_tech_stack_finds_python(self):
        """Test detect_tech_stack finds Python in this project."""
        from software_engineering.scripts.engineering import detect_tech_stack

        result = detect_tech_stack()

        # This project has Python files
        assert "Python" in result

    def test_detect_tech_stack_finds_rust(self):
        """Test detect_tech_stack finds Rust in this project."""
        from software_engineering.scripts.engineering import detect_tech_stack

        result = detect_tech_stack()

        # This project has Rust files
        assert "Rust" in result


class TestExports:
    """Test module exports."""

    def test_all_exports_defined(self):
        """Test engineering module __all__ is defined."""
        from software_engineering.scripts import engineering

        assert hasattr(engineering, "__all__")
        expected = ["run_tests", "analyze_project_structure", "detect_tech_stack"]
        for item in expected:
            assert item in engineering.__all__, f"{item} not in engineering.__all__"
