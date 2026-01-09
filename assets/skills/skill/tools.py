"""
agent/skills/skill/tools.py
Phase 27: JIT Skill Acquisition Commands

Commands:
- skill.discover: Search known skills index
- skill.suggest: Get suggestions for a task
- skill.jit_install: Install and load a skill from index
"""

from agent.skills.decorators import skill_command


@skill_command(category="workflow")
def discover(query: str = "", limit: int = 5) -> str:
    """
    Search the known skills index for matching skills.

    Use this to find skills that can be installed for specific tasks.

    Args:
        query: Search query (matched against name, description, keywords)
        limit: Maximum number of results (default: 5)

    Returns:
        Formatted list of matching skills with installation info
    """
    from agent.core.skill_registry import discover_skills as registry_discover

    result = registry_discover(query=query, limit=limit)

    if result["count"] == 0:
        return "🔍 **No matching skills found**\n\nTry a different search term, or describe your task with `skill.suggest()`."

    lines = ["# 🔍 Skill Discovery Results", ""]

    for skill in result["skills"]:
        lines.append(f"## {skill['name']}")
        lines.append(f"**ID**: `{skill['id']}`")
        lines.append(f"**Description**: {skill['description']}")
        lines.append(f"**Keywords**: {', '.join(skill.get('keywords', []))}")
        lines.append(f"**URL**: {skill['url']}")
        lines.append("")

    lines.append("---")
    lines.append("**To install a skill**:")
    lines.append("```python")
    lines.append(f"# Via omni tool:")
    lines.append(f'@omni("skill.jit_install", {{"skill_id": "{result["skills"][0]["id"]}"}})')
    lines.append("")
    lines.append(f"# Or via CLI:")
    lines.append(f"omni skill install {skill['url']}")
    lines.append("```")

    return "\n".join(lines)


@skill_command(category="workflow")
def suggest(task: str) -> str:
    """
    Analyze a task and suggest relevant skills from the known index.

    Use this when you're not sure which skill to use for a task.

    Args:
        task: Task description (e.g., "analyze pcap file", "work with docker containers")

    Returns:
        Skill suggestions with installation commands
    """
    from agent.core.skill_registry import suggest_skills_for_task as registry_suggest

    result = registry_suggest(task=task)

    lines = ["# 💡 Skill Suggestions", ""]
    lines.append(f"**Task**: {result['query']}")
    lines.append(f"**Found**: {result['count']} matching skills")
    lines.append("")

    if result["count"] == 0:
        lines.append("No matching skills found in the known index.")
        lines.append("\n**Options**:")
        lines.append("1. Use `omni skill install <url>` with a Git URL")
        lines.append("2. Search GitHub for relevant skills")
        lines.append("3. Create a custom skill")
        return "\n".join(lines)

    for skill in result.get("suggestions", []):
        lines.append(f"## {skill['name']}")
        lines.append(f"**ID**: `{skill['id']}`")
        lines.append(f"**Description**: {skill['description']}")
        lines.append(f"**Keywords**: {', '.join(skill.get('keywords', []))}")
        lines.append(f'**Install**: `@omni("skill.jit_install", {{"skill_id": "{skill["id"]}"}})`')
        lines.append("")

    lines.append("---")
    lines.append("**To install the best match**:")
    lines.append("```python")
    lines.append(f'@omni("skill.jit_install", {{"skill_id": "{result["suggestions"][0]["id"]}"}})')
    lines.append("```")

    return "\n".join(lines)


@skill_command(category="workflow")
def jit_install(skill_id: str, auto_load: bool = True) -> str:
    """
    Just-in-Time Skill Installation - Install and load a skill from the known index.

    Use this when you need a skill that's not already installed.

    Args:
        skill_id: Skill ID from known_skills.json (e.g., "pandas-expert", "docker-ops")
        auto_load: Whether to load the skill after installation (default: True)

    Returns:
        Installation status and next steps
    """
    from agent.core.skill_registry import jit_install_skill as registry_jit_install

    result = registry_jit_install(skill_id=skill_id, auto_load=auto_load)

    if not result["success"]:
        lines = ["# ❌ Installation Failed", ""]
        lines.append(f"**Error**: {result.get('error', 'Unknown error')}")
        if "hint" in result:
            lines.append(f"\n**Hint**: {result['hint']}")
        return "\n".join(lines)

    lines = ["# ✅ Skill Installed Successfully", ""]
    lines.append(f"**Skill**: {result['skill_name']}")
    lines.append(f"**URL**: {result['url']}")
    lines.append(f"**Version**: {result['version']}")
    lines.append(f"**Installed at**: {result['installed_path']}")
    lines.append(f"**Loaded**: {'Yes' if result['loaded'] else 'No'}")

    if result.get("loaded"):
        lines.append("\n🎉 **Skill is ready to use!**")
        lines.append(f'Use `@omni("{result["skill_name"]}.help")` to see available commands.')
    else:
        lines.append(f"\n**Load message**: {result.get('load_message', 'Unknown')}")

    return "\n".join(lines)


@skill_command(category="workflow")
def list_index() -> str:
    """
    List all skills in the known skills index.

    Returns:
        Formatted list of all available skills
    """
    from agent.core.skill_discovery import SkillDiscovery

    discovery = SkillDiscovery()
    skills = discovery.list_all()

    lines = ["# 📦 Known Skills Index", ""]
    lines.append(f"**Total**: {len(skills)} skills")
    lines.append("")

    for skill in sorted(skills, key=lambda x: x["name"]):
        lines.append(f"## {skill['name']}")
        lines.append(f"**ID**: `{skill['id']}`")
        lines.append(f"**Description**: {skill['description']}")
        lines.append(f"**Keywords**: {', '.join(skill.get('keywords', []))[:60]}...")
        lines.append("")

    lines.append("---")
    lines.append("**Install any skill**:")
    lines.append("```python")
    lines.append('@omni("skill.jit_install", {"skill_id": "<skill-id>"})')
    lines.append("```")

    return "\n".join(lines)


@skill_command(category="workflow")
def check(skill_name: str | None = None, show_examples: bool = False) -> str:
    """
    Validate skill structure against ODF-EP v7.0 standards.

    Use this to check if a skill conforms to the canonical structure defined in
    assets/settings.yaml (skills.architecture).

    Args:
        skill_name: Optional specific skill to check (default: all skills)
        show_examples: Show optional structure examples (default: False)

    Returns:
        Validation report with score, missing files, and recommendations
    """
    from agent.core.security.structure_validator import SkillStructureValidator
    from common.config.settings import get_setting

    validator = SkillStructureValidator()

    if skill_name:
        result = validator.validate_skill(skill_name)
        skill_dir = validator.skills_dir / skill_name

        lines = [
            f"# 🔍 Skill Structure Validation: {skill_name}",
            "",
            f"**Valid**: {'✅' if result.valid else '❌'}",
            f"**Score**: {result.score:.1f}%",
            f"**Location**: `{skill_dir}`",
            "",
        ]

        # Show actual structure
        if skill_dir.exists():
            lines.append("## 📁 Current Structure")
            lines.append("```")
            for item in sorted(skill_dir.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    lines.append(f"├── {item.name}/")
                    # Show subdir contents
                    subitems = list(item.iterdir())
                    for i, sub in enumerate(subitems[:3]):
                        prefix = "│   └── " if i == len(subitems) - 1 else "│   ├── "
                        lines.append(f"{prefix}{sub.name}")
                    if len(subitems) > 3:
                        lines.append(f"│   └── ... ({len(subitems) - 3} more)")
                else:
                    lines.append(f"├── {item.name}")
            lines.append("```")
            lines.append("")

        if result.missing_required:
            lines.append("## ❌ Missing Required Files")
            for f in result.missing_required:
                lines.append(f"- `{f}`")
            lines.append("")

        if result.disallowed_files:
            lines.append("## 🚫 Disallowed Files (MUST DELETE)")
            for f in result.disallowed_files:
                lines.append(f"- `{f}`")
            lines.append("_These files cause LLM context confusion._")
            lines.append("")

        if result.ghost_files:
            lines.append("## ⚠️ Ghost Files (Non-standard)")
            for f in result.ghost_files:
                lines.append(f"- `{f}`")
            lines.append("")

        if result.warnings:
            lines.append("## ⚡ Warnings")
            for w in result.warnings:
                lines.append(f"- {w}")
            lines.append("")

        if result.valid:
            lines.append("✅ **Skill structure is valid!**")

        # Show optional examples if requested
        if show_examples:
            lines.append("")
            lines.append("## 📚 Optional Structure Examples")
            lines.append("")

            # Get optional structure from settings
            config = validator.config
            optional = config.get("structure", {}).get("optional", [])

            for spec in optional:
                lines.append(f"### `{spec['path']}`")
                lines.append(f"_{spec.get('description', '')}_")
                lines.append("")
                if spec.get("example"):
                    lines.append("```")
                    lines.append(spec["example"].strip())
                    lines.append("```")
                lines.append("")
    else:
        report = validator.get_validation_report()
        summary = report["summary"]

        lines = [
            "# 🔍 Skill Structure Validation Report",
            "",
            f"**Config Version**: {summary['config_version']}",
            f"**Total Skills**: {summary['total_skills']}",
            f"**Valid**: {summary['valid_skills']} ✅ | **Invalid**: {summary['invalid_skills']} ❌",
            f"**Average Score**: {summary['average_score']:.1f}%",
            "",
        ]

        # List invalid skills with details
        invalid_skills = [s for s in report["skills"] if not s["valid"]]
        if invalid_skills:
            lines.append("## ❌ Invalid Skills")
            for skill in invalid_skills:
                lines.append(f"### {skill['skill']}")
                lines.append(f"**Score**: {skill['score']:.1f}%")
                if skill["missing_required"]:
                    lines.append(f"**Missing**: {', '.join(skill['missing_required'])}")
                if skill.get("disallowed_files"):
                    lines.append(f"**🚫 Disallowed**: {', '.join(skill['disallowed_files'])}")
                if skill["ghost_files"]:
                    lines.append(f"**Ghost**: {', '.join(skill['ghost_files'])}")
                lines.append("")

        # List valid skills
        valid_skills = [s for s in report["skills"] if s["valid"]]
        if valid_skills:
            lines.append("## ✅ Valid Skills")
            lines.append(", ".join(f"`{s['skill']}`" for s in valid_skills))

        # Summary of structure requirements
        lines.append("")
        lines.append("## 📋 Structure Requirements")
        lines.append("")
        lines.append("**Required**: SKILL.md, tools.py")
        lines.append("")
        lines.append("**Optional**: scripts/, templates/, references/, assets/, data/, tests/")
        lines.append("")
        lines.append(
            'Run `@omni("skill.check", {"skill_name": "<name>", "show_examples": true})` for details.'
        )

    return "\n".join(lines)


@skill_command(category="workflow")
def create(
    skill_name: str,
    description: str = "A new skill for Omni DevEnv Fusion.",
    author: str = "omni-dev",
    keywords: str = "",
    git_add: bool = True,
) -> str:
    """
    Create a new skill from the template using Jinja2 templates.

    This command scaffolds a new skill with the Phase 35.2 Isolated Sandbox
    architecture, including tools.py router, scripts/ controllers, and
    SKILL.md manifest.

    Args:
        skill_name: Name of the new skill (kebab-case, e.g., "my-custom-skill")
        description: Brief description of the skill's purpose
        author: Author name for the skill manifest
        keywords: Comma-separated keywords for skill discovery
        git_add: Whether to stage created files with git (default: True)

    Returns:
        Creation report with file paths and next steps

    Example:
        ```python
        @omni("skill.create", {
            "skill_name": "my-custom-skill",
            "description": "A skill for processing custom data",
            "keywords": "data, processing, custom"
        })
        ```
    """
    import shutil
    import subprocess
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader

    # Validate skill name
    if not skill_name.replace("-", "").replace("_", "").isalnum():
        return "❌ **Invalid skill name**\n\nUse only alphanumeric characters, hyphens (-), and underscores (_)."

    if not skill_name.islower():
        return "❌ **Skill name must be lowercase**"

    # SSOT: Use common.skills_path for path resolution (Phase 35.2)
    from common.skills_path import SKILLS_DIR

    # Get paths from settings.yaml via SKILLS_DIR
    skills_base = SKILLS_DIR()  # assets/skills (resolved to project root)
    templates_dir = SKILLS_DIR() / ".." / "templates" / "skill"  # assets/templates/skill
    new_skill_dir = skills_base / skill_name

    # Module name for imports (convert kebab-case to snake_case)
    module_name = skill_name.replace("-", "_")

    # Check if skill already exists
    if new_skill_dir.exists():
        return f"❌ **Skill already exists**\n\n`{skill_name}` already exists at `{new_skill_dir}`"

    # Prepare template context
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    context = {
        "skill_name": skill_name,
        "module_name": module_name,  # For Python imports (snake_case)
        "description": description,
        "author": author,
        "keywords": keyword_list,
    }

    # Create Jinja2 environment
    jinja_env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        keep_trailing_newline=True,
    )

    # Files to create with their templates
    template_files = [
        ("SKILL.md.j2", "SKILL.md"),
        ("tools.py.j2", "tools.py"),
        ("guide.md.j2", "guide.md"),
        ("scripts/__init__.py.j2", "scripts/__init__.py"),
        ("scripts/result.j2", "scripts/result.py"),
        ("scripts/error.j2", "scripts/error.py"),
    ]

    created_files = []

    # Create skill directory
    new_skill_dir.mkdir(parents=True, exist_ok=True)
    (new_skill_dir / "scripts").mkdir(parents=True, exist_ok=True)

    # Render and write each template
    for template_name, output_name in template_files:
        template = jinja_env.get_template(template_name)
        content = template.render(**context)
        output_path = new_skill_dir / output_name
        output_path.write_text(content)
        created_files.append(str(output_path.relative_to(skills_base.parent)))

    # Sort created files for consistent output
    created_files.sort()

    # Optionally stage with git
    git_staged = False
    if git_add:
        try:
            subprocess.run(
                ["git", "add", f"assets/skills/{skill_name}"],
                cwd=str(skills_base.parent),
                capture_output=True,
                check=True,
            )
            git_staged = True
        except subprocess.CalledProcessError as e:
            git_staged = False

    # Build output
    lines = [
        f"# ✅ Skill Created Successfully",
        "",
        f"**Skill Name**: `{skill_name}`",
        f"**Location**: `{new_skill_dir}`",
        f"**Files Created**: {len(created_files)}",
        "",
        "## Created Files",
        "",
    ]

    for f in created_files:
        lines.append(f"- `{f}`")

    lines.extend(
        [
            "",
            "## Next Steps",
            "",
            "1. **Add your commands** - Edit `tools.py` to add new commands",
            "2. **Implement logic** - Add implementations in `scripts/`",
            "3. **Test your skill** - Run `just validate`",
            "4. **Commit changes** - Use `/commit` to save your work",
            "",
        ]
    )

    if git_staged:
        lines.append("✅ **Files staged with git** - Ready to commit")
    else:
        lines.append("💡 **To stage files**: `git add assets/skills/{skill_name}`")

    lines.extend(
        [
            "",
            "## Usage",
            "",
            f"```python",
            f'@omni("{skill_name}.help")  # Get skill context',
            f'@omni("{skill_name}.example")  # Run example command',
            f"```",
        ]
    )

    return "\n".join(lines)


@skill_command(category="workflow")
def templates(
    skill_name: str,
    action: str = "list",
    template_name: str = "",
) -> str:
    """
    List or manage skill templates with cascading override support.

    This command supports the "User Overrides > Skill Defaults" pattern:
    - Templates in assets/templates/<skill>/ take priority
    - Templates in assets/skills/<skill>/templates/ are defaults

    Args:
        skill_name: Name of the skill (e.g., "git", "docker")
        action: Action to perform (list, eject, info)
        template_name: Specific template to eject (for "eject" action)

    Returns:
        Formatted output showing template status

    Examples:
        ```python
        @omni("skill.templates", {"skill_name": "git"})
        @omni("skill.templates", {"skill_name": "git", "action": "eject", "template_name": "commit_message.j2"})
        ```
    """
    import importlib.util
    from pathlib import Path

    # SSOT: Use common.skills_path to locate the skill scripts directory
    from common.skills_path import SKILLS_DIR

    # Get the scripts directory for this skill using SSOT
    skill_scripts_dir = SKILLS_DIR("skill", path="scripts")
    templates_file = skill_scripts_dir / "templates.py"

    spec = importlib.util.spec_from_file_location("templates_mod", templates_file)
    templates_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(templates_mod)

    # Validate skill has templates directory
    from common.skills_path import SKILLS_DIR

    skill_templates_dir = SKILLS_DIR(skill_name, path="templates")
    if not skill_templates_dir.exists():
        return f"❌ **Skill not found**\n\nSkill '{skill_name}' has no templates directory at `{skill_templates_dir}`"

    # Dispatch actions
    if action == "list":
        return templates_mod.format_template_list(skill_name)

    if action == "eject":
        if not template_name:
            return "❌ **Template name required**\n\nSpecify which template to eject with `template_name`"
        return templates_mod.format_eject_result(skill_name, template_name)

    if action == "info":
        if not template_name:
            return "❌ **Template name required**\n\nSpecify which template to inspect with `template_name`"
        return templates_mod.format_info_result(skill_name, template_name)

    return f"❌ **Unknown action**\n\nUnknown action '{action}'. Use: list, eject, info"
