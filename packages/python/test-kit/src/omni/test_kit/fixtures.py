"""Test fixtures - re-export from submodules for backwards compatibility.

This module re-exports all fixtures from the fixtures/ subdirectory.
Import directly from submodules for better IDE support:

    from omni.test_kit.fixtures.core import test_tracer
    from omni.test_kit.fixtures.scanner import skill_directory
"""

# Re-export from submodules for backwards compatibility
from omni.test_kit.fixtures import (
    test_tracer,
    project_root,
    skills_root,
    config_dir,
    cache_dir,
    clean_settings,
    mock_agent_context,
    temp_git_repo,
    git_repo,
    git_test_env,
    gitops_verifier,
    SkillTestBuilder,
    SkillTestSuite,
    skill_test_suite,
    skill_directory,
    multi_skill_directory,
    skill_tester,
    SkillResult,
    SkillTester,
    parametrize_skills,
)

# Also re-export from other test-kit modules
from omni.test_kit.langgraph import langgraph_tester
from omni.test_kit.mcp import mcp_tester, unused_port

__all__ = [
    # Core
    "test_tracer",
    "project_root",
    "skills_root",
    "config_dir",
    "cache_dir",
    "clean_settings",
    "mock_agent_context",
    # Git
    "temp_git_repo",
    "git_repo",
    "git_test_env",
    "gitops_verifier",
    # Scanner
    "SkillTestBuilder",
    "SkillTestSuite",
    "skill_test_suite",
    "skill_directory",
    "multi_skill_directory",
    "skill_tester",
    "SkillResult",
    "SkillTester",
    "parametrize_skills",
    # LangGraph
    "langgraph_tester",
    # MCP
    "mcp_tester",
    "unused_port",
]
