# utils
"""
Utilities Module

Provides common utility functions:
- templating.py: Template rendering
- skills.py: Skill-related utilities
- common.py: Common helper functions

Usage:
    from omni.foundation.utils.templating import render_template
    from omni.foundation.config.skills import SKILLS_DIR
    from omni.foundation.utils.common import is_binary
"""

from .common import agent_src, common_src, project_root, setup_import_paths
from .asyncio import run_async_blocking
from .fs import find_files_by_extension, find_markdown_files
from .skills import (
    current_skill_dir,
    skill_asset,
    skill_command,
    skill_data,
    skill_path,
    skill_reference,
)
from .templating import render_string

__all__ = [
    "agent_src",
    "common_src",
    "current_skill_dir",
    "find_files_by_extension",
    "find_markdown_files",
    "project_root",
    "render_string",
    "run_async_blocking",
    "setup_import_paths",
    "skill_asset",
    "skill_command",
    "skill_data",
    "skill_path",
    "skill_reference",
]
