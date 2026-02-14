"""Unit tests for db command extensions."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from omni.agent.cli.app import app


class TestDbCommandExtensions:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_table_info_json(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.get_table_info = AsyncMock(
            return_value={"version_id": 7, "num_rows": 42, "fragment_count": 2}
        )

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(app, ["db", "table-info", "skills", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["database"] == "skills"
        assert payload["table"] == "skills"
        assert payload["info"]["version_id"] == 7

    def test_versions_json(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.list_versions = AsyncMock(
            return_value=[
                {"version": 3, "timestamp": 1700000000},
                {"version": 2, "timestamp": 1699999999},
            ]
        )

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(app, ["db", "versions", "skills", "--limit", "1", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["database"] == "skills"
        assert len(payload["versions"]) == 1
        assert payload["versions"][0]["version"] == 3

    def test_fragments_json(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.get_fragment_stats = AsyncMock(
            return_value=[{"id": 1, "num_rows": 100, "num_files": 1}]
        )

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(app, ["db", "fragments", "skills", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["table"] == "skills"
        assert payload["fragments"][0]["id"] == 1

    def test_add_columns_calls_store(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.add_columns = AsyncMock(return_value=True)
        columns = [{"name": "tag", "data_type": "Utf8", "nullable": True}]

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(
                app,
                [
                    "db",
                    "add-columns",
                    "skills",
                    "--columns-json",
                    json.dumps(columns),
                    "--json",
                ],
            )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["ok"] is True
        mock_store.add_columns.assert_awaited_once_with("skills", columns)

    def test_alter_columns_calls_store(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.alter_columns = AsyncMock(return_value=True)
        alterations = [{"type": "rename", "old_name": "tag", "new_name": "label"}]

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(
                app,
                [
                    "db",
                    "alter-columns",
                    "skills",
                    "--alterations-json",
                    json.dumps(alterations),
                    "--json",
                ],
            )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["ok"] is True
        mock_store.alter_columns.assert_awaited_once_with("skills", alterations)

    def test_drop_columns_calls_store(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.drop_columns = AsyncMock(return_value=True)

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(
                app,
                [
                    "db",
                    "drop-columns",
                    "skills",
                    "--column",
                    "tag",
                    "--column",
                    "label",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["ok"] is True
        assert payload["columns"] == ["tag", "label"]
        mock_store.drop_columns.assert_awaited_once_with("skills", ["tag", "label"])

    def test_add_columns_rejects_invalid_json(self, runner: CliRunner):
        result = runner.invoke(
            app,
            ["db", "add-columns", "skills", "--columns-json", "{not-json}"],
        )

        assert result.exit_code != 0
        # CLI must surface add-columns (usage or error); BadParameter text varies by Typer/Click
        combined = result.output + getattr(result, "stderr", "")
        assert "add-columns" in combined or "columns" in combined

    def test_health_json(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.analyze_table_health.return_value = {
            "row_count": 100,
            "fragment_count": 3,
            "fragmentation_ratio": 0.15,
            "indices_status": [],
            "recommendations": [{"type": "run_compaction"}],
        }

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(app, ["db", "health", "skills", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "skills/skills" in payload
        report = payload["skills/skills"]
        assert report["row_count"] == 100
        assert report["fragment_count"] == 3
        assert report["recommendations"][0]["type"] == "run_compaction"
        mock_store.analyze_table_health.assert_called_once_with("skills")

    def test_compact_json(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.compact.return_value = {
            "fragments_before": 5,
            "fragments_after": 1,
            "fragments_removed": 4,
            "bytes_freed": 1024,
            "duration_ms": 42,
        }

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(app, ["db", "compact", "skills", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["database"] == "skills"
        assert payload["table"] == "skills"
        assert payload["compaction"]["fragments_before"] == 5
        assert payload["compaction"]["fragments_after"] == 1
        mock_store.compact.assert_called_once_with("skills")

    def test_compact_error_exit(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.compact.side_effect = RuntimeError("table not found")

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(app, ["db", "compact", "skills"])

        assert result.exit_code == 1
        assert "Compact failed" in result.output

    def test_query_metrics_json(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.get_query_metrics.return_value = {
            "query_count": 0,
            "last_query_ms": None,
        }

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(app, ["db", "query-metrics", "skills", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["database"] == "skills"
        assert payload["table"] == "skills"
        assert payload["metrics"]["query_count"] == 0
        mock_store.get_query_metrics.assert_called_once_with("skills")

    def test_index_stats_json(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.get_index_cache_stats.return_value = {
            "entry_count": 2,
            "hit_rate": 0.85,
        }

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(app, ["db", "index-stats", "skills", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["database"] == "skills"
        assert payload["table"] == "skills"
        assert payload["index_cache"]["entry_count"] == 2
        assert payload["index_cache"]["hit_rate"] == 0.85
        mock_store.get_index_cache_stats.assert_called_once_with("skills")

    def test_index_create_hnsw_json(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.create_hnsw_index.return_value = {"index_type": "hnsw", "rows_indexed": 100}

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(
                app,
                ["db", "index", "create", "skills", "--type", "hnsw", "--json"],
            )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["database"] == "skills"
        assert payload["table"] == "skills"
        assert payload["type"] == "hnsw"
        assert payload["result"]["index_type"] == "hnsw"
        mock_store.create_hnsw_index.assert_called_once_with("skills")

    def test_index_create_btree_with_column_json(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.create_btree_index.return_value = {"index_type": "btree", "column": "name"}

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(
                app,
                [
                    "db",
                    "index",
                    "create",
                    "skills",
                    "--type",
                    "btree",
                    "--column",
                    "name",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["type"] == "btree"
        mock_store.create_btree_index.assert_called_once_with("skills", "name")

    def test_index_create_btree_without_column_exits_1(self, runner: CliRunner):
        result = runner.invoke(
            app,
            ["db", "index", "create", "skills", "--type", "btree", "--json"],
        )

        assert result.exit_code == 1
        assert "column" in result.output.lower() or "required" in result.output.lower()

    def test_index_create_optimal_vector_json(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.create_optimal_vector_index.return_value = {
            "index_type": "optimal",
            "rows_indexed": 50,
        }

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(
                app,
                ["db", "index", "create", "knowledge_chunks", "-t", "optimal-vector", "-j"],
            )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["type"] == "optimal-vector"
        mock_store.create_optimal_vector_index.assert_called_once_with("knowledge_chunks")

    def test_partition_suggest_with_column_json(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.suggest_partition_column.return_value = "skill_name"

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(
                app,
                ["db", "partition-suggest", "skills", "--json"],
            )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["database"] == "skills"
        assert payload["table"] == "skills"
        assert payload["suggested_column"] == "skill_name"
        mock_store.suggest_partition_column.assert_called_once_with("skills")

    def test_partition_suggest_none_json(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.suggest_partition_column.return_value = None

        with patch("omni.agent.cli.commands.db._resolver._get_rust_store", return_value=mock_store):
            result = runner.invoke(
                app,
                ["db", "partition-suggest", "knowledge_chunks", "-d", "knowledge", "-j"],
            )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["suggested_column"] is None
        mock_store.suggest_partition_column.assert_called_once_with("knowledge_chunks")
