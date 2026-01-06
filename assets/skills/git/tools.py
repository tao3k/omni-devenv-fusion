"""
agent/skills/git/tools.py
Git Skill - Phase 25.1 Macro System

Clean, simple Git operations with @skill_command decorators and DI.
"""

import subprocess
from pathlib import Path
from typing import Optional

from agent.skills.decorators import skill_command


# ==============================================================================
# Helper (private)
# ==============================================================================


def _run(cmd: list[str], cwd: Optional[Path] = None) -> str:
    """Execute a git command and return output."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def _check_sensitive_files(staged_files: list[str]) -> list[str]:
    """Check for potentially sensitive files in staged changes."""
    import glob

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

    sensitive = []
    for pattern in sensitive_patterns:
        matches = glob.glob(pattern, recursive=True)
        for m in matches:
            if m in staged_files and m not in sensitive:
                sensitive.append(m)
    return sensitive


# ==============================================================================
# Read Operations (safe, idempotent)
# ==============================================================================


@skill_command(
    name="git_status",
    category="read",
    description="Get git status",
    inject_root=True,
)
def status(project_root: Path = None) -> str:
    """Check git status in project directory."""
    return _run(["git", "status", "--short"], cwd=project_root) or "✅ Clean"


@skill_command(name="git_branch", category="read", description="List git branches.")
def branch() -> str:
    """List all branches."""
    return _run(["git", "branch", "-a"])


@skill_command(name="git_log", category="read", description="Show recent commits.")
def log(n: int = 5) -> str:
    """Show recent commit history."""
    return _run(["git", "log", f"-n{n}", "--oneline"])


@skill_command(name="git_diff", category="read", description="Show changes.")
def diff(staged: bool = False, filename: Optional[str] = None) -> str:
    """Show working directory or staged changes."""
    cmd = ["git", "diff"]
    if staged:
        cmd.append("--staged")
    if filename:
        cmd.append(filename)
    return _run(cmd)


@skill_command(name="git_remote", category="read", description="Show remotes.")
def remote() -> str:
    """Show remote repositories."""
    return _run(["git", "remote", "-v"])


@skill_command(name="git_tag_list", category="read", description="List tags.")
def tag_list() -> str:
    """List all git tags."""
    return _run(["git", "tag", "-l"])


# ==============================================================================
# View Operations (enhanced UX)
# ==============================================================================


@skill_command(name="git_status_report", category="view", description="Formatted status report.")
def status_report() -> str:
    """Get a nice formatted status report."""
    branch = _run(["git", "branch", "--show-current"]) or "unknown"
    staged = _run(["git", "diff", "--staged", "--name-only"])
    unstaged = _run(["git", "diff", "--name-only"])

    lines = [f"**Branch**: `{branch}", ""]
    if staged:
        lines.extend(["**Staged**:", *[f"  ✅ {f}" for f in staged.split("\n")], ""])
    if unstaged:
        lines.extend(["**Unstaged**:", *[f"  ⚠️ {f}" for f in unstaged.split("\n")], ""])
    if not staged and not unstaged:
        lines.append("✅ Working tree clean")

    return "\n".join(lines)


@skill_command(name="git_smart_diff", category="view", description="Instructions for native diff.")
def smart_diff(filename: str, context: int = 3) -> str:
    """Show how to view diff natively."""
    return f"Run: `git diff -U{context} {filename}`"


# ==============================================================================
# Workflow Operations
# ==============================================================================


@skill_command(name="git_plan_hotfix", category="workflow", description="Generate hotfix plan.")
def hotfix(issue_id: str, base: str = "main") -> str:
    """Generate a hotfix execution plan."""
    plan = [
        f"git checkout {base}",
        "git pull",
        f"git checkout -b hotfix/{issue_id}",
    ]
    return f"**Hotfix Plan for {issue_id}**\n\n" + "\n".join([f"`{c}`" for c in plan])


# ==============================================================================
# Write Operations (caution required)
# ==============================================================================


@skill_command(name="git_add", category="write", description="Stage files.")
def add(files: list[str]) -> str:
    """Stage files for commit."""
    return _run(["git", "add"] + files)


@skill_command(name="git_stage_all", category="write", description="Stage all changes.")
def stage_all(scan: bool = True) -> str:
    """Stage all changes with optional security scan."""
    if scan:
        import glob

        sensitive = []
        for p in ["*.env", "*.pem", "*.key", "*.secret"]:
            sensitive.extend(glob.glob(p, recursive=True))

        if sensitive:
            return f"⚠️ Blocked: {sensitive}"

    return _run(["git", "add", "."])


@skill_command(name="git_commit", category="write", description="Commit changes.")
def commit(message: str) -> str:
    """Commit staged changes."""
    return _run(["git", "commit", "-m", message])


@skill_command(name="git_checkout", category="write", description="Switch branch.")
def checkout(branch: str, create: bool = False) -> str:
    """Switch to a branch."""
    cmd = ["git", "checkout"]
    if create:
        cmd.append("-b")
    cmd.append(branch)
    return _run(cmd)


@skill_command(name="git_stash_save", category="write", description="Stash changes.")
def stash_save(msg: Optional[str] = None) -> str:
    """Stash working directory changes."""
    cmd = ["git", "stash", "push"]
    if msg:
        cmd.extend(["-m", msg])
    return _run(cmd)


@skill_command(name="git_stash_pop", category="write", description="Pop stash.")
def stash_pop() -> str:
    """Apply and remove last stash."""
    return _run(["git", "stash", "pop"])


@skill_command(name="git_stash_list", category="write", description="List stashes.")
def stash_list() -> str:
    """List all stashes."""
    return _run(["git", "stash", "list"])


@skill_command(name="git_reset", category="write", description="Reset HEAD.")
def reset(soft: bool = False, commit: Optional[str] = None) -> str:
    """Reset HEAD to a commit."""
    cmd = ["git", "reset"]
    if soft:
        cmd.append("--soft")
    if commit:
        cmd.append(commit)
    return _run(cmd)


@skill_command(name="git_merge", category="write", description="Merge branch.")
def merge(branch: str, no_ff: bool = True) -> str:
    """Merge a branch."""
    cmd = ["git", "merge"]
    if no_ff:
        cmd.append("--no-ff")
    cmd.append(branch)
    return _run(cmd)


@skill_command(name="git_tag_create", category="write", description="Create tag.")
def tag_create(name: str, msg: Optional[str] = None) -> str:
    """Create an annotated tag."""
    cmd = ["git", "tag"]
    if msg:
        cmd.extend(["-m", msg])
    cmd.append(name)
    return _run(cmd)


@skill_command(name="git_revert", category="write", description="Revert commit.")
def revert(commit: str, no_commit: bool = False) -> str:
    """Revert a specific commit."""
    cmd = ["git", "revert"]
    if no_commit:
        cmd.append("--no-commit")
    cmd.append(commit)
    return _run(cmd)


@skill_command(name="git_submodule_update", category="write", description="Update submodules.")
def submodule_update(init: bool = False) -> str:
    """Update git submodules."""
    cmd = ["git", "submodule", "update", "--recursive"]
    if init:
        cmd.append("--init")
    return _run(cmd)


# ==============================================================================
# Smart Commit Flow (Phase 25.2)
# ==============================================================================


def _run_with_rc(cmd: list[str], cwd: Optional[Path] = None) -> tuple[str, int]:
    """Execute a command and return (output, returncode)."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip(), result.returncode


@skill_command(
    name="git_prepare_commit",
    category="workflow",
    description="Stage files, run lefthook, return diff for analysis",
    inject_root=True,
)
def prepare_commit(project_root: Path = None) -> str:
    """[Phase 1] Prepare for commit: stage, lefthook, re-stage, return diff."""
    import shutil

    results = ["🔍 **Git Commit Preparation**"]
    lefthook_report = ""

    # 0. Check if there are staged files (even if working tree is clean)
    staged_files, _ = _run_with_rc(["git", "diff", "--cached", "--name-only"], cwd=project_root)
    has_staged = bool(staged_files)

    # 1. First Stage
    _, rc = _run_with_rc(["git", "add", "."], cwd=project_root)
    if rc != 0:
        return "❌ **Stage Failed**"

    # 2. Lefthook Checks
    if shutil.which("lefthook"):
        results.append("Running `lefthook run pre-commit`...")
        lh_out, lh_rc = _run_with_rc(["lefthook", "run", "pre-commit"], cwd=project_root)

        if lh_rc != 0:
            return f"""❌ **Lefthook Checks Failed**

Automatic checks found issues that need your attention before committing.

```text
{lh_out}
```

**Action Required:**
Please fix the errors above and run `/commit` again.
"""

        # Capture lefthook version and output for commit message
        lh_version, _ = _run_with_rc(["lefthook", "--version"], cwd=project_root)

        if lh_out.strip():
            lefthook_report = f"""
🥊 lefthook {lh_version}  hook: pre-commit
╰───────────────────────────────────────╯
{lh_out}"""

        if "fixed" in lh_out.lower() or "formatted" in lh_out.lower():
            results.append("✨ Lefthook auto-fixed some files.")
        else:
            results.append("✅ Lefthook checks passed.")

        # 3. Re-stage (in case lefthook modified files)
        _run_with_rc(["git", "add", "."], cwd=project_root)
    else:
        results.append("⚠️ Lefthook not found, skipping checks.")

    # 4. Check working tree status
    status, _ = _run_with_rc(["git", "status", "--porcelain"], cwd=project_root)

    # Check if there are UNSTAGED changes (working tree has modifications)
    unstaged, _ = _run_with_rc(["git", "diff", "--name-only"], cwd=project_root)
    has_unstaged = bool(unstaged)

    # Re-check staged files after re-stage
    staged_files, _ = _run_with_rc(["git", "diff", "--cached", "--name-only"], cwd=project_root)

    if not staged_files:
        return "🛑 **Nothing to commit**. Working tree clean."

    # 5. Check for sensitive files
    staged_list_all = staged_files.split("\n")
    sensitive_files = _check_sensitive_files(staged_list_all)
    security_warning = ""
    if sensitive_files:
        sensitive_display = "\n".join([f"  ⚠️ {f}" for f in sensitive_files])
        security_warning = f"""
⚠️ **Security Check**

Detected {len(sensitive_files)} potentially sensitive file(s):

{sensitive_display}

**LLM Advisory:** Please verify these files are safe to commit.
- Are they intentional additions (not accidentally staged)?
- Do they contain secrets, keys, or credentials?
- Should they be in `.gitignore`?

If unsure, press `No` and run `git reset <file>` to unstage.
"""

    if not has_unstaged and staged_files:
        # Staged but working tree clean (e.g., after reset --soft)
        # Skip analysis, go directly to commit
        staged_list = "\n".join([f"  ✅ {f}" for f in staged_list_all if f])
        return f"""🔄 **Staged Files Detected - Ready to Commit**

**{len(staged_list_all)} staged files ready to commit:**

{staged_list}

{lefthook_report}
{security_warning}
**Please confirm:** Press `Yes` to submit commit, or `No` to cancel.
"""

    stats, _ = _run_with_rc(["git", "diff", "--cached", "--stat"], cwd=project_root)
    diff, _ = _run_with_rc(["git", "diff", "--cached"], cwd=project_root)
    if len(diff) > 8000:
        diff = diff[:8000] + "\n... (diff truncated)"

    return f"""

{chr(10).join(results)}

✅ **Ready for Analysis**

{lefthook_report}
{security_warning}
**Staged Changes:**

```text
{stats}

```

**Detailed Diff:**

```diff
{diff}

```

"""


@skill_command(
    name="git_execute_commit",
    category="workflow",
    description="Execute the commit using cog (validates scope automatically)",
    inject_root=True,
)
def execute_commit(message: str, project_root: Path = None) -> str:
    """[Phase 2] Execute the commit using cog.

    Args:
        message: Full commit message in format: "type(scope): description\n\n- detail..."
        project_root: Project root directory

    Uses cog commit which validates:
    - Type: feat, fix, docs, style, refactor, test, chore, perf, build, ci, revert
    - Scope: Against cog.toml allowed scopes
    """
    import shutil

    # Parse the message to extract type, scope, and description
    # Format: "type(scope): description\n\n- detail..."
    lines = message.strip().split("\n")
    first_line = lines[0]

    # Parse "type(scope): description" or "type: description"
    import re

    match = re.match(r"^(\w+)(?:\(([^)]+)\))?:\s*(.+)$", first_line)

    if not match:
        return f"""❌ **Invalid Message Format**

Expected format: `type(scope): description`

Got: `{first_line}`

**Action:** Please regenerate the commit message.
"""

    commit_type = match.group(1)
    scope = match.group(2) or ""
    description = match.group(3)

    # Try cog first, fallback to git
    if shutil.which("cog"):
        cmd = ["cog", "commit", commit_type, description]
        if scope:
            cmd.append(scope)

        out, rc = _run_with_rc(cmd, cwd=project_root)

        if rc != 0:
            return f"""❌ **Commit Failed (cog)**

```text
{out}
```

**Action:** Please fix the issue and run `/commit` again.
"""

        commit_hash, _ = _run_with_rc(["git", "rev-parse", "--short", "HEAD"], cwd=project_root)
        return f"""💾 **COMMITTING** `{commit_hash}`

✅ **Commit Successful!**

```
{first_line}
```

---
✨ *Verified by Omni Git Skill (cog)* ✨"""

    # Fallback to git commit
    out, rc = _run_with_rc(["git", "commit", "-m", message], cwd=project_root)

    if rc != 0:
        return f"""💾 COMMIT FAILED:

```text
{out}
```"""

    commit_hash, _ = _run_with_rc(["git", "rev-parse", "--short", "HEAD"], cwd=project_root)

    return f"""💾 **COMMITTING** `{commit_hash}`

✅ **Commit Successful!**

```
{first_line}
```

---
✨ *Verified by Omni Git Skill* ✨"""


# ==============================================================================
# Evolution (Bootstrap)
# ==============================================================================


@skill_command(name="git_read_backlog", category="evolution", description="Read skill backlog.")
def read_backlog() -> str:
    """Read the Git Skill's own backlog."""
    backlog = Path(__file__).parent / "Backlog.md"
    return backlog.read_text() if backlog.exists() else "No backlog found"
