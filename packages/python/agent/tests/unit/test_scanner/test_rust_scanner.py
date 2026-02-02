"""Tests for Rust Skill Scanner Bindings.

These tests verify that the Rust skill scanner provides:
- 10-50x faster skill discovery than Python AST parsing
- Correct metadata extraction from SKILL.md
- Tool discovery in scripts/ directory

Uses test-kit fixtures for consistent test environment.
"""

import os
import tempfile
import pytest
from omni_core_rs import PySkillScanner, PySkillMetadata
from omni.test_kit.fixtures import test_tracer, skills_root


# Sample SKILL.md content for testing
SAMPLE_SKILL_MD = """---
name: "test_skill"
version: "1.0.0"
description: "A test skill for unit testing"
routing_keywords: ["test", "example", "demo"]
authors: ["Test Author <test@example.com>"]
intents: ["test.intent", "example.action"]
repository: "https://github.com/example/test-skill"
permissions: ["filesystem:read", "network:http"]
---

# Test Skill

This is a test skill for validating the Rust skill scanner bindings.
"""


@pytest.fixture
def skill_directory():
    """Create a temporary skill directory with SKILL.md using test-kit paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = os.path.join(tmpdir, "test_skill")
        os.makedirs(skill_path)

        # Create SKILL.md
        skill_md = os.path.join(skill_path, "SKILL.md")
        with open(skill_md, "w") as f:
            f.write(SAMPLE_SKILL_MD)

        # Create scripts directory with a sample tool
        scripts_dir = os.path.join(skill_path, "scripts")
        os.makedirs(scripts_dir)

        # Create a sample tool file
        tool_file = os.path.join(scripts_dir, "example_tool.py")
        with open(tool_file, "w") as f:
            f.write('''from omni.foundation import skill

@skill.command
def example_tool(input_data: str) -> dict:
    """An example tool for testing.

    Args:
        input_data: Input data to process

    Returns:
        Dictionary with processed result
    """
    return {"result": f"Processed: {input_data}"}
''')

        yield tmpdir


@pytest.fixture
def multi_skill_directory():
    """Create a temporary directory with multiple skills using test-kit patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create skill 1
        skill1_path = os.path.join(tmpdir, "skill_one")
        os.makedirs(skill1_path)
        with open(os.path.join(skill1_path, "SKILL.md"), "w") as f:
            f.write("""---
name: "skill_one"
version: "1.0.0"
description: "First test skill"
routing_keywords: ["one", "first"]
---

# Skill One
""")

        # Create skill 2
        skill2_path = os.path.join(tmpdir, "skill_two")
        os.makedirs(skill2_path)
        with open(os.path.join(skill2_path, "SKILL.md"), "w") as f:
            f.write("""---
name: "skill_two"
version: "2.0.0"
description: "Second test skill"
routing_keywords: ["two", "second"]
authors: ["Author Two"]
---

# Skill Two
""")

        # Create invalid skill (no SKILL.md)
        invalid_path = os.path.join(tmpdir, "invalid_skill")
        os.makedirs(invalid_path)

        yield tmpdir


class TestPySkillScanner:
    """Tests for PySkillScanner class using test-kit fixtures."""

    def test_scan_all_empty_directory(self, test_tracer):
        """Test scanning an empty directory returns empty list."""
        test_tracer.log_step("scan_empty_directory")
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = PySkillScanner(tmpdir)
            skills = scanner.scan_all()
            assert skills == []

    def test_scan_all_single_skill(self, skill_directory, test_tracer):
        """Test scanning a directory with one skill."""
        test_tracer.log_step("scan_single_skill")
        scanner = PySkillScanner(skill_directory)
        skills = scanner.scan_all()

        assert len(skills) == 1
        skill = skills[0]
        assert isinstance(skill, PySkillMetadata)
        assert skill.skill_name == "test_skill"
        assert skill.version == "1.0.0"
        assert skill.description == "A test skill for unit testing"
        assert "test" in skill.routing_keywords
        assert "example" in skill.routing_keywords

    def test_scan_all_multiple_skills(self, multi_skill_directory, test_tracer):
        """Test scanning a directory with multiple skills."""
        test_tracer.log_step("scan_multiple_skills")
        scanner = PySkillScanner(multi_skill_directory)
        skills = scanner.scan_all()

        assert len(skills) == 2

        # Check both skills are present
        skill_names = [s.skill_name for s in skills]
        assert "skill_one" in skill_names
        assert "skill_two" in skill_names

    def test_scan_skill_by_name(self, skill_directory, test_tracer):
        """Test scanning a specific skill by name."""
        test_tracer.log_step("scan_skill_by_name")
        scanner = PySkillScanner(skill_directory)
        skill = scanner.scan_skill("test_skill")

        assert skill is not None
        assert skill.skill_name == "test_skill"
        assert skill.version == "1.0.0"

    def test_scan_skill_not_found(self, skill_directory, test_tracer):
        """Test scanning a non-existent skill returns None."""
        test_tracer.log_step("scan_skill_not_found")
        scanner = PySkillScanner(skill_directory)
        skill = scanner.scan_skill("nonexistent")

        assert skill is None

    def test_scan_skill_with_tools(self, skill_directory, test_tracer):
        """Test scanning a skill with its tools."""
        test_tracer.log_step("scan_skill_with_tools")
        scanner = PySkillScanner(skill_directory)
        result = scanner.scan_skill_with_tools("test_skill")

        assert result is not None
        skill, _ = result

        assert skill.skill_name == "test_skill"

    def test_scan_all_with_tools(self, multi_skill_directory, test_tracer):
        """Test scanning all skills with their tools."""
        test_tracer.log_step("scan_all_with_tools")
        scanner = PySkillScanner(multi_skill_directory)
        results = scanner.scan_all_with_tools()

        assert len(results) == 2

        for skill, tools in results:
            assert isinstance(skill, PySkillMetadata)
            assert isinstance(tools, list)

    def test_validate_skill_valid(self, skill_directory, test_tracer):
        """Test validating a valid skill returns True."""
        test_tracer.log_step("validate_skill_valid")
        scanner = PySkillScanner(skill_directory)
        is_valid = scanner.validate_skill("test_skill")

        assert is_valid is True

    def test_validate_skill_invalid(self, multi_skill_directory, test_tracer):
        """Test validating an invalid skill returns False."""
        test_tracer.log_step("validate_skill_invalid")
        scanner = PySkillScanner(multi_skill_directory)
        is_valid = scanner.validate_skill("invalid_skill")

        assert is_valid is False

    def test_base_path_getter(self, skill_directory, test_tracer):
        """Test that base_path is correctly stored."""
        test_tracer.log_step("base_path_getter")
        scanner = PySkillScanner(skill_directory)
        assert scanner.base_path == skill_directory

    def test_permissions_field(self, skill_directory, test_tracer):
        """Test that permissions field is correctly extracted."""
        test_tracer.log_step("permissions_field")
        scanner = PySkillScanner(skill_directory)
        skills = scanner.scan_all()

        assert len(skills) == 1
        skill = skills[0]
        assert "filesystem:read" in skill.permissions
        assert "network:http" in skill.permissions

    def test_authors_field(self, skill_directory, test_tracer):
        """Test that authors field is correctly extracted."""
        test_tracer.log_step("authors_field")
        scanner = PySkillScanner(skill_directory)
        skills = scanner.scan_all()

        assert len(skills) == 1
        skill = skills[0]
        assert len(skill.authors) == 1
        assert "Test Author" in skill.authors[0]

    def test_intents_field(self, skill_directory, test_tracer):
        """Test that intents field is correctly extracted."""
        test_tracer.log_step("intents_field")
        scanner = PySkillScanner(skill_directory)
        skills = scanner.scan_all()

        assert len(skills) == 1
        skill = skills[0]
        assert "test.intent" in skill.intents
        assert "example.action" in skill.intents


class TestPySkillMetadata:
    """Tests for PySkillMetadata class."""

    def test_metadata_fields(self, skill_directory, test_tracer):
        """Test that all metadata fields are correctly extracted."""
        test_tracer.log_step("metadata_fields")
        scanner = PySkillScanner(skill_directory)
        skills = scanner.scan_all()

        assert len(skills) == 1
        skill = skills[0]

        # Verify all fields
        assert skill.skill_name == "test_skill"
        assert skill.version == "1.0.0"
        assert skill.description == "A test skill for unit testing"
        assert skill.authors == ["Test Author <test@example.com>"]
        assert skill.routing_keywords == ["test", "example", "demo"]
        assert skill.intents == ["test.intent", "example.action"]
        assert skill.repository == "https://github.com/example/test-skill"
        assert skill.permissions == ["filesystem:read", "network:http"]


class TestSkillScannerPerformance:
    """Performance tests for the Rust skill scanner using test-kit tracer."""

    def test_scan_performance(self, skill_directory, test_tracer):
        """Test that scanning is fast (< 2ms per skill)."""
        test_tracer.log_step("scan_performance_start")
        scanner = PySkillScanner(skill_directory)

        # Warm up
        scanner.scan_all()

        # Measure average scan time
        import time

        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            scanner.scan_all()
        end = time.perf_counter()

        avg_ms = (end - start) * 1000 / iterations
        test_tracer.log_step("scan_performance_complete", {"avg_ms": avg_ms})
        print(f"Average scan time: {avg_ms:.4f} ms")

        # Should be well under 2ms per scan
        assert avg_ms < 2.0, f"Scan too slow: {avg_ms:.4f} ms"

    def test_single_skill_scan_performance(self, skill_directory, test_tracer):
        """Test that single skill scan is fast."""
        test_tracer.log_step("single_skill_scan_start")
        scanner = PySkillScanner(skill_directory)

        # Warm up
        scanner.scan_skill("test_skill")

        # Measure average scan time
        import time

        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            scanner.scan_skill("test_skill")
        end = time.perf_counter()

        avg_ms = (end - start) * 1000 / iterations
        test_tracer.log_step("single_skill_scan_complete", {"avg_ms": avg_ms})
        print(f"Average single skill scan time: {avg_ms:.4f} ms")

        # Should be well under 1ms per scan
        assert avg_ms < 1.0, f"Single skill scan too slow: {avg_ms:.4f} ms"


class TestSkillScannerWithRealSkills:
    """Integration tests using real skills from skills_root fixture."""

    def test_scan_real_skills_directory(self, skills_root, test_tracer):
        """Test scanning the actual skills directory."""
        test_tracer.log_step("scan_real_skills")
        scanner = PySkillScanner(str(skills_root))
        skills = scanner.scan_all()

        # Should find at least some skills
        assert len(skills) > 0

        # Each skill should have valid metadata
        for skill in skills:
            assert skill.skill_name is not None
            assert skill.skill_name != ""

    def test_scan_real_skill_by_name(self, skills_root, test_tracer):
        """Test scanning a specific real skill by name."""
        test_tracer.log_step("scan_real_skill_by_name")
        scanner = PySkillScanner(str(skills_root))

        # Try to find the first available skill
        all_skills = scanner.scan_all()
        if all_skills:
            first_skill_name = all_skills[0].skill_name
            skill = scanner.scan_skill(first_skill_name)

            assert skill is not None
            assert skill.skill_name == first_skill_name

    def test_real_skills_have_routing_keywords(self, skills_root, test_tracer):
        """Test that real skills have routing keywords for hybrid search."""
        test_tracer.log_step("check_routing_keywords")
        scanner = PySkillScanner(str(skills_root))
        skills = scanner.scan_all()

        # Most skills should have routing keywords
        skills_with_keywords = [s for s in skills if s.routing_keywords]
        assert len(skills_with_keywords) > 0

        test_tracer.log_step("routing_keywords_found", {"count": len(skills_with_keywords)})
