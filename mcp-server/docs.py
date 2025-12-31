# mcp-server/docs.py
"""
Docs Executor - Execute documentation as code

Reads docs/*.md files and applies their rules to operations.
Enables: "When Agent needs X → Read docs/X.md → Execute according to rules"

Philosophy:
- docs/* as the source of truth
- MCP tools as the executor of doc rules
- Zero Hallucination: Code doesn't misinterpret rules

Usage:
    @omni-orchestrator read_docs doc="how-to/git-workflow" action="commit" params={...}
"""
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional


def load_doc(doc_path: str) -> Optional[str]:
    """Load documentation content from docs/ directory."""
    path = Path(f"docs/{doc_path}.md")
    if path.exists():
        return path.read_text()
    return None


def extract_section(content: str, section: str) -> str:
    """Extract a section from documentation."""
    # Match headers like ## Section, ### Section
    pattern = rf"(?i)(?:^|\n)##?\s*{re.escape(section)}.*?(?=\n##?\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(0) if match else ""


def list_docs() -> list:
    """List available documentation files."""
    docs_dir = Path("docs")
    if not docs_dir.exists():
        return []
    return [f.stem for f in docs_dir.glob("*.md")]


def register_docs_tools(mcp: Any) -> None:
    """Register all docs execution tools with the MCP server."""

    @mcp.tool()
    async def read_docs(
        doc: str,
        action: str,
        params: Dict[str, Any] = None
    ) -> str:
        """
        Read documentation and execute according to its rules.

        Args:
            doc: Documentation file (e.g., "how-to/git-workflow")
            action: Action to perform (e.g., "commit", "validate")
            params: Parameters for the action

        Returns:
            JSON result with rules and execution guidance
        """
        params = params or {}
        content = load_doc(doc)

        if not content:
            return json.dumps({
                "status": "error",
                "message": f"docs/{doc}.md not found",
                "available_docs": list_docs()
            }, indent=2)

        # Extract relevant section based on action
        rules = extract_section(content, action)

        # Also get the full doc for reference
        return json.dumps({
            "status": "success",
            "doc": doc,
            "action": action,
            "rules": rules if rules else extract_section(content, "Quick Reference"),
            "params": params,
            "source": f"docs/{doc}.md",
            "note": "Rules extracted from documentation - apply these rules to the action"
        }, indent=2)

    @mcp.tool()
    async def get_doc_protocol(doc: str) -> str:
        """
        Get the protocol summary from a documentation file.

        Args:
            doc: Documentation file (e.g., "how-to/git-workflow")

        Returns:
            JSON summary of the protocol
        """
        content = load_doc(doc)

        if not content:
            return json.dumps({
                "status": "error",
                "message": f"docs/{doc}.md not found",
                "available_docs": list_docs()
            }, indent=2)

        # Extract key information
        return json.dumps({
            "status": "success",
            "doc": doc,
            "source": f"docs/{doc}.md",
            "summary": _extract_summary(content)
        }, indent=2)

    @mcp.tool()
    async def list_available_docs() -> str:
        """
        List all available documentation files in docs/.

        Returns:
            JSON list of documentation files
        """
        return json.dumps({
            "status": "success",
            "docs": list_docs()
        }, indent=2)

    @mcp.tool()
    async def execute_doc_action(
        doc: str,
        action: str,
        type: str = None,
        scope: str = None,
        message: str = None
    ) -> str:
        """
        Execute an action according to documentation rules.

        This tool reads docs/{doc}.md and applies its rules to the action.
        Currently supports:
        - doc="how-to/git-workflow", action="commit": Validates and prepares commit

        Args:
            doc: Documentation file
            action: Action to perform
            type: commit type (for git-workflow)
            scope: commit scope (for git-workflow)
            message: commit message (for git-workflow)

        Returns:
            JSON result with validation and next steps
        """
        content = load_doc(doc)

        if not content:
            return json.dumps({
                "status": "error",
                "message": f"docs/{doc}.md not found"
            }, indent=2)

        # Git workflow handler
        if doc == "how-to/git-workflow" and action == "commit":
            from .git_ops import (
                _validate_type, _validate_scope, _validate_message,
                PROJECT_SCOPES, VALID_TYPES
            )

            violations = []

            # Validate
            if type:
                valid, error = _validate_type(type)
                if not valid:
                    violations.append(error)
            if scope:
                valid, error = _validate_scope(scope)
                if not valid:
                    violations.append(error)
            if message:
                valid, error = _validate_message(message)
                if not valid:
                    violations.append(error)

            if violations:
                return json.dumps({
                    "status": "validation_error",
                    "violations": violations,
                    "allowed_types": VALID_TYPES,
                    "allowed_scopes": PROJECT_SCOPES,
                    "reference": "agent/how-to/git-workflow.md"
                }, indent=2)

            # Return ready state (Stop and Ask protocol)
            return json.dumps({
                "status": "ready",
                "message": "Validated according to agent/how-to/git-workflow.md",
                "command": f"just agent-commit {type} {scope} \"{message}\"",
                "protocol": "stop_and_ask",
                "authorization_required": True,
                "reference": "agent/how-to/git-workflow.md"
            }, indent=2)

        # Fallback to generic
        rules = extract_section(content, action)
        return json.dumps({
            "status": "executed",
            "doc": doc,
            "action": action,
            "rules": rules if rules else "No specific rules found",
            "reference": f"docs/{doc}.md"
        }, indent=2)


def _extract_summary(content: str) -> dict:
    """Extract protocol summary from a doc."""
    summary = {
        "quick_ref": "",
        "types": [],
        "scopes": [],
        "rules": []
    }

    # Extract quick reference table
    quick_ref = extract_section(content, "Quick Reference")
    summary["quick_ref"] = quick_ref[:300] + "..." if len(quick_ref) > 300 else quick_ref

    # Extract type info
    types_match = re.search(r"(?i)types?[:\s]+([^\n]+)", content)
    if types_match:
        summary["types"] = [t.strip() for t in types_match.group(1).split(',')]

    # Extract scope info
    scopes_match = re.search(r"(?i)scopes?[:\s]+([^\n]+)", content)
    if scopes_match:
        summary["scopes"] = [s.strip() for s in scopes_match.group(1).split(',')]

    return summary


# =============================================================================
# Export
# =============================================================================

__all__ = ["register_docs_tools", "load_doc", "extract_section"]
