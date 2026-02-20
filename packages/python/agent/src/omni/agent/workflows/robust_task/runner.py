"""
Robust Task workflow runner: execute LangGraph workflow with HITL and session report.

Single responsibility: run the robust task graph (streaming, interrupt handling, metrics).
CLI and gateway call this module; no orchestration logic in CLI.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.box import ROUNDED

if TYPE_CHECKING:
    pass


# Thread config for LangGraph checkpointer (stable for single-session runs)
DEFAULT_THREAD_ID = "1"


async def run_robust_task(
    request: str,
    *,
    console: Console | None = None,
    thread_id: str = DEFAULT_THREAD_ID,
) -> dict[str, Any]:
    """Execute the robust task graph: streaming, HITL review, session report.

    Args:
        request: User task description.
        console: Rich console for output; if None, a new Console() is used.
        thread_id: LangGraph thread_id for checkpointer state.

    Returns:
        Session metrics: duration_sec, llm_hits, tool_calls, tool_counts, est_tokens, est_cost.
    """
    from langgraph.checkpoint.memory import MemorySaver

    from .graph import build_graph

    out = console if console is not None else Console()
    checkpointer = MemorySaver()
    app = build_graph(checkpointer=checkpointer)
    thread = {"configurable": {"thread_id": thread_id}}

    initial_state: dict[str, Any] = {
        "user_request": request,
        "execution_history": [],
        "retry_count": 0,
        "trace": [],
        "approval_status": "pending",
    }

    out.print(
        Panel(
            f"[bold cyan]Task:[/bold cyan] {request}",
            title="🕸️ Robust Task Workflow (HITL Enabled)",
            border_style="cyan",
        )
    )

    seen_trace_ids: set[str] = set()
    session_start = time.monotonic()
    tool_calls: list[str] = []
    llm_hits = 0

    current_input: dict[str, Any] | None = initial_state

    while True:
        try:
            async for event in app.astream(current_input, thread):
                for node_name, state_update in event.items():
                    style = "white"
                    icon = "⏺️"
                    title = node_name.capitalize()

                    if not isinstance(state_update, dict):
                        continue

                    thought = state_update.get("last_thought", "")
                    trace = state_update.get("trace", [])

                    for i, t in enumerate(trace):
                        t_id = f"{node_name}_{i}_{t.get('type')}"
                        if t_id not in seen_trace_ids:
                            seen_trace_ids.add(t_id)
                            t_type = t.get("type")
                            t_data = t.get("data", {})
                            if t_type == "tool_call_start":
                                tool_calls.append(t_data.get("tool", ""))
                                out.print(
                                    f"  [dim]🔧 [bold]Call:[/bold] {t_data.get('tool')}({json.dumps(t_data.get('args'))})[/dim]"
                                )
                            elif t_type == "tool_call_end":
                                status = (
                                    "[green]Success[/green]"
                                    if t_data.get("status") == "success" or t_data.get("success")
                                    else "[red]Failed[/red]"
                                )
                                out.print(f"  [dim]🔙 [bold]Result:[/bold] {status}[/dim]")
                            elif t_type == "llm_hit":
                                llm_hits += 1
                                out.print(
                                    f"  [dim]🧠 [bold]LLM:[/bold] {t_data.get('task')} -> {t_data.get('intent') or t_data.get('goal') or '...'}[/dim]"
                                )
                            elif t_type == "memory_op":
                                action = t_data.get("action")
                                details = (
                                    f"Query: {t_data.get('query')}"
                                    if "query" in t_data
                                    else f"Result: {t_data.get('count') or t_data.get('result') or 'done'}"
                                )
                                out.print(
                                    f"  [dim]🧠 [bold]Memory:[/bold] {action} | {details}[/dim]"
                                )

                    content, style, icon = _node_display(node_name, state_update)
                    panel_body = ""
                    if thought:
                        panel_body += f"[dim]💭 {thought}[/dim]\n"
                        if content:
                            panel_body += "─" * 40 + "\n"
                    panel_body += content
                    out.print(
                        Panel(
                            panel_body,
                            title=f"{icon} {title}",
                            border_style=style,
                        )
                    )

            snapshot = await app.aget_state(thread)

            if not snapshot.next:
                final_summary = snapshot.values.get("final_summary")
                if final_summary:
                    out.print("\n" + "─" * 60)
                    out.print(
                        Panel(
                            Markdown(final_summary),
                            title="✨ Task Execution Summary",
                            border_style="green",
                        )
                    )
                break

            if snapshot.next and "review" in snapshot.next:
                execution_history = snapshot.values.get("execution_history", [])
                goal = snapshot.values.get("clarified_goal", "Unknown")

                out.print("\n" + "━" * 60)
                out.print(
                    Panel(
                        f"[bold cyan]Goal:[/bold cyan] {goal}",
                        border_style="yellow",
                    )
                )

                hist_table = Table(
                    title="📊 Execution Results",
                    box=ROUNDED,
                    border_style="green",
                )
                hist_table.add_column("Step")
                display_history = (
                    execution_history[-5:] if len(execution_history) > 5 else execution_history
                )
                for h in display_history:
                    hist_table.add_row(h[:200] + "..." if len(h) > 200 else h)

                out.print(hist_table)
                out.print("\n[bold yellow]✋ Outcome Review:[/bold yellow]")
                out.print("• [bold green]y[/bold green]: Approve results and finalize")
                out.print("• [bold red]n[/bold red]: Reject and exit")
                out.print("• Or type [italic]feedback[/italic] to adjust/retry")

                user_input = out.input("\n[bold yellow]>> [/bold yellow]").strip()

                if user_input.lower() == "y":
                    app.update_state(thread, {"approval_status": "approved"})
                elif user_input.lower() == "n":
                    app.update_state(thread, {"approval_status": "rejected"})
                    break
                else:
                    app.update_state(
                        thread,
                        {
                            "approval_status": "modified",
                            "user_feedback": user_input,
                        },
                    )

                current_input = None
                continue

            break

        except Exception as e:
            import traceback

            out.print(f"[bold red]❌ Graph Error: {e}[/bold red]")
            out.print(f"[dim]Traceback: {traceback.format_exc()}[/dim]")
            break

    duration = time.monotonic() - session_start
    est_input_tokens = llm_hits * 500
    est_output_tokens = llm_hits * 300
    total_tokens = est_input_tokens + est_output_tokens
    est_cost = (est_input_tokens * 3 + est_output_tokens * 15) / 1_000_000

    tool_counts = dict(Counter(tool_calls)) if tool_calls else {}

    grid = Table.grid(expand=True)
    grid.add_column(justify="left", style="cyan")
    grid.add_column(justify="right", style="white")
    grid.add_row("[bold]Session Duration:[/bold]", f"{duration:.2f}s")
    grid.add_row("[bold]LLM Requests:[/bold]", f"{llm_hits}")
    grid.add_row(
        "[bold]Est. Tokens:[/bold]",
        f"~{total_tokens} (In: {est_input_tokens}, Out: {est_output_tokens})",
    )
    grid.add_row("[bold]Est. Cost:[/bold]", f"~${est_cost:.4f}")
    grid.add_row("[bold]Tool Calls:[/bold]", f"{len(tool_calls)}")
    if tool_calls:
        grid.add_row("", "")
        grid.add_row("[bold yellow]Tool Usage Breakdown:[/bold yellow]", "")
        for tool, count in Counter(tool_calls).most_common():
            grid.add_row(f"  • {tool}", f"[green]{count}[/green]")

    out.print("\n")
    out.print(
        Panel(
            grid,
            title="📊 Session Intelligence Report",
            border_style="bright_blue",
            expand=False,
        )
    )

    return {
        "duration_sec": duration,
        "llm_hits": llm_hits,
        "tool_calls": len(tool_calls),
        "tool_counts": tool_counts,
        "est_tokens": total_tokens,
        "est_cost": est_cost,
        "thread_id": thread_id,
    }


def _node_display(node_name: str, state_update: dict[str, Any]) -> tuple[str, str, str]:
    """Map node name and state to (content, style, icon) for the streaming panel."""
    style = "white"
    icon = "⏺️"

    if node_name == "review":
        return ("Waiting for user approval...", "bold yellow", "✋")

    if node_name == "discovery":
        style, icon = "magenta", "🔍"
        if "discovered_tools" in state_update:
            tools = state_update["discovered_tools"]
            count = len(tools)
            top_tools = tools[:5]
            tool_list = "\n".join(
                [
                    f"  • [bold]{t.get('tool')}[/bold] [dim]({t.get('score', 0):.3f})[/dim]: {t.get('description', '')[:60]}..."
                    for t in top_tools
                ]
            )
            content = f"Found {count} relevant tools.\n\n[dim]Top Matches:[/dim]\n{tool_list}"
            if count > 5:
                content += f"\n  [dim]... and {count - 5} more[/dim]"
            return (content, style, icon)
        return ("Discovering capabilities...", style, icon)

    if node_name == "clarify":
        style, icon = "yellow", "🤔"
        if "clarified_goal" in state_update:
            return (f"[bold]Goal:[/bold] {state_update['clarified_goal']}", style, icon)
        if state_update.get("status") == "clarifying":
            return ("[italic]Requesting clarification...[/italic]", style, icon)
        return ("Analyzing request...", style, icon)

    if node_name == "plan":
        style, icon = "blue", "📝"
        if "plan" in state_update:
            steps = state_update["plan"]["steps"]
            step_list = "\n".join([f"  {s['id']}. {s['description']}" for s in steps])
            return (f"Plan ({len(steps)} steps):\n{step_list}", style, icon)
        return ("Formulating plan...", style, icon)

    if node_name == "execute":
        style, icon = "green", "⚙️"
        if state_update.get("execution_history"):
            last_exec = state_update["execution_history"][-1]
            content = last_exec[:200] + "..." if len(last_exec) > 200 else last_exec
            return (content, style, icon)
        return ("Executing step...", style, icon)

    if node_name == "validate":
        style, icon = "red", "✅"
        if "validation_result" in state_update:
            res = state_update["validation_result"]
            if res.get("is_valid"):
                return ("Success! Goal achieved.", "bold green", "🎉")
            return (f"Validation Failed: {res.get('feedback')}", "bold red", "❌")
        return ("Validating results...", style, icon)

    if node_name == "reflect":
        style, icon = "magenta", "🧠"
        if state_update.get("execution_history"):
            last_exec = state_update["execution_history"][-1]
            if "REFLECTION:" in last_exec:
                return (last_exec, style, icon)
        return ("Reflecting on failure...", style, icon)

    if node_name == "summary":
        style, icon = "bold magenta", "📄"
        if "final_summary" in state_update:
            return (state_update["final_summary"], style, icon)
        return ("Generating session summary...", style, icon)

    return (str(state_update), style, icon)
