"""
agent.skills - Skill modules package

This package contains:
- decorators.py: @skill_command decorator for defining skill commands
- core/: Core skill loading and management (skill_manifest_loader, test_framework, etc.)
- <skill_name>/: Individual skill implementations (git, filesystem, etc.)

Architecture:
- skills/<skill>/tools.py: Router layer (dispatch to scripts/)
- skills/<skill>/scripts/: Controller layer (atomic implementations)
"""

from .decorators import skill_command, CommandResult

__all__ = [
    "skill_command",
    "CommandResult",
]
