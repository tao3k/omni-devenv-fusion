"""Tests for researcher skill."""

import sys
from pathlib import Path

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))


class TestResearcherScripts:
    """Test researcher skill scripts can be imported."""

    def test_research_script_imports(self):
        """Test research script imports successfully."""
        from researcher.scripts import research

        assert hasattr(research, "clone_repo")
        assert hasattr(research, "repomix_map")
        assert hasattr(research, "repomix_compress")
        assert hasattr(research, "save_report")

    def test_clone_repo_function_exists(self):
        """Test clone_repo function exists."""
        from researcher.scripts.research import clone_repo

        assert callable(clone_repo)

    def test_repomix_map_function_exists(self):
        """Test repomix_map function exists."""
        from researcher.scripts.research import repomix_map

        assert callable(repomix_map)

    def test_repomix_compress_function_exists(self):
        """Test repomix_compress function exists."""
        from researcher.scripts.research import repomix_compress

        assert callable(repomix_compress)

    def test_save_report_function_exists(self):
        """Test save_report function exists."""
        from researcher.scripts.research import save_report

        assert callable(save_report)
