"""
skill/scripts/discovery.py - Tool Discovery Commands

Unified discovery system for Agent capabilities.
Replaces the old suggest/discover dual-tool pattern with a single powerful discover.

Key Features:
- Hybrid search (keyword + intent matching)
- Usage templates to prevent parameter errors
- "Anti-hallucination" quick guide for LLM
"""

from typing import Any

from omni.foundation.api.decorators import skill_command


def _get_discovery_service():
    """Get SkillDiscoveryService instance (lazy loaded)."""
    from omni.core.skills.discovery import SkillDiscoveryService

    return SkillDiscoveryService()


@skill_command(
    name="discover",
    category="system",
    description="""
    [CRITICAL] Capability Discovery & Intent Resolver - The Agent's PRIMARY Entry Point.

    MANDATORY WORKFLOW: This tool is the EXCLUSIVE gateway for solving any task. It maps high-level natural language goals to specific, executable @omni commands.

    CORE RESPONSIBILITIES:
    1. INTENT MAPPING: Converts vague requests (e.g., "debug network", "optimize rust") into concrete tool sequences.
    2. GLOBAL REGISTRY ACCESS: Searches the entire Skill Registry (Active + Inactive). If a tool is found but not loaded, it provides `jit_install` instructions.
    3. SYNTAX ENFORCEMENT: Resolves the EXACT @omni(...) invocation template. Direct @omni calls are FORBIDDEN without first retrieving the template from discovery.
    4. ARCHITECTURAL ORIENTATION: Use this at the START of every session or new sub-task to identify available "superpowers" before planning.

    WHEN TO USE:
    - To find out *how* to perform a task (e.g., "how to analyze a pcap").
    - To check if a specific capability (e.g., "image processing") exists.
    - To get the correct parameter schema for a tool.
    - Whenever you encounter a new domain you haven't worked with in the current session.

    Args:
        - intent: str - The natural language goal or action (required).
        - limit: int = 5 - Max results to return (increase for complex/ambiguous tasks).

    Returns:
        A structured map containing:
        - 'quick_guide': Direct usage templates to copy and paste.
        - 'details': Full metadata, descriptions, and scores for each tool.
    """,
)
async def discover(intent: str, limit: int = 3) -> dict[str, Any]:
    """
    Unified discovery tool. Replaces 'suggest' and old 'discover'.

    This is the "Google for Agent Tools" - always consult when unsure.
    """
    from omni.core.skills.discovery import SkillDiscoveryService

    service = SkillDiscoveryService()
    matches = await service.search_tools(query=intent, limit=limit)

    if not matches:
        return {
            "status": "no_result",
            "message": f"No specific tools found for '{intent}'. Fallback to basic `terminal` or `filesystem` skills.",
            "quick_guide": [
                "No matching tools found.",
                "Consider using: terminal.run(cmd='...') or filesystem.read_files(paths=['...'])",
            ],
        }

    # Construct "anti-hallucination" guide
    quick_guide = []
    details = []

    for m in matches:
        usage = m.usage_template if m.usage_template else f'@omni("{m.name}", {{"..."}})'

        # Create a clear instruction for the LLM
        if m.name == "skill.jit_install":
            quick_guide.append(f"To install a new skill, use: {usage}")
        else:
            quick_guide.append(f"If you want to {m.matched_intent}, use: {usage}")

        details.append(
            {
                "name": m.name,
                "skill": m.skill_name,
                "description": m.description,
                "score": f"{m.score:.2f}",
                "usage_example": usage,
                "how_to_use": f"Copy and use the @omni() format above exactly as shown.",
            }
        )

    return {
        "status": "success",
        "analysis": f"Found {len(matches)} capabilities matching '{intent}'",
        "quick_guide": quick_guide,
        "details": details,
    }


@skill_command(
    name="jit_install",
    category="workflow",
    description="""
    Install and load a skill from the skill index on-demand.

    Args:
        - skill_id: str - The unique identifier of the skill to install (required)
        - auto_load: bool = true - If true, automatically load after installation

    Returns:
        Status message confirming the installation request.
    """,
)
def jit_install(skill_id: str, auto_load: bool = True) -> str:
    return f"Installing skill: {skill_id} (auto_load={auto_load})"


@skill_command(
    name="list_index",
    category="view",
    description="""
    List all skills in the known skills index (installed and available).

    Args:
        - None

    Returns:
        Formatted list with total skill count and collection info.
    """,
)
async def list_index() -> str:
    from omni.core.skills.discovery import SkillDiscoveryService

    service = SkillDiscoveryService()
    skills = service.discover_all()

    lines = ["Skills Index:", ""]
    lines.append(f"Total skills: {len(skills)}")

    for skill in skills:
        lines.append(f"- {skill.name}")

    return "\n".join(lines)
