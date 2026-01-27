# runtime
"""
Runtime Environment Module

Provides execution environment utilities:
- isolation.py: Sidecar execution for skill scripts
- gitops.py: Git operations and project root detection
- path.py: Safe sys.path manipulation utilities

Usage:
    from omni.foundation.runtime.isolation import run_skill_command
    from omni.foundation.runtime.gitops import get_project_root
    from omni.foundation.runtime.path import temporary_sys_path
"""

from .gitops import (
    PROJECT,
    get_agent_dir,
    get_docs_dir,
    get_instructions_dir,
    get_project_root,
    get_spec_dir,
    get_src_dir,
    is_git_repo,
    is_project_root,
)
from .isolation import run_skill_command
from .path import temporary_sys_path

__all__ = [
    "PROJECT",
    "get_agent_dir",
    "get_docs_dir",
    "get_instructions_dir",
    "get_project_root",
    "get_spec_dir",
    "get_src_dir",
    "is_git_repo",
    "is_project_root",
    "run_skill_command",
    "temporary_sys_path",
]
