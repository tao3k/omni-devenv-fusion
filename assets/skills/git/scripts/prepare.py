"""
git/scripts/prepare.py - Commit preparation workflow

Implements the prepare_commit command for /commit workflow:
1. Stage all changes with security scan
2. Run quality checks (lefthook pre-commit)
3. Return staged diff for commit analysis with template output

Uses cascading template pattern with configuration via settings (system: packages/conf/settings.yaml, user: $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml).
"""

import re
import shutil
import subprocess
from pathlib import Path

from omni.foundation.config.logging import get_logger

logger = get_logger("git.prepare")

# Summary-only scenario: enough for commit message (see skill-tool-context-practices.md)
DIFF_SUMMARY_MAX_CHARS = 4000


def _is_non_blocking_pre_commit_error(output: str) -> bool:
    """Whether pre-commit hook failure should be treated as non-blocking.

    We only downgrade known "hook not configured" cases. Real hook failures
    (lint/test/format errors) must still block commit preparation.
    """
    text = (output or "").lower()
    patterns = (
        "cannot find a hook named pre-commit",
        "hook named pre-commit not found",
        "no hook named pre-commit",
    )
    return any(pattern in text for pattern in patterns)


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[str, str, int]:
    """Run command and return stdout, stderr, returncode."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def run_pre_commit_hook(cwd: Path | None = None) -> tuple[str, str, int]:
    """Run pre-commit hook with lefthook when available, else git hook runner."""
    if shutil.which("lefthook"):
        return _run(["lefthook", "run", "pre-commit"], cwd=cwd)
    return _run(["git", "hook", "run", "pre-commit"], cwd=cwd)


def _check_sensitive_files(staged_files: list[str]) -> list[str]:
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


def _get_cog_scopes(project_root: Path | None = None) -> list[str]:
    """Read allowed scopes from cog.toml or .conform.yaml.

    Supports both formats:
    - cog.toml: scopes = ["scope1", "scope2"]
    - .conform.yaml: YAML list format

    Falls back to .conform.yaml if cog.toml doesn't exist.
    """
    try:
        from omni.foundation.config.settings import get_setting
        from omni.foundation.runtime.gitops import get_project_root

        root = project_root or get_project_root()

        # First try cog.toml (primary)
        cog_path = root / get_setting("config.cog_toml")
        if cog_path.exists():
            content = cog_path.read_text()
            match = re.search(r"scopes\s*=\s*\[([^\]]+)\]", content, re.DOTALL)
            if match:
                scopes_str = match.group(1)
                scopes = re.findall(r'"([^"]+)"', scopes_str)
                if scopes:
                    return scopes

        # Fall back to .conform.yaml (legacy support)
        conform_path = root / get_setting("config.conform_yaml")
        if conform_path.exists():
            import yaml

            content = conform_path.read_text()
            data = yaml.safe_load(content)
            if data and "policies" in data:
                for policy in data["policies"]:
                    spec = policy.get("spec", {})
                    conventional = spec.get("conventional", {})
                    scopes = conventional.get("scopes", [])
                    if scopes:
                        return scopes

    except Exception:
        pass
    return []


def _validate_and_fix_scope(
    commit_type: str, scope: str, project_root: Path | None = None
) -> tuple[bool, str, list[str]]:
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


def _check_lefthook(cwd: Path | None = None) -> tuple[bool, str, str]:
    """Run git pre-commit hook (lefthook is installed as the hook).

    Returns:
        Tuple of (success, report_message, lefthook_output)
    """
    lh_out, lh_err, lh_rc = run_pre_commit_hook(cwd=cwd)

    lefthook_output = lh_err or lh_out

    lefthook_report = f"pre-commit hook:\n{lefthook_output}" if lefthook_output.strip() else ""

    if lh_rc != 0:
        return False, lefthook_report, lefthook_output

    return True, lefthook_report, lefthook_output


def stage_and_scan(root_dir: str = ".") -> dict:
    from pathlib import Path as PathType

    result = {
        "staged_files": [],
        "diff": "",
        "security_issues": [],
        "scope_warning": "",
        "lefthook_error": "",
        "lefthook_summary": "",
    }

    root_path = PathType(root_dir)

    if not root_path.exists():
        return result

    try:
        _run(["git", "add", "-A"], cwd=root_path)
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

    lefthook_failed = False
    lefthook_output = ""
    lefthook_summary = ""

    # Run pre-commit hook (prefer lefthook binary when available)
    lh_out, lh_err, lh_rc = run_pre_commit_hook(cwd=root_path)
    lefthook_output = lh_err or lh_out
    lefthook_failed = lh_rc != 0
    if lefthook_failed and _is_non_blocking_pre_commit_error(lefthook_output):
        lefthook_failed = False
        if not lefthook_summary:
            lefthook_summary = "pre-commit hook not configured; skipped"

    # Extract summary - look for "summary:" keyword in output (stderr)
    for line in reversed(lh_err.splitlines()):
        if "summary:" in line.lower():
            lefthook_summary = line.strip()
            break

    # Re-stage all modified files (including those modified by hook/formatting)
    # Use git add -A to stage all changes (both modified tracked and untracked)
    modified_out, _, _ = _run(["git", "diff", "--name-only"], cwd=root_path)
    untracked_out, _, _ = _run(["git", "ls-files", "--others", "--exclude-standard"], cwd=root_path)

    modified_set = set(line for line in modified_out.splitlines() if line.strip())
    untracked_set = set(line for line in untracked_out.splitlines() if line.strip())

    if modified_set or untracked_set:
        _run(["git", "add", "-A"], cwd=root_path)
        logger.info(f"Re-staged {len(modified_set)} modified + {len(untracked_set)} new files")

    if lefthook_failed:
        # Re-run hook on newly staged files
        lh_out, lh_err, lh_rc = run_pre_commit_hook(cwd=root_path)
        lefthook_output = lh_err or lh_out
        lefthook_failed = lh_rc != 0
        if lefthook_failed and _is_non_blocking_pre_commit_error(lefthook_output):
            lefthook_failed = False
            if not lefthook_summary:
                lefthook_summary = "pre-commit hook not configured; skipped"

        # Re-extract summary after retry
        for line in reversed(lh_err.splitlines()):
            if "summary:" in line.lower():
                lefthook_summary = line.strip()
                break

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

    # Store lefthook summary for display
    result["lefthook_summary"] = lefthook_summary

    valid_scopes = _get_cog_scopes(root_path)
    if valid_scopes:
        result["scope_warning"] = f"Scope validation: Valid scopes are {', '.join(valid_scopes)}"

    return result


__all__ = [
    "DIFF_SUMMARY_MAX_CHARS",
    "_check_lefthook",
    "_check_sensitive_files",
    "_get_cog_scopes",
    "_is_non_blocking_pre_commit_error",
    "_run",
    "_validate_and_fix_scope",
    "stage_and_scan",
]
