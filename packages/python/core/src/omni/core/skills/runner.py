"""
runner.py - Unified Skill Run Interface

Single entry point for executing a skill command. Implements on-demand loading
(fast path: load only the requested skill) with fallback to full kernel when needed.
CLI and other callers should use run_skill() only; no run logic in the CLI layer.
"""

from __future__ import annotations

import inspect
import os
import time
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger, is_verbose
from omni.foundation.skill_hooks import run_after_skill_execute, run_before_skill_execute

logger = get_logger(__name__)


class FastPathUnavailable(Exception):
    """Raised when fast path cannot be used; runner should fall back to kernel."""


def _validate_required_args_from_handler(
    handler: Any,
    *,
    skill_name: str,
    command_name: str,
    args: dict[str, Any],
) -> None:
    """Fast-fail required-arg validation using handler-attached schema metadata."""
    config = getattr(handler, "_skill_config", None)
    if not isinstance(config, dict):
        return

    input_schema = config.get("input_schema", {})
    if not isinstance(input_schema, dict):
        return

    required = input_schema.get("required", [])
    if not isinstance(required, list) or not required:
        return

    missing = [name for name in required if isinstance(name, str) and name not in args]
    if not missing:
        return

    provided = ", ".join(sorted(args.keys())) if args else "(none)"
    missing_text = ", ".join(missing)
    raise ValueError(
        f"Argument validation failed for '{skill_name}.{command_name}': "
        f"missing required field(s): {missing_text}. Provided: {provided}"
    )


def _read_memory_snapshot() -> tuple[float | None, float | None]:
    """Read current and peak RSS from skills monitor metrics when available."""
    try:
        from omni.foundation.runtime.skills_monitor.metrics import get_rss_mb, get_rss_peak_mb

        return float(get_rss_mb()), float(get_rss_peak_mb())
    except Exception:
        return None, None


def _memory_phase_fields(
    rss_before: float | None,
    rss_peak_before: float | None,
    rss_after: float | None,
    rss_peak_after: float | None,
) -> dict[str, float]:
    """Build monitor phase memory fields."""
    payload: dict[str, float] = {}
    if rss_before is not None and rss_after is not None:
        payload["rss_before_mb"] = round(rss_before, 2)
        payload["rss_after_mb"] = round(rss_after, 2)
        payload["rss_delta_mb"] = round(rss_after - rss_before, 2)
    if rss_peak_before is not None and rss_peak_after is not None:
        payload["rss_peak_before_mb"] = round(rss_peak_before, 2)
        payload["rss_peak_after_mb"] = round(rss_peak_after, 2)
        payload["rss_peak_delta_mb"] = round(rss_peak_after - rss_peak_before, 2)
    return payload


def _record_runner_phase(phase: str, duration_ms: float, **extra: Any) -> None:
    """Record a runner phase when monitor is active; never fail command execution."""
    try:
        from omni.foundation.runtime.skills_monitor import record_phase

        record_phase(phase, duration_ms, **extra)
    except Exception:
        pass


async def _run_fast_path(skill_name: str, command_name: str, cmd_args: dict[str, Any]) -> Any:
    """Load only the requested skill and execute. No kernel, no index scan.

    Raises FastPathUnavailable if skill dir missing, load fails, or command not found.
    """
    from omni.core.skills.discovery import DiscoveredSkill
    from omni.core.skills.universal import UniversalSkillFactory

    try:
        from omni.foundation.config.skills import SKILLS_DIR
        from omni.foundation.runtime.gitops import get_project_root

        skills_dir = SKILLS_DIR()
        project_root = get_project_root()
    except Exception as e:
        logger.debug("Fast path skipped: config unavailable", error=str(e))
        raise FastPathUnavailable("config") from e

    skill_path = Path(skills_dir) / skill_name
    if not skill_path.is_dir():
        raise FastPathUnavailable("skill not found")

    ds = DiscoveredSkill(
        name=skill_name,
        path=str(skill_path),
        metadata={"description": "", "version": "1.0.0", "routing_keywords": []},
        has_extensions=(skill_path / "extensions").is_dir(),
    )
    factory = UniversalSkillFactory(project_root)
    skill = factory.create_from_discovered(ds)
    load_started = time.perf_counter()
    load_rss_before, load_peak_before = _read_memory_snapshot()
    await skill.load(
        {
            "cwd": str(project_root),
            "target_command": command_name,
            "allow_module_reuse": True,
            "skip_workflow_clear": True,
        }
    )
    load_rss_after, load_peak_after = _read_memory_snapshot()
    _record_runner_phase(
        "runner.fast.load",
        (time.perf_counter() - load_started) * 1000,
        skill=skill_name,
        command=command_name,
        **_memory_phase_fields(load_rss_before, load_peak_before, load_rss_after, load_peak_after),
    )

    handler = skill.get_command(command_name) or (
        skill._tools_loader.get_command_simple(command_name) if skill._tools_loader else None
    )
    if handler is None:
        raise FastPathUnavailable("command not found")

    execute_started = time.perf_counter()
    exec_rss_before, exec_peak_before = _read_memory_snapshot()
    run_before_skill_execute()
    try:
        _validate_required_args_from_handler(
            handler,
            skill_name=skill_name,
            command_name=command_name,
            args=cmd_args,
        )
        if inspect.iscoroutinefunction(handler):
            return await handler(**cmd_args)
        return handler(**cmd_args)
    finally:
        run_after_skill_execute()
        exec_rss_after, exec_peak_after = _read_memory_snapshot()
        _record_runner_phase(
            "runner.fast.execute",
            (time.perf_counter() - execute_started) * 1000,
            skill=skill_name,
            command=command_name,
            **_memory_phase_fields(
                exec_rss_before, exec_peak_before, exec_rss_after, exec_peak_after
            ),
        )


async def _run_via_kernel(skill_name: str, command_name: str, cmd_args: dict[str, Any]) -> Any:
    """Execute via full kernel (all skills loaded, cortex disabled for CLI)."""
    from omni.core import get_kernel

    kernel = get_kernel(enable_cortex=False, reset=True)
    if not kernel.is_ready:
        init_started = time.perf_counter()
        init_rss_before, init_peak_before = _read_memory_snapshot()
        await kernel.initialize()
        init_rss_after, init_peak_after = _read_memory_snapshot()
        _record_runner_phase(
            "runner.kernel.init",
            (time.perf_counter() - init_started) * 1000,
            skill=skill_name,
            command=command_name,
            **_memory_phase_fields(
                init_rss_before, init_peak_before, init_rss_after, init_peak_after
            ),
        )

    ctx = kernel.skill_context
    skill = ctx.get_skill(skill_name)
    if skill is None:
        raise ValueError(f"Skill not found: {skill_name}. Available: {ctx.list_skills()}")

    full_cmd = f"{skill_name}.{command_name}"
    if not ctx.get_command(full_cmd):
        alt = f"{skill_name}.{skill_name}_{command_name}"
        if ctx.get_command(alt):
            full_cmd = alt
        else:
            raise ValueError(
                f"Command not found: {skill_name}.{command_name}. "
                f"Available in {skill_name}: {skill.list_commands()}"
            )

    execute_started = time.perf_counter()
    exec_rss_before, exec_peak_before = _read_memory_snapshot()
    run_before_skill_execute()
    try:
        return await skill.execute(command_name, **cmd_args)
    finally:
        run_after_skill_execute()
        exec_rss_after, exec_peak_after = _read_memory_snapshot()
        _record_runner_phase(
            "runner.kernel.execute",
            (time.perf_counter() - execute_started) * 1000,
            skill=skill_name,
            command=command_name,
            **_memory_phase_fields(
                exec_rss_before, exec_peak_before, exec_rss_after, exec_peak_after
            ),
        )


async def _run_with_fallback(skill_name: str, command_name: str, cmd_args: dict[str, Any]) -> Any:
    """Try fast path first, then kernel fallback; keep duration logging consistent."""
    tool_id = f"{skill_name}.{command_name}"
    start = time.perf_counter()
    try:
        out = await _run_fast_path(skill_name, command_name, cmd_args)
        path = "fast"
    except FastPathUnavailable:
        out = await _run_via_kernel(skill_name, command_name, cmd_args)
        path = "kernel"

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "skill_tool_duration",
        tool=tool_id,
        duration_ms=round(elapsed_ms, 2),
        path=path,
    )
    return out


def _monitor_enabled() -> bool:
    """Return True when CLI/Runtime requests verbose skill monitoring."""
    if is_verbose():
        return True
    flag = os.environ.get("OMNI_CLI_VERBOSE", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


async def run_skill(
    skill_name: str,
    command_name: str,
    args: dict[str, Any] | None = None,
) -> Any:
    """Unified skill run: try fast path (on-demand load), then kernel fallback.

    Call this from CLI, MCP, or any single-command execution. No need to
    implement fast path or fallback logic at the caller.

    Args:
        skill_name: Skill name (e.g. "knowledge").
        command_name: Command name (e.g. "recall").
        args: Optional keyword arguments for the command.

    Returns:
        Command result (string or dict, skill-defined).

    Raises:
        ValueError: Skill or command not found (after fallback).
        Other: Any exception raised by the skill command.
    """
    cmd_args = args or {}
    result, _monitor = await run_skill_with_monitor(
        skill_name,
        command_name,
        cmd_args,
        output_json=False,
        auto_report=True,
    )
    return result


async def run_skill_with_monitor(
    skill_name: str,
    command_name: str,
    args: dict[str, Any] | None = None,
    *,
    output_json: bool = False,
    auto_report: bool = True,
) -> tuple[Any, Any | None]:
    """Unified skill run + optional monitor control for callers that need output ordering.

    This keeps monitoring logic in common runner code:
    - default (auto_report=True): same behavior as run_skill(), scope prints dashboard on exit.
    - deferred mode (auto_report=False): scope collects metrics but caller chooses when to report.
      Returns (result, monitor_handle) where monitor_handle can be used to call report().
    """
    cmd_args = args or {}
    tool_id = f"{skill_name}.{command_name}"

    if _monitor_enabled():
        try:
            from omni.foundation.runtime.skills_monitor import (
                get_current_monitor,
                skills_monitor_scope,
            )
        except Exception as e:
            logger.debug("skills_monitor_unavailable", tool=tool_id, error=str(e))
        else:
            if get_current_monitor() is None:
                async with skills_monitor_scope(
                    tool_id,
                    verbose=True,
                    output_json=output_json,
                    auto_report=auto_report,
                ) as monitor:
                    result = await _run_with_fallback(skill_name, command_name, cmd_args)
                return result, (None if auto_report else monitor)

    return await _run_with_fallback(skill_name, command_name, cmd_args), None


__all__ = ["FastPathUnavailable", "run_skill", "run_skill_with_monitor"]
