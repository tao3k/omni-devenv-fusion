"""
Run entry points - ReAct, Omega, and Graph workflow execution.

CLI run command should only parse args and call these; no orchestration logic in CLI.
"""

from __future__ import annotations

import time
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.box import ROUNDED

from omni.foundation.utils.common import setup_import_paths

setup_import_paths()

console = Console()


def print_banner() -> None:
    """Print CCA runtime banner."""
    from rich.text import Text

    banner = Text()
    banner.append(" CCA Runtime ", style="bold green")
    banner.append("• ", style="dim")
    banner.append("Omni Loop (v2.0)", style="italic")
    console.print(Panel(banner, expand=False, border_style="green"))


def print_session_report(
    task: str, result: dict, step_count: int, tool_counts: dict, tokens: int
) -> None:
    """Print enriched session report with stats."""
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_row(f"[bold cyan]Task:[/bold cyan] {task}")
    grid.add_row(f"[bold dim]Session ID:[/bold dim] {result.get('session_id', 'N/A')}")
    grid.add_row("")
    metrics = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
    metrics.add_column("Metric")
    metrics.add_column("Value", style="yellow")
    metrics.add_row("Steps", str(step_count))
    metrics.add_row("Tools", str(sum(tool_counts.values())))
    metrics.add_row("Est. Tokens", f"~{tokens}")
    grid.add_row(metrics)
    grid.add_row("")
    if tool_counts:
        t_table = Table(title="Tool Usage", show_header=False, box=ROUNDED)
        t_table.add_column("Tool")
        t_table.add_column("Count", justify="right")
        for tool, count in tool_counts.items():
            t_table.add_row(tool, f"[bold green]{count}[/bold green]")
        grid.add_row(t_table)
        grid.add_row("")
    grid.add_row("[bold green]Reflection & Outcome:[/bold green]")
    output = result.get("output", "Task completed")
    if output:
        output_str = str(output)
        if isinstance(output, dict):
            import json

            output_str = f"```json\n{json.dumps(output, indent=2)}\n```"
        import re

        output_str = re.sub(r"<thinking>.*?</thinking>", "", output_str, flags=re.DOTALL)
        output_str = output_str.strip()
        note_panel = Panel(Markdown(output_str), border_style="dim", expand=True)
        grid.add_row(note_panel)
    else:
        grid.add_row("Task completed")
    console.print(Panel(grid, title="✨ CCA Session Report ✨", border_style="green", expand=False))


# Session limits for execute_task_with_session
SESSION_MAX_TURNS = 50
CONSOLIDATE_AFTER_TURNS = 20


async def _run_one_turn(
    kernel: Any,
    task: str,
    max_steps: int = 20,
    verbose: bool = False,
    mcp_port: int = 0,
) -> dict[str, Any]:
    """Run one turn (router + OmniLoop) with an already-started kernel. No kernel lifecycle."""
    from omni.agent.core.omni import OmniLoop, OmniLoopConfig
    from omni.agent.cli.mcp_embed import make_mcp_embed_func
    from omni.core.router.main import RouterRegistry

    router = RouterRegistry.get("run_command")
    if mcp_port > 0:
        embed_func = make_mcp_embed_func(mcp_port)
        if hasattr(router, "_search") and router._search:
            router._search._embed_func = embed_func

    skills_data = []
    for skill in kernel.skill_context._skills.values():
        cmd_names = skill.list_commands() if hasattr(skill, "list_commands") else []
        commands = []
        for cmd_name in cmd_names:
            handler = skill.get_command(cmd_name)
            cmd_keywords = []
            cmd_desc = ""
            if handler and hasattr(handler, "_skill_config"):
                cfg = handler._skill_config or {}
                cmd_keywords = (
                    cfg.get("keywords", [])
                    if isinstance(cfg, dict)
                    else getattr(cfg, "keywords", [])
                )
                cmd_desc = (
                    cfg.get("description", "")
                    if isinstance(cfg, dict)
                    else getattr(cfg, "description", "")
                )
            commands.append({"name": cmd_name, "description": cmd_desc, "keywords": cmd_keywords})
        skills_data.append(
            {
                "name": skill.name,
                "description": getattr(skill.metadata, "description", ""),
                "commands": commands,
            }
        )
    await router.initialize(skills_data)
    route_result = await router.route(task)
    if route_result and getattr(route_result, "command_name", None):
        full_command = f"{route_result.skill_name}.{route_result.command_name}"
        output = await kernel.execute_tool(full_command, {})
        return {
            "session_id": "direct_exec",
            "output": output,
            "step_count": 1,
            "tool_calls": 1,
            "status": "completed",
        }
    loop_config = OmniLoopConfig(
        max_tokens=128000,
        max_tool_calls=max_steps,
        verbose=verbose,
    )
    loop = OmniLoop(config=loop_config, kernel=kernel)
    llm_response = await loop.run(task)
    return {
        "session_id": loop.session_id,
        "output": llm_response,
        "step_count": loop.step_count,
        "tool_calls": loop.tool_calls_count,
        "status": "completed",
    }


async def execute_task_via_kernel(
    task: str, max_steps: int | None = None, verbose: bool = False
) -> dict[str, Any]:
    """Execute task using ReAct loop (router + OmniLoop fallback). Starts and shuts down kernel."""
    from omni.agent.cli.mcp_embed import detect_mcp_port
    from omni.core.kernel.engine import get_kernel

    try:
        mcp_port = await detect_mcp_port()
        console.print(f"[dim]Detected MCP port: {mcp_port}[/dim]")
    except Exception as e:
        console.print(f"[dim]MCP detection failed: {e}, using default[/dim]")
        mcp_port = 0

    if mcp_port > 0:
        console.print(f"[dim]Using MCP embedding (port {mcp_port}) for fast warm path.[/dim]")

    kernel = get_kernel()
    await kernel.initialize()
    await kernel.start()
    try:
        return await _run_one_turn(
            kernel, task, max_steps=(max_steps or 20), verbose=verbose, mcp_port=mcp_port
        )
    finally:
        await kernel.shutdown()


# Module-level cache of session_id -> PySessionWindow (Rust omni-window only)
_session_window_cache: dict[str, Any] = {}


def _get_or_create_session_window(session_id: str, max_turns: int | None = None) -> Any:
    """Get or create Rust session window for session_id. Requires omni_core_rs."""
    from omni_core_rs import PySessionWindow

    if max_turns is None:
        try:
            from omni.foundation.config.settings import get_setting

            max_turns = int(get_setting("session.window_max_turns", 2048))
        except Exception:
            max_turns = 2048
    if session_id not in _session_window_cache:
        _session_window_cache[session_id] = PySessionWindow(session_id, max_turns)
    return _session_window_cache[session_id]


def _seed_window_from_history(window: Any, history: list[dict[str, Any]], max_turns: int) -> None:
    """Replay last max_turns turns from history into the window (e.g. after load)."""
    if not history:
        return
    turns = history[-(2 * max_turns) :]
    for t in turns:
        role = t.get("role", "user")
        content = (t.get("content") or "")[:2000]
        window.append_turn(role, content, t.get("tool_count", 0))


def _build_context_for_session(
    history: list[dict[str, Any]],
    user_message: str,
    max_context_turns: int,
    use_memory: bool,
    window: Any | None = None,
) -> str:
    """Build task string with optional two_phase_recall and conversation history."""
    parts = []

    if use_memory:
        try:
            from omni.agent.services.memory import get_memory_service

            service = get_memory_service()
            recalled = service.two_phase_recall(user_message, k2=5)
            if recalled:
                lines = [
                    f"- {ep.intent[:80]}... → {ep.outcome} (Q={ep.q_value:.2f})"
                    for ep, _ in recalled[:5]
                ]
                parts.append("Relevant past episodes:\n" + "\n".join(lines) + "\n")
        except Exception:
            pass

    # Prefer window.get_recent_turns when available; else use history
    if window:
        turns = window.get_recent_turns(max_context_turns)
    else:
        turns = []
    if not turns and history:
        turns = history[-(2 * max_context_turns) :]
    if turns:
        conv = []
        for t in turns:
            role = t.get("role", "user") if isinstance(t, dict) else getattr(t, "role", "user")
            content = (t.get("content", "") if isinstance(t, dict) else getattr(t, "content", ""))[
                :500
            ]
            conv.append(f"{str(role).capitalize()}: {content}")
        parts.append("Conversation so far:\n" + "\n".join(conv) + "\n")

    parts.append("User: " + user_message)
    return "\n".join(parts)


async def execute_task_with_session(
    session_id: str,
    user_message: str,
    kernel: Any | None = None,
    max_steps: int = 20,
    verbose: bool = False,
    max_context_turns: int = 10,
    use_memory: bool = True,
) -> dict[str, Any]:
    """Execute one turn in a session: load history, build context, run loop, save session.

    If kernel is None, a kernel is started and shut down for this call.
    If kernel is provided (e.g. from gateway), it is reused and not shut down.
    """
    from omni.agent.session import load_session, save_session
    from omni.agent.session.store import SessionStore

    store = SessionStore()
    history = load_session(session_id, store=store)
    window = _get_or_create_session_window(session_id)
    if window.get_stats()["total_turns"] == 0 and history:
        _seed_window_from_history(window, history, max_context_turns)
    task = _build_context_for_session(
        history, user_message, max_context_turns, use_memory, window=window
    )

    own_kernel = kernel is None
    mcp_port = 0
    if own_kernel:
        from omni.agent.cli.mcp_embed import detect_mcp_port
        from omni.core.kernel.engine import get_kernel

        try:
            mcp_port = await detect_mcp_port()
        except Exception:
            pass
        kernel = get_kernel()
        await kernel.initialize()
        await kernel.start()

    try:
        result = await _run_one_turn(kernel, task, max_steps, verbose, mcp_port=mcp_port)
    finally:
        if own_kernel:
            await kernel.shutdown()

    output_str = str(result.get("output", ""))
    tool_calls = result.get("tool_calls", 0)
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": output_str})
    window.append_turn("user", user_message, 0)
    window.append_turn("assistant", output_str, tool_calls)

    # Optional consolidation into omni-memory when over threshold
    num_turns = len(history) // 2
    if use_memory and num_turns >= CONSOLIDATE_AFTER_TURNS:
        try:
            from omni.agent.services.memory import get_memory_service

            service = get_memory_service()
            summary = "\n".join(
                f"{h['role']}: {(h.get('content') or '')[:200]}"
                for h in history[-2 * CONSOLIDATE_AFTER_TURNS :]
            )
            ep_id = service.store_episode(
                intent=user_message[:200],
                experience=summary[:2000],
                outcome="success",
            )
            service.mark_success(ep_id)
        except Exception:
            pass
        history = store.trim(history, SESSION_MAX_TURNS)

    save_session(session_id, history, store=store)
    return result


async def run_omega_mission(goal: str, socket_path: str):  # noqa: ANN201
    """Run Project Omega mission with TUI bridge. Returns mission result."""
    from omni.agent.core.omni import OmegaRunner, MissionConfig
    from omni.agent.cli.tui_bridge import TUIManager, TUIConfig

    config = TUIConfig(socket_path=socket_path, enabled=True)
    manager = TUIManager(config)
    async with manager.lifecycle() as bridge:
        mission_config = MissionConfig(
            goal=goal,
            enable_isolation=True,
            enable_conflict_detection=True,
            enable_memory_recall=True,
            enable_skill_crystallization=True,
            auto_merge=True,
            auto_recovery=True,
        )
        runner = OmegaRunner(config=mission_config, tui_bridge=bridge)
        return await runner.run_mission(goal)


def print_omega_result(result: Any, json_output: bool) -> None:
    """Print Omega mission result (table or JSON)."""
    if json_output:
        import json

        print(
            json.dumps(
                {
                    "success": result.success,
                    "duration_ms": result.duration_ms,
                    "tasks_completed": result.tasks_completed,
                    "tasks_failed": result.tasks_failed,
                    "conflicts_detected": result.conflicts_detected,
                },
                indent=2,
            )
        )
    else:
        table = Table(title="Ω Omega Mission Result", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")
        table.add_row("Success", "✅ Yes" if result.success else "❌ No")
        table.add_row("Duration", f"{result.duration_ms:.0f}ms")
        table.add_row("Tasks", f"{result.tasks_completed}/{result.tasks_total}")
        table.add_row("Conflicts", str(result.conflicts_detected))
        console.print(table)


__all__ = [
    "console",
    "print_banner",
    "print_session_report",
    "execute_task_via_kernel",
    "execute_task_with_session",
    "run_omega_mission",
    "print_omega_result",
]
