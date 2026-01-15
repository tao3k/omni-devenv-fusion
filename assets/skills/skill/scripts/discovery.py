"""
skill/scripts/discovery.py - Skill Discovery Commands

Phase 63: Migrated from tools.py
"""

from agent.skills.decorators import skill_script


def _get_discovery():
    """Get VectorSkillDiscovery instance (lazy loaded)."""
    from agent.core.skill_discovery import VectorSkillDiscovery

    return VectorSkillDiscovery()


@skill_script(
    name="discover",
    category="workflow",
    description="Search for skills using semantic vector matching.",
)
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
    """
    discovery = _get_discovery()

    results = await discovery.search(
        query=query,
        limit=limit,
        installed_only=local_only,
    )

    if not results:
        return f"No skills found for: {query}"

    lines = [f"Discovery Results: '{query}'", ""]

    for skill in results:
        score = skill.get("score", 0.0)
        icon = "installed" if skill.get("installed") else "remote"
        score_pct = f"{(score * 100):.0f}%" if score > 0 else "N/A"

        lines.append(f"- {skill['name']} ({icon}, match: {score_pct})")
        lines.append(f"  ID: {skill.get('id', 'N/A')}")

        if skill.get("keywords"):
            keywords = (
                skill["keywords"]
                if isinstance(skill["keywords"], list)
                else skill["keywords"].split(",")
            )
            lines.append(f"  Keywords: {', '.join(k.strip() for k in keywords[:5])}")

        lines.append("")

    return "\n".join(lines)


@skill_script(
    name="suggest",
    category="workflow",
    description="Analyze a task and suggest the best skill.",
)
async def suggest(task: str) -> str:
    """
    Analyze a task and suggest the best skill using semantic matching.

    Args:
        task: Description of what you want to do

    Returns:
        Recommendation with reasoning
    """
    discovery = _get_discovery()

    suggestions = await discovery.search(
        query=task,
        limit=5,
        installed_only=False,
    )

    if not suggestions:
        return f"No matching skills found for: {task}"

    best_match = suggestions[0]
    lines = [f"Recommendation for: {task}", ""]
    lines.append(f"Best match: {best_match['name']} ({best_match.get('score', 0):.0%})")
    lines.append(f"Description: {best_match.get('description', 'N/A')}")

    return "\n".join(lines)


@skill_script(
    name="jit_install",
    category="workflow",
    description="Install and load a skill from the index.",
)
def jit_install(skill_id: str, auto_load: bool = True) -> str:
    """
    Just-in-Time Skill Installation.

    Args:
        skill_id: Skill ID to install
        auto_load: Whether to load after install

    Returns:
        Installation status
    """
    from mcp.types import Tool

    # This is a placeholder - actual implementation would be more complex
    return f"Installing skill: {skill_id} (auto_load={auto_load})"


@skill_script(
    name="list_index",
    category="workflow",
    description="List all skills in the known skills index.",
)
async def list_index() -> str:
    """
    List all skills in the known skills index.

    Returns:
        Formatted list of installed and available skills
    """
    discovery = _get_discovery()
    skills = discovery.list_all()

    if not skills:
        return "No skills in index"

    lines = ["Skills Index:", ""]
    installed = []
    remote = []

    for skill in skills:
        if skill.get("installed"):
            installed.append(skill)
        else:
            remote.append(skill)

    if installed:
        lines.append(f"Installed ({len(installed)}):")
        for s in installed:
            lines.append(f"  - {s['name']}")

    if remote:
        lines.append(f"Available ({len(remote)}):")
        for s in remote:
            lines.append(f"  - {s['name']} (remote)")

    return "\n".join(lines)
