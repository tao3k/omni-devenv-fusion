"""Shared utilities for building test skill artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SkillMetadata:
    """Metadata used to render a test SKILL.md file."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    routing_keywords: list[str] | None = None
    authors: list[str] | None = None
    intents: list[str] | None = None
    repository: str = ""
    permissions: list[str] | None = None


def _yaml_list(values: list[str]) -> str:
    quoted = [f"'{value}'" for value in values]
    return f"[{', '.join(quoted)}]"


def render_skill_markdown(metadata: SkillMetadata) -> str:
    """Render SKILL.md with Anthropic-style frontmatter."""
    lines = ["---"]
    lines.append(f'name: "{metadata.name}"')
    lines.append(f'description: "{metadata.description}"')
    lines.append("metadata:")
    lines.append(f'  version: "{metadata.version}"')

    if metadata.authors:
        lines.append(f"  authors: {_yaml_list(metadata.authors)}")
    if metadata.routing_keywords:
        lines.append(f"  routing_keywords: {_yaml_list(metadata.routing_keywords)}")
    if metadata.intents:
        lines.append(f"  intents: {_yaml_list(metadata.intents)}")
    if metadata.repository:
        lines.append(f'  source: "{metadata.repository}"')
    if metadata.permissions:
        lines.append(f"  permissions: {_yaml_list(metadata.permissions)}")

    lines.append("---")
    lines.append(f"\n# {metadata.name}")
    return "\n".join(lines)


class SkillTestBuilder:
    """Builder for creating test skill directories with SKILL.md."""

    def __init__(self, skill_name: str):
        self.skill_name = skill_name
        self.metadata: dict[str, Any] = {
            "name": skill_name,
            "version": "1.0.0",
            "description": f"Test skill: {skill_name}",
        }
        self.routing_keywords: list[str] = []
        self.authors: list[str] = []
        self.intents: list[str] = []
        self.repository: str = ""
        self.permissions: list[str] = []
        self.scripts: dict[str, str] = {}

    def with_metadata(
        self,
        version: str = "1.0.0",
        description: str | None = None,
        routing_keywords: list[str] | None = None,
        authors: list[str] | None = None,
        intents: list[str] | None = None,
        repository: str = "",
        permissions: list[str] | None = None,
    ) -> "SkillTestBuilder":
        """Set skill metadata fields."""
        if version is not None:
            self.metadata["version"] = version
        if description is not None:
            self.metadata["description"] = description
        if routing_keywords is not None:
            self.routing_keywords = routing_keywords
        if authors is not None:
            self.authors = authors
        if intents is not None:
            self.intents = intents
        if repository is not None:
            self.repository = repository
        if permissions is not None:
            self.permissions = permissions
        return self

    def with_script(self, filename: str, content: str) -> "SkillTestBuilder":
        """Add a script file to the skill's scripts directory."""
        self.scripts[filename] = content
        return self

    def create(self, base_dir: str) -> str:
        """Create the skill directory and return its path."""
        skill_path = Path(base_dir) / self.skill_name
        skill_path.mkdir(parents=True, exist_ok=True)

        metadata = SkillMetadata(
            name=str(self.metadata.get("name", self.skill_name)),
            version=str(self.metadata.get("version", "1.0.0")),
            description=str(self.metadata.get("description", f"Test skill: {self.skill_name}")),
            routing_keywords=self.routing_keywords or None,
            authors=self.authors or None,
            intents=self.intents or None,
            repository=self.repository,
            permissions=self.permissions or None,
        )
        (skill_path / "SKILL.md").write_text(render_skill_markdown(metadata))

        if self.scripts:
            scripts_dir = skill_path / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            for filename, content in self.scripts.items():
                (scripts_dir / filename).write_text(content)

        return str(skill_path)


__all__ = ["SkillMetadata", "SkillTestBuilder", "render_skill_markdown"]
