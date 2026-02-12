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

        with patch("omni.agent.cli.commands.db._get_rust_store", return_value=mock_store):
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

        with patch("omni.agent.cli.commands.db._get_rust_store", return_value=mock_store):
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

        with patch("omni.agent.cli.commands.db._get_rust_store", return_value=mock_store):
            result = runner.invoke(app, ["db", "fragments", "skills", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["table"] == "skills"
        assert payload["fragments"][0]["id"] == 1

    def test_add_columns_calls_store(self, runner: CliRunner):
        mock_store = MagicMock()
        mock_store.add_columns = AsyncMock(return_value=True)
        columns = [{"name": "tag", "data_type": "Utf8", "nullable": True}]

        with patch("omni.agent.cli.commands.db._get_rust_store", return_value=mock_store):
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

        with patch("omni.agent.cli.commands.db._get_rust_store", return_value=mock_store):
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

        with patch("omni.agent.cli.commands.db._get_rust_store", return_value=mock_store):
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
        assert "Invalid --columns-json" in result.output
