"""
agent/testing/context.py - Unified Skills Context for Type Hints and CLI

This module provides:
1. SkillsContext class for IDE autocomplete with pytest fixtures
2. TestContext class for CLI commands (test, check, templates, create)

Usage:
    # For pytest fixtures
    def test_workflow(skills):  # IDE infers SkillsContext
        skills.git.init()
        skills.docker.run()

    # For CLI commands
    ctx = TestContext()
    ctx.run_skill_tests("git")
    ctx.validate_skill_structure("crawl4ai")
"""

from typing import TYPE_CHECKING, Any, Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

import pytest

if TYPE_CHECKING:
    # Static imports only - no runtime dependency
    # These imports enable IDE autocomplete
    from assets.skills.git import tools as git_tools
    from assets.skills.knowledge import tools as knowledge_tools  # noqa: F401
    from assets.skills.filesystem import tools as filesystem_tools  # noqa: F401
    from assets.skills.skill import tools as skill_tools

from common.skills_path import SKILLS_DIR


class SkillsContext:
    """
    Virtual context class for type hints only.

    Runtime behavior:
        - Delegates to pytest fixtures via __getattr__
        - Lazy fixture resolution (only when accessed)

    Type hints:
        - All properties return typed references for IDE autocomplete
        - Actual fixture values returned at runtime

    Example:
        skills.git.init()  # Returns actual git fixture at runtime
                          # IDE knows git has init() method
    """

    def __init__(self, request: pytest.FixtureRequest):
        self._request = request
        # Cache accessed fixtures to avoid repeated lookups
        self._cache: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to pytest fixtures."""
        if name.startswith("_"):
            raise AttributeError(name)

        if name in self._cache:
            return self._cache[name]

        # Get fixture from pytest
        fixture = self._request.getfixturevalue(name)
        self._cache[name] = fixture
        return fixture

    def __dir__(self) -> list[str]:
        """List available skills for IDE autocomplete."""
        return ["git", "knowledge", "filesystem", "skill"]

    # Explicit type hints for IDE autocomplete
    # These are property stubs - actual values come from fixtures

    @property
    def git(self) -> "git_tools":
        """Git skill fixture."""
        return self._request.getfixturevalue("git")

    @property
    def knowledge(self) -> "knowledge_tools":
        """Knowledge skill fixture."""
        return self._request.getfixturevalue("knowledge")

    @property
    def filesystem(self) -> "filesystem_tools":
        """Filesystem skill fixture."""
        return self._request.getfixturevalue("filesystem")

    @property
    def skill(self) -> "skill_tools":
        """Skill skill fixture."""
        return self._request.getfixturevalue("skill")


def get_skills_context(request: pytest.FixtureRequest) -> SkillsContext:
    """
    Factory function to create SkillsContext.

    Args:
        request: Pytest FixtureRequest object

    Returns:
        SkillsContext instance with typed access to all skill fixtures
    """
    return SkillsContext(request)


# =============================================================================
# TestContext for CLI Commands (Phase 35.2)
# =============================================================================


class TestContext:
    """
    Test and validation context for CLI commands.

    Provides unified interface for:
    - Running skill tests
    - Validating skill structure
    - Managing templates
    - Creating new skills
    """

    def __init__(self):
        """Initialize the test context."""
        self.skills_dir = SKILLS_DIR()

    def run_skill_tests(self, skill_name: str) -> dict:
        """
        Run tests for a specific skill.

        Args:
            skill_name: Name of the skill to test

        Returns:
            Dictionary with test results
        """
        skill_dir = self.skills_dir / skill_name
        tests_dir = skill_dir / "tests"

        if not skill_dir.exists():
            return {"success": False, "error": f"Skill '{skill_name}' not found"}

        if not tests_dir.exists():
            return {"success": False, "error": f"No tests directory for '{skill_name}'"}

        # Run pytest with live output to stderr
        import subprocess

        result = subprocess.run(
            ["pytest", str(tests_dir), "-v", "--tb=short"],
            capture_output=False,  # Stream output to stderr
            cwd=str(self.skills_dir),
        )

        return {
            "success": result.returncode == 0,
            "output": "",
            "error": None if result.returncode == 0 else "Tests failed",
        }

    def run_all_tests(self) -> dict:
        """
        Run tests for all skills that have a tests/ directory.

        Returns:
            Dictionary with aggregated test results
        """
        results = {}

        for skill_path in sorted(self.skills_dir.iterdir()):
            if skill_path.is_dir() and not skill_path.name.startswith("_"):
                tests_dir = skill_path / "tests"
                if tests_dir.exists():
                    results[skill_path.name] = self.run_skill_tests(skill_path.name)

        return results

    def print_summary(self, results: dict) -> None:
        """Print a summary of test results."""
        from rich.console import Console

        console = Console(stderr=True)
        table = Table(title="🧪 Test Results", show_header=True)
        table.add_column("Skill", style="bold")
        table.add_column("Status")
        table.add_column("Details")

        for skill, result in results.items():
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            style = "green" if result["success"] else "red"
            error = result.get("error") or ""
            details = error[:50] if error else "OK"
            table.add_row(skill, f"[{style}]{status}[/]", details)

        console.print(table)

    def validate_skill_structure(self, skill_name: str) -> dict:
        """
        Validate the structure of a skill.

        Args:
            skill_name: Name of the skill to validate

        Returns:
            Dictionary with validation results
        """
        skill_dir = self.skills_dir / skill_name

        if not skill_dir.exists():
            return {"success": False, "error": f"Skill '{skill_name}' not found"}

        required_files = ["SKILL.md", "tools.py"]
        optional_files = ["tests/", "scripts/", "prompts.md", "pyproject.toml"]

        missing = []
        found = []

        for f in required_files:
            path = skill_dir / f
            if path.exists():
                found.append(f)
            else:
                missing.append(f)

        for f in optional_files:
            path = skill_dir / f
            if path.exists():
                found.append(f)

        if missing:
            return {
                "success": False,
                "error": f"Missing required files: {', '.join(missing)}",
                "found": found,
                "missing": missing,
            }

        return {"success": True, "found": found, "missing": missing}

    def list_templates(self, skill_name: str) -> None:
        """List available templates for a skill."""
        from rich.console import Console

        console = Console(stderr=True)
        skill_dir = self.skills_dir / skill_name
        templates_dir = skill_dir / "templates"

        if not templates_dir.exists():
            console.print(Panel(f"No templates directory for '{skill_name}'", title="📋 Templates"))
            return

        templates = list(templates_dir.glob("*.j2"))
        if not templates:
            console.print(Panel(f"No templates found in '{templates_dir}'", title="📋 Templates"))
            return

        table = Table(title=f"📋 Templates for '{skill_name}'", show_header=True)
        table.add_column("Template")
        table.add_column("Path")

        for t in templates:
            table.add_row(t.name, str(t.relative_to(templates_dir)))

        console.print(table)

    def eject_template(self, skill_name: str, template_name: str) -> None:
        """Copy a template to the user's template directory."""
        from rich.console import Console

        console = Console(stderr=True)
        skill_dir = self.skills_dir / skill_name
        template_path = skill_dir / "templates" / template_name

        if not template_path.exists():
            console.print(
                Panel(f"Template not found: {template_path}", title="❌ Error", style="red")
            )
            return

        # Copy to user template directory
        user_templates = Path.home() / ".config" / "omni" / "templates" / skill_name
        user_templates.mkdir(parents=True, exist_ok=True)
        dest = user_templates / template_name

        import shutil

        shutil.copy(template_path, dest)
        console.print(Panel(f"Copied {template_name} to {dest}", title="✅ Success", style="green"))

    def show_template_info(self, skill_name: str, template_name: str) -> None:
        """Show the content of a template."""
        from rich.console import Console

        console = Console(stderr=True)
        skill_dir = self.skills_dir / skill_name
        template_path = skill_dir / "templates" / template_name

        if not template_path.exists():
            console.print(
                Panel(f"Template not found: {template_path}", title="❌ Error", style="red")
            )
            return

        content = template_path.read_text()
        console.print(Panel(content, title=f"📄 {template_name}", expand=False))

    def create_skill(self, skill_name: str, description: str, force: bool = False) -> None:
        """
        Create a new skill from the _template.

        Args:
            skill_name: Name of the new skill (kebab-case)
            description: Description of the skill
            force: Overwrite existing skill
        """
        from agent.core.skill_generator import SkillGenerator
        from rich.console import Console

        console = Console(stderr=True)
        skill_dir = self.skills_dir / skill_name

        if skill_dir.exists() and not force:
            console.print(
                Panel(
                    f"Skill '{skill_name}' already exists. Use --force to overwrite.",
                    title="❌ Error",
                    style="red",
                )
            )
            return

        generator = SkillGenerator()
        try:
            generator.generate(skill_name, description, self.skills_dir)
            console.print(
                Panel(
                    f"Created skill '{skill_name}' at {skill_dir}",
                    title="✅ Success",
                    style="green",
                )
            )
        except Exception as e:
            console.print(Panel(f"Failed to create skill: {e}", title="❌ Error", style="red"))


# Export for plugin.py and CLI
__all__ = ["SkillsContext", "get_skills_context", "TestContext"]
