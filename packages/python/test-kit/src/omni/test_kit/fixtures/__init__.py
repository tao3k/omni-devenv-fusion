"""Test fixtures - re-export from submodules for backwards compatibility."""

from omni.test_kit.fixtures.core import (
    test_tracer,
    project_root,
    skills_root,
    config_dir,
    cache_dir,
    clean_settings,
    mock_agent_context,
)

from omni.test_kit.fixtures.git import (
    temp_git_repo,
    git_repo,
    git_test_env,
    gitops_verifier,
)

from omni.test_kit.fixtures.scanner import (
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
]
