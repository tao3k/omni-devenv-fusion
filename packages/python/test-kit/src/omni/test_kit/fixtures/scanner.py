"""Skill scanner test fixtures and helpers."""

import shutil
import tempfile
from pathlib import Path
from typing import Any, Generator
import pytest

from omni.test_kit.fixtures.skill_builder import SkillTestBuilder


class SkillTestSuite:
    """Helper class for skill scanner tests.

    Provides:
    - Fixture creation for test skills
    - Scanner instantiation
    - Assertion helpers

    Usage:
        suite = SkillTestSuite(tmp_path)
        suite.create_skill("test_skill", with_metadata(...))
        skills = suite.scan_all()
    """

    def __init__(self, base_path: str | Path, managed: bool = False):
        self.base_path = Path(base_path)
        self._managed = managed

    def create_skill(
        self,
        skill_name: str,
        version: str = "1.0.0",
        description: str | None = None,
        routing_keywords: list[str] | None = None,
        authors: list[str] | None = None,
        intents: list[str] | None = None,
        repository: str = "",
        permissions: list[str] | None = None,
        scripts: dict[str, str] | None = None,
    ) -> "SkillTestSuite":
        """Create a test skill and return self for chaining."""
        builder = SkillTestBuilder(skill_name)
        builder.with_metadata(
            version=version,
            description=description,
            routing_keywords=routing_keywords,
            authors=authors,
            intents=intents,
            repository=repository,
            permissions=permissions,
        )
        if scripts:
            for filename, content in scripts.items():
                builder.with_script(filename, content)

        builder.create(str(self.base_path))
        return self

    def create_multi_skill(
        self,
        skills: list[dict[str, Any]],
        add_invalid: bool = False,
    ) -> "SkillTestSuite":
        """Create multiple test skills at once."""
        for skill_data in skills:
            self.create_skill(
                skill_name=skill_data["name"],
                version=skill_data.get("version", "1.0.0"),
                description=skill_data.get("description"),
                routing_keywords=skill_data.get("routing_keywords"),
                authors=skill_data.get("authors"),
                intents=skill_data.get("intents"),
                repository=skill_data.get("repository", ""),
                permissions=skill_data.get("permissions"),
                scripts=skill_data.get("scripts"),
            )

        if add_invalid:
            invalid_path = self.base_path / "invalid_skill"
            invalid_path.mkdir(exist_ok=True)

        return self

    def scanner(self) -> Any:
        """Get a PySkillScanner for the base path."""
        from omni_core_rs import PySkillScanner

        return PySkillScanner(str(self.base_path))

    def scan_all(self) -> list:
        """Scan all skills in base path."""
        return self.scanner().scan_all()

    def scan_skill(self, name: str):
        """Scan a specific skill by name."""
        return self.scanner().scan_skill(name)

    def cleanup(self):
        """Clean up temporary directories."""
        if self._managed and self.base_path.exists():
            shutil.rmtree(self.base_path, ignore_errors=True)

    def __enter__(self) -> "SkillTestSuite":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def skill_test_suite() -> Generator[SkillTestSuite, None, None]:
    """Fixture providing SkillTestSuite for scanner tests.

    Creates a temporary directory that is cleaned up after the test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        suite = SkillTestSuite(tmpdir)
        yield suite


@pytest.fixture
def skill_directory() -> Generator[str, None, None]:
    """Create a temporary skill directory with SKILL.md.

    Creates a single skill named 'test_skill' with standard metadata
    and a sample tool script.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        builder = SkillTestBuilder("test_skill")
        builder.with_metadata(
            version="1.0.0",
            description="A test skill for unit testing",
            routing_keywords=["test", "example", "demo"],
            authors=["Test Author <test@example.com>"],
            intents=["test.intent", "example.action"],
            repository="https://github.com/example/test-skill",
            permissions=["filesystem:read", "network:http"],
        )
        builder.with_script(
            "example_tool.py",
            '''from omni.foundation import skill

@skill.command
def example_tool(input_data: str) -> dict:
    """An example tool for testing."""
    return {"result": f"Processed: {input_data}"}
''',
        )
        yield builder.create(tmpdir)


@pytest.fixture
def multi_skill_directory() -> Generator[str, None, None]:
    """Create a temporary directory with multiple skills."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create skill 1
        builder1 = SkillTestBuilder("skill_one")
        builder1.with_metadata(
            version="1.0.0",
            description="First test skill",
            routing_keywords=["one", "first"],
        )
        builder1.create(tmpdir)

        # Create skill 2
        builder2 = SkillTestBuilder("skill_two")
        builder2.with_metadata(
            version="2.0.0",
            description="Second test skill",
            routing_keywords=["two", "second"],
            authors=["Author Two"],
        )
        builder2.create(tmpdir)

        # Create invalid skill (no SKILL.md)
        invalid_path = Path(tmpdir) / "invalid_skill"
        invalid_path.mkdir(exist_ok=True)

        yield tmpdir


# =============================================================================
# Parametrized Test Helpers
# =============================================================================


def parametrize_skills(*fields: str):
    """Parametrize tests with skill metadata field assertions.

    Usage:
        @parametrize_skills("permissions", "authors", "intents")
        def test_metadata_fields(self, skill_directory, field):
            scanner = PySkillScanner(skill_directory)
            skill = scanner.scan_all()[0]
            assert getattr(skill, field)
    """
    return pytest.mark.parametrize(
        "field",
        fields,
        ids=fields,
    )
