"""Unit tests for omni.core.skills.runner."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_RUN_ARGS = ("demo", "echo", {"message": "hi"})
_OK_RESULT = {"status": "ok"}


def test_validate_required_args_from_handler_reports_missing_fields():
    """Runner fast-path should detect missing required fields from handler schema."""
    from omni.core.skills.runner import _validate_required_args_from_handler

    def _handler(**_kwargs):
        return "ok"

    _handler._skill_config = {  # type: ignore[attr-defined]
        "input_schema": {
            "type": "object",
            "required": ["repo_url"],
            "properties": {"repo_url": {"type": "string"}},
        }
    }

    with pytest.raises(ValueError, match="missing required field\\(s\\): repo_url"):
        _validate_required_args_from_handler(
            _handler,
            skill_name="researcher",
            command_name="git_repo_analyer",
            args={},
        )


def test_validate_required_args_from_handler_allows_complete_args():
    """Runner fast-path should pass when required fields are present."""
    from omni.core.skills.runner import _validate_required_args_from_handler

    def _handler(**_kwargs):
        return "ok"

    _handler._skill_config = {  # type: ignore[attr-defined]
        "input_schema": {
            "type": "object",
            "required": ["repo_url"],
            "properties": {"repo_url": {"type": "string"}},
        }
    }

    _validate_required_args_from_handler(
        _handler,
        skill_name="researcher",
        command_name="git_repo_analyer",
        args={"repo_url": "https://example.com/repo.git"},
    )


def _fake_monitor_scope(
    state: dict[str, object] | None = None,
    *,
    track_exit: bool = False,
):
    """Build a monitor scope stub for run_skill tests."""

    @asynccontextmanager
    async def _scope(
        skill_command: str,
        *,
        verbose: bool = False,
        output_json: bool = False,
        auto_report: bool = True,
    ):
        if state is not None:
            state["skill_command"] = skill_command
            state["verbose"] = verbose
            state["output_json"] = output_json
            state["auto_report"] = auto_report
            state["entered"] = True
        try:
            yield
        finally:
            if state is not None and track_exit:
                state["exited"] = True

    return _scope


@contextmanager
def _patched_runner(
    *,
    verbose: bool,
    current_monitor: object | None = None,
    scope: object | None = None,
    fallback_return: object = _OK_RESULT,
    fallback_side_effect: Exception | None = None,
):
    """Patch monitor/runtime dependencies around run_skill."""
    run_patch_kwargs: dict[str, object] = {}
    if fallback_side_effect is not None:
        run_patch_kwargs["side_effect"] = fallback_side_effect
    else:
        run_patch_kwargs["return_value"] = fallback_return

    with (
        patch("omni.core.skills.runner.is_verbose", return_value=verbose),
        patch(
            "omni.foundation.runtime.skills_monitor.get_current_monitor",
            return_value=current_monitor,
        ),
        patch(
            "omni.foundation.runtime.skills_monitor.skills_monitor_scope",
            scope if scope is not None else _fake_monitor_scope(),
        ),
        patch(
            "omni.core.skills.runner._run_with_fallback",
            new_callable=AsyncMock,
            **run_patch_kwargs,
        ) as mock_run,
    ):
        yield mock_run


@pytest.mark.asyncio
async def test_run_skill_uses_monitor_scope_when_verbose_and_no_active_monitor():
    """Verbose mode should wrap run_skill execution with skills_monitor_scope."""
    from omni.core.skills.runner import run_skill

    monitor_state: dict[str, object] = {}

    with _patched_runner(
        verbose=True,
        current_monitor=None,
        scope=_fake_monitor_scope(monitor_state, track_exit=True),
    ) as mock_run:
        out = await run_skill(*_RUN_ARGS)

    assert out == _OK_RESULT
    assert monitor_state["skill_command"] == "demo.echo"
    assert monitor_state["verbose"] is True
    assert monitor_state["output_json"] is False
    assert monitor_state["auto_report"] is True
    assert monitor_state.get("entered") is True
    assert monitor_state.get("exited") is True
    mock_run.assert_awaited_once_with(*_RUN_ARGS)


@pytest.mark.asyncio
async def test_run_skill_skips_monitor_scope_when_not_verbose():
    """Non-verbose mode should execute directly without monitor scope."""
    from omni.core.skills.runner import run_skill

    with (
        patch("omni.core.skills.runner.is_verbose", return_value=False),
        patch(
            "omni.core.skills.runner._run_with_fallback",
            new_callable=AsyncMock,
            return_value=_OK_RESULT,
        ) as mock_run,
    ):
        out = await run_skill(*_RUN_ARGS)

    assert out == _OK_RESULT
    mock_run.assert_awaited_once_with(*_RUN_ARGS)


@pytest.mark.asyncio
async def test_run_skill_does_not_nest_monitor_scope():
    """If a monitor already exists, run_skill should not create another scope."""
    from omni.core.skills.runner import run_skill

    scope_mock = MagicMock()

    with _patched_runner(
        verbose=True,
        current_monitor=object(),
        scope=scope_mock,
    ) as mock_run:
        out = await run_skill(*_RUN_ARGS)

    assert out == _OK_RESULT
    scope_mock.assert_not_called()
    mock_run.assert_awaited_once_with(*_RUN_ARGS)


@pytest.mark.asyncio
async def test_run_skill_uses_env_verbose_flag_for_monitor_scope():
    """Env OMNI_CLI_VERBOSE should enable monitor even if logging verbose is false."""
    from omni.core.skills.runner import run_skill

    monitor_state: dict[str, object] = {}

    with (
        patch.dict(os.environ, {"OMNI_CLI_VERBOSE": "1"}, clear=False),
        _patched_runner(
            verbose=False,
            current_monitor=None,
            scope=_fake_monitor_scope(monitor_state),
        ) as mock_run,
    ):
        out = await run_skill(*_RUN_ARGS)

    assert out == _OK_RESULT
    assert monitor_state["skill_command"] == "demo.echo"
    assert monitor_state["verbose"] is True
    mock_run.assert_awaited_once_with(*_RUN_ARGS)


@pytest.mark.asyncio
async def test_run_skill_does_not_rerun_when_command_raises_inside_monitor():
    """Command exceptions in monitored runs should propagate without a second execution."""
    from omni.core.skills.runner import run_skill

    with (
        _patched_runner(
            verbose=True,
            current_monitor=None,
            scope=_fake_monitor_scope(),
            fallback_side_effect=RuntimeError("boom"),
        ) as mock_run,
        pytest.raises(RuntimeError, match="boom"),
    ):
        await run_skill(*_RUN_ARGS)

    assert mock_run.await_count == 1


@pytest.mark.asyncio
async def test_run_skill_with_monitor_returns_handle_when_auto_report_disabled():
    """Deferred mode should return monitor handle for caller-controlled reporting."""
    from omni.core.skills.runner import run_skill_with_monitor

    monitor_state: dict[str, object] = {}
    monitor_obj = object()

    @asynccontextmanager
    async def _scope(
        skill_command: str,
        *,
        verbose: bool = False,
        output_json: bool = False,
        auto_report: bool = True,
    ):
        monitor_state["skill_command"] = skill_command
        monitor_state["verbose"] = verbose
        monitor_state["output_json"] = output_json
        monitor_state["auto_report"] = auto_report
        yield monitor_obj

    with _patched_runner(
        verbose=True,
        current_monitor=None,
        scope=_scope,
    ) as mock_run:
        out, monitor = await run_skill_with_monitor(
            *_RUN_ARGS,
            output_json=True,
            auto_report=False,
        )

    assert out == _OK_RESULT
    assert monitor is monitor_obj
    assert monitor_state["skill_command"] == "demo.echo"
    assert monitor_state["verbose"] is True
    assert monitor_state["output_json"] is True
    assert monitor_state["auto_report"] is False
    mock_run.assert_awaited_once_with(*_RUN_ARGS)
