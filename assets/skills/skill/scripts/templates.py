"""
skill/scripts/templates.py - Template Management

Implements cascading template loading with "User Overrides > Skill Defaults" pattern.

Template Locations:
    User Overrides: assets/templates/{skill}/
    Skill Defaults: assets/skills/{skill}/templates/
"""

from pathlib import Path
from typing import Dict, Optional

from omni.core.skills.script_loader import skill_command
from omni.foundation.config.skills import SKILLS_DIR
from omni.foundation.config.settings import get_setting
from omni.foundation.runtime.gitops import get_project_root


def get_template_dirs(skill_name: str) -> Dict[str, Path]:
    """
    Get template directories for a skill.

    Returns:
        Dict with "user" and "skill" keys mapping to Path objects
    """
    project_root = get_project_root()

    templates_config = get_setting("assets.templates_dir", "assets/templates")
    user_templates_root = project_root / templates_config
    user_skill_templates = user_skill_templates = user_templates_root / skill_name

    skill_templates_dir = SKILLS_DIR(skill_name, path="templates")

    return {
        "user": user_skill_templates,
        "skill": skill_templates_dir,
    }


@skill_command(
    name="list_templates",
    category="read",
    description="""
    Lists all available templates for a skill with their sources.

    Templates follow the cascading pattern: User Overrides > Skill Defaults.

    Args:
        skill_name: Name of the skill (e.g., `git`, `docker`).

    Returns:
        Dictionary mapping template names to their source (`user` or `skill`)
        and absolute file paths.
    """,
)
def list_templates(skill_name: str) -> Dict[str, Dict[str, str]]:
    dirs = get_template_dirs(skill_name)
    user_dir = dirs["user"]
    skill_dir = dirs["skill"]

    all_templates = {}

    if skill_dir.exists():
        for f in skill_dir.glob("*.j2"):
            all_templates[f.name] = {"source": "skill", "path": str(f)}

    if user_dir.exists():
        for f in user_dir.glob("*.j2"):
            all_templates[f.name] = {"source": "user", "path": str(f)}

    return all_templates


@skill_command(
    name="get_template_info",
    category="read",
    description="""
    Gets information about a specific template.

    Args:
        skill_name: Name of the skill.
        template_name: Template filename (e.g., `commit_message.j2`).

    Returns:
        Dictionary with `source` (`user` or `skill`), `path`,
        or `None` if not found.
    """,
)
def get_template_info(skill_name: str, template_name: str) -> Optional[Dict[str, str]]:
    templates = list_templates(skill_name)
    return templates.get(template_name)


@skill_command(
    name="get_template_source",
    category="read",
    description="""
    Gets the source code content of a template.

    Args:
        skill_name: Name of the skill.
        template_name: Template filename.

    Returns:
        Template file content as string, or `None` if not found.
    """,
)
def get_template_source(skill_name: str, template_name: str) -> Optional[str]:
    info = get_template_info(skill_name, template_name)
    if info and info.get("path"):
        path = Path(info["path"])
        if path.exists():
            return path.read_text()
    return None


@skill_command(
    name="eject_template",
    category="write",
    description="""
    Copies a skill default template to the user directory for customization.

    Creates a user override that takes precedence over skill defaults.

    Args:
        skill_name: Name of the skill.
        template_name: Template filename (e.g., `commit_message.j2`).
                      The `.j2` extension is added automatically if missing.

    Returns:
        Dictionary with `status` (`success`, `already_exists`, `not_found`),
        `message`, `source` path, and destination `path`.

    Example:
        @omni("skill.eject_template", {"skill_name": "git", "template_name": "commit_message"})
    """,
)
def eject_template(skill_name: str, template_name: str) -> Dict[str, str]:
    dirs = get_template_dirs(skill_name)
    user_dir = dirs["user"]
    skill_dir = dirs["skill"]

    if not template_name.endswith(".j2"):
        template_name += ".j2"

    user_path = user_dir / template_name
    if user_path.exists():
        return {
            "status": "already_exists",
            "message": f"Template already overridden at `{user_path}`",
            "path": str(user_path),
        }

    skill_path = skill_dir / template_name
    if not skill_path.exists():
        return {
            "status": "not_found",
            "message": f"Template not found in skill defaults: {skill_path}",
            "path": None,
        }

    user_dir.mkdir(parents=True, exist_ok=True)
    content = skill_path.read_text()
    user_path.write_text(content)

    return {
        "status": "success",
        "message": f"Template ejected from skill default to user override",
        "source": str(skill_path),
        "path": str(user_path),
    }


def format_template_list(skill_name: str) -> str:
    """
    Format template list for display.

    Args:
        skill_name: Name of the skill

    Returns:
        Formatted markdown string
    """
    templates = list_templates(skill_name)
    dirs = get_template_dirs(skill_name)

    if not templates:
        return f"No templates found for skill '{skill_name}'"

    lines = [
        f"# Skill Templates: {skill_name}",
        "",
        "**Cascading Pattern**: User Overrides > Skill Defaults",
        "",
        "## Templates",
        "",
    ]

    for name in sorted(templates.keys()):
        info = templates[name]
        source_emoji = "user" if info["source"] == "user" else "skill"
        lines.append(f"- `{name}` ({source_emoji})")

    lines.extend(
        [
            "",
            "## Template Locations",
            "",
            f"User Overrides: `{dirs['user']}`",
            f"Skill Defaults: `{dirs['skill']}`",
        ]
    )

    return "\n".join(lines)


def format_eject_result(skill_name: str, template_name: str) -> str:
    """
    Format eject result for display.

    Args:
        skill_name: Name of the skill
        template_name: Template filename

    Returns:
        Formatted markdown string
    """
    result = eject_template(skill_name, template_name)

    if result["status"] == "success":
        return "\n".join(
            [
                f"# Template Ejected",
                "",
                f"Template: `{template_name}`",
                f"Source: Skill Default",
                f"Location: `{result['path']}`",
                "",
                "## Next Steps",
                "",
                f"1. Edit: `code {result['path']}`",
                "2. Test changes",
                "3. Commit with `/commit`",
                "",
                "User templates override skill defaults automatically.",
            ]
        )
    elif result["status"] == "already_exists":
        return f"Already Overridden\n\n{result['message']}"
    else:
        return f"Not Found\n\n{result['message']}"


def format_info_result(skill_name: str, template_name: str) -> str:
    """
    Format template info for display.

    Args:
        skill_name: Name of the skill
        template_name: Template filename

    Returns:
        Formatted markdown string
    """
    info = get_template_info(skill_name, template_name)

    if not info:
        return f"Template `{template_name}` not found for skill `{skill_name}`"

    content = get_template_source(skill_name, template_name)
    preview = content[:500] + "..." if content and len(content) > 500 else content or ""

    return "\n".join(
        [
            f"# Template: {template_name}",
            "",
            f"Source: {info['source'].title()}",
            f"Path: `{info['path']}`",
            "",
            "## Content Preview",
            "",
            "```jinja",
            preview,
            "```",
        ]
    )
