# runtime
"""
Runtime Environment Module

Provides execution environment utilities:
- isolation.py: Sidecar execution for skill scripts
- gitops.py: Git operations and project root detection

Usage:
    from omni.foundation.runtime.isolation import run_skill_command
    from omni.foundation.runtime.gitops import get_project_root
"""

from .isolation import run_skill_command
from .gitops import (
    get_project_root,
    get_spec_dir,
    get_instructions_dir,
    get_docs_dir,
    get_agent_dir,
    get_src_dir,
    is_git_repo,
    is_project_root,
    PROJECT,
)

__all__ = [
    "run_skill_command",
    "get_project_root",
    "get_spec_dir",
    "get_instructions_dir",
    "get_docs_dir",
    "get_agent_dir",
    "get_src_dir",
    "is_git_repo",
    "is_project_root",
    "PROJECT",
]
