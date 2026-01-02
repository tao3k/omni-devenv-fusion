# mcp-server/docs.py
"""
Docs Executor - Execute documentation as code

Reads docs from multiple source directories and applies their rules to operations.
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


# =============================================================================
# Documentation Sources Configuration
# =============================================================================
# Add new documentation sources here. Format: (prefix, directory_path)
# - prefix: Used in doc parameter (e.g., "how-to/git-workflow" uses "how-to" prefix)
# - directory: Where the actual .md files are located

# Documentation sources queryable via read_docs (for answering user questions)
# agent/ is loaded via load_*_memory tools (for LLM to follow rules when acting)
DOC_SOURCES = [
    ("docs", "docs"),              # User-facing documentation (for answering questions)
    ("mcp-server", "mcp-server"),  # MCP server implementation docs
]

# =============================================================================
# Core Functions
# =============================================================================


def load_doc(doc_path: str) -> Optional[str]:
    """
    Load documentation content from configured sources.

    Searches through DOC_SOURCES in order and returns the first match.
    """
    for prefix, directory in DOC_SOURCES:
        # Try matching the full doc_path
        full_path = Path(directory) / f"{doc_path}.md"
        if full_path.exists():
            return full_path.read_text()

        # Try with prefix stripped (e.g., "how-to/git-workflow" -> "git-workflow")
        if "/" in doc_path:
            suffix = doc_path.split("/", 1)[1]
            prefix_path = Path(directory) / f"{suffix}.md"
            if prefix_path.exists():
                return prefix_path.read_text()

    return None


def extract_section(content: str, section_name: str) -> str:
    """
    Extract a section from markdown content.

    Looks for headers like '## Section Name' or '### Section Name'
    and returns the content until the next header or end of file.
    """
    # Pattern for section headers (## or ###)
    patterns = [
        rf"(?i)^##+\s*{re.escape(section_name)}\s*$",
        rf"(?i)^##+\s*{re.escape(section_name)}[^\n]*$",
    ]

    lines = content.split('\n')
    in_section = False
    result_lines = []

    for line in lines:
        # Check if this line is a header
        is_header = False
        for pattern in patterns:
            if re.match(pattern, line.strip()):
                is_header = True
                break

        if is_header:
            if in_section:
                # We've hit the next section, stop
                break
            else:
                # Start of target section
                in_section = True
        elif in_section:
            result_lines.append(line)

    return '\n'.join(result_lines).strip()


def list_docs() -> list:
    """List available documentation files from all configured sources."""
    docs = []

    for prefix, directory in DOC_SOURCES:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue

        # Use **/*.md to recursively find all .md files in subdirectories
        for md_file in dir_path.rglob("*.md"):
            if md_file.name.startswith("_"):
                continue  # Skip partials
            # Calculate relative path from the base directory
            try:
                relative_path = md_file.relative_to(dir_path)
                # Build doc path: prefix/subdir/filename
                doc_path = f"{prefix}/{relative_path}"
                # Use stem for files without subdirectory
                if str(relative_path) == md_file.name:
                    docs.append(f"{prefix}/{md_file.stem}")
                else:
                    # Convert extension back to path format
                    doc_path = str(relative_path).replace(".md", "")
                    docs.append(f"{prefix}/{doc_path}")
            except ValueError:
                continue

    return sorted(set(docs))  # Remove duplicates and sort


def register_docs_tools(mcp: Any) -> None:
    """Register all docs execution tools with the MCP server."""

    @mcp.tool()
    async def read_docs(
        doc: str,
        action: str,
        params: Dict[str, Any] = None
    ) -> str:
        """
        Read user documentation to answer questions.

        This tool reads from docs/ directory - content written FOR USERS.
        LLM uses this to answer user questions about the project.

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
                "message": f"docs/{doc}.md or mcp-server/{doc}.md not found",
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
                "message": f"docs/{doc}.md or mcp-server/{doc}.md not found",
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
