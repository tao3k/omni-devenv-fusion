"""Tests for Rust-only dispatch in `omni run` command."""

import os
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from omni.agent.cli.commands.run import register_run_command


def _build_run_app() -> typer.Typer:
    app = typer.Typer()
    with patch("omni.agent.cli.load_requirements.register_requirements"):
        register_run_command(app)
    return app


def test_run_dispatches_query_to_omni_agent():
    app = _build_run_app()
    runner = CliRunner()

    with patch("os.execvp") as m_execvp:
        result = runner.invoke(app, ["research this repo"])

    assert result.exit_code == 0
    m_execvp.assert_called_once_with(
        "omni-agent",
        ["omni-agent", "repl", "--query", "research this repo"],
    )


def test_run_dispatches_repl_when_no_task():
    app = _build_run_app()
    runner = CliRunner()

    with patch("os.execvp") as m_execvp:
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    m_execvp.assert_called_once_with(
        "omni-agent",
        ["omni-agent", "repl"],
    )


def test_run_sets_max_tool_rounds_when_steps_given(monkeypatch):
    app = _build_run_app()
    runner = CliRunner()
    monkeypatch.delenv("OMNI_AGENT_MAX_TOOL_ROUNDS", raising=False)

    with patch("os.execvp"):
        result = runner.invoke(app, ["--steps", "77", "hello"])

    assert result.exit_code == 0
    assert os.environ["OMNI_AGENT_MAX_TOOL_ROUNDS"] == "77"


def test_run_rejects_python_only_flags():
    app = _build_run_app()
    runner = CliRunner()

    result = runner.invoke(app, ["--graph", "hello"])
    assert result.exit_code == 2
    assert "Unsupported flags" in result.output


def test_run_reports_missing_omni_agent():
    app = _build_run_app()
    runner = CliRunner()

    with patch("os.execvp", side_effect=FileNotFoundError):
        result = runner.invoke(app, ["hello"])

    assert result.exit_code == 1
    assert "omni-agent not found in PATH" in result.output
