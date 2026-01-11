"""
agent/skills/skill/tools.py
Phase 36.2: Vector-Enhanced Skill Discovery Interface

Commands:
- skill.discover: Semantic search for skills (Local + Remote)
- skill.suggest: Task-based suggestion (Virtual Loading)
- skill.reindex: Manual trigger for vector indexing
"""

from agent.skills.decorators import skill_command


def _get_discovery():
    """Get VectorSkillDiscovery instance (lazy loaded)."""
    from agent.core.skill_discovery import VectorSkillDiscovery

    return VectorSkillDiscovery()


@skill_command(category="workflow")
async def discover(query: str = "", limit: int = 5, local_only: bool = False) -> str:
    """
    Search for skills using semantic vector matching.

    Uses ChromaDB-based semantic search to find skills that match your query,
    even when keywords don't exactly match.

    Args:
        query: Search query (e.g., "process pdf files", "git workflow")
        limit: Maximum results (default: 5)
        local_only: If True, only search installed skills (default: False)

    Returns:
        Formatted skill list with similarity scores

    Examples:
        ```python
        @omni("skill.discover", {"query": "write documentation"})
        @omni("skill.discover", {"query": "docker containers", "local_only": true})
        ```
    """
    discovery = _get_discovery()

    # Call vector search (Phase 36.2)
    results = await discovery.search(
        query=query,
        limit=limit,
        installed_only=local_only,  # local_only=False means search all (local + remote)
    )

    if not results:
        return f"🔍 **No skills found for:** `{query}`\n\nTry broader terms, or run `omni skill reindex` to refresh the index."

    lines = [f"# 🔍 Discovery Results: '{query}'", ""]

    for skill in results:
        # VectorSkillDiscovery returns score in 0-1 range
        score = skill.get("score", 0.0)
        icon = "✅" if skill.get("installed") else "☁️"
        score_pct = f"{(score * 100):.0f}%" if score > 0 else "N/A"

        lines.append(f"## {icon} {skill['name']} (Match: {score_pct})")
        lines.append(f"**ID**: `{skill['id']}`")
        lines.append(f"**Description**: {skill.get('description', 'No description')[:200]}")
        if skill.get("keywords"):
            keywords = (
                skill["keywords"]
                if isinstance(skill["keywords"], list)
                else skill["keywords"].split(",")
            )
            lines.append(f"**Keywords**: {', '.join(k for k in keywords[:5])}")

        if not skill.get("installed"):
            url = skill.get("url", "")
            if url:
                lines.append(f"**URL**: {url}")
            lines.append(f"**Action**: `omni skill install {skill['id']}`")

        lines.append("")

    lines.append("---")
    lines.append("**Tips**:")
    lines.append("- Use `skill.suggest` for task-based recommendations")
    lines.append("- Use `local_only=true` to search only installed skills")

    return "\n".join(lines)


@skill_command(category="workflow")
async def suggest(task: str) -> str:
    """
    Analyze a task and suggest the best skill using semantic matching.

    This uses the same logic as the Router's cold path fallback.
    Searches both local and remote skills to find the best match.

    Args:
        task: Description of what you want to do (e.g., "analyze pcap file", "work with docker")

    Returns:
        Recommendation with reasoning and installation instructions

    Examples:
        ```python
        @omni("skill.suggest", {"task": "convert this video to mp4"})
        @omni("skill.suggest", {"task": "analyze nginx logs"})
        ```
    """
    discovery = _get_discovery()

    # Search all skills (local + remote)
    suggestions = await discovery.search(
        query=task,
        limit=5,
        installed_only=False,  # Search all skills
    )

    if not suggestions:
        return (
            "🤷 **No matching skills found**\n\n"
            "No relevant skills found in the index.\n\n"
            "**Options**:\n"
            "1. Search GitHub for relevant skills\n"
            "2. Create a custom skill with `skill.create`"
        )

    best_match = suggestions[0]

    lines = ["# 💡 Skill Recommendation", ""]
    lines.append(f"**Task**: {task}")
    lines.append("")

    # Show all suggestions
    lines.append("## Top Matches")
    for i, skill in enumerate(suggestions, 1):
        icon = "✅" if skill.get("installed") else "☁️"
        score = skill.get("score", 0.0)
        lines.append(
            f"{i}. {icon} **{skill['name']}** - {skill.get('description', '')[:80]}... ({score:.0%})"
        )

    lines.append("")

    # Best match details
    lines.append(f"## Best Match: {best_match['name']}")
    lines.append(f"**Confidence**: {best_match.get('score', 0):.0%}")
    lines.append(f"**Description**: {best_match.get('description', 'No description')}")
    lines.append("")

    if best_match.get("installed"):
        lines.append("✅ **This skill is installed and ready to use!**")
        lines.append(f'👉 Try: `@omni("{best_match["name"]}.help")`')
    else:
        lines.append("☁️ **This skill is NOT installed.**")
        lines.append("")
        lines.append("**To install**:")
        lines.append("```python")
        lines.append(f'@omni("skill.jit_install", {{"skill_id": "{best_match["id"]}"}})')
        lines.append("```")
        lines.append("")
        lines.append("**Or via CLI**:")
        lines.append(f"`omni skill install {best_match.get('url', best_match['id'])}`")

    return "\n".join(lines)


@skill_command(category="admin")
async def reindex(clear: bool = False) -> str:
    """
    [Admin] Force update the vector index from SKILL.md files.

    This rebuilds the ChromaDB index for skill discovery.
    Run this after installing new skills or modifying SKILL.md.

    Args:
        clear: If True, delete existing index before reindexing

    Returns:
        Index update status

    Examples:
        ```python
        @omni("skill.reindex")  # Incremental update
        @omni("skill.reindex", {"clear": true})  # Full rebuild
        ```
    """
    from agent.core.skill_discovery import reindex_skills_from_manifests

    lines = ["# 🧠 Knowledge Index Update", ""]

    if clear:
        lines.append("**Mode**: Full rebuild (clearing existing index)")
    else:
        lines.append("**Mode**: Incremental update")

    lines.append("")
    lines.append("⏳ *Reindexing skills...*")

    # Run reindexing
    stats = await reindex_skills_from_manifests(clear_existing=clear)

    lines = [
        "# ✅ Knowledge Index Updated",
        "",
        f"**Local Skills Indexed**: {stats['local_skills_indexed']}",
        f"**Remote Skills Indexed**: {stats['remote_skills_indexed']}",
        f"**Total**: {stats['total_skills_indexed']}",
        "",
    ]

    if stats.get("errors"):
        lines.append("## ⚠️ Errors")
        for err in stats["errors"][:5]:  # Show first 5 errors
            lines.append(f"- **{err['skill']}**: {err['error']}")
        if len(stats["errors"]) > 5:
            lines.append(f"_... and {len(stats['errors']) - 5} more_")
        lines.append("")

    lines.append("---")
    lines.append("**Next**: Use `skill.discover` or `skill.suggest` to test.")

    return "\n".join(lines)


@skill_command(category="workflow")
def jit_install(skill_id: str, auto_load: bool = True) -> str:
    """
    Just-in-Time Skill Installation - Install and load a skill from the index.

    Use this when you need a skill that's not already installed.

    Args:
        skill_id: Skill ID (e.g., "pandas-expert", "docker-ops")
        auto_load: Whether to load the skill after installation (default: True)

    Returns:
        Installation status and next steps

    Examples:
        ```python
        @omni("skill.jit_install", {"skill_id": "my-skill"})
        ```
    """
    from agent.core.registry import jit_install_skill as registry_jit_install

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
async def list_index() -> str:
    """
    List all skills in the known skills index.

    Shows both installed (local) and available (remote) skills.

    Returns:
        Formatted list of all available skills

    Examples:
        ```python
        @omni("skill.list_index")
        ```
    """
    from agent.core.skill_discovery import SkillDiscovery

    discovery = SkillDiscovery()
    skills = discovery.list_all()

    # Also get index stats
    from agent.core.skill_discovery import VectorSkillDiscovery

    vsd = VectorSkillDiscovery()
    stats = await vsd.get_index_stats()

    lines = [
        "# 📦 Known Skills Index",
        "",
        f"**Total Skills**: {len(skills)}",
        f"**Indexed in Vector Store**: {stats.get('skill_count', 'N/A')}",
        "",
    ]

    # Group by installed status
    installed = [s for s in skills if s.get("installed", False)]
    remote = [s for s in skills if not s.get("installed", False)]

    if installed:
        lines.append("## ✅ Installed Skills")
        lines.append("")
        for skill in sorted(installed, key=lambda x: x.get("name", "")):
            lines.append(
                f"- **{skill.get('name', skill.get('id', '?'))}** - {skill.get('description', '')[:60]}..."
            )
        lines.append("")

    if remote:
        lines.append(f"## ☁️ Available Skills ({len(remote)})")
        lines.append("")
        for skill in sorted(remote, key=lambda x: x.get("name", "")):
            desc = skill.get("description", "")[:50]
            lines.append(f"- **{skill.get('name', skill.get('id', '?'))}** - {desc}...")
        lines.append("")

    lines.append("---")
    lines.append("**To install a skill**:")
    lines.append("```python")
    lines.append('@omni("skill.jit_install", {"skill_id": "<skill-id>"})')
    lines.append("```")

    return "\n".join(lines)


# =============================================================================
# Legacy commands (kept for backward compatibility)
# =============================================================================


@skill_command(category="workflow")
def check(skill_name: str | None = None, show_examples: bool = False) -> str:
    """
    Validate skill structure against ODF-EP v7.0 standards.
    (Unchanged - kept for backward compatibility)
    """
    from agent.core.security.structure_validator import SkillStructureValidator

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

        if result.missing_required:
            lines.append("## ❌ Missing Required Files")
            for f in result.missing_required:
                lines.append(f"- `{f}`")
            lines.append("")

        if result.valid:
            lines.append("✅ **Skill structure is valid!**")

        return "\n".join(lines)
    else:
        report = validator.get_validation_report()
        summary = report["summary"]

        lines = [
            "# 🔍 Skill Structure Validation Report",
            "",
            f"**Total Skills**: {summary['total_skills']}",
            f"**Valid**: {summary['valid_skills']} ✅ | **Invalid**: {summary['invalid_skills']} ❌",
            f"**Average Score**: {summary['average_score']:.1f}%",
            "",
        ]

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
    Create a new skill from the template.
    (Unchanged - kept for backward compatibility)
    """
    import shutil
    import subprocess
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader
    from common.skills_path import SKILLS_DIR

    # Validate skill name
    if not skill_name.replace("-", "").replace("_", "").isalnum():
        return "❌ **Invalid skill name**\n\nUse only alphanumeric characters, hyphens (-), and underscores (_)."

    if not skill_name.islower():
        return "❌ **Skill name must be lowercase**"

    skills_base = SKILLS_DIR()
    templates_dir = SKILLS_DIR() / ".." / "templates" / "skill"
    new_skill_dir = skills_base / skill_name

    if new_skill_dir.exists():
        return f"❌ **Skill already exists**\n\n`{skill_name}` already exists at `{new_skill_dir}`"

    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
    context = {
        "skill_name": skill_name,
        "module_name": skill_name.replace("-", "_"),
        "description": description,
        "author": author,
        "keywords": keyword_list,
    }

    jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)), keep_trailing_newline=True)

    template_files = [
        ("SKILL.md.j2", "SKILL.md"),
        ("tools.py.j2", "tools.py"),
        ("guide.md.j2", "guide.md"),
        ("scripts/__init__.py.j2", "scripts/__init__.py"),
        ("scripts/result.j2", "scripts/result.py"),
        ("scripts/error.j2", "scripts/error.py"),
    ]

    created_files = []
    new_skill_dir.mkdir(parents=True, exist_ok=True)
    (new_skill_dir / "scripts").mkdir(parents=True, exist_ok=True)

    for template_name, output_name in template_files:
        template = jinja_env.get_template(template_name)
        content = template.render(**context)
        output_path = new_skill_dir / output_name
        output_path.write_text(content)
        created_files.append(str(output_path.relative_to(skills_base.parent)))

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
        except subprocess.CalledProcessError:
            git_staged = False

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

    for f in sorted(created_files):
        lines.append(f"- `{f}`")

    lines.extend(
        [
            "",
            "## Next Steps",
            "",
            "1. **Add your commands** - Edit `tools.py`",
            "2. **Implement logic** - Add in `scripts/`",
            "",
        ]
    )

    if git_staged:
        lines.append("✅ **Files staged with git**")
    else:
        lines.append("💡 **To stage files**: `git add assets/skills/{skill_name}`")

    return "\n".join(lines)


@skill_command(category="view")
def list_tools() -> str:
    """List all registered MCP tools."""
    from agent.skills.skill.scripts.list_tools import format_tools_list

    return format_tools_list(compact=False)


@skill_command(category="view")
def tools() -> str:
    """List all registered MCP tools (compact)."""
    from agent.skills.skill.scripts.list_tools import format_tools_list

    return format_tools_list(compact=True)


@skill_command(category="read")
def templates(skill_name: str, action: str = "list") -> str:
    """
    List or manage skill templates.

    Template Locations:
    - User Overrides: assets/templates/{skill}/
    - Skill Defaults: assets/skills/{skill}/templates/

    Args:
        skill_name: Name of the skill (e.g., "git", "filesystem")
        action: Action to perform (default: "list")
            - "list": List available templates
            - "info": Get info about a specific template

    Returns:
        Formatted template list or info

    Examples:
        ```python
        @omni("skill.templates", {"skill_name": "git", "action": "list"})
        @omni("skill.templates", {"skill_name": "git", "action": "info", "template_name": "commit_message.j2"})
        ```
    """
    from agent.skills.skill.scripts import templates as template_module

    if action == "list":
        return template_module.format_template_list(skill_name)
    elif action == "info":
        import re

        # Extract template_name from kwargs if passed
        # This is a simple approach - full implementation would parse args
        return f"# 📄 Template Info\n\n**Skill**: {skill_name}\n\n**Note**: Use template_name parameter for specific template info."
    else:
        return f"# ❌ Unknown action: {action}\n\n**Valid actions**: list, info"
