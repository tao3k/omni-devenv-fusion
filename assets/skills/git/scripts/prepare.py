"""
git/scripts/prepare.py - Commit preparation workflow (Phase 35.2)

Implements the prepare_commit command for /commit workflow:
1. Stage all changes with security scan
2. Run quality checks (lefthook pre-commit)
3. Return staged diff for commit analysis with template output

This module uses the cascading template pattern:
- Template rendering via scripts/rendering.py
- Configuration via settings.yaml
"""

import subprocess
import shutil
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path


def _run(cmd: list[str], cwd: Optional[Path] = None) -> tuple[str, str, int]:
    """Run command and return stdout, stderr, returncode."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def _check_sensitive_files(staged_files: List[str]) -> List[str]:
    """Check for potentially sensitive files in staged changes."""
    sensitive_patterns = [
        "*.env*",
        "*.pem",
        "*.key",
        "*.secret",
        "*.credentials*",
        "*.psd",
        "*.ai",
        "*.sketch",
        "*.fig",
        "id_rsa*",
        "id_ed25519*",
        "*.priv",
        "secrets.yml",
        "secrets.yaml",
        "credentials.yml",
    ]

    import glob

    sensitive = []
    for pattern in sensitive_patterns:
        matches = glob.glob(pattern, recursive=True)
        for m in matches:
            if m in staged_files and m not in sensitive:
                sensitive.append(m)
    return sensitive


def _get_cog_scopes(project_root: Optional[Path] = None) -> List[str]:
    """Read allowed scopes from cog.toml."""
    try:
        from common.config.settings import get_setting
        from common.gitops import get_project_root

        root = project_root or get_project_root()
        cog_path = root / get_setting("config.cog_toml", "cog.toml")

        if cog_path.exists():
            content = cog_path.read_text()
            # Parse allowed_scopes = [...] format
            match = re.search(r"allowed_scopes\s*=\s*\[([^\]]+)\]", content)
            if match:
                scopes_str = match.group(1)
                # Extract quoted strings
                scopes = re.findall(r'"([^"]+)"', scopes_str)
                return scopes
    except Exception:
        pass
    return []


def _validate_and_fix_scope(
    commit_type: str, scope: str, project_root: Optional[Path] = None
) -> tuple[bool, str, List[str]]:
    """Validate scope against cog.toml and auto-fix if close match."""
    valid_scopes = _get_cog_scopes(project_root)

    if not valid_scopes:
        return True, scope, []

    scope_lower = scope.lower()
    valid_scopes_lower = [s.lower() for s in valid_scopes]

    # Exact match
    if scope_lower in valid_scopes_lower:
        return True, scope, []

    # Find close matches (Levenshtein distance)
    from difflib import get_close_matches

    close_matches = get_close_matches(scope_lower, valid_scopes_lower, n=1, cutoff=0.6)

    if close_matches:
        # Find the original casing
        original_casing = valid_scopes[valid_scopes_lower.index(close_matches[0])]
        warning = f"Scope '{scope}' not in cog.toml. Auto-fixed to '{original_casing}'."
        return True, original_casing, [warning]

    # No match found
    warning = f"Scope '{scope}' not found in cog.toml. Allowed: {', '.join(valid_scopes)}"
    return False, scope, [warning]


def _check_lefthook(cwd: Optional[Path] = None) -> tuple[bool, str, str]:
    """
    Run lefthook pre-commit checks.

    Returns:
        Tuple of (success, report_message, lefthook_output)
    """
    if not shutil.which("lefthook"):
        return True, "", ""

    lh_version, _, _ = _run(["lefthook", "--version"], cwd=cwd)
    lh_out, lh_err, lh_rc = _run(["lefthook", "run", "pre-commit"], cwd=cwd)

    lefthook_output = lh_out or lh_err

    if lefthook_output.strip():
        lefthook_report = f"""lefthook {lh_version} hook: pre-commit
{lefthook_output}"""
    else:
        lefthook_report = ""

    if lh_rc != 0:
        return False, lefthook_report, lefthook_output

    return True, lefthook_report, lefthook_output


def prepare_commit(
    project_root: Optional[Path] = None,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    [Phase 1] Prepare for commit: stage, lefthook, re-stage, return diff.

    Args:
        project_root: Project root path (auto-injected via inject_root)
        message: Optional commit message for scope validation

    Returns:
        Dict with all preparation results for template rendering
    """
    from common.gitops import get_project_root
    from common.config.settings import get_setting

    root = project_root or get_project_root()

    result = {
        "success": True,
        "checks_passed": True,
        "has_staged": False,
        "has_unstaged": False,
        "staged_files": [],
        "staged_file_count": 0,
        "unstaged_files": [],
        "staged_diff": "",
        "staged_diff_stats": "",
        "lefthook_passed": True,
        "lefthook_report": "",
        "lefthook_output": "",
        "sensitive_files": [],
        "security_warning": "",
        "scope_warning": "",
        "scope_valid": True,
        "fixed_scope": "",
        "commit_type": "",
        "commit_scope": "",
        "commit_description": "",
        "results": ["Git Commit Preparation"],
        "message": message or "",
        "project_root": str(root),
    }

    # Validate scope if message is provided
    if message:
        match = re.match(r"^(\w+)(?:\(([^)]+)\))?:", message.strip())
        if match:
            commit_type = match.group(1)
            scope = match.group(2) or ""
            result["commit_type"] = commit_type
            result["commit_scope"] = scope
            result["commit_description"] = message.strip()

            if scope:
                valid, fixed_scope, warnings = _validate_and_fix_scope(commit_type, scope, root)
                result["scope_valid"] = valid
                result["fixed_scope"] = fixed_scope
                if warnings:
                    result["scope_warning"] = "\n" + "\n".join(warnings) + "\n"
                    result["results"].append(result["scope_warning"])

    # 1. First Stage
    stdout, stderr, rc = _run(["git", "add", "."], cwd=root)
    if rc != 0:
        result["success"] = False
        result["results"].append("Stage Failed")
        return result

    # 2. Lefthook Checks
    lh_passed, lefthook_report, lh_out = _check_lefthook(root)
    result["lefthook_passed"] = lh_passed
    result["lefthook_report"] = lefthook_report
    result["lefthook_output"] = lh_out

    if not lh_passed:
        result["checks_passed"] = False
        result["results"].append(
            f"""Lefthook Checks Failed

Automatic checks found issues that need your attention before committing.

{lh_out}

Action Required:
Please fix the errors above and run /commit again."""
        )
        return result

    result["results"].append("Lefthook checks passed.")

    if "fixed" in lh_out.lower() or "formatted" in lh_out.lower():
        result["results"].append("Lefthook auto-fixed some files.")

    # 3. Re-stage (in case lefthook modified files)
    _run(["git", "add", "."], cwd=root)

    # 4. Check working tree status
    unstaged, _, _ = _run(["git", "diff", "--name-only"], cwd=root)
    result["has_unstaged"] = bool(unstaged)
    if unstaged:
        result["unstaged_files"] = unstaged.split("\n")

    # Check staged files
    staged_files, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root)
    result["has_staged"] = bool(staged_files)
    result["staged_files"] = staged_files.split("\n") if staged_files else []
    result["staged_file_count"] = len(result["staged_files"])

    if not result["has_staged"]:
        result["success"] = False
        result["results"].append("Nothing to commit. Working tree clean.")
        return result

    # 5. Check for sensitive files
    sensitive_files = _check_sensitive_files(result["staged_files"])
    result["sensitive_files"] = sensitive_files
    if sensitive_files:
        sensitive_display = "\n".join([f"  {f}" for f in sensitive_files])
        result["security_warning"] = f"""Security Check

Detected {len(sensitive_files)} potentially sensitive file(s):

{sensitive_display}

LLM Advisory: Please verify these files are safe to commit.
- Are they intentional additions (not accidentally staged)?
- Do they contain secrets, keys, or credentials?
- Should they be in .gitignore?

If unsure, press No and run git reset <file> to unstage."""

    # 6. Get diff for analysis
    if result["has_staged"] and not result["has_unstaged"]:
        # Staged but working tree clean - show simplified output
        staged_list = "\n".join([f"  {f}" for f in result["staged_files"] if f])
        result["staged_diff"] = f"""{result["staged_file_count"]} staged files ready to commit:

{staged_list}"""
    else:
        # Get full diff
        stats, _, _ = _run(["git", "diff", "--cached", "--stat"], cwd=root)
        diff, _, _ = _run(["git", "diff", "--cached"], cwd=root)
        if len(diff) > 8000:
            diff = diff[:8000] + "\n... (diff truncated)"
        result["staged_diff_stats"] = stats
        result["staged_diff"] = diff

    return result


def format_prepare_result(prep_result: Dict[str, Any]) -> str:
    """
    Format the prepare_commit result using cascading template.

    Uses the cascading template pattern for output rendering:
    - User Override: assets/templates/git/prepare_result.j2
    - Skill Default: assets/skills/git/templates/prepare_result.j2

    Args:
        prep_result: Result from prepare_commit()

    Returns:
        Formatted output using cascading Jinja2 template
    """
    try:
        from .rendering import render_workflow_result

        # Use render_workflow_result for the workflow output
        return render_workflow_result(
            intent="prepare_commit",
            success=prep_result["success"] and prep_result["checks_passed"],
            message="Commit preparation completed",
            details={
                "has_staged": str(prep_result["has_staged"]),
                "staged_file_count": str(prep_result["staged_file_count"]),
                "checks_passed": str(prep_result["checks_passed"]),
                "scope_valid": str(prep_result.get("scope_valid", True)),
            },
        )
    except Exception:
        # Fallback to legacy string formatting if template fails
        return _legacy_format_result(prep_result)


def _legacy_format_result(prep_result: Dict[str, Any]) -> str:
    """
    Legacy string formatting fallback (for debugging/fallback).

    Args:
        prep_result: Result from prepare_commit()

    Returns:
        Formatted markdown string matching original output format
    """
    lines = []

    # Header
    lines.append("\n".join(prep_result["results"]))

    # Lefthook report
    if prep_result["lefthook_report"]:
        lines.append(prep_result["lefthook_report"])

    # Scope warning
    if prep_result["scope_warning"]:
        lines.append(prep_result["scope_warning"])

    # Security warning
    if prep_result["security_warning"]:
        lines.append(prep_result["security_warning"])

    # Ready for analysis
    if prep_result["checks_passed"] and prep_result["has_staged"]:
        if not prep_result["has_unstaged"]:
            # Simplified output for clean working tree
            lines.append(f"""Staged Files Detected - Ready to Commit

{prep_result["staged_file_count"]} staged files ready to commit:
{prep_result["staged_diff"]}
Please confirm: Press Yes to submit commit, or No to cancel.""")
        else:
            # Full diff output
            lines.append("Ready for Analysis")
            if prep_result["security_warning"]:
                lines.append(prep_result["security_warning"])

            lines.append(f"""Staged Changes:

{prep_result["staged_diff_stats"]}


Detailed Diff:

{prep_result["staged_diff"]}


""")

            # Final confirmation
            lines.append("Please confirm: Press Yes to submit commit, or No to cancel.")

    # Error cases
    if not prep_result["has_staged"]:
        lines.append(prep_result["results"][-1])  # Last message

    return "\n".join(lines)
