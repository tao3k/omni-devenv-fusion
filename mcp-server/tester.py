# mcp-server/tester.py
"""
Smart Test Runner - Enforcing docs/how-to/testing-workflows.md

Implements "Modified-Code Protocol" for intelligent test selection:
- Docs only changes → Skip tests
- MCP server changes → Run MCP tests only
- Infrastructure changes → Run full test suite

Usage:
    @omni-orchestrator smart_test_runner
"""
import json
import subprocess
from typing import Dict, Any, Optional


def get_git_status() -> Dict[str, list]:
    """Get git status for changed files."""
    try:
        # Get staged files
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True
        )
        staged = result.stdout.strip().split('\n') if result.stdout.strip() else []

        # Get unstaged files
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True
        )
        unstaged = result.stdout.strip().split('\n') if result.stdout.strip() else []

        # Get untracked files
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True
        )
        untracked = result.stdout.strip().split('\n') if result.stdout.strip() else []

        return {
            "staged": [f for f in staged if f],
            "unstaged": [f for f in unstaged if f],
            "untracked": [f for f in untracked if f]
        }
    except Exception as e:
        return {"error": str(e)}


def categorize_changes(files: list) -> Dict[str, bool]:
    """Categorize changes by type."""
    categories = {
        "docs_only": True,  # Assume docs only until proven otherwise
        "mcp_server": False,
        "tool_router": False,
        "nix_config": False,
        "code_changes": False,
    }

    all_files = files
    for f in all_files:
        f_lower = f.lower()
        # Docs check (must be only docs to be docs_only)
        if not any(ext in f_lower for extensions in [
            ['.md', '.txt', '.rst', '.adoc'],
            ['.py', '.nix', '.yaml', '.yml', '.json', '.toml']
        ]):
            pass  # Unknown extension, ignore

        # If any non-docs file, docs_only becomes False
        if not (f_lower.endswith('.md') or 'docs/' in f or 'doc/' in f):
            categories["docs_only"] = False

        # Check specific categories
        if 'mcp-server/' in f or f.startswith('mcp-server/'):
            categories["mcp_server"] = True
            categories["code_changes"] = True
        if 'tool-router/' in f or f.startswith('tool-router/'):
            categories["tool_router"] = True
            categories["code_changes"] = True
        if '.nix' in f or 'devenv' in f:
            categories["nix_config"] = True
            categories["code_changes"] = True
        if f.endswith('.py') and 'test' not in f:
            categories["code_changes"] = True

    return categories


def register_tester_tools(mcp: Any) -> None:
    """Register all testing tools with the MCP server."""

    @mcp.tool()
    async def smart_test_runner(focus_file: str = None) -> str:
        """
        Execute tests following docs/how-to/testing-workflows.md.

        Implements the Modified-Code Protocol:
        1. Identify modified files
        2. Categorize changes
        3. Run MINIMUM necessary tests

        Args:
            focus_file: Optional specific file to test

        Returns:
            JSON result with test strategy and execution
        """
        if focus_file:
            return json.dumps({
                "strategy": "focused",
                "file": focus_file,
                "command": f"pytest {focus_file}",
                "reason": "Specific file requested"
            }, indent=2)

        # Step 1: Get git status
        status = get_git_status()
        if "error" in status:
            return json.dumps({
                "status": "error",
                "message": f"Failed to get git status: {status['error']}"
            }, indent=2)

        all_files = status["staged"] + status["unstaged"] + status["untracked"]

        if not all_files:
            return json.dumps({
                "status": "success",
                "message": "No changes detected",
                "strategy": "skip",
                "reason": "No modified files",
                "command": "echo 'No changes to test'"
            }, indent=2)

        # Step 2: Categorize changes
        categories = categorize_changes(all_files)

        # Step 3: Determine strategy (Modified-Code Protocol)
        if categories["docs_only"]:
            return json.dumps({
                "status": "success",
                "message": "Documentation changes only",
                "strategy": "skip",
                "reason": "docs/how-to/testing-workflows.md Rule #3: Docs only → Skip tests",
                "command": "echo 'Docs only - skipping tests'",
                "files": all_files[:5] + ["..."] if len(all_files) > 5 else all_files
            }, indent=2)

        elif categories["mcp_server"]:
            return json.dumps({
                "status": "ready",
                "message": "MCP server changes detected",
                "strategy": "mcp_only",
                "reason": "mcp-server/ modified → Run MCP tests (docs/how-to/testing-workflows.md)",
                "command": "just test-mcp-only",
                "files": all_files[:5] + ["..."] if len(all_files) > 5 else all_files
            }, indent=2)

        elif categories["tool_router"]:
            return json.dumps({
                "status": "ready",
                "message": "Tool router changes detected",
                "strategy": "mcp_only",
                "reason": "tool-router/ modified → Run MCP tests",
                "command": "just test-mcp-only",
                "files": all_files[:5] + ["..."] if len(all_files) > 5 else all_files
            }, indent=2)

        elif categories["nix_config"]:
            return json.dumps({
                "status": "ready",
                "message": "Infrastructure changes detected",
                "strategy": "full",
                "reason": ".nix or devenv modified → Run full test suite",
                "command": "just test",
                "files": all_files[:5] + ["..."] if len(all_files) > 5 else all_files
            }, indent=2)

        else:
            return json.dumps({
                "status": "ready",
                "message": "Code changes detected",
                "strategy": "full",
                "reason": "General code changes → Run full test suite",
                "command": "just test",
                "files": all_files[:5] + ["..."] if len(all_files) > 5 else all_files
            }, indent=2)

    @mcp.tool()
    async def run_test_command(command: str) -> str:
        """
        Run a test command and return results.

        Args:
            command: Test command to run

        Returns:
            JSON result with command output
        """
        # Security: Only allow specific test commands
        allowed_commands = [
            "just test",
            "just test-unit",
            "just test-int",
            "just test-mcp",
            "just test-mcp-only",
            "pytest",
            "devenv test",
        ]

        # Check if command is allowed (simple check)
        is_allowed = any(command.startswith(allowed) for allowed in allowed_commands)

        if not is_allowed:
            return json.dumps({
                "status": "error",
                "message": "Command not allowed",
                "allowed_commands": allowed_commands
            }, indent=2)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )

            return json.dumps({
                "status": "success" if result.returncode == 0 else "failed",
                "command": command,
                "returncode": result.returncode,
                "stdout": result.stdout[:2000] if result.stdout else "",
                "stderr": result.stderr[:500] if result.stderr else ""
            }, indent=2)

        except subprocess.TimeoutExpired:
            return json.dumps({
                "status": "error",
                "message": "Command timed out (>120s)",
                "command": command
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": str(e),
                "command": command
            }, indent=2)

    @mcp.tool()
    async def get_test_protocol() -> str:
        """
        Get the testing protocol summary.

        Returns:
            JSON summary of docs/how-to/testing-workflows.md
        """
        return json.dumps({
            "doc": "docs/how-to/testing-workflows.md",
            "rules": [
                "Rule #1: Fast tests first. Fail fast.",
                "Rule #2: No feature code without test code.",
                "Rule #3: Modified docs only → Skip tests."
            ],
            "strategies": {
                "docs_only": {"action": "skip", "command": "echo 'Docs only'"},
                "mcp_server": {"action": "test-mcp-only", "command": "just test-mcp-only"},
                "tool_router": {"action": "test-mcp-only", "command": "just test-mcp-only"},
                "nix_config": {"action": "full", "command": "just test"},
                "general": {"action": "full", "command": "just test"}
            },
            "test_levels": {
                "unit": {"command": "just test-unit", "timeout": "<30s"},
                "integration": {"command": "just test-int", "timeout": "<2m"},
                "mcp": {"command": "just test-mcp-only", "timeout": "<60s"},
                "full": {"command": "just test", "timeout": "varies"}
            }
        }, indent=2)


# =============================================================================
# Export
# =============================================================================

__all__ = ["register_tester_tools", "get_git_status", "categorize_changes"]
