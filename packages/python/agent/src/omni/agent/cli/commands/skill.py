"""
skill.py - Skill Command Group

This file is a backward compatibility wrapper.
The actual implementation is now in agent.cli.commands.skill package.

Provides full skill management commands:
- run: Run a skill command
- list: List installed skills
- discover: Discover skills from index
- search: Semantic vector search
- info: Show skill information
- install: Install a skill from URL
- update: Update an installed skill
- test: Test skills
- check: Validate skill structure
- templates: Manage skill templates
- create: Create a new skill from template
- reindex: Reindex skills into vector store
- index-stats: Show index statistics
"""

from __future__ import annotations

# Re-export from the skill package for backward compatibility
from omni.agent.cli.commands.skill import (
    register_skill_command,
    skill_app,
)

__all__ = ["skill_app", "register_skill_command"]
