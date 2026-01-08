"""
agent/core/skill_generator.py - Phase 33 Skill Template Generator

Uses Jinja2 templates to generate new skills from the _template directory.
Supports both interactive CLI use and programmatic skill creation.
"""

from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape


class SkillGenerator:
    """
    Generate new skills from Jinja2 templates.

    Templates are located in `assets/skills/_template/`:
    - SKILL.md.j2 -> SKILL.md
    - tools.py.j2 -> tools.py
    - guide.md.j2 -> guide.md
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize the generator with template directory.

        Args:
            template_dir: Path to template directory (defaults to _template)
        """
        if template_dir is None:
            # Default to _template in skills directory
            from common.gitops import get_project_root

            root = get_project_root()
            template_dir = root / "assets/skills/_template"

        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(
        self,
        skill_name: str,
        description: str,
        output_dir: Path,
        author: str = "omni-dev",
        keywords: Optional[list[str]] = None,
    ) -> Path:
        """
        Generate a new skill from templates.

        Args:
            skill_name: Name of the skill (used in routing and filenames)
            description: Brief description of the skill's purpose
            output_dir: Parent directory for the new skill
            author: Author name for SKILL.md metadata
            keywords: Additional routing keywords

        Returns:
            Path to the created skill directory
        """
        skill_dir = output_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Prepare template variables
        vars = {
            "skill_name": skill_name,
            "description": description,
            "author": author,
            "keywords": keywords or [],
        }

        # Render templates
        self._render_template("SKILL.md.j2", skill_dir / "SKILL.md", vars)
        self._render_template("tools.py.j2", skill_dir / "tools.py", vars)
        self._render_template("guide.md.j2", skill_dir / "guide.md", vars)

        return skill_dir

    def _render_template(self, template_name: str, output_path: Path, vars: dict) -> None:
        """
        Render a single template and write to file.

        Args:
            template_name: Name of the template file
            output_path: Path to write the rendered content
            vars: Variables to pass to the template
        """
        template = self.env.get_template(template_name)
        content = template.render(**vars)
        output_path.write_text(content)

    def generate_from_template(self, skill_name: str, description: str) -> Path:
        """
        Convenience method to generate a skill in the default skills directory.

        Args:
            skill_name: Name of the skill
            description: Brief description

        Returns:
            Path to the created skill
        """
        from common.skills_path import SKILLS_DIR

        skills_dir = SKILLS_DIR()
        return self.generate(skill_name, description, skills_dir)


# Convenience function for CLI use
def create_skill(
    skill_name: str,
    description: str,
    author: str = "omni-dev",
    keywords: Optional[list[str]] = None,
) -> Path:
    """
    Create a new skill from templates.

    Args:
        skill_name: Name of the skill
        description: Brief description of the skill's purpose
        author: Author name for SKILL.md metadata
        keywords: Additional routing keywords

    Returns:
        Path to the created skill directory
    """
    generator = SkillGenerator()
    return generator.generate(
        skill_name, description, generator.template_dir.parent, author, keywords
    )
