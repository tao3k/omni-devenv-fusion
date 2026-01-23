"""
skill/scripts/discovery.py - Skill Discovery Commands
"""

from omni.foundation.api.decorators import skill_command


def _get_discovery():
    """Get SkillDiscovery instance (lazy loaded)."""
    from agent.core.skill_discovery import SkillDiscovery

    return SkillDiscovery()


@skill_command(
    name="discover",
    category="workflow",
    description="""
    Search for skills using semantic vector matching.

    **Parameters**:
    - `query` (optional): Search query (e.g., "process pdf files"). Empty = browse all skills
    - `limit` (optional, default: 5): Maximum number of results
    - `local_only` (optional, default: false): If true, only search installed skills

    **Returns**: Formatted skill list with names, match percentages, and keywords.
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
    Analyze a task description and suggest the best skill using semantic matching.

    **Parameters**:
    - `task` (required): Description of what you want to do (e.g., "commit code", "search files")

    **Returns**: Recommendation with best matching skill name, confidence score, and description.
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
    Install and load a skill from the skill index on-demand.

    **Parameters**:
    - `skill_id` (required): The unique identifier of the skill to install
    - `auto_load` (optional, default: true): If true, automatically load after installation

    **Returns**: Status message confirming the installation request.
    """,
)
def jit_install(skill_id: str, auto_load: bool = True) -> str:
    return f"Installing skill: {skill_id} (auto_load={auto_load})"


@skill_command(
    name="list_index",
    category="workflow",
    description="""
    List all skills in the known skills index (installed and available).

    **Parameters**: None

    **Returns**: Formatted list with total skill count and collection info.
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
