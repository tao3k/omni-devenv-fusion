"""
testing_protocol/scripts/protocol.py - Testing Protocol Skill Commands
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

import structlog

from omni.core.skills.script_loader import skill_command

logger = structlog.get_logger(__name__)


def get_git_status() -> Dict[str, list]:
    """Get git status for changed files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True
        )
        staged = result.stdout.strip().split("\n") if result.stdout.strip() else []

        result = subprocess.run(["git", "diff", "--name-only"], capture_output=True, text=True)
        unstaged = result.stdout.strip().split("\n") if result.stdout.strip() else []

        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True
        )
        untracked = result.stdout.strip().split("\n") if result.stdout.strip() else []

        return {
            "staged": [f for f in staged if f],
            "unstaged": [f for f in unstaged if f],
            "untracked": [f for f in untracked if f],
        }
    except Exception as e:
        return {"error": str(e)}


def categorize_changes(files: list) -> Dict[str, bool]:
    """Categorize changes by type."""
    categories = {
        "docs_only": True,
        "mcp_server": False,
        "tool_router": False,
        "nix_config": False,
        "code_changes": False,
    }

    doc_extensions = {".md", ".txt", ".rst", ".adoc"}
    code_extensions = {".py", ".nix", ".yaml", ".yml", ".json", ".toml"}

    for f in files:
        f_lower = f.lower()
        _, ext = os.path.splitext(f_lower)
        ext = ext.lower()

        is_doc = ext in doc_extensions
        is_code = ext in code_extensions

        if not (is_doc or is_code):
            categories["docs_only"] = False

        if is_code and not is_doc:
            categories["docs_only"] = False

        if "mcp-server/" in f or f.startswith("mcp-server/"):
            categories["mcp_server"] = True
            categories["code_changes"] = True
        if "tool-router/" in f or f.startswith("tool-router/"):
            categories["tool_router"] = True
            categories["code_changes"] = True
        if ".nix" in f or "devenv" in f:
            categories["nix_config"] = True
            categories["code_changes"] = True
        if f.endswith(".py") and "test" not in f:
            categories["code_changes"] = True

    return categories


@skill_command(
    name="smart_test_runner",
    category="read",
    description="""
    Executes tests following assets/how-to/testing-workflows.md.

    Implements the Modified-Code Protocol:
    1. Identifies modified files via git status
    2. Categorizes changes (docs, MCP, tool-router, nix, general)
    3. Runs MINIMUM necessary tests based on change type

    Args:
        focus_file: Optional specific file to test (bypasses protocol).

    Returns:
        JSON result with test strategy, recommended command, and reason.
        Strategies: `skip`, `mcp_only`, `full`.

    Example:
        @omni("testing_protocol.smart_test_runner")
        @omni("testing_protocol.smart_test_runner", {"focus_file": "tests/test_core.py"})
    """,
)
async def smart_test_runner(focus_file: Optional[str] = None) -> str:
    if focus_file:
        return json.dumps(
            {
                "strategy": "focused",
                "file": focus_file,
                "command": f"pytest {focus_file}",
                "reason": "Specific file requested",
            },
            indent=2,
        )

    status = get_git_status()
    if "error" in status:
        return json.dumps(
            {"status": "error", "message": f"Failed to get git status: {status['error']}"}, indent=2
        )

    all_files = status["staged"] + status["unstaged"] + status["untracked"]

    if not all_files:
        return json.dumps(
            {
                "status": "success",
                "message": "No changes detected",
                "strategy": "skip",
                "reason": "No modified files",
                "command": "echo 'No changes to test'",
            },
            indent=2,
        )

    categories = categorize_changes(all_files)

    if categories["docs_only"]:
        return json.dumps(
            {
                "status": "success",
                "message": "Documentation changes only",
                "strategy": "skip",
                "reason": "assets/how-to/testing-workflows.md Rule #3: Docs only -> Skip tests",
                "command": "echo 'Docs only - skipping tests'",
                "files": all_files[:5] + ["..."] if len(all_files) > 5 else all_files,
            },
            indent=2,
        )

    elif categories["mcp_server"]:
        return json.dumps(
            {
                "status": "ready",
                "message": "MCP server changes detected",
                "strategy": "mcp_only",
                "reason": "mcp-server/ modified -> Run MCP tests (assets/how-to/testing-workflows.md)",
                "command": "just test-mcp-only",
                "files": all_files[:5] + ["..."] if len(all_files) > 5 else all_files,
            },
            indent=2,
        )

    elif categories["tool_router"]:
        return json.dumps(
            {
                "status": "ready",
                "message": "Tool router changes detected",
                "strategy": "mcp_only",
                "reason": "tool-router/ modified -> Run MCP tests",
                "command": "just test-mcp-only",
                "files": all_files[:5] + ["..."] if len(all_files) > 5 else all_files,
            },
            indent=2,
        )

    elif categories["nix_config"]:
        return json.dumps(
            {
                "status": "ready",
                "message": "Infrastructure changes detected",
                "strategy": "full",
                "reason": ".nix or devenv modified -> Run full test suite",
                "command": "just test",
                "files": all_files[:5] + ["..."] if len(all_files) > 5 else all_files,
            },
            indent=2,
        )

    else:
        return json.dumps(
            {
                "status": "ready",
                "message": "Code changes detected",
                "strategy": "full",
                "reason": "General code changes -> Run full test suite",
                "command": "just test",
                "files": all_files[:5] + ["..."] if len(all_files) > 5 else all_files,
            },
            indent=2,
        )


@skill_command(
    name="run_test_command",
    category="read",
    description="""
    Runs a predefined test command and returns results.

    Validates command against allowed list for safety.

    Args:
        command: Test command to run (e.g., `just test`, `pytest`).

    Returns:
        JSON result with status, returncode, stdout, and stderr.
        Returns error if command not in allowed list.

    Allowed Commands:
        - `just test`, `just test-unit`, `just test-int`, `just test-mcp`, `just test-mcp-only`
        - `pytest`, `devenv test`

    Example:
        @omni("testing_protocol.run_test_command", {"command": "just test-unit"})
    """,
)
async def run_test_command(command: str) -> str:
    allowed_commands = [
        "just test",
        "just test-unit",
        "just test-int",
        "just test-mcp",
        "just test-mcp-only",
        "pytest",
        "devenv test",
    ]

    is_allowed = any(command.startswith(allowed) for allowed in allowed_commands)

    if not is_allowed:
        return json.dumps(
            {
                "status": "error",
                "message": "Command not allowed",
                "allowed_commands": allowed_commands,
            },
            indent=2,
        )

    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)

        return json.dumps(
            {
                "status": "success" if result.returncode == 0 else "failed",
                "command": command,
                "returncode": result.returncode,
                "stdout": result.stdout[:2000] if result.stdout else "",
                "stderr": result.stderr[:500] if result.stderr else "",
            },
            indent=2,
        )

    except subprocess.TimeoutExpired:
        return json.dumps(
            {"status": "error", "message": "Command timed out (>120s)", "command": command},
            indent=2,
        )
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e), "command": command}, indent=2)


@skill_command(
    name="get_test_protocol",
    category="read",
    description="""
    Gets the testing protocol summary from assets/how-to/testing-workflows.md.

    Returns:
        JSON summary with document reference, rules, strategies, and test levels.
        Includes command suggestions for each strategy and level.

    Example:
        @omni("testing_protocol.get_test_protocol")
    """,
)
async def get_test_protocol() -> str:
    return json.dumps(
        {
            "doc": "assets/how-to/testing-workflows.md",
            "rules": [
                "Rule #1: Fast tests first. Fail fast.",
                "Rule #2: No feature code without test code.",
                "Rule #3: Modified docs only -> Skip tests.",
            ],
            "strategies": {
                "docs_only": {"action": "skip", "command": "echo 'Docs only'"},
                "mcp_server": {"action": "test-mcp-only", "command": "just test-mcp-only"},
                "tool_router": {"action": "test-mcp-only", "command": "just test-mcp-only"},
                "nix_config": {"action": "full", "command": "just test"},
                "general": {"action": "full", "command": "just test"},
            },
            "test_levels": {
                "unit": {"command": "just test-unit", "timeout": "<30s"},
                "integration": {"command": "just test-int", "timeout": "<2m"},
                "mcp": {"command": "just test-mcp-only", "timeout": "<60s"},
                "full": {"command": "just test", "timeout": "varies"},
            },
        },
        indent=2,
    )
