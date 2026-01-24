# utils
"""
Utilities Module

Provides common utility functions:
- templating.py: Template rendering
- skills.py: Skill-related utilities
- common.py: Common helper functions

Usage:
    from omni.foundation.utils.templating import render_template
    from omni.foundation.utils.skills import SKILLS_DIR
    from omni.foundation.utils.common import is_binary
"""

# Re-export get_setting from config.settings for backward compatibility
from ..config.settings import get_setting

# Re-export SKILLS_DIR from config.skills for backward compatibility
from ..config.skills import SKILLS_DIR
from .common import agent_src, common_src, project_root, setup_import_paths
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
    "SKILLS_DIR",
    "agent_src",
    "common_src",
    "current_skill_dir",
    "get_setting",
    "project_root",
    "render_string",
    "setup_import_paths",
    "skill_asset",
    "skill_command",
    "skill_data",
    "skill_path",
    "skill_reference",
]
