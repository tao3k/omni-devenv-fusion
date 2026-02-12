"""Unit tests for route CLI command extensions."""

from __future__ import annotations

import json
import os
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from omni.test_kit.fixtures.vector import (
    make_router_result_payload,
    parametrize_route_intent_queries,
)
from typer.testing import CliRunner

from omni.agent.cli.app import app
from omni.agent.cli.commands import route as route_module

# Strip ANSI escape sequences so assertions on help/CLI output work under Rich
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m|\x1b\[[?0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


class TestRouteSchemaCommand:
    def test_route_schema_help(self):
        runner = CliRunner()
        result = runner.invoke(app, ["route", "schema", "--help"])
        assert result.exit_code == 0
        assert "Export or print router search settings schema" in result.output

    @patch("omni.core.router.write_router_search_json_schema")
    @patch("omni.core.router.resolve_router_schema_path")
    def test_route_schema_write_default(self, mock_resolve, mock_write):
        mock_write.return_value = "/tmp/router.schema.json"
        mock_resolve.return_value = "/tmp/router.schema.json"

        runner = CliRunner()
        result = runner.invoke(app, ["route", "schema", "--json"])

        assert result.exit_code == 0
        assert '"status": "success"' in result.output
        assert '"path": "/tmp/router.schema.json"' in result.output

    @patch("omni.core.router.router_search_json_schema")
    def test_route_schema_stdout(self, mock_schema):
        mock_schema.return_value = {
            "title": "RouterSearchConfig",
            "type": "object",
            "properties": {"active_profile": {"type": "string"}},
        }

        runner = CliRunner()
        result = runner.invoke(app, ["route", "schema", "--stdout"])

        assert result.exit_code == 0
        assert '"RouterSearchConfig"' in result.output
        assert '"active_profile"' in result.output

    def test_route_schema_respects_active_conf_directory(self, tmp_path):
        """Default schema output should resolve under active conf directory."""
        conf_dir = tmp_path / "custom_conf"
        conf_dir.mkdir(parents=True, exist_ok=True)

        # CliRunner invokes Typer app directly (not entry_point pre-parser),
        # so we bootstrap config directory explicitly for this test.
        from omni.agent.cli.app import _bootstrap_configuration

        original_conf_home = os.environ.get("PRJ_CONFIG_HOME")
        try:
            _bootstrap_configuration(str(conf_dir))

            runner = CliRunner()
            result = runner.invoke(app, ["route", "schema", "--json"])

            assert result.exit_code == 0
            expected = conf_dir / "omni-dev-fusion" / "schemas" / "router.search.schema.json"
            assert expected.exists()
            assert f'"path": "{expected}"' in result.output
        finally:
            if original_conf_home is None:
                os.environ.pop("PRJ_CONFIG_HOME", None)
            else:
                os.environ["PRJ_CONFIG_HOME"] = original_conf_home

            from omni.foundation.config.dirs import PRJ_DIRS
            from omni.foundation.config.settings import get_settings

            PRJ_DIRS.clear_cache()
            get_settings().reload()


class TestRouteTestCommand:
    def test_route_defaults_from_router_search_namespace(self, monkeypatch):
        config = MagicMock(default_limit=12, default_threshold=0.33)
        monkeypatch.setattr(route_module, "_load_router_config", lambda: config)
        limit, threshold = route_module._load_route_test_defaults()
        assert limit == 12
        assert threshold == 0.33

    def test_route_defaults_use_hard_defaults_when_missing(self, monkeypatch):
        config = MagicMock(default_limit=10, default_threshold=0.2)
        monkeypatch.setattr(route_module, "_load_router_config", lambda: config)
        limit, threshold = route_module._load_route_test_defaults()
        assert limit == 10
        assert threshold == 0.2

    def test_route_test_requires_query_argument(self):
        """`omni route test` should fail clearly when QUERY is missing."""
        runner = CliRunner()
        result = runner.invoke(app, ["route", "test"])
        assert result.exit_code != 0
        assert "Missing argument 'QUERY'" in result.output

    def test_route_test_help_includes_query_examples(self):
        """`omni route test --help` should show required QUERY and concrete examples."""
        runner = CliRunner()
        result = runner.invoke(app, ["route", "test", "--help"])
        assert result.exit_code == 0
        out = _strip_ansi(result.output)
        assert "QUERY" in out
        assert 'omni route test "git commit"' in out
        assert 'omni route test "refactor rust module" --debug' in out

    def test_route_test_help_uses_settings_defaults(self):
        """`omni route test --help` should expose configured defaults."""
        runner = CliRunner()
        result = runner.invoke(app, ["route", "test", "--help"])
        assert result.exit_code == 0
        out = _strip_ansi(result.output)
        assert "Maximum results (default" in out
        assert "settings" in out
        assert "Score threshold (default" in out
        assert "--confidence-profile" in out

    @patch("omni.core.router.hybrid_search.HybridSearch")
    def test_route_test_debug_shows_real_raw_final_scores(self, mock_search_cls):
        """Debug output should use real raw/final scores (not derived sem/kw placeholders)."""
        runner = CliRunner()
        mock_search = MagicMock()
        mock_search.search = AsyncMock(
            return_value=[
                {
                    "id": "git.commit",
                    "skill_name": "git",
                    "command": "commit",
                    "score": 0.82,
                    "final_score": 0.91,
                    "confidence": "high",
                }
            ]
        )
        mock_search.stats.return_value = {
            "semantic_weight": 0.7,
            "keyword_weight": 0.3,
            "rrf_k": 60,
            "strategy": "weighted_rrf",
        }
        mock_search_cls.return_value = mock_search

        result = runner.invoke(app, ["route", "test", "git commit", "--debug", "--local"])

        assert result.exit_code == 0
        assert "raw=0.820 | final=0.910" in result.output
        assert "sem=" not in result.output

    @patch("omni.core.router.hybrid_search.HybridSearch")
    def test_route_test_json_outputs_full_payload(self, mock_search_cls):
        runner = CliRunner()
        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=[make_router_result_payload()])
        mock_search.stats.return_value = {
            "semantic_weight": 1.0,
            "keyword_weight": 1.5,
            "rrf_k": 10,
            "strategy": "weighted_rrf_field_boosting",
        }
        mock_search_cls.return_value = mock_search

        with patch.object(
            route_module,
            "_select_confidence_profile",
            new=AsyncMock(return_value=(None, None, "none-configured")),
        ):
            result = runner.invoke(app, ["route", "test", "git commit", "--local", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["query"] == "git commit"
        assert payload["schema"] == "omni.router.route_test.v1"
        assert payload["count"] == 1
        assert payload["results"][0]["id"] == "git.commit"
        assert payload["results"][0]["tool_name"] == "git.commit"
        assert payload["results"][0]["routing_keywords"] == ["git", "commit"]
        assert payload["results"][0]["payload"]["metadata"]["tool_name"] == "git.commit"
        assert payload["results"][0]["payload"]["metadata"]["routing_keywords"] == [
            "git",
            "commit",
        ]

    @pytest.mark.parametrize("local_flag", [True, False], ids=["local", "remote"])
    @parametrize_route_intent_queries()
    @patch("omni.core.router.hybrid_search.HybridSearch")
    def test_route_test_json_intent_shape_is_stable(
        self,
        mock_search_cls,
        query: str,
        expected_tool_name: str,
        local_flag: bool,
    ):
        runner = CliRunner()
        mock_search = MagicMock()
        mock_search.search = AsyncMock(
            return_value=[
                make_router_result_payload(
                    id=expected_tool_name,
                    tool_name=expected_tool_name,
                    skill_name=expected_tool_name.split(".", 1)[0],
                    command=expected_tool_name.split(".", 1)[1],
                    routing_keywords=["find", "files", "directory"]
                    if expected_tool_name == "advanced_tools.smart_find"
                    else ["git", "commit"],
                    payload={
                        "type": "command",
                        "description": "Find files by extension"
                        if expected_tool_name == "advanced_tools.smart_find"
                        else "Commit changes",
                        "metadata": {
                            "tool_name": expected_tool_name,
                            "routing_keywords": ["find", "files", "directory"]
                            if expected_tool_name == "advanced_tools.smart_find"
                            else ["git", "commit"],
                            "input_schema": {"type": "object"},
                        },
                    },
                )
            ]
        )
        mock_search.stats.return_value = {
            "semantic_weight": 1.0,
            "keyword_weight": 1.5,
            "rrf_k": 10,
            "strategy": "weighted_rrf_field_boosting",
        }
        mock_search_cls.return_value = mock_search

        with patch.object(
            route_module,
            "_select_confidence_profile",
            new=AsyncMock(return_value=(None, "balanced", "active-profile")),
        ):
            args = ["route", "test", query, "--json"]
            if local_flag:
                args.append("--local")
            result = runner.invoke(app, args)

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["schema"] == "omni.router.route_test.v1"
        assert payload["query"] == query
        assert payload["count"] == 1
        assert payload["results"][0]["tool_name"] == expected_tool_name
        assert payload["results"][0]["payload"]["metadata"]["tool_name"] == expected_tool_name

    @patch("omni.core.router.hybrid_search.HybridSearch")
    def test_route_test_json_empty_results_keeps_canonical_shape(self, mock_search_cls):
        runner = CliRunner()
        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=[])
        mock_search.stats.return_value = {
            "semantic_weight": 1.0,
            "keyword_weight": 1.5,
            "rrf_k": 10,
            "strategy": "weighted_rrf_field_boosting",
        }
        mock_search_cls.return_value = mock_search

        with patch.object(
            route_module,
            "_select_confidence_profile",
            new=AsyncMock(return_value=(None, "balanced", "active-profile")),
        ):
            result = runner.invoke(app, ["route", "test", "git commit", "--local", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["schema"] == "omni.router.route_test.v1"
        assert payload["query"] == "git commit"
        assert payload["count"] == 0
        assert payload["results"] == []
        assert "confidence_profile" in payload
        assert payload["confidence_profile"]["name"] == "balanced"
        assert "stats" in payload
        assert payload["stats"]["strategy"] is None

    @patch("omni.agent.cli.commands.route.run_async_blocking")
    def test_route_test_uses_shared_async_runner(self, mock_run_async_blocking):
        """route test should dispatch through shared run_async_blocking helper."""

        def _consume(coro):
            name = getattr(coro, "cr_code", None).co_name if hasattr(coro, "cr_code") else ""
            coro.close()
            if name == "_select_confidence_profile":
                return (None, None, "none-configured")
            return None

        mock_run_async_blocking.side_effect = _consume

        runner = CliRunner()
        result = runner.invoke(app, ["route", "test", "git commit"])

        assert result.exit_code == 0
        assert mock_run_async_blocking.called

    @patch("omni.core.router.hybrid_search.HybridSearch")
    def test_route_test_passes_confidence_profile_overrides(self, mock_search_cls):
        """Named confidence profile should be resolved and passed for this invocation."""
        runner = CliRunner()
        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=[])
        mock_search.stats.return_value = {
            "semantic_weight": 1.0,
            "keyword_weight": 1.5,
            "rrf_k": 10,
            "strategy": "weighted_rrf_field_boosting",
        }
        mock_search_cls.return_value = mock_search

        with patch.object(
            route_module,
            "_select_confidence_profile",
            new=AsyncMock(return_value=({"high_threshold": 0.82}, "precision", "explicit")),
        ) as mock_select:
            result = runner.invoke(
                app,
                [
                    "route",
                    "test",
                    "git commit",
                    "--local",
                    "--confidence-profile",
                    "precision",
                ],
            )

        assert result.exit_code == 0
        assert mock_select.called
        kwargs = mock_search.search.call_args.kwargs
        assert kwargs["confidence_profile"]["high_threshold"] == 0.82

    def test_route_confidence_profile_returns_none_when_not_requested(self):
        payload = route_module._load_named_confidence_profile(None)
        assert payload is None

    @patch("omni.core.router.hybrid_search.HybridSearch")
    def test_route_test_fails_on_unknown_confidence_profile(self, mock_search_cls):
        runner = CliRunner()
        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=[])
        mock_search.stats.return_value = {
            "semantic_weight": 1.0,
            "keyword_weight": 1.5,
            "rrf_k": 10,
            "strategy": "weighted_rrf_field_boosting",
        }
        mock_search_cls.return_value = mock_search

        with (
            patch.object(
                route_module,
                "_select_confidence_profile",
                new=AsyncMock(return_value=(None, "missing", "invalid")),
            ),
            patch.object(route_module, "_available_confidence_profiles", return_value=["balanced"]),
        ):
            result = runner.invoke(
                app,
                ["route", "test", "git commit", "--confidence-profile", "missing"],
            )
        assert result.exit_code != 0
        assert "Unknown confidence profile 'missing'" in result.output

    @patch("omni.core.router.hybrid_search.HybridSearch")
    def test_route_test_auto_selects_profile_without_flag(self, mock_search_cls):
        runner = CliRunner()
        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=[])
        mock_search.stats.return_value = {
            "semantic_weight": 1.0,
            "keyword_weight": 1.5,
            "rrf_k": 10,
            "strategy": "weighted_rrf_field_boosting",
        }
        mock_search_cls.return_value = mock_search

        with patch.object(
            route_module,
            "_select_confidence_profile",
            new=AsyncMock(return_value=({"high_threshold": 0.75}, "balanced", "active-profile")),
        ):
            result = runner.invoke(app, ["route", "test", "git commit", "--local"])

        assert result.exit_code == 0
        kwargs = mock_search.search.call_args.kwargs
        assert kwargs["confidence_profile"]["high_threshold"] == 0.75


class TestRouteStatsCommand:
    @patch("omni.core.router.config.load_router_search_config")
    @patch("omni.core.router.hybrid_search.HybridSearch")
    def test_route_stats_shows_confidence_profile(self, mock_search_cls, mock_config):
        mock_search = MagicMock()
        mock_search.stats.return_value = {
            "semantic_weight": 1.0,
            "keyword_weight": 1.5,
            "rrf_k": 10,
            "strategy": "weighted_rrf_field_boosting",
            "field_boosting": {"name_token_boost": 0.5, "exact_phrase_boost": 1.5},
        }
        mock_search_cls.return_value = mock_search
        profile = MagicMock(high_threshold=0.75, medium_threshold=0.5, low_floor=0.1)
        mock_config.return_value = MagicMock(
            active_profile="balanced",
            profiles={"balanced": profile},
        )

        runner = CliRunner()
        result = runner.invoke(app, ["route", "stats"])

        assert result.exit_code == 0
        assert "Confidence Profile (settings-driven)" in result.output
        assert "active_profile: balanced" in result.output
        assert "high_threshold: 0.75" in result.output
        assert "medium_threshold: 0.5" in result.output
