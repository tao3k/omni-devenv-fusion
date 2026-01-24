"""
Stress tests configuration - Trinity Architecture v2.0

Stress tests are separated from the main test suite for performance reasons.
Run them separately with: just test-stress

Note: Fixtures like skills_root, git_repo, project_root are provided
by the centralized conftest.py in parent directory.
"""

import asyncio

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def git_skill(skills_root, git_repo):
    """Load the git skill for testing with a temporary git repo.

    Args:
        skills_root: Centralized fixture providing skills directory
        git_repo: Centralized fixture providing temp git repo
    """
    from omni.core.skills import UniversalScriptSkill

    skill = UniversalScriptSkill("git", str(skills_root / "git"))
    await skill.load({"cwd": str(git_repo)})
    yield skill
