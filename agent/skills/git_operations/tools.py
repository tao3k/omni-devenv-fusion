# agent/skills/git_operations/tools.py
"""
Git Operations Skill - MCP Tool Definitions

This module contains the MCP tool definitions for the Git Operations skill.
The actual implementation is registered in src/mcp_server/executor/git_ops.py.

Available Tools:
- git_status: Show working tree status
- git_diff: Show unstaged changes
- git_diff_staged: Show staged changes
- git_log: Show recent commit history
- smart_commit: Execute commit with authorization protocol
- suggest_commit_message: Generate conventional commit message
- validate_commit_message: Validate commit message format
- check_commit_scope: Verify scope against cog.toml
- spec_aware_commit: Generate commit from Spec + Scratchpad

Usage:
    This skill is automatically loaded when git operations are needed.
    Tools are available through the executor MCP server.
"""
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class GitToolDefinition:
    """Definition of a git operation tool."""
    name: str
    description: str
    parameters: dict
    returns: str


# Tool definitions for skill documentation
GIT_OPS_TOOLS = [
    GitToolDefinition(
        name="git_status",
        description="Show working tree status with rules and protocol info",
        parameters={},
        returns="JSON with status, rules_loaded, workflow_protocol",
    ),
    GitToolDefinition(
        name="git_diff",
        description="Show unstaged changes in the working directory",
        parameters={},
        returns="JSON with status, has_changes, diff content",
    ),
    GitToolDefinition(
        name="git_diff_staged",
        description="Show staged changes ready for commit",
        parameters={},
        returns="JSON with status, has_staged_changes, staged_diff",
    ),
    GitToolDefinition(
        name="git_log",
        description="Show recent commit history",
        parameters={"n": "Number of commits to show (default: 10)"},
        returns="JSON with status, commits list",
    ),
    GitToolDefinition(
        name="smart_commit",
        description="Execute commit with Auto-Fix intelligence and authorization protocol",
        parameters={
            "type": "Commit type (feat, fix, docs, etc.)",
            "scope": "Commit scope (from cog.toml)",
            "message": "Commit message (imperative mood, lowercase)",
            "force_execute": "Skip authorization (use with caution)",
        },
        returns="JSON with status, authorization_required, auth_token",
    ),
    GitToolDefinition(
        name="execute_authorized_commit",
        description="Execute a commit that was authorized via smart_commit",
        parameters={"auth_token": "Token from smart_commit response"},
        returns="JSON with status, message, token_consumed",
    ),
    GitToolDefinition(
        name="suggest_commit_message",
        description="Generate conventional commit message from staged changes",
        parameters={"spec_path": "Optional path to feature spec"},
        returns="JSON with suggested type, scope, message",
    ),
    GitToolDefinition(
        name="validate_commit_message",
        description="Validate commit message against cog.toml/.conform.yaml rules",
        parameters={
            "type": "Commit type",
            "scope": "Commit scope",
            "message": "Commit message",
        },
        returns="JSON with valid status and formatted message",
    ),
    GitToolDefinition(
        name="check_commit_scope",
        description="Check if scope is valid in cog.toml",
        parameters={"scope": "Scope to validate"},
        returns="JSON with valid status and allowed scopes",
    ),
    GitToolDefinition(
        name="spec_aware_commit",
        description="Generate commit message from Spec + Scratchpad context",
        parameters={
            "spec_path": "Path to spec file",
            "force_execute": "Skip authorization",
        },
        returns="JSON with generated message and authorization token",
    ),
    GitToolDefinition(
        name="load_git_workflow_memory",
        description="Load git workflow rules into LLM context",
        parameters={},
        returns="JSON with git protocol content",
    ),
    GitToolDefinition(
        name="check_commit_authorization",
        description="Check authorization protocol status and pending tokens",
        parameters={},
        returns="JSON with protocol status and workflow guidance",
    ),
]


def get_tool_names() -> List[str]:
    """Get list of all tool names in this skill."""
    return [tool.name for tool in GIT_OPS_TOOLS]


def get_tool_definition(name: str) -> Optional[GitToolDefinition]:
    """Get definition for a specific tool."""
    for tool in GIT_OPS_TOOLS:
        if tool.name == name:
            return tool
    return None


def list_tools() -> List[GitToolDefinition]:
    """List all tool definitions in this skill."""
    return GIT_OPS_TOOLS


__all__ = [
    "GIT_OPS_TOOLS",
    "GitToolDefinition",
    "get_tool_names",
    "get_tool_definition",
    "list_tools",
]
