"""
Git Skill Tests - Trinity Architecture v2.0

Tests for git skill commands.
Uses simple import checks.
"""

import sys
from pathlib import Path

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))


class TestGitScripts:
    """Test git skill scripts can be imported."""

    def test_commit_script_imports(self):
        """Test commit script imports successfully."""
        from git.scripts import commit

        assert hasattr(
            commit, "commit"
        )  # Function name is 'commit', name='git_commit' in decorator

    def test_status_script_imports(self):
        """Test status script imports successfully."""
        from git.scripts import status

        assert hasattr(status, "status")

    def test_prepare_script_imports(self):
        """Test prepare script imports successfully."""
        from git.scripts import prepare

        assert hasattr(prepare, "stage_and_scan")

    def test_render_script_imports(self):
        """Test rendering script imports successfully."""
        from git.scripts import rendering

        assert hasattr(rendering, "render_commit_message")

    def test_commit_state_script_imports(self):
        """Test commit_state script imports successfully."""
        from git.scripts import commit_state

        assert hasattr(commit_state, "create_initial_state")

    def test_smart_commit_workflow_imports(self):
        """Test smart_commit_workflow script imports successfully."""
        from git.scripts.smart_commit_graphflow import _build_workflow

        assert callable(_build_workflow)
