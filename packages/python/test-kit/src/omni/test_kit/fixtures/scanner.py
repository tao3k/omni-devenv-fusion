"""Skill scanner test fixtures and helpers."""

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generator, List
from unittest.mock import MagicMock
import pytest

from omni.core.kernel.components.skill_loader import load_skill_scripts
from omni.foundation.config.skills import SKILLS_DIR


class SkillTestBuilder:
    """Builder for creating test skill directories with SKILL.md.

    Usage:
        builder = SkillTestBuilder("test_skill")
        builder.with_metadata(version="1.0.0", routing_keywords=["test"])
        builder.with_script("example_tool.py", tool_code)
        path = builder.create(tmpdir)
    """

    def __init__(self, skill_name: str):
        self.skill_name = skill_name
        self.metadata: dict[str, Any] = {
            "name": skill_name,
            "version": "1.0.0",
            "description": f"Test skill: {skill_name}",
            "routing_keywords": [],
            "authors": [],
            "intents": [],
            "repository": "",
            "permissions": [],
        }
        self.scripts: dict[str, str] = {}

    def with_metadata(
        self,
        version: str = "1.0.0",
        description: str | None = None,
        routing_keywords: List[str] | None = None,
        authors: List[str] | None = None,
        intents: List[str] | None = None,
        repository: str = "",
        permissions: List[str] | None = None,
    ) -> "SkillTestBuilder":
        """Set skill metadata fields."""
        if version is not None:
            self.metadata["version"] = version
        if description is not None:
            self.metadata["description"] = description
        if routing_keywords is not None:
            self.metadata["routing_keywords"] = routing_keywords
        if authors is not None:
            self.metadata["authors"] = authors
        if intents is not None:
            self.metadata["intents"] = intents
        if repository is not None:
            self.metadata["repository"] = repository
        if permissions is not None:
            self.metadata["permissions"] = permissions
        return self

    def with_script(self, filename: str, content: str) -> "SkillTestBuilder":
        """Add a Python script file to the skill's scripts directory."""
        self.scripts[filename] = content
        return self

    def create(self, base_dir: str) -> str:
        """Create the skill directory and return its path."""
        skill_path = Path(base_dir) / self.skill_name
        skill_path.mkdir(parents=True, exist_ok=True)

        # Create SKILL.md
        skill_md = skill_path / "SKILL.md"
        yaml_frontmatter = self._build_frontmatter()
        skill_md.write_text(yaml_frontmatter)

        # Create scripts directory with scripts
        if self.scripts:
            scripts_dir = skill_path / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            for filename, content in self.scripts.items():
                (scripts_dir / filename).write_text(content)

        return str(skill_path)

    def _build_frontmatter(self) -> str:
        """Build SKILL.md content with YAML frontmatter."""
        lines = ["---"]
        for key, value in self.metadata.items():
            if isinstance(value, list):
                lines.append(f"{key}: {['"' + v + '"' for v in value]}")
            elif isinstance(value, str) and value:
                lines.append(f'{key}: "{value}"')
            else:
                lines.append(f"{key}:")
        lines.append("---")
        lines.append(f"\n# {self.skill_name}")
        return "\n".join(lines)


class SkillTestSuite:
    """Helper class for skill scanner tests.

    Provides:
    - Fixture creation for test skills
    - Scanner instantiation
    - Assertion helpers

    Usage:
        suite = SkillTestSuite("assets/skills")
        suite.create_skill("test_skill", with_metadata(...))
        skills = suite.scan_all()
    """

    def __init__(self, base_path: str):
        self.base_path = base_path
        self._temp_dirs: List[str] = []

    def create_skill(
        self,
        skill_name: str,
        version: str = "1.0.0",
        description: str | None = None,
        routing_keywords: List[str] | None = None,
        authors: List[str] | None = None,
        intents: List[str] | None = None,
        repository: str = "",
        permissions: List[str] | None = None,
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

        # Create in temp directory
        tmpdir = tempfile.mkdtemp()
        self._temp_dirs.append(tmpdir)
        builder.create(tmpdir)
        return self

    def create_multi_skill(
        self,
        skills: list[dict[str, Any]],
        add_invalid: bool = False,
    ) -> "SkillTestSuite":
        """Create multiple test skills at once."""
        tmpdir = tempfile.mkdtemp()
        self._temp_dirs.append(tmpdir)

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
            )._set_base_path(tmpdir)

        if add_invalid:
            invalid_path = Path(tmpdir) / "invalid_skill"
            invalid_path.mkdir(exist_ok=True)

        return self

    def _set_base_path(self, path: str) -> "SkillTestSuite":
        """Internal: set base path for chaining."""
        self.base_path = path
        return self

    def scanner(self) -> Any:
        """Get a PySkillScanner for the base path."""
        from omni_core_rs import PySkillScanner

        return PySkillScanner(self.base_path)

    def scan_all(self) -> list:
        """Scan all skills in base path."""
        return self.scanner().scan_all()

    def scan_skill(self, name: str):
        """Scan a specific skill by name."""
        return self.scanner().scan_skill(name)

    def cleanup(self):
        """Clean up temporary directories."""
        import shutil

        for tmpdir in self._temp_dirs:
            try:
                shutil.rmtree(tmpdir)
            except OSError:
                pass
        self._temp_dirs.clear()

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
    with SkillTestSuite(tempfile.mkdtemp()) as suite:
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
# Skill Execution Fixtures
# =============================================================================


@dataclass
class SkillResult:
    """Represents the result of a skill execution."""

    success: bool
    output: Any
    error: str | None = None
    artifacts: dict | None = None


class SkillTester:
    """Dedicated Skill Test Executor."""

    def __init__(self, request):
        self.request = request
        self.context = MagicMock()
        self.config = {}
        self.skills_root = SKILLS_DIR()

    def with_config(self, config: dict[str, Any]) -> "SkillTester":
        self.config.update(config)
        return self

    def with_context(self, **kwargs) -> "SkillTester":
        for k, v in kwargs.items():
            setattr(self.context, k, v)
        return self

    async def run(self, _skill_name: str, _command_name: str, **kwargs) -> SkillResult:
        """Execute the core logic of a Skill."""
        scripts_dir = self.skills_root / _skill_name / "scripts"
        commands = await load_skill_scripts(_skill_name, scripts_dir)

        if _command_name not in commands:
            return SkillResult(
                success=False, output=None, error=f"Command '{_command_name}' not found"
            )

        func = commands[_command_name]

        try:
            if asyncio.iscoroutinefunction(func):
                output = await func(**kwargs)
            else:
                output = func(**kwargs)
            return SkillResult(success=True, output=output)
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))

    async def get_commands(self, skill_name: str) -> dict[str, Any]:
        """Get all available commands for a skill."""
        scripts_dir = self.skills_root / skill_name / "scripts"
        return await load_skill_scripts(skill_name, scripts_dir)


@pytest.fixture
async def skill_tester(request):
    return SkillTester(request)


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
