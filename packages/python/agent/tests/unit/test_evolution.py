"""
test_evolution.py - Unit Tests for Self-Evolution Module

Tests the Harvester and SkillFactory components for:
- Session analysis and skill extraction
- Rule/preference learning
- Code generation from patterns

Also tests the Immune System:
- Static analysis (Rust: omni-ast)
- Dynamic simulation (Rust: omni-security)
- System integration
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

from omni.agent.core.evolution.harvester import (
    Harvester,
    CandidateSkill,
    ExtractedLesson,
)
from omni.agent.core.evolution.factory import SkillFactory

# Immune System Tests
from omni.agent.core.evolution.immune import (
    SecurityViolation,
    StaticValidator,
    SimulationResult,
    SkillSimulator,
    ImmuneReport,
    ImmuneSystem,
)


class TestCandidateSkill:
    """Tests for CandidateSkill model."""

    def test_create_candidate_skill(self):
        """Should create a valid CandidateSkill instance."""
        skill = CandidateSkill(
            intent="fix_python_bug",
            description="Fix common Python bugs in files",
            tool_chain=[
                {"tool": "filesystem.read_file", "purpose": "Read the file"},
                {"tool": "terminal.run_command", "purpose": "Run linter"},
            ],
            variables=["file_path", "error_message"],
        )

        assert skill.intent == "fix_python_bug"
        assert skill.description == "Fix common Python bugs in files"
        assert len(skill.tool_chain) == 2
        assert len(skill.variables) == 2
        assert skill.success_count == 1  # Default

    def test_candidate_skill_with_success_count(self):
        """Should respect custom success_count."""
        skill = CandidateSkill(
            intent="test_skill",
            description="Test skill",
            tool_chain=[],
            variables=[],
            success_count=5,
        )
        assert skill.success_count == 5


class TestExtractedLesson:
    """Tests for ExtractedLesson model."""

    def test_create_extracted_lesson(self):
        """Should create a valid ExtractedLesson instance."""
        lesson = ExtractedLesson(
            rule="Always use type hints",
            domain="coding_style",
        )

        assert lesson.rule == "Always use type hints"
        assert lesson.domain == "coding_style"
        assert lesson.confidence == 1.0  # Default

    def test_lesson_with_confidence(self):
        """Should respect custom confidence."""
        lesson = ExtractedLesson(
            rule="Use f-strings",
            domain="python_style",
            confidence=0.85,
        )
        assert lesson.confidence == 0.85


class TestHarvester:
    """Tests for Harvester class."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock InferenceClient."""
        mock = MagicMock()
        mock.complete = AsyncMock()
        return mock

    @pytest.fixture
    def harvester(self, mock_llm):
        """Create a Harvester instance with mock LLM."""
        return Harvester(mock_llm)

    @pytest.mark.asyncio
    async def test_analyze_session_too_short(self, harvester):
        """Should return None for sessions with less than 3 messages."""
        history = [{"role": "user", "content": "hello"}]

        result = await harvester.analyze_session(history)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_session_no_exit_signal(self, harvester):
        """Should return None if session doesn't end with EXIT_LOOP_NOW."""
        history = [
            {"role": "user", "content": "Fix my code"},
            {"role": "assistant", "content": "I fixed it"},
        ]

        result = await harvester.analyze_session(history)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_session_success(self, harvester, mock_llm):
        """Should extract candidate skill from successful session."""
        # Setup mock LLM response
        mock_llm.complete = AsyncMock(
            return_value={
                "content": '{"intent": "refactor_python_file", "description": "Refactor Python files with best practices", "tool_chain": [{"tool": "filesystem.read_file", "purpose": "Read file content"}], "variables": ["file_path"]}'
            }
        )

        history = [
            {"role": "user", "content": "Refactor main.py"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "filesystem.read_file",
                            "arguments": '{"file_path": "main.py"}',
                        }
                    }
                ],
            },
            {
                "role": "user",
                "content": "[Tool: filesystem.read_file] File content here\nEXIT_LOOP_NOW",
            },
        ]

        result = await harvester.analyze_session(history)

        assert result is not None
        assert result.intent == "refactor_python_file"
        assert "Refactor Python files" in result.description
        assert len(result.tool_chain) == 1
        assert "file_path" in result.variables

    @pytest.mark.asyncio
    async def test_analyze_session_llm_returns_null_intent(self, harvester, mock_llm):
        """Should return None when LLM indicates workflow is not reusable."""
        mock_llm.complete = AsyncMock(return_value={"content": '{"intent": null}'})

        history = [
            {"role": "user", "content": "Fix bug"},
            {
                "role": "assistant",
                "tool_calls": [{"function": {"name": "test", "arguments": "{}"}}],
            },
            {"role": "user", "content": "EXIT_LOOP_NOW"},
        ]

        result = await harvester.analyze_session(history)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_session_no_tool_activity(self, harvester, mock_llm):
        """Should return None when not enough tool activity."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "EXIT_LOOP_NOW"},
        ]

        result = await harvester.analyze_session(history)
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_lessons_no_corrections(self, harvester):
        """Should return None when no correction patterns found."""
        history = [
            {"role": "user", "content": "Can you help me?"},
            {"role": "assistant", "content": "Sure!"},
        ]

        result = await harvester.extract_lessons(history)
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_lessons_success(self, harvester, mock_llm):
        """Should extract lesson from user corrections."""
        mock_llm.complete = AsyncMock(
            return_value={
                "content": '{"rule": "Always use async functions for I/O", "domain": "python_style", "confidence": 0.9}'
            }
        )

        history = [
            {"role": "user", "content": "No, use async instead of sync for file operations"},
            {"role": "assistant", "content": "Got it, will use async"},
        ]

        result = await harvester.extract_lessons(history)

        assert result is not None
        assert "async" in result.rule
        assert result.domain == "python_style"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_extract_lessons_no_clear_rule(self, harvester, mock_llm):
        """Should return None when LLM finds no clear rule."""
        mock_llm.complete = AsyncMock(return_value={"content": '{"rule": null}'})

        history = [
            {"role": "user", "content": "This is not what I wanted"},
        ]

        result = await harvester.extract_lessons(history)
        assert result is None

    @pytest.mark.asyncio
    async def test_detect_pattern_from_error(self, harvester, mock_llm):
        """Should extract error recovery pattern."""
        mock_llm.complete = AsyncMock(
            return_value={
                "content": '{"error_pattern": "import_error", "recovery_strategy": "use try/except", "prevention": "check dependencies first"}'
            }
        )

        result = await harvester.detect_pattern_from_error(
            error_msg="ModuleNotFoundError: No module named 'foo'",
            recovery_steps=[{"tool": "pip_install", "package": "foo"}],
        )

        assert result is not None
        assert result.get("error_pattern") == "import_error"


class TestSkillFactory:
    """Tests for SkillFactory class."""

    def test_sanitize_name_basic(self):
        """Should convert basic names to snake_case."""
        assert SkillFactory._sanitize_name("My Skill") == "my_skill"
        assert SkillFactory._sanitize_name("fix-bug") == "fix_bug"
        assert SkillFactory._sanitize_name("Refactor Code") == "refactor_code"

    def test_sanitize_name_removes_special_chars(self):
        """Should replace special characters with underscores."""
        assert SkillFactory._sanitize_name("test@#$skill") == "test___skill"
        assert SkillFactory._sanitize_name("my.skill.name") == "my_skill_name"

    def test_sanitize_name_handles_numbers(self):
        """Should handle names starting with numbers."""
        assert SkillFactory._sanitize_name("123test") == "skill_123test"

    def test_to_class_name(self):
        """Should convert snake_case to PascalCase."""
        assert SkillFactory._to_class_name("my_skill") == "MySkill"
        assert SkillFactory._to_class_name("fix_python_bug") == "FixPythonBug"

    def test_synthesize_creates_quarantine_file(self, tmp_path):
        """Should create skill file in quarantine directory."""
        candidate = CandidateSkill(
            intent="test_skill",
            description="A test skill",
            tool_chain=[{"tool": "filesystem.read_file", "purpose": "Read files"}],
            variables=["file_path"],
        )

        output_dir = tmp_path / "skills"
        path = SkillFactory.synthesize(candidate, output_dir)

        assert "quarantine" in path
        assert "test_skill.py" in path
        assert Path(path).exists()

        content = Path(path).read_text()
        assert "test_skill" in content
        assert "A test skill" in content
        assert "filesystem.read_file" in content

    def test_synthesize_creates_quarantine_dir(self, tmp_path):
        """Should create quarantine directory if it doesn't exist."""
        candidate = CandidateSkill(
            intent="new_skill",
            description="New skill",
            tool_chain=[],
            variables=[],
        )

        output_dir = tmp_path / "skills"
        SkillFactory.synthesize(candidate, output_dir)

        quarantine_dir = output_dir / "quarantine"
        assert quarantine_dir.exists()
        assert quarantine_dir.is_dir()

    def test_synthesize_with_multiple_variables(self, tmp_path):
        """Should handle multiple variables correctly."""
        candidate = CandidateSkill(
            intent="complex_workflow",
            description="A complex workflow",
            tool_chain=[
                {"tool": "tool1", "purpose": "First"},
                {"tool": "tool2", "purpose": "Second"},
            ],
            variables=["file_path", "output_dir", "config_file"],
        )

        output_dir = tmp_path / "skills"
        path = SkillFactory.synthesize(candidate, output_dir)

        content = Path(path).read_text()
        assert "file_path" in content
        assert "output_dir" in content
        assert "config_file" in content

    def test_generate_skill_code(self):
        """Should generate skill code without writing to disk."""
        code = SkillFactory.generate_skill_code(
            skill_name="my_skill",
            description="A test skill",
            tool_chain=[{"tool": "test_tool", "purpose": "Testing"}],
            variables=["param1", "param2"],
        )

        assert "my_skill" in code
        assert "A test skill" in code
        assert "test_tool" in code
        assert "param1" in code
        assert "param2" in code

    def test_skill_code_has_placeholder(self, tmp_path):
        """Generated skill should have NotImplementedError placeholder."""
        candidate = CandidateSkill(
            intent="placeholder_test",
            description="Test placeholder",
            tool_chain=[{"tool": "test", "purpose": "test"}],
            variables=[],
        )

        output_dir = tmp_path / "skills"
        path = SkillFactory.synthesize(candidate, output_dir)

        content = Path(path).read_text()
        assert "raise NotImplementedError" in content


class TestEvolutionIntegration:
    """Integration tests for the evolution module."""

    @pytest.mark.asyncio
    async def test_harvester_extracts_from_real_history(self):
        """Test harvester with realistic conversation history."""
        # This simulates a real-world scenario
        history = [
            {"role": "user", "content": "Create a new Python file with a class"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "terminal.run_command",
                            "arguments": '{"cmd": "touch myclass.py"}',
                        }
                    }
                ],
            },
            {
                "role": "user",
                "content": "[Tool: terminal.run_command] Command executed\nEXIT_LOOP_NOW",
            },
        ]

        with patch("omni.agent.core.evolution.harvester.InferenceClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.complete = AsyncMock(
                return_value={
                    "content": '{"intent": "create_python_file", "description": "Create new Python files with class template", "tool_chain": [{"tool": "terminal.run_command", "purpose": "Create the file"}], "variables": ["filename", "class_name"]}'
                }
            )
            MockClient.return_value = mock_instance

            harvester = Harvester(mock_instance)
            result = await harvester.analyze_session(history)

            assert result is not None
            assert result.intent == "create_python_file"

    def test_factory_with_special_characters(self, tmp_path):
        """Factory should handle skill names with special characters."""
        candidate = CandidateSkill(
            intent="fix/backslash\\issues",
            description="Fix path issues",
            tool_chain=[],
            variables=[],
        )

        output_dir = tmp_path / "skills"
        path = SkillFactory.synthesize(candidate, output_dir)

        # Should not crash and should sanitize the name
        assert Path(path).exists()
        assert "fix_backslash_issues" in path


# =============================================================================
# Immune System Tests
# =============================================================================


class TestSecurityViolation:
    """Tests for SecurityViolation model."""

    def test_create_security_violation(self):
        """Should create a valid SecurityViolation instance."""
        violation = SecurityViolation(
            rule_id="SEC-IMPORT-001",
            description="Forbidden import: 'os' is not allowed",
            line=5,
            snippet="import os",
        )

        assert violation.rule_id == "SEC-IMPORT-001"
        assert violation.description == "Forbidden import: 'os' is not allowed"
        assert violation.line == 5
        assert violation.snippet == "import os"

    def test_security_violation_repr(self):
        """Should have readable string representation."""
        violation = SecurityViolation(
            rule_id="SEC-CALL-002",
            description="Dangerous call: 'eval()' is not allowed",
            line=10,
            snippet="eval(x)",
        )

        repr_str = repr(violation)
        assert "SEC-CALL-002" in repr_str
        assert "eval()" in repr_str
        assert "Line 10" in repr_str

    def test_security_violation_to_dict(self):
        """Should convert to dictionary correctly."""
        violation = SecurityViolation(
            rule_id="SEC-PATTERN-001",
            description="Suspicious pattern detected",
            line=3,
            snippet="getattr(obj, name)",
        )

        data = violation.to_dict()
        assert data["rule_id"] == "SEC-PATTERN-001"
        assert data["line"] == 3
        assert "getattr" in data["snippet"]


class TestStaticValidator:
    """Tests for StaticValidator class."""

    def test_scan_safe_code(self, tmp_path):
        """Should pass safe code without violations."""
        safe_code = '''
def hello(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"

class MyClass:
    def method(self):
        pass
'''
        file_path = tmp_path / "safe_skill.py"
        file_path.write_text(safe_code)

        is_safe, violations = StaticValidator.scan(file_path)

        assert is_safe is True
        assert len(violations) == 0

    def test_scan_forbidden_import(self, tmp_path):
        """Should detect forbidden imports."""
        dangerous_code = """
import os
def read_file(path):
    return os.read(path)
"""
        file_path = tmp_path / "dangerous_skill.py"
        file_path.write_text(dangerous_code)

        is_safe, violations = StaticValidator.scan(file_path)

        assert is_safe is False
        assert len(violations) > 0
        # Should have import violation
        import_violations = [v for v in violations if "IMPORT" in v.rule_id]
        assert len(import_violations) > 0

    def test_scan_dangerous_calls(self, tmp_path):
        """Should detect dangerous function calls."""
        dangerous_code = """
def execute_code(code_str):
    result = eval(code_str)
    return result
"""
        file_path = tmp_path / "dangerous_skill.py"
        file_path.write_text(dangerous_code)

        is_safe, violations = StaticValidator.scan(file_path)

        assert is_safe is False
        # Should detect eval() call
        call_violations = [v for v in violations if "CALL" in v.rule_id or "PATTERN" in v.rule_id]
        assert len(call_violations) > 0

    def test_scan_content_directly(self):
        """Should scan content directly without file."""
        safe_code = "def hello(): return 'world'"

        is_safe, violations = StaticValidator.scan_content(safe_code, "test.py")

        assert is_safe is True
        assert len(violations) == 0

    def test_quick_check(self):
        """Should provide fast boolean check."""
        safe_code = "def hello(): pass"
        dangerous_code = "import os"

        assert StaticValidator.quick_check(safe_code) is True
        assert StaticValidator.quick_check(dangerous_code) is False

    def test_non_utf8_file_skipped(self, tmp_path):
        """Should skip non-UTF8 files gracefully."""
        # Create a binary file
        binary_path = tmp_path / "binary.bin"
        binary_path.write_bytes(b"\x80\x81\x82\xff")

        is_safe, violations = StaticValidator.scan(binary_path)

        assert is_safe is True  # Should skip gracefully


class TestSimulationResult:
    """Tests for SimulationResult model."""

    def test_simulation_result_success(self):
        """Should handle successful simulation."""
        result = SimulationResult(
            success=True,
            stdout="TEST_PASSED",
            exit_code=0,
            duration_ms=150,
        )

        assert result.passed is True
        assert result.success is True
        assert result.stdout == "TEST_PASSED"
        assert result.exit_code == 0

    def test_simulation_result_failure(self):
        """Should handle failed simulation."""
        result = SimulationResult(
            success=False,
            stderr="Traceback (most recent call last):\n  ValueError: invalid",
            exit_code=1,
            duration_ms=50,
        )

        assert result.passed is False
        assert result.success is False
        assert "ValueError" in result.stderr

    def test_simulation_result_to_dict(self):
        """Should convert to dictionary correctly."""
        result = SimulationResult(
            success=True,
            stdout="All tests passed",
            exit_code=0,
            duration_ms=100,
        )

        data = result.to_dict()
        assert data["success"] is True
        assert data["duration_ms"] == 100


class TestSkillSimulator:
    """Tests for SkillSimulator class."""

    def test_simple_smoke_test_generation(self):
        """Should generate simple smoke test for skill without LLM."""
        simulator = SkillSimulator(llm_client=None)

        source_code = """
def hello(name: str) -> str:
    return f"Hello, {name}!"
"""
        test_code = simulator._simple_smoke_test(source_code, Path("hello_skill.py"))

        assert "TEST_PASSED" in test_code
        assert "hello_skill" in test_code

    def test_check_sandbox_available(self):
        """Should check sandbox availability."""
        simulator = SkillSimulator()
        # Sandbox may or may not be available depending on system
        # Just verify it doesn't crash
        try:
            result = simulator.check_sandbox_available()
            assert isinstance(result, bool)
        except Exception:
            pass  # Acceptable if Rust not available


class TestImmuneReport:
    """Tests for ImmuneReport model."""

    def test_immune_report_creation(self, tmp_path):
        """Should create valid ImmuneReport."""
        skill_path = tmp_path / "test_skill.py"

        report = ImmuneReport(
            skill_name="test_skill",
            skill_path=skill_path,
        )

        assert report.skill_name == "test_skill"
        assert report.skill_path == skill_path
        assert report.static_analysis_passed is False
        assert report.simulation_passed is False
        assert report.promoted is False

    def test_immune_report_with_violations(self, tmp_path):
        """Should include violations in report."""
        skill_path = tmp_path / "dangerous_skill.py"

        violation = SecurityViolation(
            rule_id="SEC-IMPORT-001",
            description="Forbidden import",
            line=1,
            snippet="import os",
        )

        report = ImmuneReport(
            skill_name="dangerous_skill",
            skill_path=skill_path,
            static_analysis_passed=False,
            static_violations=[violation],
        )

        assert report.static_analysis_passed is False
        assert len(report.static_violations) == 1
        assert report.static_violations[0].rule_id == "SEC-IMPORT-001"

    def test_immune_report_to_dict(self, tmp_path):
        """Should convert to dictionary correctly."""
        skill_path = tmp_path / "test_skill.py"

        report = ImmuneReport(
            skill_name="test_skill",
            skill_path=skill_path,
            static_analysis_passed=True,
        )

        data = report.to_dict()
        assert data["skill_name"] == "test_skill"
        assert data["static_analysis"]["passed"] is True

    def test_immune_report_summary(self, tmp_path):
        """Should generate readable summary."""
        skill_path = tmp_path / "test_skill.py"

        report = ImmuneReport(
            skill_name="test_skill",
            skill_path=skill_path,
            static_analysis_passed=True,
            simulation_passed=True,
            permission_check_passed=True,
            promoted=True,
        )

        summary = report.summary()
        assert "test_skill" in summary
        assert "PASSED" in summary
        assert "PROMOTED" in summary


class TestImmuneSystem:
    """Tests for ImmuneSystem class."""

    def test_immune_system_initialization(self, tmp_path):
        """Should initialize with correct settings."""
        immune = ImmuneSystem(
            quarantine_dir=tmp_path / "quarantine",
            require_simulation=False,
            llm_client=None,
        )

        assert immune.quarantine_dir == tmp_path / "quarantine"
        assert immune.require_simulation is False

    def test_immune_system_rejects_dangerous_code(self, tmp_path):
        """Should reject code with security violations."""
        dangerous_code = """
import os
import subprocess

def bad_function():
    eval("1+1")
"""
        file_path = tmp_path / "dangerous.py"
        file_path.write_text(dangerous_code)

        immune = ImmuneSystem(
            require_simulation=False,
            llm_client=None,
        )

        import asyncio

        report = asyncio.run(immune.process_candidate(file_path))

        assert report.static_analysis_passed is False
        assert report.promoted is False
        assert report.rejection_reason is not None

    def test_immune_system_promotes_safe_code(self, tmp_path):
        """Should promote code that passes all checks."""
        safe_code = '''
def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}!"
'''
        file_path = tmp_path / "safe_skill.py"
        file_path.write_text(safe_code)

        immune = ImmuneSystem(
            require_simulation=False,
            llm_client=None,
        )

        import asyncio

        report = asyncio.run(immune.process_candidate(file_path))

        assert report.static_analysis_passed is True
        assert report.promoted is True

    def test_immune_system_handles_nonexistent_file(self, tmp_path):
        """Should handle non-existent files gracefully."""
        non_existent = tmp_path / "does_not_exist.py"

        immune = ImmuneSystem(require_simulation=False)

        import asyncio

        report = asyncio.run(immune.process_candidate(non_existent))

        assert report.rejection_reason is not None
        assert "not found" in report.rejection_reason.lower()

    def test_immune_system_scan_directory(self, tmp_path):
        """Should scan all skills in directory."""
        # Create test skills
        safe_code = "def safe(): pass"
        dangerous_code = "import os"

        (tmp_path / "safe_skill.py").write_text(safe_code)
        (tmp_path / "dangerous_skill.py").write_text(dangerous_code)

        immune = ImmuneSystem(require_simulation=False)

        import asyncio

        reports = asyncio.run(immune.scan_directory(tmp_path))

        assert len(reports) == 2
        # One should be promoted, one rejected
        promoted = sum(1 for r in reports if r.promoted)
        assert promoted == 1


class TestRustImmuneBridge:
    """Tests for Rust Immune Bridge availability."""

    def test_rust_bridge_available(self):
        """Should check if Rust core is available."""
        from omni.foundation.bridge import rust_immune

        result = rust_immune.is_rust_available()
        assert isinstance(result, bool)

    def test_scan_code_security_function_exists(self):
        """Should have scan_code_security function."""
        from omni.foundation.bridge import rust_immune

        assert hasattr(rust_immune, "scan_code_security")
        assert callable(rust_immune.scan_code_security)

    def test_is_code_safe_function_exists(self):
        """Should have is_code_safe function."""
        from omni.foundation.bridge import rust_immune

        assert hasattr(rust_immune, "is_code_safe")
        assert callable(rust_immune.is_code_safe)

    def test_scan_code_security_safe_code(self):
        """Should return empty list for safe code."""
        from omni.foundation.bridge import rust_immune

        safe_code = "def hello(): return 'world'"
        is_safe, violations = rust_immune.scan_code_security(safe_code)

        assert is_safe is True
        assert violations == []

    def test_scan_code_security_dangerous_code(self):
        """Should detect violations in dangerous code."""
        from omni.foundation.bridge import rust_immune

        dangerous_code = "import os"
        is_safe, violations = rust_immune.scan_code_security(dangerous_code)

        assert is_safe is False
        assert len(violations) > 0
        assert violations[0]["rule_id"].startswith("SEC-")
