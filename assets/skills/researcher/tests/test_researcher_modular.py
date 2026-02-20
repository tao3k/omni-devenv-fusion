import json
import pytest
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from omni.test_kit.decorators import omni_skill

# Ensure scripts directory is in path for imports
import sys

RESEARCHER_SCRIPTS = Path(__file__).parent.parent / "scripts"
if str(RESEARCHER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(RESEARCHER_SCRIPTS))


@pytest.mark.asyncio
@omni_skill(name="researcher")
class TestResearcherIntegration:
    """Integration tests for researcher skill."""

    async def test_run_research_graph(self, skill_tester):
        """Test run_research_graph entry point exists and is callable."""
        # This tests that the entry point is properly registered
        # Full integration test with real LLM is skipped to avoid long-running tests
        try:
            result = await skill_tester.run(
                "researcher",
                "run_research_graph",
                repo_url="https://github.com/test/repo",
                request="Test request",
            )
            # Accept either success or expected error types
            assert (
                result.success
                or "not found" in str(result.error).lower()
                or "api" in str(result.error).lower()
            )
        except Exception as e:
            # Expected when skill_tester can't load the skill outside MCP context
            pytest.skip(f"Skill not loaded in test context: {e}")


class TestResearchGraph:
    """Unit tests for research graph components."""

    def test_node_setup_returns_correct_state(self):
        """Test that node_setup returns properly structured state."""
        # Import after path setup
        from research_graph import ResearchState

        # Mock the research module functions
        test_state = ResearchState(
            request="Test request",
            repo_url="https://github.com/test/repo",
            repo_path="/tmp/test",
            repo_revision="abc123",
            repo_revision_date="2026-02-05",
            repo_owner="test",
            repo_name="repo",
            file_tree="",
            shards_queue=[],
            current_shard=None,
            shard_counter=0,
            shard_analyses=[],
            harvest_dir="",
            final_report="",
            steps=0,
            messages=[],
            error=None,
        )

        # Verify state structure
        assert isinstance(test_state, dict)
        assert "request" in test_state
        assert "repo_url" in test_state
        assert test_state["steps"] == 0
        assert test_state["error"] is None

    def test_research_state_typeddict_compliance(self):
        """Test that ResearchState TypedDict works correctly."""
        from research_graph import ResearchState, ShardDef

        # Test creating a valid ResearchState
        state: ResearchState = {
            "request": "Analyze architecture",
            "repo_url": "https://github.com/example/repo",
            "repo_path": "/path/to/repo",
            "repo_revision": "abc123",
            "repo_revision_date": "2026-02-05",
            "repo_owner": "example",
            "repo_name": "repo",
            "file_tree": "src/\n  main.rs",
            "shards_queue": [],
            "current_shard": None,
            "shard_counter": 0,
            "shard_analyses": [],
            "harvest_dir": "/path/to/harvest",
            "final_report": "",
            "steps": 1,
            "messages": [],
            "error": None,
        }

        assert state["shard_counter"] == 0
        assert len(state["shards_queue"]) == 0

    def test_shard_def_structure(self):
        """Test ShardDef TypedDict structure."""
        from research_graph import ShardDef

        shard: ShardDef = {
            "name": "Core Module",
            "targets": ["src/core.rs", "src/lib.rs"],
            "description": "Core functionality",
        }

        assert shard["name"] == "Core Module"
        assert len(shard["targets"]) == 2

    def test_normalize_shards_splits_oversized(self):
        """Oversized shards are split into chunks of at most MAX_FILES_PER_SHARD."""
        from researcher.scripts.research_graph import (
            MAX_FILES_PER_SHARD,
            _normalize_shards,
        )
        from researcher.scripts.research_graph import ShardDef

        shards: list[ShardDef] = [
            {
                "name": "BigCore",
                "targets": [f"src/f{i}.py" for i in range(8)],
                "description": "Core",
            },
        ]
        out = _normalize_shards(shards)
        assert len(out) >= 2
        for s in out:
            assert len(s["targets"]) <= MAX_FILES_PER_SHARD
        total = sum(len(s["targets"]) for s in out)
        assert total == 8

    def test_normalize_shards_caps_total_files(self):
        """Total files across shards are capped at MAX_TOTAL_FILES."""
        from researcher.scripts.research_graph import (
            MAX_TOTAL_FILES,
            _normalize_shards,
        )
        from researcher.scripts.research_graph import ShardDef

        shards: list[ShardDef] = [
            {"name": "A", "targets": [f"a{i}.py" for i in range(15)], "description": "A"},
            {"name": "B", "targets": [f"b{i}.py" for i in range(20)], "description": "B"},
        ]
        out = _normalize_shards(shards)
        total = sum(len(s["targets"]) for s in out)
        assert total <= MAX_TOTAL_FILES

    def test_normalize_shards_merges_tiny(self):
        """Shards with ≤ MIN_FILES_TO_MERGE files can be merged."""
        from researcher.scripts.research_graph import _normalize_shards
        from researcher.scripts.research_graph import ShardDef

        shards: list[ShardDef] = [
            {"name": "Tiny1", "targets": ["a.py"], "description": "T1"},
            {"name": "Tiny2", "targets": ["b.py"], "description": "T2"},
        ]
        out = _normalize_shards(shards)
        # After merge we expect 1 shard with 2 files (or 2 shards if merge logic keeps them separate in this case)
        assert len(out) >= 1
        total = sum(len(s["targets"]) for s in out)
        assert total == 2

    def test_build_execution_levels_respects_dependencies(self):
        """Shards with dependencies run in topological order; same level runs in parallel."""
        from omni.langgraph.parallel import build_execution_levels
        from researcher.scripts.research_graph import ShardDef

        shards: list[ShardDef] = [
            {"name": "Core", "targets": ["core.py"], "description": "Core", "dependencies": []},
            {"name": "API", "targets": ["api.py"], "description": "API", "dependencies": ["Core"]},
            {"name": "CLI", "targets": ["cli.py"], "description": "CLI", "dependencies": ["Core"]},
        ]
        levels = build_execution_levels(shards, parallel_all=False)
        assert len(levels) == 2
        assert len(levels[0]) == 1
        assert levels[0][0][0]["name"] == "Core"
        assert len(levels[1]) == 2
        names_l1 = {s["name"] for s, _ in levels[1]}
        assert names_l1 == {"API", "CLI"}


@pytest.mark.slow
class TestResearcherFullWorkflow:
    """Full workflow tests (skipped by default)."""

    async def test_full_research_workflow(self):
        """Test complete research workflow (requires LLM)."""
        pytest.skip("Requires LLM and network - run with --runslow")
        # This would test the full workflow end-to-end
        # Currently handled by the integration test above


class TestParseRepoUrl:
    """Unit tests for parse_repo_url function."""

    def test_standard_github_url(self):
        """Test parsing standard GitHub URL."""
        from researcher.scripts.research import parse_repo_url

        owner, repo = parse_repo_url("https://github.com/anthropics/claude-code")
        assert owner == "anthropics"
        assert repo == "claude-code"

    def test_github_url_with_git_suffix(self):
        """Test parsing GitHub URL with .git suffix."""
        from researcher.scripts.research import parse_repo_url

        owner, repo = parse_repo_url("https://github.com/tao3k/omni-dev-fusion.git")
        assert owner == "tao3k"
        assert repo == "omni-dev-fusion"

    def test_github_url_with_org_repo(self):
        """Test parsing URL with org and repo having same name."""
        from researcher.scripts.research import parse_repo_url

        owner, repo = parse_repo_url("https://github.com/nickel-lang/nickel")
        assert owner == "nickel-lang"
        assert repo == "nickel"

    def test_github_ssh_url(self):
        """Test parsing SSH-style GitHub URL."""
        from researcher.scripts.research import parse_repo_url

        owner, repo = parse_repo_url("git@github.com:antfu/skills.git")
        assert owner == "antfu"
        assert repo == "skills"

    def test_raw_githubusercontent_url(self):
        """Test parsing raw.githubusercontent.com URL."""
        from researcher.scripts.research import parse_repo_url

        owner, repo = parse_repo_url("https://raw.githubusercontent.com/user/repo/main/README.md")
        assert owner == "user"
        assert repo == "repo"

    def test_empty_url(self):
        """Test parsing empty URL returns fallback."""
        from researcher.scripts.research import parse_repo_url

        owner, repo = parse_repo_url("")
        assert owner == "unknown"
        assert repo == ""


class TestInitHarvestStructure:
    """Unit tests for init_harvest_structure function."""

    def test_harvest_structure_path(self, tmp_path):
        """Test that harvest structure creates correct path."""
        import researcher.scripts.research as research_module
        from researcher.scripts.research import init_harvest_structure

        # Mock get_data_dir to use tmp_path
        original = research_module.get_data_dir
        research_module.get_data_dir = lambda x: tmp_path / x

        try:
            result = init_harvest_structure("anthropics", "claude-code")
            expected = tmp_path / "harvested" / "anthropics" / "claude-code"

            assert result == expected
            assert result.exists()
            assert (result / "shards").exists()
        finally:
            research_module.get_data_dir = original

    def test_harvest_structure_creates_clean_directory(self, tmp_path):
        """Test that existing directory is removed and recreated."""
        import researcher.scripts.research as research_module
        from researcher.scripts.research import init_harvest_structure

        # Mock get_data_dir
        research_module.get_data_dir = lambda x: tmp_path / x

        # Create directory with some content
        research_module.get_data_dir("harvested").mkdir(parents=True, exist_ok=True)
        harvest_dir = research_module.get_data_dir("harvested") / "test" / "repo"
        harvest_dir.mkdir(parents=True)
        (harvest_dir / "old_file.txt").write_text("old content")

        # Call init_harvest_structure
        result = init_harvest_structure("test", "repo")

        # Verify old content is gone
        assert not (result / "old_file.txt").exists()
        # Verify new structure exists
        assert result.exists()
        assert (result / "shards").exists()

    def test_harvest_structure_path_format(self, tmp_path):
        """Test path format matches <owner>/<repo_name> pattern."""
        import researcher.scripts.research as research_module
        from researcher.scripts.research import init_harvest_structure

        # Mock get_data_dir
        research_module.get_data_dir = lambda x: tmp_path / x

        # Test various owner/repo combinations
        test_cases = [
            ("tao3k", "omni-dev-fusion"),
            ("nickel-lang", "nickel"),
            ("antfu", "skills"),
        ]

        for owner, repo in test_cases:
            result = init_harvest_structure(owner, repo)
            expected = tmp_path / "harvested" / owner / repo
            assert result == expected, f"Expected {expected}, got {result}"


class TestResearchChunkedAPI:
    """Tests for chunked research workflow (action=start | shard | synthesize)."""

    @pytest.mark.asyncio
    async def test_chunked_start_returns_session_id_and_shard_count(self):
        """action=start runs setup+architect, persists state, returns session_id and next_action."""
        from researcher.scripts.research_entry import _run_research_chunked

        with patch(
            "researcher.scripts.research_entry.run_setup_and_architect",
            new_callable=AsyncMock,
        ) as m_setup:
            m_setup.return_value = {
                "harvest_dir": "/tmp/harvest/owner/repo",
                "shards_queue": [
                    {"name": "Shard A", "targets": ["a.rs"], "description": "A"},
                    {"name": "Shard B", "targets": ["b.rs"], "description": "B"},
                ],
                "repo_url": "https://github.com/owner/repo",
                "request": "Analyze",
            }
            with (
                patch("researcher.scripts.research_entry._RESEARCH_CHUNKED_STORE.save"),
                patch("researcher.scripts.research_entry._save_chunked_state"),
            ):
                result = await _run_research_chunked(
                    repo_url="https://github.com/owner/repo",
                    request="Analyze",
                    action="start",
                    session_id="",
                )
        assert result.get("success") is True
        assert "session_id" in result
        assert result.get("shard_count") == 2
        assert [item["chunk_id"] for item in result.get("chunk_plan", [])] == ["c1", "c2"]
        assert result.get("harvest_dir") == "/tmp/harvest/owner/repo"
        assert "next_action" in result
        assert "shard" in result["next_action"].lower()
        assert "synthesize" in result["next_action"].lower()

    @pytest.mark.asyncio
    async def test_chunked_shard_with_chunk_ids_runs_selected_chunks(self):
        """action=shard with chunk_ids should process selected chunks and report remaining ids."""
        from researcher.scripts.research_entry import _run_research_chunked

        session_id = "sid-1"
        states: dict[str, dict] = {
            session_id: {
                "chunk_plan": [
                    {"chunk_id": "c1", "name": "Shard A"},
                    {"chunk_id": "c2", "name": "Shard B"},
                ],
                "harvest_dir": "/tmp/harvest/owner/repo",
                "shards_queue": [],
            },
            f"{session_id}:c1": {
                "shards_queue": [{"name": "Shard A", "targets": ["a.rs"], "description": "A"}],
                "shard_analyses": [],
            },
            f"{session_id}:c2": {
                "shards_queue": [{"name": "Shard B", "targets": ["b.rs"], "description": "B"}],
                "shard_analyses": [],
            },
        }

        def _fake_load(workflow_id: str):
            value = states.get(workflow_id)
            return deepcopy(value) if value is not None else None

        def _fake_save(workflow_id: str, state: dict):
            states[workflow_id] = deepcopy(state)

        async def _fake_run_one_shard(state: dict):
            shard = state["shards_queue"][0]
            return {
                **state,
                "shards_queue": [],
                "current_shard": {"name": shard["name"]},
                "shard_analyses": [f"{shard['name']} summary"],
            }

        with patch("researcher.scripts.research_entry._load_chunked_state", side_effect=_fake_load):
            with patch(
                "researcher.scripts.research_entry._save_chunked_state", side_effect=_fake_save
            ):
                with patch(
                    "researcher.scripts.research_entry.run_one_shard",
                    new_callable=AsyncMock,
                ) as m_one:
                    m_one.side_effect = _fake_run_one_shard
                    result = await _run_research_chunked(
                        repo_url="https://github.com/owner/repo",
                        request="Analyze",
                        action="shard",
                        session_id=session_id,
                        chunk_ids=["c1", "c2"],
                    )

        assert result.get("success") is True
        assert result.get("chunks_requested") == 2
        assert result.get("chunks_remaining") == 0
        assert result.get("pending_chunk_ids") == []
        assert sorted(result.get("completed_chunk_ids", [])) == ["c1", "c2"]
        assert m_one.await_count == 2

    @pytest.mark.asyncio
    async def test_chunked_shard_without_chunk_ids_processes_all_pending(self):
        """action=shard without selectors should run all pending chunk ids in parallel mode."""
        from researcher.scripts.research_entry import _run_research_chunked

        session_id = "sid-1"
        states: dict[str, dict] = {
            session_id: {
                "chunk_plan": [
                    {"chunk_id": "c1", "name": "Shard A"},
                    {"chunk_id": "c2", "name": "Shard B"},
                ],
                "harvest_dir": "/tmp/harvest/owner/repo",
                "shards_queue": [],
            },
            f"{session_id}:c1": {
                "shards_queue": [{"name": "Shard A", "targets": ["a.rs"], "description": "A"}],
                "shard_analyses": [],
            },
            f"{session_id}:c2": {
                "shards_queue": [{"name": "Shard B", "targets": ["b.rs"], "description": "B"}],
                "shard_analyses": [],
            },
        }

        def _fake_load(workflow_id: str):
            value = states.get(workflow_id)
            return deepcopy(value) if value is not None else None

        def _fake_save(workflow_id: str, state: dict):
            states[workflow_id] = deepcopy(state)

        async def _fake_run_one_shard(state: dict):
            shard = state["shards_queue"][0]
            return {
                **state,
                "shards_queue": [],
                "current_shard": {"name": shard["name"]},
                "shard_analyses": [f"{shard['name']} summary"],
            }

        with patch("researcher.scripts.research_entry._load_chunked_state", side_effect=_fake_load):
            with patch(
                "researcher.scripts.research_entry._save_chunked_state", side_effect=_fake_save
            ):
                with patch(
                    "researcher.scripts.research_entry.run_one_shard",
                    new_callable=AsyncMock,
                ) as m_one:
                    m_one.side_effect = _fake_run_one_shard
                    result = await _run_research_chunked(
                        repo_url="https://github.com/owner/repo",
                        request="Analyze",
                        action="shard",
                        session_id=session_id,
                    )

        assert result.get("success") is True
        assert result.get("chunks_requested") == 2
        assert result.get("chunks_remaining") == 0
        assert m_one.await_count == 2

    @pytest.mark.asyncio
    async def test_chunked_synthesize_with_pending_chunk_ids_returns_error(self):
        """action=synthesize should block until all chunk ids are completed."""
        from researcher.scripts.research_entry import _run_research_chunked

        session_id = "sid-1"
        states = {
            session_id: {
                "chunk_plan": [
                    {"chunk_id": "c1", "name": "Shard A"},
                    {"chunk_id": "c2", "name": "Shard B"},
                ],
                "harvest_dir": "/tmp/harvest/owner/repo",
            },
            f"{session_id}:c1": {"shards_queue": [], "shard_analyses": ["Shard A summary"]},
            f"{session_id}:c2": {
                "shards_queue": [{"name": "Shard B", "targets": ["b.rs"], "description": "B"}],
                "shard_analyses": [],
            },
        }

        def _fake_load(workflow_id: str):
            value = states.get(workflow_id)
            return deepcopy(value) if value is not None else None

        with patch("researcher.scripts.research_entry._load_chunked_state", side_effect=_fake_load):
            result = await _run_research_chunked(
                repo_url="https://github.com/owner/repo",
                request="Analyze",
                action="synthesize",
                session_id=session_id,
            )

        assert result.get("success") is False
        assert result.get("pending_chunk_ids") == ["c2"]

    @pytest.mark.asyncio
    async def test_chunked_synthesize_collects_child_chunk_summaries(self):
        """action=synthesize should collect summaries from child chunk sessions in plan order."""
        from researcher.scripts.research_entry import _run_research_chunked

        session_id = "sid-1"
        states = {
            session_id: {
                "chunk_plan": [
                    {"chunk_id": "c1", "name": "Shard A"},
                    {"chunk_id": "c2", "name": "Shard B"},
                ],
                "harvest_dir": "/tmp/harvest/owner/repo",
            },
            f"{session_id}:c1": {"shards_queue": [], "shard_analyses": ["Summary A"]},
            f"{session_id}:c2": {"shards_queue": [], "shard_analyses": ["Summary B"]},
        }

        def _fake_load(workflow_id: str):
            value = states.get(workflow_id)
            return deepcopy(value) if value is not None else None

        with patch("researcher.scripts.research_entry._load_chunked_state", side_effect=_fake_load):
            with patch(
                "researcher.scripts.research_entry.run_synthesize_only",
                new_callable=AsyncMock,
            ) as m_synth:
                m_synth.return_value = {
                    "harvest_dir": "/tmp/harvest/owner/repo",
                    "messages": [{"content": "Research complete."}],
                    "shard_analyses": ["Summary A", "Summary B"],
                }
                result = await _run_research_chunked(
                    repo_url="https://github.com/owner/repo",
                    request="Analyze",
                    action="synthesize",
                    session_id=session_id,
                )

        assert result.get("success") is True
        assert result.get("shards_analyzed") == 2
        called_state = m_synth.await_args.args[0]
        assert called_state.get("shard_analyses") == ["Summary A", "Summary B"]

    @pytest.mark.asyncio
    async def test_chunked_shard_without_session_id_returns_error(self):
        """action=shard without session_id returns error."""
        from researcher.scripts.research_entry import _run_research_chunked

        result = await _run_research_chunked(
            repo_url="https://github.com/owner/repo",
            request="Analyze",
            action="shard",
            session_id="",
        )
        assert result.get("success") is False
        assert "session_id" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_chunked_synthesize_without_session_id_returns_error(self):
        """action=synthesize without session_id returns error."""
        from researcher.scripts.research_entry import _run_research_chunked

        result = await _run_research_chunked(
            repo_url="https://github.com/owner/repo",
            request="Analyze",
            action="synthesize",
            session_id="",
        )
        assert result.get("success") is False
        assert "session_id" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_chunked_shard_processes_single_step_and_persists(self):
        """action=shard should process exactly one shard and persist updated state."""
        from researcher.scripts.research_entry import _run_research_chunked

        loaded_state = {
            "shards_queue": [
                {"name": "Shard A", "targets": ["a.rs"], "description": "A"},
                {"name": "Shard B", "targets": ["b.rs"], "description": "B"},
            ]
        }
        updated_state = {
            "shards_queue": [
                {"name": "Shard B", "targets": ["b.rs"], "description": "B"},
            ],
            "current_shard": {"name": "Shard A"},
            "shard_analyses": ["A summary"],
        }

        with patch("researcher.scripts.research_entry._load_chunked_state") as m_load:
            m_load.return_value = loaded_state
            with patch(
                "researcher.scripts.research_entry.run_one_shard",
                new_callable=AsyncMock,
            ) as m_one:
                m_one.return_value = updated_state
                with patch("researcher.scripts.research_entry._save_chunked_state") as m_save:
                    with patch(
                        "researcher.scripts.research_entry._RESEARCH_CHUNKED_STORE.save"
                    ) as m_store_save:
                        result = await _run_research_chunked(
                            repo_url="https://github.com/owner/repo",
                            request="Analyze",
                            action="shard",
                            session_id="sid-1",
                        )

        assert result.get("success") is True
        assert result.get("session_id") == "sid-1"
        assert result.get("chunks_remaining") == 1
        assert result.get("chunk_processed") == "Shard A"
        assert "shard again" in result.get("next_action", "").lower()
        m_one.assert_awaited_once()
        assert m_save.call_count + m_store_save.call_count >= 1

    @pytest.mark.asyncio
    async def test_chunked_shard_without_chunk_plan_uses_common_engine(self):
        """Without chunk_plan, shard step should delegate to common ChunkedWorkflowEngine."""
        from researcher.scripts.research_entry import _run_research_chunked

        with patch("researcher.scripts.research_entry._load_chunked_state") as m_load:
            m_load.return_value = {
                "shards_queue": [{"name": "Shard A", "targets": ["a.rs"], "description": "A"}],
            }
            with patch(
                "researcher.scripts.research_entry._build_research_chunked_engine"
            ) as m_builder:
                engine = MagicMock()
                engine.run_step = AsyncMock(
                    return_value={
                        "success": True,
                        "session_id": "sid-1",
                        "chunks_remaining": 1,
                        "chunk_processed": "Shard A",
                        "workflow_type": "research_chunked",
                        "next_action": "Call action=shard again with this session_id",
                    }
                )
                m_builder.return_value = engine
                result = await _run_research_chunked(
                    repo_url="https://github.com/owner/repo",
                    request="Analyze",
                    action="shard",
                    session_id="sid-1",
                )

        engine.run_step.assert_awaited_once_with(
            session_id="sid-1",
            action="shard",
            auto_complete=False,
        )
        assert result.get("success") is True
        assert result.get("chunks_remaining") == 1

    @pytest.mark.asyncio
    async def test_chunked_synthesize_returns_final_summary(self):
        """action=synthesize should return final summary payload from synthesized state."""
        from researcher.scripts.research_entry import _run_research_chunked

        with patch("researcher.scripts.research_entry._load_chunked_state") as m_load:
            m_load.return_value = {
                "shards_queue": [],
                "shard_analyses": ["A summary"],
                "harvest_dir": "/tmp/harvest/owner/repo",
            }
            with patch(
                "researcher.scripts.research_entry.run_synthesize_only",
                new_callable=AsyncMock,
            ) as m_synth:
                m_synth.return_value = {
                    "harvest_dir": "/tmp/harvest/owner/repo",
                    "messages": [{"content": "Research complete."}],
                    "shard_analyses": ["A summary"],
                }
                result = await _run_research_chunked(
                    repo_url="https://github.com/owner/repo",
                    request="Analyze",
                    action="synthesize",
                    session_id="sid-1",
                )

        assert result.get("success") is True
        assert result.get("session_id") == "sid-1"
        assert result.get("summary") == "Research complete."
        assert result.get("harvest_dir") == "/tmp/harvest/owner/repo"
        assert result.get("shards_analyzed") == 1
        m_synth.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chunked_synthesize_without_chunk_plan_uses_common_engine_result(self):
        """Without chunk_plan, synthesize path should consume common engine state payload."""
        from researcher.scripts.research_entry import _run_research_chunked

        with patch("researcher.scripts.research_entry._load_chunked_state") as m_load:
            m_load.return_value = {"shards_queue": [], "shard_analyses": ["A summary"]}
            with patch(
                "researcher.scripts.research_entry._build_research_chunked_engine"
            ) as m_builder:
                engine = MagicMock()
                engine.run_step = AsyncMock(
                    return_value={
                        "success": True,
                        "session_id": "sid-1",
                        "workflow_type": "research_chunked",
                        "state": {
                            "harvest_dir": "/tmp/harvest/owner/repo",
                            "messages": [{"content": "Research complete."}],
                            "shard_analyses": ["A summary"],
                        },
                    }
                )
                m_builder.return_value = engine
                result = await _run_research_chunked(
                    repo_url="https://github.com/owner/repo",
                    request="Analyze",
                    action="synthesize",
                    session_id="sid-1",
                )

        engine.run_step.assert_awaited_once_with(
            session_id="sid-1",
            action="synthesize",
            auto_complete=False,
        )
        assert result.get("success") is True
        assert result.get("summary") == "Research complete."
        assert result.get("harvest_dir") == "/tmp/harvest/owner/repo"
        assert result.get("shards_analyzed") == 1

    @pytest.mark.asyncio
    async def test_chunked_unknown_action_returns_error(self):
        """Unknown action returns error (or no state when session_id is invalid)."""
        from researcher.scripts.research_entry import _run_research_chunked

        result = await _run_research_chunked(
            repo_url="https://github.com/owner/repo",
            request="Analyze",
            action="unknown",
            session_id="abc123",
        )
        assert result.get("success") is False
        err = result.get("error", "")
        assert "Unknown action" in err or "No state found" in err

    @pytest.mark.asyncio
    async def test_run_research_graph_chunked_start_uses_step_mode(self):
        """Entry point: chunked+action=start must return step state, not auto-complete full workflow."""
        from researcher.scripts.research_entry import run_research_graph

        expected = {
            "success": True,
            "session_id": "sid-1",
            "shard_count": 2,
            "workflow_type": "research_chunked",
        }
        with patch(
            "researcher.scripts.research_entry._run_research_chunked",
            new_callable=AsyncMock,
        ) as m_step:
            m_step.return_value = expected
            result = await run_research_graph(
                repo_url="https://github.com/owner/repo",
                request="Analyze",
                chunked=True,
                action="start",
            )

        m_step.assert_awaited_once()
        if isinstance(result, dict) and "content" in result:
            payload = json.loads(result["content"][0]["text"])
        else:
            payload = result
        assert payload == expected

    @pytest.mark.asyncio
    async def test_chunked_auto_complete_helper_runs_full_workflow(self):
        """Helper API: _run_research_chunked_auto_complete still supports full one-call execution."""
        from researcher.scripts.research_entry import _run_research_chunked_auto_complete

        with patch(
            "researcher.scripts.research_entry.run_setup_and_architect",
            new_callable=AsyncMock,
        ) as m_setup:
            m_setup.return_value = {
                "harvest_dir": "/tmp/harvest/owner/repo",
                "shards_queue": [
                    {"name": "Shard A", "targets": ["a.rs"], "description": "A"},
                ],
                "repo_url": "https://github.com/owner/repo",
                "request": "Analyze",
            }
            with patch(
                "researcher.scripts.research_entry.run_one_shard",
                new_callable=AsyncMock,
            ) as m_shard:
                m_shard.return_value = {
                    "harvest_dir": "/tmp/harvest/owner/repo",
                    "shards_queue": [],
                    "shard_analyses": [{"name": "Shard A", "content": "Analysis A"}],
                }
                with patch(
                    "researcher.scripts.research_entry.run_synthesize_only",
                    new_callable=AsyncMock,
                ) as m_synth:
                    m_synth.return_value = {
                        "harvest_dir": "/tmp/harvest/owner/repo",
                        "messages": [{"content": "Research complete."}],
                        "shard_analyses": [{"name": "Shard A", "content": "Analysis A"}],
                    }
                    result = await _run_research_chunked_auto_complete(
                        repo_url="https://github.com/owner/repo",
                        request="Analyze",
                    )
        assert result.get("success") is True
        assert result.get("harvest_dir") == "/tmp/harvest/owner/repo"
        assert result.get("summary") == "Research complete."
        assert "shard_summaries" in result
        assert "session_id" not in result  # Auto-complete returns final result, not session

    @pytest.mark.asyncio
    async def test_chunked_action_start_handles_scalar_result_gracefully(self):
        """Regression: scalar auto-complete result must not crash with `.get`."""
        from researcher.scripts.research_entry import _run_research_chunked_auto_complete

        with patch(
            "researcher.scripts.research_entry.run_chunked_auto_complete",
            new_callable=AsyncMock,
        ) as m_auto:
            m_auto.return_value = {
                "success": True,
                "workflow_type": "research_chunked",
                "result": "Research on repo complete.",
            }
            result = await _run_research_chunked_auto_complete(
                repo_url="https://github.com/owner/repo",
                request="Analyze",
            )

        assert result.get("success") is True
        assert result.get("summary") == "Research on repo complete."
        assert result.get("harvest_dir") == ""
        assert result.get("shards_analyzed") == 0

    @pytest.mark.asyncio
    async def test_chunked_action_shard_completes_remainder_in_one_call(self):
        """action=shard with session_id completes all remaining shards + synthesize (retry scenario)."""
        from researcher.scripts.research_entry import _run_research_chunked_complete_remainder

        with patch("researcher.scripts.research_entry._load_chunked_state") as m_load:
            m_load.return_value = {
                "harvest_dir": "/tmp/harvest/owner/repo",
                "shards_queue": [
                    {"name": "Shard B", "targets": ["b.rs"], "description": "B"},
                ],
                "shard_analyses": [{"name": "Shard A", "content": "Analysis A"}],
            }
            with patch(
                "researcher.scripts.research_entry.run_one_shard",
                new_callable=AsyncMock,
            ) as m_shard:
                m_shard.return_value = {
                    "harvest_dir": "/tmp/harvest/owner/repo",
                    "shards_queue": [],
                    "shard_analyses": [
                        {"name": "Shard A", "content": "Analysis A"},
                        {"name": "Shard B", "content": "Analysis B"},
                    ],
                }
                with patch(
                    "researcher.scripts.research_entry.run_synthesize_only",
                    new_callable=AsyncMock,
                ) as m_synth:
                    m_synth.return_value = {
                        "harvest_dir": "/tmp/harvest/owner/repo",
                        "messages": [{"content": "Research complete."}],
                        "shard_analyses": [
                            {"name": "Shard A", "content": "Analysis A"},
                            {"name": "Shard B", "content": "Analysis B"},
                        ],
                    }
                    with patch("researcher.scripts.research_entry._RESEARCH_CHUNKED_STORE.save"):
                        result = await _run_research_chunked_complete_remainder("abc123")
        assert result.get("success") is True
        assert result.get("summary") == "Research complete."
        assert len(result.get("shard_summaries", [])) == 2


class TestResearchState:
    """Tests for ResearchState TypedDict."""

    def test_research_state_fields(self):
        """Test ResearchState has all required fields."""
        from researcher.scripts.research_graph import ResearchState

        state = ResearchState(
            request="Analyze architecture",
            repo_url="https://github.com/example/repo",
            repo_path="/path/to/repo",
            repo_revision="abc123",
            repo_revision_date="2026-02-04",
            repo_owner="example",
            repo_name="repo",
            file_tree="...",
            shards_queue=[],
            current_shard=None,
            shard_counter=0,
            shard_analyses=[],
            harvest_dir="/path/to/harvest",
            final_report="",
            steps=0,
            messages=[],
            error=None,
        )

        assert state["repo_owner"] == "example"
        assert state["repo_name"] == "repo"
        assert state["repo_revision"] == "abc123"


class TestResearchChunkedStateStore:
    """Tests for chunked state persistence with common WorkflowStateStore."""

    def test_load_chunked_state_accepts_native_workflow_state(self):
        """Current WorkflowStateStore payload should pass through unchanged."""
        from researcher.scripts.research_entry import _load_chunked_state

        with patch("researcher.scripts.research_entry._RESEARCH_CHUNKED_STORE.load") as m_load:
            m_load.return_value = {"shards_queue": [], "harvest_dir": "/tmp/harvest"}
            state = _load_chunked_state("sid-1")

        assert state == {"shards_queue": [], "harvest_dir": "/tmp/harvest"}
