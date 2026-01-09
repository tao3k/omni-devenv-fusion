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
def check(skill_name: str | None = None) -> str:
    """
    Validate skill structure against ODF-EP v7.0 standards.

    Use this to check if a skill conforms to the canonical structure defined in
    assets/settings.yaml (skills.architecture).

    Args:
        skill_name: Optional specific skill to check (default: all skills)

    Returns:
        Validation report with score, missing files, and recommendations
    """
    from agent.core.security.structure_validator import SkillStructureValidator

    validator = SkillStructureValidator()

    if skill_name:
        result = validator.validate_skill(skill_name)
        lines = [
            f"# 🔍 Skill Structure Validation: {skill_name}",
            "",
            f"**Valid**: {'✅' if result.valid else '❌'}",
            f"**Score**: {result.score:.1f}%",
            "",
        ]

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

    return "\n".join(lines)
