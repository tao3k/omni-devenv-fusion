"""
git/scripts/prepare.py - Commit preparation workflow (Phase 35.2)

Implements the prepare_commit command for /commit workflow:
1. Stage all changes with security scan
2. Run quality checks (lefthook pre-commit)
3. Return staged diff for commit analysis with template output

Uses cascading template pattern with configuration via settings.yaml.
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
            match = re.search(r"scopes\s*=\s*\[([^\]]+)\]", content, re.DOTALL)
            if match:
                scopes_str = match.group(1)
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

    if scope_lower in valid_scopes_lower:
        return True, scope, []

    from difflib import get_close_matches

    close_matches = get_close_matches(scope_lower, valid_scopes_lower, n=1, cutoff=0.6)

    if close_matches:
        original_casing = valid_scopes[valid_scopes_lower.index(close_matches[0])]
        warning = f"Scope '{scope}' not in cog.toml. Auto-fixed to '{original_casing}'."
        return True, original_casing, [warning]

    warning = f"Scope '{scope}' not found in cog.toml. Allowed: {', '.join(valid_scopes)}"
    return False, scope, [warning]


def _check_lefthook(cwd: Optional[Path] = None) -> tuple[bool, str, str]:
    """Run lefthook pre-commit checks.

    Returns:
        Tuple of (success, report_message, lefthook_output)
    """
    if not shutil.which("lefthook"):
        return True, "", ""

    lh_version, _, _ = _run(["lefthook", "--version"], cwd=cwd)
    lh_out, lh_err, lh_rc = _run(["lefthook", "run", "pre-commit"], cwd=cwd)

    lefthook_output = lh_out or lh_err

    if lefthook_output.strip():
        lefthook_report = f"lefthook {lh_version} hook: pre-commit\n{lefthook_output}"
    else:
        lefthook_report = ""

    if lh_rc != 0:
        return False, lefthook_report, lefthook_output

    return True, lefthook_report, lefthook_output


def stage_and_scan(root_dir: str = ".") -> dict:
    import shutil
    from pathlib import Path as PathType

    result = {
        "staged_files": [],
        "diff": "",
        "security_issues": [],
        "scope_warning": "",
        "lefthook_error": "",
    }

    root_path = PathType(root_dir)

    if not root_path.exists():
        return result

    try:
        _run(["git", "add", "."], cwd=root_path)
    except Exception:
        return result

    all_staged_after_add, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root_path)
    all_staged_set = set(line for line in all_staged_after_add.splitlines() if line.strip())

    sensitive_patterns = [
        ".env*",
        "*.env*",
        "*.pem",
        "*.key",
        "*.secret",
        "*.credentials*",
        "id_rsa*",
        "id_ed25519*",
    ]

    sensitive = []
    for staged_file in all_staged_set:
        for pattern in sensitive_patterns:
            import fnmatch

            if fnmatch.fnmatch(staged_file, pattern):
                if staged_file not in sensitive:
                    sensitive.append(staged_file)
                break

    for f in sensitive:
        _run(["git", "reset", "HEAD", "--", f], cwd=root_path)

    result["security_issues"] = sensitive

    final_staged, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root_path)
    final_staged_set = set(line for line in final_staged.splitlines() if line.strip())

    lefthook_failed = False
    lefthook_output = ""
    if shutil.which("lefthook"):
        lh_out, lh_err, lh_rc = _run(["lefthook", "run", "pre-commit"], cwd=root_path)
        lefthook_output = lh_out or lh_err
        lefthook_failed = lh_rc != 0

        # Re-stage files that lefthook may have modified (e.g., formatting)
        current_staged, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root_path)
        current_staged_set = set(line for line in current_staged.splitlines() if line.strip())
        unstaged_by_lefthook = final_staged_set - current_staged_set

        for f in unstaged_by_lefthook:
            _run(["git", "add", f], cwd=root_path)

        if lefthook_failed:
            # Re-run lefthook on newly staged files
            lh_out, lh_err, lh_rc = _run(["lefthook", "run", "pre-commit"], cwd=root_path)
            lefthook_output = lh_out or lh_err
            lefthook_failed = lh_rc != 0

    if lefthook_failed:
        result["lefthook_error"] = lefthook_output
        return result

    files_out, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=root_path)
    result["staged_files"] = [line for line in files_out.splitlines() if line.strip()]

    diff_cmd = ["git", "--no-pager", "diff", "--cached", "--", ".", ":!*lock.json", ":!*lock.yaml"]
    try:
        diff_out, _, _ = _run(diff_cmd, cwd=root_path)
    except UnicodeDecodeError:
        diff_out = "[Diff unavailable - encoding issue]"

    result["diff"] = diff_out

    valid_scopes = _get_cog_scopes(root_path)
    if valid_scopes:
        result["scope_warning"] = f"Scope validation: Valid scopes are {', '.join(valid_scopes)}"

    return result


__all__ = [
    "stage_and_scan",
    "_run",
    "_check_sensitive_files",
    "_get_cog_scopes",
    "_validate_and_fix_scope",
    "_check_lefthook",
]
