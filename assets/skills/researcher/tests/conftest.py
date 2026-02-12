"""
Test fixtures and configuration for researcher skill tests.

Provides proper fixtures and mocks to ensure tests work
both in IDE (Pyright) and command line pytest environments.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the scripts directory is in the Python path for imports
RESEARCHER_SCRIPTS = Path(__file__).parent.parent / "scripts"
if str(RESEARCHER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(RESEARCHER_SCRIPTS))


@pytest.fixture(scope="session")
def research_scripts_path():
    """Get the researcher scripts directory."""
    return Path(__file__).parent.parent / "scripts"


@pytest.fixture
def mock_omni_foundation():
    """Mock omni.foundation modules to avoid import errors in tests."""
    mock_dirs = MagicMock()
    mock_dirs.SKILLS_DIR.return_value = Path(__file__).parent.parent / "scripts"
    mock_dirs.PRJ_CACHE.return_value = Path("/tmp/.cache/research")
    mock_dirs.get_data_dir.return_value = Path("/tmp/.data")

    mock_checkpointer = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "omni": MagicMock(),
            "omni.foundation": MagicMock(),
            "omni.foundation.config": MagicMock(),
            "omni.foundation.config.dirs": mock_dirs,
            "omni.foundation.config.logging": MagicMock(),
            "omni.foundation.checkpoint": MagicMock(),
        },
    ):
        yield {
            "dirs": mock_dirs,
            "checkpointer": mock_checkpointer,
        }


@pytest.fixture
def mock_langgraph():
    """Mock LangGraph components."""
    mock_state_graph = MagicMock()
    mock_typed_dict = MagicMock()

    with patch("langgraph.graph.StateGraph", mock_state_graph):
        with patch("langgraph.graph.END", "END"):
            yield {
                "StateGraph": mock_state_graph,
                "TypedDict": mock_typed_dict,
            }


@pytest.fixture
def mock_inference_client():
    """Mock InferenceClient for LLM calls."""
    mock_client = AsyncMock()
    mock_client.model = "test-model"
    mock_client.max_tokens = 4096
    mock_client.timeout = 120
    mock_client.complete = AsyncMock(return_value={"content": "Test response content"})
    return mock_client


@pytest.fixture
def sample_research_state():
    """Provide a sample ResearchState for testing."""
    from research_graph import ResearchState

    return ResearchState(
        request="Analyze the architecture",
        repo_url="https://github.com/example/repo",
        repo_path="/tmp/test_repo",
        repo_revision="abc123",
        repo_revision_date="2026-02-05",
        repo_owner="example",
        repo_name="repo",
        file_tree="test/\n  src/\n    main.rs",
        shards_queue=[],
        current_shard=None,
        shard_counter=0,
        shard_analyses=[],
        harvest_dir="/tmp/test_harvest",
        final_report="",
        steps=0,
        messages=[],
        error=None,
    )


@pytest.fixture
def sample_shard_definition():
    """Provide a sample ShardDef for testing."""
    try:
        from research_graph import ShardDef
    except ImportError:
        pytest.skip("research_graph not available")

    return ShardDef(
        name="Test Shard", targets=["src/main.rs", "src/lib.rs"], description="Core functionality"
    )


@pytest.fixture(autouse=True)
def skip_slow_tests_marker(request):
    """Skip tests marked as slow during quick test runs."""
    if hasattr(request.config, "getoption"):
        if request.config.getoption("--quick", default=False):
            for marker in request.iter_markers("slow"):
                if marker.name in request.node.name:
                    pytest.skip(f"Slow test: {request.node.name}")
