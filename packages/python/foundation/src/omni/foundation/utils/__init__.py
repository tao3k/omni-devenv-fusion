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

from .templating import render_string
from .skills import (
    skill_path,
    skill_asset,
    skill_command,
    skill_reference,
    skill_data,
    current_skill_dir,
)
from .common import project_root, common_src, agent_src, setup_import_paths

# Re-export SKILLS_DIR from config.skills for backward compatibility
from ..config.skills import SKILLS_DIR

# Re-export get_setting from config.settings for backward compatibility
from ..config.settings import get_setting

__all__ = [
    "render_string",
    "skill_path",
    "skill_asset",
    "skill_command",
    "skill_reference",
    "skill_data",
    "current_skill_dir",
    "project_root",
    "common_src",
    "agent_src",
    "setup_import_paths",
    "SKILLS_DIR",
    "get_setting",
]
