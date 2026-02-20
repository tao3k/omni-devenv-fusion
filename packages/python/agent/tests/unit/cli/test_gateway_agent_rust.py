"""Tests for Rust-only dispatch in `omni gateway` / `omni agent` commands."""

from unittest.mock import patch

import typer
from typer.testing import CliRunner


def _build_gateway_app() -> typer.Typer:
    app = typer.Typer()
    with patch("omni.agent.cli.load_requirements.register_requirements"):
        from omni.agent.cli.commands.gateway_agent import register_gateway_command

        register_gateway_command(app)
    return app


def _build_agent_app() -> typer.Typer:
    app = typer.Typer()
    with patch("omni.agent.cli.load_requirements.register_requirements"):
        from omni.agent.cli.commands.gateway_agent import register_agent_command

        register_agent_command(app)
    return app


def test_gateway_dispatches_to_rust_stdio_by_default():
    app = _build_gateway_app()
    runner = CliRunner()

    with patch("os.execvp") as m_execvp:
        result = runner.invoke(app, ["--session", "s-1"])

    assert result.exit_code == 0
    m_execvp.assert_called_once_with(
        "omni-agent",
        ["omni-agent", "stdio", "--session-id", "s-1"],
    )


def test_gateway_dispatches_to_rust_webhook_mode():
    app = _build_gateway_app()
    runner = CliRunner()

    with patch("os.execvp") as m_execvp:
        result = runner.invoke(app, ["--webhook-port", "8080", "--webhook-host", "0.0.0.0"])

    assert result.exit_code == 0
    m_execvp.assert_called_once_with(
        "omni-agent",
        ["omni-agent", "gateway", "--bind", "0.0.0.0:8080"],
    )


def test_agent_dispatches_to_rust_repl_by_default():
    app = _build_agent_app()
    runner = CliRunner()

    with patch("os.execvp") as m_execvp:
        result = runner.invoke(app, ["--session", "s-2"])

    assert result.exit_code == 0
    m_execvp.assert_called_once_with(
        "omni-agent",
        ["omni-agent", "repl", "--session-id", "s-2"],
    )


def test_gateway_reports_missing_omni_agent():
    app = _build_gateway_app()
    runner = CliRunner()

    with patch("os.execvp", side_effect=FileNotFoundError):
        result = runner.invoke(app, ["--session", "s-1"])

    assert result.exit_code == 1
    assert "omni-agent not found in PATH" in result.output
