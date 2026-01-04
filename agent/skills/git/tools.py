"""
agent/skills/git/tools.py
Git Skill: Critical Operations Only

Phase 13.10: Executor Mode - MCP handles dangerous operations.

This module provides only critical git operations (commit, push).
Safe operations (status, diff, log, add) should be done via Claude's native bash.

Philosophy:
- MCP = "The Guard" - handles operations that need explicit confirmation
- Claude-native bash = "The Explorer" - safe read operations
"""
import asyncio
from typing import List, Optional
from mcp.server.fastmcp import FastMCP
from common.mcp_core.gitops import run_git_cmd
from common.mcp_core.inference import InferenceClient


# =============================================================================
# Sensitive File Scanner (LLM-powered)
# =============================================================================

SENSITIVE_PATTERNS = [
    "*.env", ".env*", "*.pem", "*.key", "*.crt",
    "credentials*", "secrets*", "password*", "api_key*",
    "*.sqlite3", "*.db", "*.sqlite",
    "token.json", "service-account*.json",
    ".npmrc", ".pypirc",  # Package manager auth
]

WARNING_MESSAGE = """
⚠️ **SECURITY ALERT: Potential Sensitive Files Detected**

The following files match known sensitive patterns:
{files}

**Recommendations:**
1. Add these to `.gitignore` before committing
2. Use environment variables for secrets
3. Rotate any exposed credentials

**Would you like to:**
- [c] Continue staging anyway (risky)
- [s] Skip these files and stage safe files only
- [a] Abort staging
"""


def _get_staged_files() -> List[str]:
    """Get list of files that would be staged."""
    import subprocess
    result = subprocess.run(
        ["git", "add", "-n", "--dry-run"],
        capture_output=True,
        text=True,
        cwd=run_git_cmd.__self__.cwd if hasattr(run_git_cmd, "__self__") else "."
    )
    files = []
    for line in result.stdout.splitlines():
        if line.startswith("Would add"):
            file_path = line.replace("Would add", "").strip().lstrip("./")
            files.append(file_path)
    return files


async def _scan_for_sensitive_files(files: List[str]) -> tuple[List[str], str]:
    """
    Use LLM to scan files for potential secrets or sensitive content.

    Returns:
        (alert_files, warning_message) - Files to alert about, and formatted warning
    """
    if not files:
        return [], ""

    # Build file list for LLM
    file_list = "\n".join(f"- {f}" for f in files)

    client = InferenceClient()

    prompt = f"""You are a security scanner. Review this list of files being staged for commit.

FILES TO SCAN:
{file_list}

Check for:
1. Files containing secrets, API keys, passwords, tokens
2. Environment files (.env, .env.*)
3. Database files with potential data
4. Configuration files with credentials
5. Any file with suspicious names like "secrets", "credentials", "token"

Return ONLY a JSON array of filenames that match sensitive patterns, or empty array if none:
["file1.env", "file2.json", ...]

If no sensitive files found, return: []"""

    try:
        result = await client.complete(
            system_prompt="You are a security scanner. Return ONLY valid JSON.",
            user_query=prompt,
            max_tokens=256,
        )

        if result["success"]:
            import json
            try:
                sensitive = json.loads(result["content"].strip())
                if isinstance(sensitive, list):
                    alert_files = [f for f in files if any(s in f for s in sensitive)]
                else:
                    alert_files = []
            except json.JSONDecodeError:
                # Fallback: simple pattern matching
                alert_files = [f for f in files if any(p in f.lower() for p in
                    ["env", "secret", "credential", "token", "key", "password"])]
        else:
            alert_files = []
    except Exception:
        # Fallback to simple pattern matching on filename
        alert_files = [f for f in files if any(p in f.lower() for p in
            ["env", "secret", "credential", "token", "key", "password", ".npmrc", ".pypirc"])]

    warning = ""
    if alert_files:
        warning = WARNING_MESSAGE.format(
            files="\n".join(f"- {f}" for f in alert_files[:10])  # Max 10 files
        )

    return alert_files, warning


# =============================================================================
# Critical Git Tools (Require explicit confirmation)
# =============================================================================

async def git_stage_all(scan: bool = True) -> str:
    """
    Stage all changes with optional security scan.

    ⚠️ SECURITY SCAN ENABLED by default.

    Args:
        scan: If True, scan for sensitive files before staging

    Returns:
        Staging result with security warnings if applicable

    Workflow:
    1. Get list of files to be staged
    2. If scan=True: Run LLM security scan
    3. If sensitive files found: Return warning (don't stage yet)
    4. If safe or scan=False: Execute git add -A
    """
    # Get files to be staged
    import subprocess
    result = subprocess.run(
        ["git", "add", "-n", "--dry-run"],
        capture_output=True,
        text=True
    )

    files_to_stage = []
    for line in result.stdout.splitlines():
        if line.startswith("Would add"):
            file_path = line.replace("Would add", "").strip().lstrip("./")
            files_to_stage.append(file_path)

    if not files_to_stage:
        return "Nothing to stage - no changes detected."

    # Security scan
    if scan:
        alert_files, warning = await _scan_for_sensitive_files(files_to_stage)

        if alert_files:
            return f"{warning}\n\n**Files to stage ({len(files_to_stage)} total):**\n" + \
                   "\n".join(f"- {f}" for f in files_to_stage[:20]) + \
                   (f"\n... and {len(files_to_stage) - 20} more" if len(files_to_stage) > 20 else "") + \
                   "\n\n**Reply with:**\n- [c] Continue staging anyway\n- [s] Skip sensitive files\n- [a] Abort"

    # Execute staging
    try:
        output = await run_git_cmd(["add", "-A"])
        safe_count = len([f for f in files_to_stage if f not in alert_files]) if scan else len(files_to_stage)
        return f"✅ Staged {safe_count} file(s)\n\n" + \
               "\n".join(f"- {f}" for f in files_to_stage[:15]) + \
               (f"\n... and {len(files_to_stage) - 15} more" if len(files_to_stage) > 15 else "")
    except Exception as e:
        return f"Staging failed: {e}"

async def git_commit(message: str, skip_hooks: bool = False) -> str:
    """
    Execute git commit directly.

    ⚠️ AUTHORIZATION PROTOCOL (MUST FOLLOW):
    1. BEFORE calling this tool: Show Commit Analysis to user
       - Type: feat/fix/docs/style/refactor/test/chore
       - Scope: git-ops/cli/docs/mcp/router/...
       - Message: describe change
    2. Wait for user to say "yes" or "confirm"
    3. ONLY then call this tool

    ❌ NEVER call this tool without showing analysis first
    ❌ Direct 'git commit' is PROHIBITED - use this tool

    Args:
        message: Conventional commit message (e.g., "feat(core): add feature")
        skip_hooks: If True, skip pre-commit and commit-msg hooks (--no-verify)
    """
    # Basic format check - cog will validate fully
    if ":" not in message:
        return "Error: Message must follow 'type(scope): subject' format."

    # Check for staged changes
    try:
        stat = await run_git_cmd(["diff", "--cached", "--stat"])
        if not stat.strip():
            return "Error: No staged changes. Stage first with 'git add' via bash."
    except Exception as e:
        return f"Error checking staged changes: {e}"

    # Build commit command
    # Try cog commit first (if cog.toml exists), otherwise use git directly
    import subprocess
    from pathlib import Path
    from common.mcp_core.gitops import get_project_root
    from common.mcp_core.settings import get_setting

    project_root = get_project_root()
    cog_toml_path = get_setting("config.cog_toml", "cog.toml")
    cog_toml = project_root / cog_toml_path

    use_cog = cog_toml.exists()

    if use_cog:
        # Use cog commit - it handles message validation
        cmd = ["cog", "commit", "-m", message]
    else:
        cmd = ["commit", "-m", message]
        if skip_hooks:
            cmd.insert(1, "--no-verify")

    # Execute commit
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_root)
        )
        if result.returncode != 0:
            # If cog fails, show helpful error
            if use_cog:
                return f"Commit Failed (cog):\n{result.stderr}"
            return f"Commit Failed: {result.stderr}"

        hook_note = " (hooks skipped)" if skip_hooks and not use_cog else ""
        return f"Commit Successful{hook_note}:\n{result.stdout}"
    except Exception as e:
        return f"Commit Failed: {e}"


async def git_push() -> str:
    """
    Execute git push to remote.

    Use this after successful commit to push changes.

    Note: For first push of a new branch, use 'git push -u origin branch_name' via bash.
    """
    try:
        output = await run_git_cmd(["push"])
        return f"Push Successful:\n{output}"
    except Exception as e:
        return f"Push Failed: {e}\n\nTip: For new branches, use: git push -u origin <branch>"


# =============================================================================
# Registration
# =============================================================================

def register(mcp: FastMCP):
    """Register critical Git tools only."""
    mcp.tool()(git_stage_all)
    mcp.tool()(git_commit)
    mcp.tool()(git_push)
