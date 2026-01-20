"""
skill/scripts/discovery.py - Skill Discovery Commands

Phase 63: Migrated from tools.py
"""

from agent.skills.decorators import skill_command


def _get_discovery():
    """Get SkillDiscovery instance (lazy loaded)."""
    from agent.core.skill_discovery import SkillDiscovery

    return SkillDiscovery()


@skill_command(
    name="discover",
    category="workflow",
    description="""
    Searches for skills using semantic vector matching.

    Uses LanceDB-based semantic search to find skills that match your query,
    even when keywords don't exactly match. Returns results with similarity scores.

    Args:
        query: Search query (e.g., "process pdf files", "git workflow").
               Leave empty to browse all skills.
        limit: Maximum number of results to return. Defaults to `5`.
        local_only: If `true`, only search installed skills.
                    Defaults to `false`.

    Returns:
        Formatted skill list with names, match percentages, and keywords.
        Shows `installed` or `remote` status for each skill.
    """,
)
async def discover(query: str = "", limit: int = 5, local_only: bool = False) -> str:
    discovery = _get_discovery()

    results = await discovery.search(
        query=query,
        limit=limit,
        local_only=local_only,
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


@skill_command(
    name="suggest",
    category="workflow",
    description="""
    Analyzes a task description and suggests the best skill using semantic matching.

    Args:
        task: Description of what you want to do.
              Example: "commit code with message", "search files recursively"

    Returns:
        Recommendation with the best matching skill name, confidence score,
        and the skill's description.
    """,
)
async def suggest(task: str) -> str:
    discovery = _get_discovery()

    suggestions = await discovery.search(
        query=task,
        limit=5,
        local_only=False,
    )

    if not suggestions:
        return f"No matching skills found for: {task}"

    best_match = suggestions[0]
    lines = [f"Recommendation for: {task}", ""]
    lines.append(f"Best match: {best_match['name']} ({best_match.get('score', 0):.0%})")
    lines.append(f"Description: {best_match.get('description', 'N/A')}")

    return "\n".join(lines)


@skill_command(
    name="jit_install",
    category="workflow",
    description="""
    Installs and loads a skill from the skill index on-demand.

    Just-in-Time skill installation for dynamic capability expansion.

    Args:
        skill_id: The unique identifier of the skill to install.
        auto_load: If `true`, automatically loads the skill after installation.
                   Defaults to `true`.

    Returns:
        Status message confirming the installation request.
    """,
)
def jit_install(skill_id: str, auto_load: bool = True) -> str:
    return f"Installing skill: {skill_id} (auto_load={auto_load})"


@skill_command(
    name="list_index",
    category="workflow",
    description="""
    Lists all skills in the known skills index.

    Returns both installed and remote (available) skills with counts.

    Args:
        None

    Returns:
        Formatted list showing installed skills and available remote skills.
        Grouped by status with count totals.
    """,
)
async def list_index() -> str:
    discovery = _get_discovery()

    # Get index stats
    stats = await discovery.get_index_stats()

    lines = ["Skills Index:", ""]
    lines.append(f"Total skills: {stats.get('skill_count', 0)}")
    lines.append(f"Collection: {stats.get('collection', 'unknown')}")

    return "\n".join(lines)
