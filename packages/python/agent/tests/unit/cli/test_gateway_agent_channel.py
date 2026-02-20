"""Unit tests for `omni channel` command (Rust channel dispatch)."""

from __future__ import annotations

import os
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from omni.agent.cli.commands.gateway_agent import register_channel_command


def _build_channel_app() -> typer.Typer:
    app = typer.Typer()
    with patch("omni.agent.cli.load_requirements.register_requirements"):
        register_channel_command(app)
    return app


def _get_setting_for_channel(key: str):
    if key == "telegram.allowed_users":
        return "alice,888"
    if key == "telegram.max_tool_rounds":
        return 42
    return None


def _get_setting_for_channel_without_allowlist(key: str):
    if key == "telegram.max_tool_rounds":
        return 42
    return None


def test_channel_rejects_when_token_missing(monkeypatch):
    app = _build_channel_app()
    runner = CliRunner()
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    result = runner.invoke(app, [])

    assert result.exit_code == 1
    assert "TELEGRAM_BOT_TOKEN" in result.stdout
    assert "telegram.bot_token" not in result.stdout


def test_channel_uses_env_token_and_execs_binary(monkeypatch):
    app = _build_channel_app()
    runner = CliRunner()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    monkeypatch.delenv("OMNI_AGENT_MAX_TOOL_ROUNDS", raising=False)

    with (
        patch(
            "omni.agent.cli.commands.gateway_agent.get_setting",
            side_effect=_get_setting_for_channel,
        ),
        patch("os.execvp") as m_execvp,
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    m_execvp.assert_called_once()
    binary, argv = m_execvp.call_args.args
    assert binary == "omni-agent"
    assert argv == [
        "omni-agent",
        "channel",
        "--bot-token",
        "env-token",
        "--allowed-users",
        "alice,888",
        "--allowed-groups",
        "",
    ]
    assert os.environ["OMNI_AGENT_MAX_TOOL_ROUNDS"] == "42"


def test_channel_prefers_cli_token_over_env(monkeypatch):
    app = _build_channel_app()
    runner = CliRunner()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")

    with (
        patch(
            "omni.agent.cli.commands.gateway_agent.get_setting",
            side_effect=_get_setting_for_channel,
        ),
        patch("os.execvp") as m_execvp,
    ):
        result = runner.invoke(app, ["--bot-token", "cli-token"])

    assert result.exit_code == 0
    _, argv = m_execvp.call_args.args
    assert "--bot-token" in argv
    token_index = argv.index("--bot-token") + 1
    assert argv[token_index] == "cli-token"


def test_channel_defaults_to_empty_allowlist_when_unconfigured(monkeypatch):
    app = _build_channel_app()
    runner = CliRunner()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")

    with (
        patch(
            "omni.agent.cli.commands.gateway_agent.get_setting",
            side_effect=_get_setting_for_channel_without_allowlist,
        ),
        patch("os.execvp") as m_execvp,
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    _, argv = m_execvp.call_args.args
    assert "--allowed-users" in argv
    users_index = argv.index("--allowed-users") + 1
    assert argv[users_index] == ""
    assert "--allowed-groups" in argv
    groups_index = argv.index("--allowed-groups") + 1
    assert argv[groups_index] == ""
