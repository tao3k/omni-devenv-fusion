"""
agent/testing - Pytest plugin and utilities for skill testing.

Modules:
    - plugin: Pytest plugin entry point
    - constants: Reserved and builtin fixture names
    - fixtures: Fixture creation functions
    - proxy: SkillProxy and CommandResultWrapper classes
    - setup: Module context setup functions
    - utils: Utility functions
    - context: SkillsContext for IDE type hints
"""

from agent.testing.constants import RESERVED_FIXTURES, PYTEST_BUILTIN_FIXTURES
from agent.testing.fixtures import _create_base_fixtures, _create_skill_fixture
from agent.testing.proxy import SkillProxy, _CommandResultWrapper
from agent.testing.setup import (
    _setup_skill_package_context,
    _setup_agent_skills_core,
)
from agent.testing.utils import get_skills, get_skill_module

__all__ = [
    # Constants
    "RESERVED_FIXTURES",
    "PYTEST_BUILTIN_FIXTURES",
    # Fixtures
    "_create_base_fixtures",
    "_create_skill_fixture",
    # Proxy
    "SkillProxy",
    "_CommandResultWrapper",
    # Setup
    "_setup_skill_package_context",
    "_setup_agent_skills_core",
    # Utils
    "get_skills",
    "get_skill_module",
]
