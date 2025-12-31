# mcp-server/git_ops.py
"""
Git Operations - Enforcing docs/how-to/git-workflow.md

Tools for safe, protocol-compliant Git operations:
- smart_commit: Execute commits following "Agent-Commit Protocol"
- validate_commit_message: Validate commit format against Conventional Commits
- check_commit_scope: Verify scope against project-scopes (from lefthook.nix)

Reference: docs/how-to/git-workflow.md

Performance: Uses singleton caching - rules loaded once per session.
"""
import asyncio
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# =============================================================================
# Singleton Cache - Rules loaded once per MCP session
# =============================================================================

class GitRulesCache:
    """
    Singleton cache for git workflow rules.
    Rules are loaded from docs/how-to/git-workflow.md on first access,
    then cached in memory for the lifetime of the MCP server.
    """
    _instance = None
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not GitRulesCache._loaded:
            self._load_rules()
            GitRulesCache._loaded = True

    def _load_rules(self):
        """Load rules from docs/how-to/git-workflow.md"""
        doc_path = Path("docs/how-to/git-workflow.md")

        # Default values (fallback)
        self.valid_types = [
            "feat", "fix", "docs", "style", "refactor",
            "perf", "test", "build", "ci", "chore"
        ]
        self.project_scopes = [
            "nix", "mcp", "router", "docs", "cli", "deps", "ci", "data"
        ]
        # Full document content for persistent memory
        self.full_doc = ""

        if doc_path.exists():
            try:
                self.full_doc = doc_path.read_text()
                self._parse_simple_rules(self.full_doc)
            except Exception as e:
                import sys
                print(f"⚠️ [GitRulesCache] Failed to load rules: {e}", file=sys.stderr)

    def _parse_simple_rules(self, content: str):
        """Parse types and scopes from document."""
        import re

        # Extract types from "Type Meanings" table (first table with `feat`, `fix`, etc.)
        # Pattern: | `type` | Description on its own line after "Type Meanings"
        type_section = re.search(r"### Type Meanings.*?(?=### Suggested Scopes)", content, re.DOTALL)
        if type_section:
            # Find all table rows: | `xxx` | something |
            type_rows = re.findall(r"\|\s*`([^`]+)`\s*\|\s*[^|]+\s*\|", type_section.group())
            # Filter valid commit types
            valid = ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore"]
            self.valid_types = [t for t in type_rows if t in valid]

        # Extract scopes from "Suggested Scopes" table
        scope_section = re.search(r"### Suggested Scopes.*?(?=##)", content, re.DOTALL)
        if scope_section:
            scope_rows = re.findall(r"\|\s*`([^`]+)`\s*\|\s*[^|]+\s*\|", scope_section.group())
            # Filter valid scopes
            valid_scopes = ["nix", "mcp", "router", "docs", "cli", "deps", "ci", "data"]
            self.project_scopes = [s for s in scope_rows if s in valid_scopes]

    def get_full_doc(self) -> str:
        """Get full git-workflow.md content for persistent memory."""
        return self.full_doc

    def get_types(self) -> list:
        """Get valid commit types."""
        return self.valid_types

    def get_scopes(self) -> list:
        """Get valid project scopes."""
        return self.project_scopes

    def reload(self):
        """Force reload rules (for debugging/testing)."""
        self._load_rules()


# Global cache instance
_git_rules_cache = GitRulesCache()


# =============================================================================
# Constants (fallback if cache fails)
# =============================================================================

VALID_TYPES = _git_rules_cache.get_types()
PROJECT_SCOPES = _git_rules_cache.get_scopes()

# =============================================================================
# Helper Functions
# =============================================================================

def _validate_type(msg_type: str) -> tuple[bool, str]:
    """Validate commit type."""
    if msg_type.lower() not in VALID_TYPES:
        return False, f"Invalid type '{msg_type}'. Allowed: {', '.join(VALID_TYPES)}"
    return True, ""


def _validate_scope(scope: str, allow_empty: bool = True) -> tuple[bool, str]:
    """Validate commit scope."""
    if not scope and not allow_empty:
        return False, "Scope is required"
    if scope and scope.lower() not in PROJECT_SCOPES:
        return False, f"Invalid scope '{scope}'. Allowed: {', '.join(PROJECT_SCOPES)}"
    return True, ""


def _validate_message(message: str) -> tuple[bool, str]:
    """Validate commit message content."""
    if not message or len(message.strip()) < 3:
        return False, "Message too short (minimum 3 characters)"
    if message.endswith('.'):
        return False, "Message should not end with period"
    if message[0].isupper():
        return False, "Message should start with lowercase"
    return True, ""


# =============================================================================
# MCP Tools
# =============================================================================

def register_git_ops_tools(mcp: Any) -> None:
    """Register all git operations tools with the MCP server."""

    @mcp.tool()
    async def validate_commit_message(
        type: str,
        scope: str,
        message: str
    ) -> str:
        """
        Validate a commit message against docs/how-to/git-workflow.md.

        Checks:
        - Type is valid (feat, fix, docs, etc.)
        - Scope is in project-scopes
        - Message follows rules (lowercase, no period, meaningful)

        Args:
            type: Commit type (feat, fix, docs, etc.)
            scope: Commit scope (nix, mcp, router, etc.)
            message: Commit message

        Returns:
            JSON validation result with suggestions
        """
        violations = []

        # Validate type
        valid, error = _validate_type(type)
        if not valid:
            violations.append({"field": "type", "error": error})

        # Validate scope
        valid, error = _validate_scope(scope)
        if not valid:
            violations.append({"field": "scope", "error": error})

        # Validate message
        valid, error = _validate_message(message)
        if not valid:
            violations.append({"field": "message", "error": error})

        if violations:
            return json.dumps({
                "valid": False,
                "violations": violations,
                "example": f"fix(mcp): handle connection timeout"
            }, indent=2)

        return json.dumps({
            "valid": True,
            "message": "Commit message is valid",
            "formatted": f"{type.lower()}({scope.lower() if scope else ''}): {message}"
        }, indent=2)

    @mcp.tool()
    async def smart_commit(
        type: str,
        scope: str,
        message: str,
        force_execute: bool = False
    ) -> str:
        """
        Execute a commit following docs/how-to/git-workflow.md protocol.

        Protocol Rules (from git-workflow.md):
        1. Default: "Stop and Ask" - Make changes -> Run tests -> Ask user
        2. Override: Only auto-commit if user explicitly says "run just agent-commit"
        3. Never commit without authorization

        Args:
            type: Commit type (feat, fix, docs, etc.)
            scope: Commit scope (nix, mcp, router, etc.)
            message: Commit message
            force_execute: INTERNAL - set by justfile when authorized

        Returns:
            Protocol-compliant response
        """
        # Step 1: Validate all inputs
        violations = []

        valid, error = _validate_type(type)
        if not valid:
            violations.append({"field": "type", "error": error})

        valid, error = _validate_scope(scope)
        if not valid:
            violations.append({"field": "scope", "error": error})

        valid, error = _validate_message(message)
        if not valid:
            violations.append({"field": "message", "error": error})

        if violations:
            return json.dumps({
                "status": "error",
                "message": "Validation failed",
                "violations": violations,
                "example": "fix(mcp): handle connection timeout"
            }, indent=2)

        # Step 2: Protocol enforcement
        if not force_execute:
            # Agent-Commit Protocol: Default "Stop and Ask"
            return json.dumps({
                "status": "ready",
                "protocol": "stop_and_ask",
                "message": "Changes validated. Ready to commit.",
                "command": f"just agent-commit {type.lower()} {scope.lower() if scope else ''} \"{message}\"",
                "authorization_required": True,
                "user_prompt_hint": "Reply 'run just agent-commit' to authorize"
            }, indent=2)

        # Step 3: Execute commit (only when authorized)
        try:
            result = subprocess.run(
                ["just", "agent-commit", type.lower(), scope.lower() if scope else '', message],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                return json.dumps({
                    "status": "success",
                    "message": "Commit executed successfully",
                    "output": result.stdout
                }, indent=2)
            else:
                return json.dumps({
                    "status": "error",
                    "message": "Commit failed",
                    "error": result.stderr,
                    "stdout": result.stdout
                }, indent=2)

        except subprocess.TimeoutExpired:
            return json.dumps({
                "status": "error",
                "message": "Commit timed out (>60s)"
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Commit error: {str(e)}"
            }, indent=2)

    @mcp.tool()
    async def check_commit_scope(scope: str) -> str:
        """
        Check if a scope is valid for this project.

        Reference: lefthook.nix project-scopes

        Args:
            scope: Scope to validate

        Returns:
            JSON result with valid scopes
        """
        scope_lower = scope.lower() if scope else ""

        if scope_lower and scope_lower in PROJECT_SCOPES:
            return json.dumps({
                "valid": True,
                "scope": scope_lower,
                "description": _get_scope_description(scope_lower)
            }, indent=2)

        return json.dumps({
            "valid": False,
            "scope": scope,
            "message": f"'{scope}' is not a valid scope",
            "allowed_scopes": PROJECT_SCOPES
        }, indent=2)

    @mcp.tool()
    async def load_git_workflow_memory() -> str:
        """
        Load full git-workflow.md as persistent memory.

        When conversation involves git/gh operations, call this tool
        to cache the complete workflow rules in context.

        Returns:
            Full git-workflow.md content for memory
        """
        full_doc = _git_rules_cache.get_full_doc()
        return json.dumps({
            "status": "success",
            "source": "docs/how-to/git-workflow.md",
            "memory": full_doc,
            "note": "Load this into persistent context when handling git/gh operations"
        }, indent=2)

    @mcp.tool()
    async def git_status() -> str:
        """
        Show working tree status.

        Automatically loads git-workflow.md rules before execution.

        Returns:
            JSON result with git status output
        """
        # Step 1: Load workflow rules first (triggers singleton cache init)
        _git_rules_cache.get_full_doc()

        # Step 2: Execute git status
        try:
            result = subprocess.run(
                ["git", "status"],
                capture_output=True,
                text=True,
                timeout=30
            )

            return json.dumps({
                "status": "success",
                "rules_loaded": True,
                "source": "docs/how-to/git-workflow.md",
                "output": result.stdout,
                "stderr": result.stderr if result.stderr else None
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"git status failed: {str(e)}"
            }, indent=2)

    @mcp.tool()
    async def git_log(n: int = 10) -> str:
        """
        Show recent commit history.

        Automatically loads git-workflow.md rules before execution.

        Args:
            n: Number of commits to show (default: 10)

        Returns:
            JSON result with git log output
        """
        # Step 1: Load workflow rules first (triggers singleton cache init)
        _git_rules_cache.get_full_doc()

        # Step 2: Execute git log
        try:
            result = subprocess.run(
                ["git", "log", f"-{n}", "--oneline"],
                capture_output=True,
                text=True,
                timeout=30
            )

            return json.dumps({
                "status": "success",
                "rules_loaded": True,
                "source": "docs/how-to/git-workflow.md",
                "commits": [line.strip() for line in result.stdout.strip().split('\n') if line.strip()],
                "raw_output": result.stdout
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"git log failed: {str(e)}"
            }, indent=2)

    @mcp.tool()
    async def git_diff() -> str:
        """
        Show unstaged changes in working directory.

        Automatically loads git-workflow.md rules before execution.

        Returns:
            JSON result with git diff output
        """
        # Step 1: Load workflow rules first (triggers singleton cache init)
        _git_rules_cache.get_full_doc()

        # Step 2: Execute git diff
        try:
            result = subprocess.run(
                ["git", "diff"],
                capture_output=True,
                text=True,
                timeout=30
            )

            has_changes = bool(result.stdout.strip())

            return json.dumps({
                "status": "success",
                "rules_loaded": True,
                "source": "docs/how-to/git-workflow.md",
                "has_changes": has_changes,
                "diff": result.stdout if result.stdout else None,
                "stderr": result.stderr if result.stderr else None
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"git diff failed: {str(e)}"
            }, indent=2)

    @mcp.tool()
    async def git_diff_staged() -> str:
        """
        Show staged changes (diff --cached).

        Automatically loads git-workflow.md rules before execution.

        Returns:
            JSON result with staged diff output
        """
        # Step 1: Load workflow rules first (triggers singleton cache init)
        _git_rules_cache.get_full_doc()

        # Step 2: Execute git diff --cached
        try:
            result = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True,
                text=True,
                timeout=30
            )

            has_staged = bool(result.stdout.strip())

            return json.dumps({
                "status": "success",
                "rules_loaded": True,
                "source": "docs/how-to/git-workflow.md",
                "has_staged_changes": has_staged,
                "staged_diff": result.stdout if result.stdout else None,
                "stderr": result.stderr if result.stderr else None
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"git diff --cached failed: {str(e)}"
            }, indent=2)


def _get_scope_description(scope: str) -> str:
    """Get description for a scope."""
    descriptions = {
        "nix": "Infrastructure: devenv.nix, modules",
        "mcp": "Application: mcp-server logic",
        "router": "Logic: Tool routing & intent",
        "docs": "Documentation",
        "cli": "Tooling: justfile, lefthook",
        "deps": "Dependency management",
        "ci": "GitHub Actions, DevContainer",
        "data": "JSONL examples, assets",
    }
    return descriptions.get(scope, "Unknown scope")


# =============================================================================
# Export
# =============================================================================

__all__ = ["register_git_ops_tools", "VALID_TYPES", "PROJECT_SCOPES"]
