# mcp-server/context_builder.py
"""
 Context Builder - Mission Brief Injection
 Ghost Tool Injection (Adaptive Loader)

Provides utilities to assemble worker context with mission briefs.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Set

from agent.core.router import get_hive_router
from agent.core.router.models import RoutingResult
from agent.core.skill_registry import get_skill_registry

logger = logging.getLogger(__name__)


def build_mission_injection(routing_result: RoutingResult) -> str:
    """
    Generate the mission brief injection for worker context.

    This is the "Telepathic Link" - the mission brief that tells the worker
    exactly what to do, bypassing the need for the worker to reanalyze intent.

     Also includes remote skill suggestions when available.

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

    #  Add remote skill suggestions
    suggestions_block = ""
    if routing_result.remote_suggestions:
        suggestion_lines = []
        for s in routing_result.remote_suggestions[:3]:  # Max 3 suggestions
            name = s.get("name", s.get("id", "Unknown"))
            description = s.get("description", "")[:60]
            suggestion_lines.append(f"  • {name}: {description}...")

        if suggestion_lines:
            suggestions_block = f"""
║                                                                              ║
║ 🎯 SUGGESTED SKILLS (not installed):                                        ║
║ {chr(10).join(suggestion_lines):<76}║
║                                                                              ║
║ Install: @omni('skill.jit_install', {{'skill_name': '<skill_id>'}})        ║
"""

    return f"""

╔══════════════════════════════════════════════════════════════════════════════╗
║ 🚀 MISSION BRIEF (from Orchestrator)                                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ {indicator} | Skills: {skills:<50}║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║ 📋 YOUR OBJECTIVE:                                                          ║
║ {brief:<76}║
{suggestions_block}║                                                                              ║
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
        metadata = registry.get_skill_metadata(skill_name)
        if metadata and metadata.prompts_file:
            # Load skill prompt from file
            skill_dir = registry.skills_dir / skill_name
            prompt_file = skill_dir / metadata.prompts_file
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

    This is the main entry point for the  workflow:
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
    router = get_hive_router()

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
) -> Dict[str, Any]:
    """
    Format context for LLM API call.

    Args:
        context: The assembled context string
        user_message: The user's actual message

    Returns:
        Dict ready for LLM API (system_prompt, user_message)
    """
    return {
        "system_prompt": context,
        "user_message": user_message,
    }


# =============================================================================
#  Ghost Tool Injection (Adaptive Loader)
# =============================================================================


async def fetch_ghost_tools(
    query: str,
    skill_manager: Any,
    limit: int = 5,
    exclude_tools: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve Ghost Tools (unloaded skills) relevant to the query from the index.

    These tools are returned as schemas, allowing the LLM to 'see' and 'call' them.
    The SkillManager will intercept the execution and JIT load the implementation.

    Args:
        query: The user's intent string.
        skill_manager: Instance of SkillManager (for accessing find_tools).
        limit: Max number of ghost tools to retrieve.
        exclude_tools: Set of tool names to exclude (usually already loaded tools).

    Returns:
        List of tool definitions (JSON schemas) ready for LLM tool use.
    """
    ghost_tools: List[Dict[str, Any]] = []
    exclude_tools = exclude_tools or set()

    try:
        # 1. Search Index via SkillManager (The Librarian)
        results = await skill_manager.search_skills(query, limit=limit)

        for tool_doc in results:
            tool_name = tool_doc.get("name")

            # Skip if already loaded or excluded
            if tool_name in exclude_tools:
                continue

            metadata = tool_doc.get("metadata", {})
            schema_str = metadata.get("input_schema", "{}")
            description = tool_doc.get("description", "")

            # Parse schema
            try:
                input_schema = json.loads(schema_str)
            except (json.JSONDecodeError, TypeError):
                input_schema = {"type": "object", "properties": {}}

            # Construct Ghost Tool Definition
            # This matches the structure expected by Claude/OpenAI tool use
            ghost_tool = {
                "name": tool_name,
                "description": f"[GHOST] {description} (Auto-loads on use)",
                "input_schema": input_schema,
                # Tag it as a ghost tool for debugging/telemetry
                "attributes": {"ghost": True, "score": tool_doc.get("score", 0)},
            }

            ghost_tools.append(ghost_tool)
            exclude_tools.add(tool_name)  # Prevent duplicates

        logger.info(f"Injected {len(ghost_tools)} ghost tools for query: '{query[:30]}...'")

    except Exception as e:
        logger.warning(f"Failed to fetch ghost tools: {e}")

    return ghost_tools


def merge_tool_definitions(
    loaded_tools: List[Dict[str, Any]],
    ghost_tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merge real tools and ghost tools, ensuring no duplicates.

    Loaded tools take priority - if a tool is already loaded, the ghost version
    is ignored. This prevents confusion where LLM might see two definitions
    for the same tool.

    Args:
        loaded_tools: List of currently loaded tool definitions.
        ghost_tools: List of ghost tool definitions from the index.

    Returns:
        Merged list with loaded tools first, then unique ghost tools.
    """
    final_tools = list(loaded_tools)
    loaded_names = {t["name"] for t in loaded_tools}

    for ghost in ghost_tools:
        if ghost["name"] not in loaded_names:
            final_tools.append(ghost)

    return final_tools
