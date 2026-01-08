"""
Test Utilities Package.

Provides centralized fixtures and helpers for the Omni-Dev Fusion test suite.

Modules:
    - fixtures: Toxic skill factories and skill loaders
    - assertions: Common assertion helpers
    - async_helpers: Async test utilities
    - module_helpers: Module loading utilities
    - skill_path: Skill path utilities - re-exported from common.skills_path

Note:
    Path utilities (SKILLS_DIR, load_skill_module, SkillPathBuilder) are now
    in common.skills_path. Project root detection uses common.gitops.get_project_root()
    which runs `git rev-parse --show-toplevel`.
"""

from .fixtures import (
    TOXIC_SKILL_TEMPLATES,
    create_toxic_skill_factory,
    TestAssertions,
)

# Re-export from common.skills_path (the canonical source)
from common.skills_path import (
    SKILLS_DIR,
    load_skill_module,
    load_skill_function,
    SkillPathBuilder,
)

__all__ = [
    "TOXIC_SKILL_TEMPLATES",
    "create_toxic_skill_factory",
    "TestAssertions",
    # From common.skills_path
    "SKILLS_DIR",
    "load_skill_module",
    "load_skill_function",
    "SkillPathBuilder",
]
