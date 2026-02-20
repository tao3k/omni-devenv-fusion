"""Tests for CLI runner output ordering with verbose skills monitor."""

from __future__ import annotations

import asyncio
import importlib
from typing import Any


def test_run_skills_verbose_reports_after_result(monkeypatch) -> None:
    """Verbose mode should print command result before monitor dashboard."""
    from omni.agent.cli.runner import run_skills

    events: list[str] = []

    class _FakeMonitor:
        def report(self, *, output_json: bool = False) -> None:
            events.append(f"report:{output_json}")

    async def _fake_run_skill_with_monitor(
        _skill: str,
        _command: str,
        _args: dict[str, Any],
        *,
        output_json: bool = False,
        auto_report: bool = False,
    ):
        assert auto_report is False
        events.append("common_runner")
        return (
            {"content": [{"type": "text", "text": '{"status":"success"}'}], "isError": False},
            _FakeMonitor(),
        )

    async def _fake_close_embedding_client() -> None:
        return None

    def _run_async_blocking(awaitable):
        return asyncio.run(awaitable)

    def _fake_print_result(_result: Any, _is_tty: bool, _json_output: bool) -> None:
        events.append("print_result")

    monkeypatch.setattr("omni.agent.cli.runner.run_async_blocking", _run_async_blocking)
    monkeypatch.setattr("omni.agent.cli.runner.print_result", _fake_print_result)
    monkeypatch.setattr("omni.agent.cli.runner.err_console.print", lambda *args, **kwargs: None)
    monkeypatch.setattr("omni.core.skills.run_skill_with_monitor", _fake_run_skill_with_monitor)
    monkeypatch.setattr(
        "omni.foundation.api.tool_context.run_with_execution_timeout",
        lambda coro: coro,
    )
    monkeypatch.setattr(
        "omni.foundation.embedding_client.close_embedding_client",
        _fake_close_embedding_client,
    )

    run_skills(["knowledge.recall", '{"query":"x"}'])

    assert "print_result" in events
    report_events = [idx for idx, event in enumerate(events) if event.startswith("report:")]
    assert report_events, f"missing report event, got: {events}"
    assert events.index("print_result") < report_events[0], events


def test_run_skills_verbose_json_reports_after_result(monkeypatch) -> None:
    """Verbose + JSON mode should keep result before monitor dashboard."""
    from omni.agent.cli.runner import run_skills

    events: list[str] = []
    captured_output_json: list[bool] = []

    class _FakeMonitor:
        def report(self, *, output_json: bool = False) -> None:
            events.append(f"report:{output_json}")

    async def _fake_run_skill_with_monitor(
        _skill: str,
        _command: str,
        _args: dict[str, Any],
        *,
        output_json: bool = False,
        auto_report: bool = False,
    ):
        assert auto_report is False
        captured_output_json.append(output_json)
        events.append("common_runner")
        return (
            {
                "content": [{"type": "text", "text": '{"status":"success","mode":"json"}'}],
                "isError": False,
            },
            _FakeMonitor(),
        )

    async def _fake_close_embedding_client() -> None:
        return None

    def _run_async_blocking(awaitable):
        return asyncio.run(awaitable)

    def _fake_print_result(_result: Any, _is_tty: bool, _json_output: bool) -> None:
        events.append(f"print_result:{_json_output}")

    monkeypatch.setattr("omni.agent.cli.runner.run_async_blocking", _run_async_blocking)
    monkeypatch.setattr("omni.agent.cli.runner.print_result", _fake_print_result)
    monkeypatch.setattr("omni.agent.cli.runner.err_console.print", lambda *args, **kwargs: None)
    monkeypatch.setattr("omni.core.skills.run_skill_with_monitor", _fake_run_skill_with_monitor)
    monkeypatch.setattr(
        "omni.foundation.api.tool_context.run_with_execution_timeout",
        lambda coro: coro,
    )
    monkeypatch.setattr(
        "omni.foundation.embedding_client.close_embedding_client",
        _fake_close_embedding_client,
    )
    app_module = importlib.import_module("omni.agent.cli.app")
    monkeypatch.setattr(app_module, "_is_verbose", lambda: True)

    run_skills(["knowledge.recall", '{"query":"x"}'], json_output=True)

    assert captured_output_json == [True]
    assert "print_result:True" in events
    report_events = [idx for idx, event in enumerate(events) if event.startswith("report:")]
    assert report_events, f"missing report event, got: {events}"
    assert events.index("print_result:True") < report_events[0], events
