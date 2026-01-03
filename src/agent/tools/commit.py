# agent/tools/commit.py
"""
Commit Workflow Tools

Provides commit message generation from specs and context.

Tools:
- spec_aware_commit: Generate commit message from Spec + Scratchpad
"""
import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from common.mcp_core import log_decision
from common.mcp_core.gitops import get_project_root
import structlog

logger = structlog.get_logger(__name__)

PROJECT_ROOT = get_project_root()


def load_conform_config() -> Dict[str, Any]:
    """Load types and scopes from .conform.yaml."""
    conform_path = PROJECT_ROOT / ".conform.yaml"
    if not conform_path.exists():
        return {"types": [], "scopes": []}

    import yaml
    try:
        with open(conform_path, "r") as f:
            config = yaml.safe_load(f)

        for policy in config.get("policies", []):
            if policy.get("type") == "commit":
                spec = policy.get("spec", {})
                return {
                    "types": spec.get("types", []),
                    "scopes": spec.get("scopes", [])
                }
    except Exception as e:
        logger.warning("Failed to load conform config", error=str(e))

    return {"types": [], "scopes": []}


# Load conform config once at module level
CONFORM_CONFIG = load_conform_config()
COMMIT_TYPES = CONFORM_CONFIG.get("types", ["feat", "fix", "chore", "docs"])
COMMIT_SCOPES = CONFORM_CONFIG.get("scopes", ["mcp", "router", "cli"])


def register_commit_tools(mcp: FastMCP) -> None:
    """Register all commit workflow tools."""

    @mcp.tool()
    async def spec_aware_commit(
        spec_path: Optional[str] = None,
        context: str = "",
    ) -> str:
        """
        Generate a Conventional Commit message from Spec + Scratchpad.

        This tool implements "Spec-Aware GitOps":
        1. Reads the Spec file to extract Context & Goal
        2. Reads Scratchpad for recent activity
        3. Uses AI to generate high-quality commit message

        Args:
            spec_path: Optional path to spec file. Auto-detects if not provided.
            context: Required when no spec exists. Description of changes.

        Returns:
            Generated commit message in conventional format.

        Note:
            After getting the message, use your MCP client's confirmation
            dialog to authorize the actual git commit.
        """
        # Import InferenceClient lazily
        from common.mcp_core.inference import InferenceClient

        project_root = get_project_root()

        # Auto-detect spec path if not provided
        if not spec_path:
            specs_dir = project_root / "agent/specs"
            if specs_dir.exists():
                specs = sorted(specs_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
                if specs:
                    spec_path = str(specs[0])

        # Read spec content
        spec_content = ""
        if spec_path:
            spec_file = project_root / spec_path
            if spec_file.exists():
                spec_content = spec_file.read_text(encoding="utf-8")

        # Read scratchpad
        scratchpad_path = project_root / ".memory/active_context/SCRATCHPAD.md"
        scratchpad_content = ""
        has_scratchpad = False
        if scratchpad_path.exists():
            scratchpad_content = scratchpad_path.read_text(encoding="utf-8")
            lines = scratchpad_content.split("\n")
            scratchpad_content = "\n".join(lines[-100:])
            has_scratchpad = bool(scratchpad_content.strip())

        # Validate: need at least one source of context
        if not spec_content and not has_scratchpad and not context:
            return json.dumps({
                "status": "error",
                "error": "context_required",
                "message": "No spec or scratchpad found. Please provide 'context' parameter.",
                "hint": "Use spec_aware_commit(spec_path='agent/specs/xxx.md') or spec_aware_commit(context='description')"
            }, indent=2)

        # Generate commit message
        client = InferenceClient()

        # Build extra context if provided
        extra_context = f"\n=== USER PROVIDED CONTEXT ===\n{context}" if context else ""

        # Format types and scopes from conform.yaml
        types_str = ", ".join(COMMIT_TYPES)
        scopes_str = ", ".join(COMMIT_SCOPES)

        prompt = f"""Generate a Conventional Commit message based on:

=== SPEC ===
{spec_content[:2000] if spec_content else "(No spec available)"}

=== RECENT ACTIVITY (SCRATCHPAD) ===
{scratchpad_content[:1000] if scratchpad_content else "(No scratchpad available)"}
{extra_context}

Format: <type>(<scope>): <description>

Allowed types: {types_str}
Allowed scopes: {scopes_str}

Provide ONLY the commit message line, no markdown, no explanation."""

        try:
            commit_msg = await client.complete(prompt=prompt, max_tokens=100)
            commit_msg = commit_msg.strip()

            log_decision("spec_aware_commit.generated", {
                "spec_path": spec_path,
                "message": commit_msg[:100]
            }, logger)

            return json.dumps({
                "status": "success",
                "commit_message": commit_msg,
                "message": f"Generated commit message: {commit_msg}",
                "instructions": [
                    f"1. Review: {commit_msg}",
                    "2. Use git tools to commit (MCP client will confirm)",
                ]
            }, indent=2)

        except Exception as e:
            logger.error("spec_aware_commit failed", error=str(e))
            return json.dumps({
                "status": "error",
                "error": str(e),
                "message": f"Failed to generate commit message: {str(e)}"
            }, indent=2)

    logger.info("Commit tools registered: spec_aware_commit")
