"""
skill/scripts/templates.py - Template Management

Implements cascading template loading with "User Overrides > Skill Defaults" pattern.

Template Locations:
    User Overrides: assets/templates/{skill}/
    Skill Defaults: assets/skills/{skill}/templates/
"""

from pathlib import Path

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.settings import get_setting
from omni.foundation.config.skills import SKILLS_DIR
from omni.foundation.runtime.gitops import get_project_root


def get_template_dirs(skill_name: str) -> dict[str, Path]:
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
    category="view",
    description="""
    List all available templates for a skill with their sources.

    Args:
        - skill_name: str - Name of the skill (e.g., git, docker) (required)

    Returns:
        Dictionary mapping template names to source (user or skill) and path.
    """,
)
def list_templates(skill_name: str) -> dict[str, dict[str, str]]:
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
    Get information about a specific template.

    Args:
        - skill_name: str - Name of the skill (required)
        - template_name: str - Template filename (e.g., commit_message.j2) (required)

    Returns:
        Dictionary with source (user or skill), path, or null if not found.
    """,
)
def get_template_info(skill_name: str, template_name: str) -> dict[str, str] | None:
    templates = list_templates(skill_name)
    return templates.get(template_name)


@skill_command(
    name="get_template_source",
    category="read",
    description="""
    Get the source code content of a template.

    Args:
        - skill_name: str - Name of the skill (required)
        - template_name: str - Template filename (required)

    Returns:
        Template file content as string, or null if not found.
    """,
)
def get_template_source(skill_name: str, template_name: str) -> str | None:
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
    Copy a skill default template to the user directory for customization.

    Args:
        - skill_name: str - Name of the skill (required)
        - template_name: str - Template filename (e.g., commit_message). .j2 added automatically (required)

    Returns:
        Dictionary with status (success, already_exists, not_found), message, source, path.
    """,
)
def eject_template(skill_name: str, template_name: str) -> dict[str, str]:
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
        "message": "Template ejected from skill default to user override",
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
                "# Template Ejected",
                "",
                f"Template: `{template_name}`",
                "Source: Skill Default",
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
