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
            # Parse scopes = [...] format (cog.toml standard)
            match = re.search(r"scopes\s*=\s*\[([^\]]+)\]", content, re.DOTALL)
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

    # 1. Conservative Stage: only staged + modified tracked files (NOT untracked)
    initially_staged, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root)
    initially_staged_set = set(line for line in initially_staged.splitlines() if line.strip())

    modified, _, _ = _run(["git", "diff", "--name-only", "--diff-filter=ACM"], cwd=root)
    modified_set = set(line for line in modified.splitlines() if line.strip())

    all_to_stage = initially_staged_set | modified_set

    if all_to_stage:
        for f in all_to_stage:
            stdout, stderr, rc = _run(["git", "add", f], cwd=root)
            if rc != 0:
                result["success"] = False
                result["results"].append("Stage Failed")
                return result
    elif not initially_staged_set:
        # No files to stage and nothing was previously staged
        result["success"] = False
        result["results"].append("Nothing to commit. No tracked files modified.")
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

    # 3. Re-stage originally staged files (lefthook may have unstaged them)
    current_staged, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root)
    current_staged_set = set(line for line in current_staged.splitlines() if line.strip())
    unstaged_by_lefthook = initially_staged_set - current_staged_set
    if unstaged_by_lefthook:
        for f in unstaged_by_lefthook:
            _run(["git", "add", f], cwd=root)

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
        # Use cascading template for security warning
        try:
            from .rendering import _get_jinja_env

            env = _get_jinja_env()
            template = env.get_template("security_warning.j2")
            result["security_warning"] = template.render(
                file_count=len(sensitive_files),
                files=sensitive_files,
            )
        except Exception:
            # Fallback to plain text if template fails
            sensitive_display = "\n".join([f"  ⚠️ {f}" for f in sensitive_files])
            result["security_warning"] = (
                f"\n⚠️ **Security Guard Detection**\n\nDetected {len(sensitive_files)} sensitive files:\n{sensitive_display}\n\nLLM: Please verify these files are safe to commit."
            )
    else:
        # No sensitive files - provide confirmation to LLM
        result["security_passed"] = True
        result["security_warning"] = (
            "\n🛡️ **Security Guard Detection** - No sensitive files detected. Safe to proceed."
        )

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
    Format the prepare_commit result for LLM consumption.

    Constructs complete output including security status in Controller Layer.
    LLM should always see security feedback (passed or warning).

    Args:
        prep_result: Result from prepare_commit()

    Returns:
        Formatted output with security status visible to LLM
    """
    lines = []

    # Header: Status
    if prep_result["success"] and prep_result["checks_passed"]:
        lines.append("## ✅ Commit Preparation Passed")
    else:
        lines.append("## ❌ Commit Preparation Failed")
        if prep_result.get("results"):
            lines.extend(prep_result["results"])
        return "\n".join(lines)

    # Security Guard Detection - ALWAYS show to LLM
    security_passed = prep_result.get("security_passed", False)
    security_warning = prep_result.get("security_warning", "")
    sensitive_files = prep_result.get("sensitive_files", [])

    if security_passed:
        lines.append(security_warning)
    elif sensitive_files:
        lines.append(security_warning)
    else:
        lines.append(
            "\n🛡️ **Security Guard Detection** - No sensitive files detected. Safe to proceed."
        )

    # Lefthook Report
    lefthook_report = prep_result.get("lefthook_report", "")
    if lefthook_report:
        lines.append(f"\n{lefthook_report}")

    # Scope Validation
    scope_warning = prep_result.get("scope_warning", "")
    if scope_warning:
        lines.append(f"\n{scope_warning}")

    # Staged Files Summary
    has_staged = prep_result["has_staged"]
    staged_count = prep_result["staged_file_count"]
    has_unstaged = prep_result.get("has_unstaged", False)

    if has_staged and not has_unstaged:
        lines.append(f"\n### 📁 {staged_count} Staged Files Ready")
        for f in prep_result.get("staged_files", [])[:10]:  # Limit to 10 files
            if f:
                lines.append(f"  - {f}")
        if staged_count > 10:
            lines.append(f"  ... and {staged_count - 10} more files")
    elif has_staged:
        lines.append(f"\n### 📁 {staged_count} Staged Files")
        staged_diff = prep_result.get("staged_diff_stats", "")
        if staged_diff:
            lines.append(f"\n{staged_diff}")

    # Final confirmation
    lines.append("\n---\n**Please confirm:** Reply Yes to proceed to commit, or No to cancel.")

    return "\n".join(lines)


# ==============================================================================
# Smart Commit Workflow Functions (Phase 36.7)
# ==============================================================================


def stage_and_scan(root_dir: str = ".") -> dict:
    """
    Stage files and capture diff for LLM analysis.

    Workflow:
    1. git add . - Stage ALL files (including untracked)
    2. Check sensitive files - UNSTAGE them (not just warn)
    3. Run lefthook pre-commit (may reformat files)
    4. Re-stage originally staged files (lefthook may have unstaged them)
    5. Scope check - if scope not in cog.toml, return warning for LLM
    6. Generate commit analysis

    Args:
        root_dir: Project root directory

    Returns:
        Dict with:
        - staged_files: List of staged file paths
        - diff: Raw diff content for LLM analysis
        - security_issues: List of sensitive files detected
        - scope_warning: Warning if scope not in cog.toml
    """
    import glob as glob_module
    import shutil
    from pathlib import Path as PathType

    result = {
        "staged_files": [],
        "diff": "",
        "security_issues": [],
        "scope_warning": "",
    }

    root_path = PathType(root_dir)

    # 1. git add . - Stage ALL files (including untracked)
    _run(["git", "add", "."], cwd=root_path)

    # Get all staged files after initial add
    all_staged_after_add, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root_path)
    all_staged_set = set(line for line in all_staged_after_add.splitlines() if line.strip())

    # 2. Check sensitive files and UNSTAGE them
    sensitive_patterns = [
        "*.env*",
        "*.pem",
        "*.key",
        "*.secret",
        "*.credentials*",
        "id_rsa*",
        "id_ed25519*",
    ]

    sensitive = []
    for pattern in sensitive_patterns:
        matches = glob_module.glob(pattern, recursive=True)
        for m in matches:
            if m in all_staged_set and m not in sensitive:
                sensitive.append(m)

    # UNSTAGE sensitive files
    for f in sensitive:
        _run(["git", "reset", "HEAD", "--", f], cwd=root_path)

    result["security_issues"] = sensitive

    # Get final staged files after unstaging sensitive ones
    final_staged, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root_path)
    final_staged_set = set(line for line in final_staged.splitlines() if line.strip())

    # 3. Run lefthook pre-commit (may reformat files)
    if shutil.which("lefthook"):
        _run(["lefthook", "run", "pre-commit"], cwd=root_path)

    # 4. Re-stage originally staged files (lefthook may have unstaged them)
    current_staged, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root_path)
    current_staged_set = set(line for line in current_staged.splitlines() if line.strip())

    # Find files that were staged but are now unstaged (lefthook reformatted them)
    unstaged_by_lefthook = final_staged_set - current_staged_set

    if unstaged_by_lefthook:
        for f in unstaged_by_lefthook:
            _run(["git", "add", f], cwd=root_path)

    # 5. Get staged file list (after re-stage)
    files_out, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root_path)
    result["staged_files"] = [line for line in files_out.splitlines() if line.strip()]

    # 6. Get diff content (truncated to prevent context overflow)
    # Use --no-pager to avoid encoding issues
    diff_cmd = ["git", "--no-pager", "diff", "--cached", "--", ".", ":!*lock.json", ":!*lock.yaml"]
    try:
        diff_out, _, _ = _run(diff_cmd, cwd=root_path)
    except UnicodeDecodeError:
        diff_out = "[Diff unavailable - encoding issue]"

    if len(diff_out) > 6000:
        result["diff"] = diff_out[:6000] + "\n... (Diff truncated for analysis)"
    else:
        result["diff"] = diff_out

    # 7. Scope validation (check against cog.toml)
    valid_scopes = _get_cog_scopes(root_path)
    if valid_scopes:
        result["scope_warning"] = f"Scope validation: Valid scopes are {', '.join(valid_scopes)}"

    return result


__all__ = [
    "prepare_commit",
    "format_prepare_result",
    "stage_and_scan",
]
