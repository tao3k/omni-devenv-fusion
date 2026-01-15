"""
git/scripts/ - Isolated implementation module

This package contains atomic script implementations for the git skill.
Each script is isolated via absolute imports, preventing namespace conflicts
with other skills (e.g., docker/scripts/status.py).

Architecture:
    tools.py  -> Router (just dispatches)
    scripts/  -> Controllers (actual implementation)

Usage in tools.py:
    from agent.skills.git.scripts import status as status_module
    from agent.skills.git.scripts import branch
    from agent.skills.git.scripts import log

Each script module is directly importable as agent.skills.git.scripts.<module_name>
"""

from agent.skills.git.scripts import status as status_module
from agent.skills.git.scripts import commit as commit_module

# Re-export status functions (avoid name conflict with module)
git_status = status_module.status
git_status_detailed = status_module.git_status_detailed
current_branch = status_module.current_branch
has_staged_files = status_module.has_staged_files
has_unstaged_files = status_module.has_unstaged_files

# Re-export commit functions
commit = commit_module.commit
commit_with_amend = commit_module.commit_with_amend
commit_no_verify = commit_module.commit_no_verify
get_last_commit = commit_module.get_last_commit
get_last_commit_msg = commit_module.get_last_commit_msg
revert = commit_module.revert
