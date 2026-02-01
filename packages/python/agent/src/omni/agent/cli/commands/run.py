"""run.py - Omni Loop Command (CCA Runtime)

Execute task via Omni Loop using the new Trinity Architecture.
Supports the hyper-robust Agentic OS Smart Loop and Project Omega.

Commands:
- run: Standard ReAct loop execution
- run --omega: Full Omega execution with Cortex + Homeostasis + TUI
- run --graph: LangGraph robust workflow
"""

from __future__ import annotations

import asyncio
import time
from typing import Annotated

import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from omni.foundation.utils.common import setup_import_paths

# Setup paths before importing omni modules
setup_import_paths()

console = Console()


def _print_banner():
    """Print CCA runtime banner."""
    from rich.text import Text

    banner = Text()
    banner.append(" CCA Runtime ", style="bold green")
    banner.append("• ", style="dim")
    banner.append("Omni Loop (v2.0)", style="italic")
    console.print(Panel(banner, expand=False, border_style="green"))


def _print_session_report(task: str, result: dict, step_count: int, tool_counts: dict, tokens: int):
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
        from rich.markdown import Markdown

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


async def _execute_task_via_kernel(task: str, max_steps: int | None, verbose: bool = False) -> dict:
    """Execute task using the standard ReAct Loop."""
    from omni.agent.core.omni import OmniLoop, OmniLoopConfig
    from omni.core.kernel.engine import get_kernel

    kernel = get_kernel()
    await kernel.initialize()
    await kernel.start()

    try:
        # First try direct routing
        from omni.core.router.main import RouterRegistry

        router = RouterRegistry.get("run_command")
        route_result = await router.route(task)

        if route_result and getattr(route_result, "command_name", None):
            # Direct execution for simple tasks
            full_command = f"{route_result.skill_name}.{route_result.command_name}"
            output = await kernel.execute_tool(full_command, {{}})
            return {
                "session_id": "direct_exec",
                "output": output,
                "step_count": 1,
                "tool_calls": 1,
                "status": "completed",
            }

        # Fallback to standard OmniLoop (ReAct)
        max_calls = max_steps if max_steps else 20
        loop_config = OmniLoopConfig(
            max_tokens=128000,
            max_tool_calls=max_calls,
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
    finally:
        await kernel.shutdown()


def register_run_command(parent_app: typer.Typer):
    """Register the run command with the parent app."""

    @parent_app.command()
    def run(
        task: Annotated[str | None, typer.Argument(help="Task description or query")] = None,
        steps: Annotated[
            int | None,
            typer.Option("-s", "--steps", help="Max steps (default: 20)"),
        ] = None,
        json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
        repl: Annotated[bool, typer.Option("--repl", help="Enter interactive REPL mode")] = False,
        graph: Annotated[
            bool, typer.Option("--graph", help="Use LangGraph Robust Workflow")
        ] = False,
        omega: Annotated[
            bool,
            typer.Option(
                "--omega", "-O", help="Use Project Omega: Full Cortex + Homeostasis + TUI"
            ),
        ] = False,
        tui_socket: Annotated[
            str,
            typer.Option("--socket", help="TUI Unix socket path (default: /tmp/omni-omega.sock)"),
        ] = "/tmp/omni-omega.sock",
        verbose: Annotated[
            bool,
            typer.Option("--verbose/--quiet", "-v/-q", help="Show/hide tool execution details"),
        ] = True,
    ):
        """Execute a task through the Omni Loop (ReAct Mode).

        Use --omega for full autonomous execution with:
        - Cortex parallel task orchestration
        - Homeostasis branch isolation
        - Real-time TUI dashboard
        """
        if not task:
            console.print("[bold red]Error:[/bold red] Task description is required")
            raise typer.Exit(1)

        _print_banner()
        console.print(f"\n[bold]🚀 Starting:[/bold] {task}")

        # Omega Mode: Full autonomous execution
        if omega:
            from omni.agent.core.omni import OmegaRunner, MissionConfig
            from omni.agent.cli.console import init_tui, shutdown_tui, get_tui_bridge

            async def run_omega(goal: str, socket_path: str):
                # Initialize TUI bridge
                init_tui(socket_path)
                bridge = get_tui_bridge()

                # Create mission config
                config = MissionConfig(
                    goal=goal,
                    enable_isolation=True,
                    enable_conflict_detection=True,
                    enable_memory_recall=True,
                    enable_skill_crystallization=True,
                    auto_merge=True,
                    auto_recovery=True,
                )

                # Create and run Omega (pass TUI bridge for event forwarding)
                runner = OmegaRunner(config=config, tui_bridge=bridge)
                start_time = time.time()

                try:
                    result = await runner.run_mission(goal)
                    return result
                finally:
                    shutdown_tui()

            result = asyncio.run(run_omega(task, tui_socket))

            # Output result
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
                from rich.table import Table

                table = Table(title="Ω Omega Mission Result", show_header=True)
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="yellow")
                table.add_row("Success", "✅ Yes" if result.success else "❌ No")
                table.add_row("Duration", f"{result.duration_ms:.0f}ms")
                table.add_row("Tasks", f"{result.tasks_completed}/{result.tasks_total}")
                table.add_row("Conflicts", str(result.conflicts_detected))
                console.print(table)

            return

        if graph:
            # Execute Graph Workflow
            from omni.agent.workflows.robust_task.graph import build_graph
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text
            from rich.live import Live
            from rich.progress import SpinnerColumn, Progress, BarColumn, TextColumn

            async def run_graph(request):
                import json  # Ensure json is available

                # Use standard checkpointer for interrupt support
                from langgraph.checkpoint.memory import MemorySaver

                checkpointer = MemorySaver()

                app = build_graph(checkpointer=checkpointer)  # This is the compiled graph

                # We need a thread_id for state tracking
                thread = {"configurable": {"thread_id": "1"}}

                initial_state = {
                    "user_request": request,
                    "execution_history": [],
                    "retry_count": 0,
                    "trace": [],
                    "approval_status": "pending",
                }

                console.print(
                    Panel(
                        f"[bold cyan]Task:[/bold cyan] {request}",
                        title="🕸️ Robust Task Workflow (HITL Enabled)",
                        border_style="cyan",
                    )
                )

                seen_trace_ids = set()
                session_start = asyncio.get_event_loop().time()
                tool_calls = []
                llm_hits = 0

                # Run loop to handle interrupts
                current_input = initial_state
                resume = False

                while True:
                    try:
                        # STREAMING LOOP
                        # Always provide thread config when using checkpointer
                        async for event in app.astream(current_input, thread):
                            for node_name, state_update in event.items():
                                # Choose color and icon based on node
                                style = "white"
                                icon = "⏺️"
                                title = node_name.capitalize()

                                # Type safety check: ensure state_update is a dict
                                if not isinstance(state_update, dict):
                                    continue

                                thought = state_update.get("last_thought", "")

                                # Extract Trace Events
                                trace = state_update.get("trace", [])
                                for i, t in enumerate(trace):
                                    t_id = f"{node_name}_{i}_{t.get('type')}"
                                    if t_id not in seen_trace_ids:
                                        seen_trace_ids.add(t_id)
                                        t_type = t.get("type")
                                        t_data = t.get("data", {})
                                        if t_type == "tool_call_start":
                                            tool_calls.append(t_data.get("tool"))
                                            console.print(
                                                f"  [dim]🔧 [bold]Call:[/bold] {t_data.get('tool')}({json.dumps(t_data.get('args'))})[/dim]"
                                            )
                                        elif t_type == "tool_call_end":
                                            status = (
                                                "[green]Success[/green]"
                                                if t_data.get("status") == "success"
                                                or t_data.get("success")
                                                else "[red]Failed[/red]"
                                            )
                                            console.print(
                                                f"  [dim]🔙 [bold]Result:[/bold] {status}[/dim]"
                                            )
                                        elif t_type == "llm_hit":
                                            llm_hits += 1
                                            console.print(
                                                f"  [dim]🧠 [bold]LLM:[/bold] {t_data.get('task')} -> {t_data.get('intent') or t_data.get('goal') or '...'}[/dim]"
                                            )
                                        elif t_type == "memory_op":
                                            action = t_data.get("action")
                                            details = (
                                                f"Query: {t_data.get('query')}"
                                                if "query" in t_data
                                                else f"Result: {t_data.get('count') or t_data.get('result') or 'done'}"
                                            )
                                            console.print(
                                                f"  [dim]🧠 [bold]Memory:[/bold] {action} | {details}[/dim]"
                                            )

                                if node_name == "review":
                                    # This is where we handle the interrupt logic VISUALLY
                                    style = "bold yellow"
                                    icon = "✋"
                                    content = "Waiting for user approval..."

                                elif node_name == "discovery":
                                    style = "magenta"
                                    icon = "🔍"
                                    content = "Discovering capabilities..."
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

                                elif node_name == "clarify":
                                    style = "yellow"
                                    icon = "🤔"
                                    content = "Analyzing request..."
                                    if "clarified_goal" in state_update:
                                        content = (
                                            f"[bold]Goal:[/bold] {state_update['clarified_goal']}"
                                        )
                                    elif (
                                        "status" in state_update
                                        and state_update["status"] == "clarifying"
                                    ):
                                        content = "[italic]Requesting clarification...[/italic]"

                                elif node_name == "plan":
                                    style = "blue"
                                    icon = "📝"
                                    content = "Formulating plan..."
                                    if "plan" in state_update:
                                        steps = state_update["plan"]["steps"]
                                        step_list = "\n".join(
                                            [f"  {s['id']}. {s['description']}" for s in steps]
                                        )
                                        content = f"Plan ({len(steps)} steps):\n{step_list}"

                                elif node_name == "execute":
                                    style = "green"
                                    icon = "⚙️"
                                    content = "Executing step..."
                                    if (
                                        "execution_history" in state_update
                                        and state_update["execution_history"]
                                    ):
                                        last_exec = state_update["execution_history"][-1]
                                        display_exec = (
                                            last_exec[:200] + "..."
                                            if len(last_exec) > 200
                                            else last_exec
                                        )
                                        content = f"{display_exec}"

                                elif node_name == "validate":
                                    style = "red"
                                    icon = "✅"
                                    content = "Validating results..."
                                    if "validation_result" in state_update:
                                        res = state_update["validation_result"]
                                        if res.get("is_valid"):
                                            icon = "🎉"
                                            style = "bold green"
                                            content = "Success! Goal achieved."
                                        else:
                                            icon = "❌"
                                            style = "bold red"
                                            content = f"Validation Failed: {res.get('feedback')}"

                                elif node_name == "reflect":
                                    style = "magenta"
                                    icon = "🧠"
                                    content = "Reflecting on failure..."
                                    if "execution_history" in state_update:
                                        last_exec = state_update["execution_history"][-1]
                                        if "REFLECTION:" in last_exec:
                                            content = last_exec

                                elif node_name == "summary":
                                    style = "bold magenta"
                                    icon = "📄"
                                    content = "Generating session summary..."
                                    if "final_summary" in state_update:
                                        content = state_update["final_summary"]

                                else:
                                    content = str(state_update)

                                panel_body = ""
                                if thought:
                                    panel_body += f"[dim]💭 {thought}[/dim]\n"
                                    if content:
                                        panel_body += "─" * 40 + "\n"
                                panel_body += content
                                console.print(
                                    Panel(panel_body, title=f"{icon} {title}", border_style=style)
                                )

                        # Check snapshot to see if we are suspended
                        snapshot = await app.aget_state(thread)

                        # Final Summary extraction
                        if not snapshot.next:
                            final_summary = snapshot.values.get("final_summary")
                            if final_summary:
                                console.print("\n" + "─" * 60)
                                console.print(
                                    Panel(
                                        Markdown(final_summary),
                                        title="✨ Task Execution Summary",
                                        border_style="green",
                                    )
                                )

                        if snapshot.next:
                            # WE ARE INTERRUPTED
                            if "review" in snapshot.next:
                                # Clean UI for Review
                                console.print("\n" + "━" * 60)
                                execution_history = snapshot.values.get("execution_history", [])
                                goal = snapshot.values.get("clarified_goal", "Unknown")

                                # Show Execution Results
                                console.print(
                                    Panel(
                                        f"[bold cyan]Goal:[/bold cyan] {goal}",
                                        border_style="yellow",
                                    )
                                )

                                hist_table = Table(
                                    title="📊 Execution Results", box=ROUNDED, border_style="green"
                                )
                                hist_table.add_column("Step")

                                # Show last 5 steps to keep it concise
                                display_history = (
                                    execution_history[-5:]
                                    if len(execution_history) > 5
                                    else execution_history
                                )
                                for i, h in enumerate(display_history):
                                    hist_table.add_row(h[:200] + "..." if len(h) > 200 else h)

                                console.print(hist_table)

                                console.print("\n[bold yellow]✋ Outcome Review:[/bold yellow]")
                                console.print(
                                    "• [bold green]y[/bold green]: Approve results and finalize"
                                )
                                console.print("• [bold red]n[/bold red]: Reject and exit")
                                console.print("• Or type [italic]feedback[/italic] to adjust/retry")

                                user_input = console.input(
                                    "\n[bold yellow]>> [/bold yellow]"
                                ).strip()

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

                                # Resume next iteration
                                current_input = None
                                resume = True
                                continue

                        # Truly finished
                        break

                    except Exception as e:
                        console.print(f"[bold red]❌ Graph Error: {e}[/bold red]")

                # --- SESSION DASHBOARD ---
                duration = asyncio.get_event_loop().time() - session_start

                # Calculate estimated tokens (rough approximation)
                # Input: ~500 tokens/prompt * hits
                # Output: ~300 tokens/response * hits
                est_input_tokens = llm_hits * 500
                est_output_tokens = llm_hits * 300
                total_tokens = est_input_tokens + est_output_tokens
                # Cost (Claude 3.5 Sonnet approximation: $3/M in, $15/M out)
                est_cost = (est_input_tokens * 3 + est_output_tokens * 15) / 1_000_000

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
                    from collections import Counter

                    counts = Counter(tool_calls)
                    grid.add_row("", "")  # Spacer
                    grid.add_row("[bold yellow]Tool Usage Breakdown:[/bold yellow]", "")
                    for tool, count in counts.most_common():
                        grid.add_row(f"  • {tool}", f"[green]{count}[/green]")

                console.print("\n")
                console.print(
                    Panel(
                        grid,
                        title="📊 Session Intelligence Report",
                        border_style="bright_blue",
                        expand=False,
                    )
                )
                return

            asyncio.run(run_graph(task))
            return

        # Execute task
        result = asyncio.run(_execute_task_via_kernel(task, steps, verbose))

        # Generate report
        step_count = result.get("step_count", 1)
        tool_calls = result.get("tool_calls", 0)
        tool_counts = {"tool_calls": tool_calls}

        if json_output:
            import json

            print(json.dumps(result, indent=2))
        else:
            _print_session_report(task, result, step_count, tool_counts, 500)


__all__ = ["register_run_command"]
