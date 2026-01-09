"""
git/tools.py - Git Skill Router (Phase 35.2)

This is the ROUTER layer - it only dispatches to implementation scripts.
All actual logic is in the scripts/ directory.

Architecture (Isolated Sandbox + Explicit Routing):
    tools.py    -> Router (just dispatches, validates params)
    scripts/    -> Controllers (actual implementation)
                -> Fully isolated namespace (no conflicts with docker/scripts/)

Naming Convention:
    @skill_command(name="git.<command>", ...)
    - All command names use "skill.command" format for LLM clarity
    - Example: git.status, git.commit, git.branch

Usage:
    from agent.skills.git.scripts import status, branch, log

Note: We use absolute imports to work with ModuleLoader's package setup.
The scripts module is loaded as agent.skills.git.scripts.xxx
"""

from agent.skills.decorators import skill_command
from pathlib import Path
from typing import Optional

# ==============================================================================
# READ Operations (Router Layer)
# ==============================================================================


@skill_command(
    name="git.status",
    category="read",
    description="Get git status",
    inject_root=True,
)
def status(project_root: Path = None) -> str:
    """Check git status in project directory."""
    from agent.skills.git.scripts import status as status_mod

    return status_mod.git_status(project_root)


@skill_command(name="git.branch", category="read", description="List git branches.")
def branch() -> str:
    """List all branches."""
    from agent.skills.git.scripts import branch as branch_mod

    return branch_mod.list_branches()


@skill_command(name="git.log", category="read", description="Show recent commits.")
def log(n: int = 5) -> str:
    """Show recent commit history."""
    from agent.skills.git.scripts import log as log_mod

    return log_mod.get_log(n)


@skill_command(name="git.diff", category="read", description="Show changes.")
def diff(staged: bool = False, filename: Optional[str] = None) -> str:
    """Show working directory or staged changes."""
    from agent.skills.git.scripts import diff as diff_mod

    return diff_mod.get_diff(staged, filename)


@skill_command(name="git.remote", category="read", description="Show remotes.")
def remote() -> str:
    """Show remote repositories."""
    from agent.skills.git.scripts import remote as remote_mod

    return remote_mod.list_remotes()


@skill_command(name="git.tag_list", category="read", description="List tags.")
def tag_list() -> str:
    """List all git tags."""
    from agent.skills.git.scripts import tag_list as tag_mod

    return tag_mod.list_tags()


# ==============================================================================
# VIEW Operations (Router Layer)
# ==============================================================================


@skill_command(name="git.status_report", category="view", description="Formatted status report.")
def status_report() -> str:
    """Get a nice formatted status report."""
    from agent.skills.git.scripts import status as status_mod

    branch = status_mod.current_branch() or "unknown"
    has_staged, staged = status_mod.has_staged_files()
    has_unstaged, unstaged = status_mod.has_unstaged_files()

    lines = [f"**Branch**: `{branch}", ""]
    if has_staged:
        lines.extend(["**Staged**:", *[f"  ✅ {f}" for f in staged], ""])
    if has_unstaged:
        lines.extend(["**Unstaged**:", *[f"  ⚠️ {f}" for f in unstaged], ""])
    if not has_staged and not has_unstaged:
        lines.append("✅ Working tree clean")

    return "\n".join(lines)


@skill_command(name="git.smart_diff", category="view", description="Instructions for native diff.")
def smart_diff(filename: str, context: int = 3) -> str:
    """Show how to view diff natively."""
    return f"Run: `git diff -U{context} {filename}`"


# ==============================================================================
# WORKFLOW Operations (Router Layer)
# ==============================================================================


@skill_command(name="git.hotfix", category="workflow", description="Generate hotfix plan.")
def hotfix(issue_id: str, base: str = "main") -> str:
    """Generate a hotfix execution plan."""
    from agent.skills.git.scripts import branch as branch_mod

    plan = [
        f"git checkout {base}",
        "git pull",
        f"git checkout -b hotfix/{issue_id}",
    ]
    return f"**Hotfix Plan for {issue_id}**\n\n" + "\n".join([f"`{c}`" for c in plan])


# ==============================================================================
# WRITE Operations (Router Layer)
# ==============================================================================


@skill_command(name="git.add", category="write", description="Stage files.")
def add(files: list[str]) -> str:
    """Stage files for commit."""
    from agent.skills.git.scripts import add as add_mod

    return add_mod.add(files)


@skill_command(name="git.stage_all", category="write", description="Stage all changes.")
def stage_all(scan: bool = True) -> str:
    """Stage all changes with optional security scan."""
    import glob

    if scan:
        sensitive = []
        for p in ["*.env", "*.pem", "*.key", "*.secret"]:
            sensitive.extend(glob.glob(p, recursive=True))

        if sensitive:
            return f"⚠️ Blocked: {sensitive}"

    from agent.skills.git.scripts import add as add_mod

    return add_mod.add_all()


@skill_command(
    name="git.prepare_commit",
    category="workflow",
    description="Prepare commit: stage all, run checks, return staged diff.",
    inject_root=True,
)
def prepare_commit(project_root: Path = None, message: str = None) -> str:
    """
    Prepare commit workflow for /commit command.

    This command:
    1. Stages all changes with security scan
    2. Runs quality checks (lefthook pre-commit)
    3. Returns staged diff for commit analysis

    Returns:
        Formatted result with status, staged files, and diff
    """
    from agent.skills.git.scripts import prepare as prepare_mod

    result = prepare_mod.prepare_commit(project_root=project_root, message=message)
    return prepare_mod.format_prepare_result(result)


@skill_command(name="git.commit", category="write", description="Commit staged changes.")
def commit(message: str) -> str:
    """Commit staged changes."""
    from agent.skills.git.scripts import commit as commit_mod

    return commit_mod.commit(message)


@skill_command(name="git.checkout", category="write", description="Switch branch.")
def checkout(branch: str, create: bool = False) -> str:
    """Switch to a branch."""
    from agent.skills.git.scripts import branch as branch_mod

    if create:
        return branch_mod.create_branch(branch, checkout=True)
    return branch_mod.create_branch(branch, checkout=False)


@skill_command(name="git.stash_save", category="write", description="Stash changes.")
def stash_save(msg: Optional[str] = None) -> str:
    """Stash working directory changes."""
    from agent.skills.git.scripts import stash as stash_mod

    return stash_mod.stash_save(msg)


@skill_command(name="git.stash_pop", category="write", description="Pop stash.")
def stash_pop() -> str:
    """Apply and remove last stash."""
    from agent.skills.git.scripts import stash as stash_mod

    return stash_mod.stash_pop()


@skill_command(name="git.stash_list", category="write", description="List stashes.")
def stash_list() -> str:
    """List all stashes."""
    from agent.skills.git.scripts import stash as stash_mod

    return stash_mod.stash_list()


@skill_command(name="git.reset", category="write", description="Reset HEAD.")
def reset(soft: bool = False, commit: Optional[str] = None) -> str:
    """Reset HEAD to a commit."""
    from agent.skills.git.scripts import add as add_mod

    cmd = ["git", "reset"]
    if soft:
        cmd.append("--soft")
    if commit:
        cmd.append(commit)
    import subprocess

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


@skill_command(name="git.merge", category="write", description="Merge branch.")
def merge(branch: str, no_ff: bool = True) -> str:
    """Merge a branch."""
    import subprocess

    cmd = ["git", "merge"]
    if no_ff:
        cmd.append("--no-ff")
    cmd.append(branch)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


@skill_command(name="git.tag_create", category="write", description="Create tag.")
def tag_create(name: str, msg: Optional[str] = None) -> str:
    """Create an annotated tag."""
    from agent.skills.git.scripts import tag_list as tag_mod

    return tag_mod.create_tag(name, msg)


@skill_command(name="git.revert", category="write", description="Revert commit.")
def revert(commit: str, no_commit: bool = False) -> str:
    """Revert a specific commit."""
    from agent.skills.git.scripts import commit as commit_mod

    return commit_mod.revert(commit, no_commit)


@skill_command(name="git.submodule_update", category="write", description="Update submodules.")
def submodule_update(init: bool = False) -> str:
    """Update git submodules."""
    import subprocess

    cmd = ["git", "submodule", "update", "--recursive"]
    if init:
        cmd.append("--init")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


# ==============================================================================
# EVOLUTION Operations (Router Layer)
# ==============================================================================


@skill_command(name="git.read_backlog", category="evolution", description="Read skill backlog.")
def read_backlog() -> str:
    """Read the Git Skill's own backlog."""
    from common.skill_utils import skill_path

    backlog = skill_path("assets/Backlog.md")
    return backlog.read_text() if backlog.exists() else "No backlog found"


# ==============================================================================
# LEGACY FUNCTIONS (still in tools.py for backward compatibility)
# These are used by workflow.py and other internal modules
# ==============================================================================


def _run(cmd: list[str], cwd: Optional[Path] = None) -> str:
    """Execute a git command and return output."""
    import subprocess

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def _get_cog_scopes(project_root: Optional[Path] = None) -> list[str]:
    """Read allowed scopes from cog.toml."""
    try:
        from common.config.settings import get_setting

        cog_path_str = get_setting("tools.cog.config_path")
        if not cog_path_str:
            cog_path = (project_root or Path.cwd()) / "cog.toml"
        else:
            cog_path = Path(cog_path_str)

        if cog_path.exists():
            content = cog_path.read_text()
            import re

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
) -> tuple[str, str, list[str]]:
    """Validate scope against cog.toml, return (type, fixed_scope, warnings)."""
    warnings = []
    valid_scopes = _get_cog_scopes(project_root)

    if not valid_scopes:
        return commit_type, scope, warnings

    if scope and scope not in valid_scopes:
        warnings.append(f"⚠️  Scope '{scope}' not in cog.toml allowed scopes")
        if valid_scopes:
            scope = valid_scopes[0]
            warnings.append(f"🔄 Auto-switched to scope '{scope}'")
    elif not scope:
        if valid_scopes:
            scope = valid_scopes[0]
            warnings.append(f"ℹ️  No scope provided, using '{scope}'")

    return commit_type, scope, warnings


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
