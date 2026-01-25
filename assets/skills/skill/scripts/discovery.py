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
    [CRITICAL] Tool Registry Lookup - The ONLY Way to Call @omni Commands

    MANDATORY RULE: Before calling ANY @omni(...) command, you MUST call skill.discover first
    to get the exact tool name and correct usage template. Direct @omni calls are FORBIDDEN
    without先用 skill.discover 确定工具.

    WHEN TO USE (ALWAYS call this first):
    1. ANY time you want to call a tool via @omni(...)
    2. You are unsure which tool to use
    3. You need the exact tool name and arguments schema
    4. You need to verify a tool exists before calling it
    5. You are starting any new task that requires a tool

    WORKFLOW:
    1. User: "I need to analyze a GitHub repository"
    2. You call: skill.discover(intent="analyze github repository structure")
    3. Returns: @omni("software_engineering.analyze_project_structure", {"depth": 3})
    4. NOW you can call the tool with confidence

    Args:
        - intent: str - Your goal/action in natural language (required)
        - limit: int = 3 - Max results to return

    Returns:
        List of matching tools with exact @omni() usage templates.
        Copy the template EXACTLY as shown - no modifications allowed.
    """,
)
async def discover(intent: str, limit: int = 3) -> dict[str, Any]:
    """
    Unified discovery tool. Replaces 'suggest' and old 'discover'.

    This is the "Google for Agent Tools" - always consult when unsure.
    """
    from omni.core.skills.discovery import SkillDiscoveryService

    service = SkillDiscoveryService()
    matches = service.search_tools(query=intent, limit=limit)

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
