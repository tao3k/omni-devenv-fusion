"""
agent/core/orchestrator/tools.py
Tool Registry for Agent Dependency Injection.

Phase 19: Maps skill tools to agent capabilities using the Skill Registry.
"""

from typing import Dict, Any


def get_tools_for_agent(self, agent_name: str) -> Dict[str, Any]:
    """
    Get tools for a specific agent type.

    Args:
        agent_name: Name of the agent (coder, reviewer, etc.)

    Returns:
        Dict of tool name -> callable function
    """
    from agent.core.registry import get_skill_tools

    # Get tools from loaded skills via Skill Registry
    tools = {}

    # Get filesystem skill tools
    fs_tools = get_skill_tools("filesystem")
    tools.update(fs_tools)

    # Get file_ops skill tools (may have additional tools)
    file_ops_tools = get_skill_tools("file_ops")
    tools.update(file_ops_tools)

    # Add agent-specific tools
    if agent_name == "coder":
        # Coder gets write_file (already included in filesystem tools)
        pass

    elif agent_name == "reviewer":
        # Reviewer gets git and testing tools from skill registry
        git_tools = get_skill_tools("git")
        testing_tools = get_skill_tools("testing")
        tools.update(git_tools)
        tools.update(testing_tools)

    return tools


__all__ = ["get_tools_for_agent"]
