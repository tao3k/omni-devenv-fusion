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
        assert hasattr(research, "repomix_compress_shard")
        assert hasattr(research, "save_index")

    def test_clone_repo_function_exists(self):
        """Test clone_repo function exists."""
        from researcher.scripts.research import clone_repo

        assert callable(clone_repo)

    def test_repomix_map_function_exists(self):
        """Test repomix_map function exists."""
        from researcher.scripts.research import repomix_map

        assert callable(repomix_map)

    def test_repomix_compress_shard_function_exists(self):
        """Test repomix_compress_shard function exists."""
        from researcher.scripts.research import repomix_compress_shard

        assert callable(repomix_compress_shard)

    def test_save_index_function_exists(self):
        """Test save_index function exists."""
        from researcher.scripts.research import save_index

        assert callable(save_index)


class TestResearcherCheckpoint:
    """Test researcher skill checkpoint integration."""

    def test_workflow_type_defined(self):
        """Test workflow type is defined for checkpointing."""
        from researcher.scripts.research_graph import _WORKFLOW_TYPE

        assert _WORKFLOW_TYPE == "research"

    def test_checkpointer_import(self):
        """Test checkpoint functions can be imported."""
        from researcher.scripts.research_graph import (
            load_workflow_state,
            save_workflow_state,
        )

        assert callable(save_workflow_state)
        assert callable(load_workflow_state)


class TestResearcherEntry:
    """Test researcher entry point."""

    def test_run_research_graph_exists(self):
        """Test run_research_graph function exists."""
        from researcher.scripts.research_entry import run_research_graph

        assert callable(run_research_graph)

    def test_get_workflow_id_exists(self):
        """Test _get_workflow_id helper exists."""
        from researcher.scripts.research_entry import _get_workflow_id

        assert callable(_get_workflow_id)
        # Test the function generates consistent IDs
        url1 = "https://github.com/example/repo"
        url2 = "https://github.com/example/repo"
        assert _get_workflow_id(url1) == _get_workflow_id(url2)
