# mcp-server/context_builder.py
"""
Phase 14: Context Builder - Mission Brief Injection

Provides utilities to assemble worker context with mission briefs.
"""
from typing import List, Dict, Any, Optional
from agent.core.router import RoutingResult, get_router
from agent.core.skill_registry import get_skill_registry


def build_mission_injection(routing_result: RoutingResult) -> str:
    """
    Generate the mission brief injection for worker context.

    This is the "Telepathic Link" - the mission brief that tells the worker
    exactly what to do, bypassing the need for the worker to reanalyze intent.

    Args:
        routing_result: The routing result from SemanticRouter

    Returns:
        Formatted mission brief block for context injection
    """
    brief = routing_result.mission_brief
    skills = ", ".join(routing_result.selected_skills)
    confidence = routing_result.confidence

    # Confidence indicator
    if confidence >= 0.9:
        indicator = "🟢 HIGH CONFIDENCE"
    elif confidence >= 0.7:
        indicator = "🟡 MEDIUM CONFIDENCE"
    else:
        indicator = "🔴 LOW CONFIDENCE"

    return f"""

╔══════════════════════════════════════════════════════════════════════════════╗
║ 🚀 MISSION BRIEF (from Orchestrator)                                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ {indicator} | Skills: {skills:<50}║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║ 📋 YOUR OBJECTIVE:                                                          ║
║ {brief:<76}║
║                                                                              ║
║ 💡 FOCUS ONLY ON THIS OBJECTIVE. Use the activated skills above.            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


def build_worker_context(
    routing_result: RoutingResult,
    base_prompt: str = "",
) -> str:
    """
    Build complete worker context with mission brief injection.

    This assembles:
    1. Base system prompt
    2. Mission brief (highest priority)
    3. Relevant skill prompts

    Args:
        routing_result: The routing result from SemanticRouter
        base_prompt: Optional base system prompt to prepend

    Returns:
        Complete context string for the worker
    """
    registry = get_skill_registry()
    mission_injection = build_mission_injection(routing_result)

    # Get skill contexts for selected skills
    skill_contexts = []
    for skill_name in routing_result.selected_skills:
        manifest = registry.get_skill_manifest(skill_name)
        if manifest and manifest.prompts_file:
            # Load skill prompt from file
            skill_dir = registry.skills_dir / skill_name
            prompt_file = skill_dir / manifest.prompts_file
            if prompt_file.exists():
                skill_contexts.append(f"\n--- {skill_name.upper()} SKILL ---\n")
                skill_contexts.append(prompt_file.read_text())

    skills_context = "\n".join(skill_contexts)

    # Assemble full context
    context_parts = []
    if base_prompt:
        context_parts.append(base_prompt)
    context_parts.append(mission_injection)
    if skills_context:
        context_parts.append(skills_context)

    return "\n\n".join(context_parts)


async def route_and_build_context(
    user_query: str,
    chat_history: List[Dict] = None,
    base_prompt: str = "",
) -> Dict[str, Any]:
    """
    Convenience function: Route request AND build worker context in one call.

    This is the main entry point for the Phase 14 workflow:
    1. Route (SemanticRouter) -> 2. Brief -> 3. Build Context

    Args:
        user_query: The user's request
        chat_history: Optional conversation history
        base_prompt: Optional base system prompt

    Returns:
        Dict with:
            - routing_result: The RoutingResult object
            - context: Complete worker context string
            - skills: List of selected skill names
    """
    router = get_router()

    # Step 1: Route and get mission brief
    routing_result = await router.route(user_query, chat_history)

    # Step 2: Build context with mission injection
    context = build_worker_context(routing_result, base_prompt)

    return {
        "routing_result": routing_result,
        "context": context,
        "skills": routing_result.selected_skills,
        "mission_brief": routing_result.mission_brief,
    }


def format_context_for_llm(
    context: str,
    user_message: str,
    include_mission_highlight: bool = True,
) -> Dict[str, Any]:
    """
    Format context for LLM API call.

    Args:
        context: The assembled context string
        user_message: The user's actual message
        include_mission_highlight: Whether to highlight mission in output

    Returns:
        Dict ready for LLM API (system_prompt, user_message)
    """
    return {
        "system_prompt": context,
        "user_message": user_message,
    }
