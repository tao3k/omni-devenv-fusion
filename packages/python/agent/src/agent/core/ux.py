"""
src/agent/core/ux.py
UXManager - Glass Cockpit for Omni Orchestrator

Phase 18: The Glass Cockpit (Sidecar Dashboard Pattern)
- Real-time TUI for agent state visualization
- Rich-powered terminal output
- Visual audit feedback and RAG knowledge display
- Dual-mode: 'tui' (direct rendering) or 'headless' (event emission)

Usage (TUI mode - CLI):
    from agent.core.ux import ux_manager

    ux_manager.start_task("Fix SQL injection")
    ux_manager.show_routing_result("coder", "Improve exception handling...")
    ux_manager.show_rag_hits([...])
    ux_manager.end_task()

Usage (Headless mode - MCP Server):
    export OMNI_UX_MODE=headless
    # Events are written to /tmp/omni_ux_events.jsonl
    # Sidecar dashboard reads and replays them
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.tree import Tree
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.columns import Columns
from rich.align import Align
from rich.rule import Rule
from enum import Enum

# Event log path for sidecar pattern
EVENT_LOG_PATH = Path("/tmp/omni_ux_events.jsonl")


class AgentState(Enum):
    """Agent execution states for TUI display."""

    IDLE = "idle"
    ROUTING = "routing"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    CORRECTING = "correcting"
    COMPLETED = "completed"
    FAILED = "failed"


class UXManager:
    """
    Glass Cockpit - Terminal UI Manager for Omni Orchestrator.

    Transforms complex agent internal states into beautiful, readable TUI.

    Dual-Mode Support:
    - 'tui': Direct rendering to terminal (CLI mode)
    - 'headless': Emit events to log file for sidecar dashboard (MCP Server mode)
    """

    def __init__(self, force_mode: Optional[str] = None):
        # mode: 'tui' (direct rendering) or 'headless' (write to event log)
        self.mode = force_mode or os.getenv("OMNI_UX_MODE", "tui")
        self.console = Console()
        self.task_id: Optional[str] = None
        self.current_state: AgentState = AgentState.IDLE
        self._live: Optional[Live] = None
        self._status: Optional[Progress] = None
        self._phase_stack: List[str] = []

    # ==================== Event Emission (Headless Mode) ====================

    def _emit(self, method: str, **kwargs) -> None:
        """
        Emit event to the event log stream (for sidecar dashboard).

        In headless mode, this is called instead of direct rendering.
        """
        event = {
            "timestamp": time.time(),
            "method": method,
            "params": kwargs,
        }
        try:
            with open(EVENT_LOG_PATH, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception:
            # Production: never let logging break the main flow
            pass

    def _should_emit(self) -> bool:
        """Check if we should emit events (headless mode)."""
        return self.mode == "headless"

    # ==================== Proxy Methods ====================

    def rule(self, title: str = "", style: str = "blue") -> None:
        """Print a rule (horizontal line) with title."""
        if self._should_emit():
            self._emit("rule", title=title, style=style)
        else:
            self._render_rule(title, style)

    def start_task(self, user_query: str) -> None:
        """Start a new task - show user query and initialize UI."""
        if self._should_emit():
            self._emit("start_task", user_query=user_query)
        else:
            self._render_start_task(user_query)

    def end_task(self, success: bool = True) -> None:
        """End the current task."""
        if self._should_emit():
            self._emit("end_task", success=success)
        else:
            self._render_end_task(success)

    # ==================== Routing Visualization ====================

    def start_routing(self) -> None:
        """Show routing in progress."""
        if self._should_emit():
            self._emit("start_routing")
        else:
            self._render_start_routing()

    def stop_routing(self) -> None:
        """Stop routing spinner."""
        if self._should_emit():
            self._emit("stop_routing")
        else:
            self._render_stop_routing()

    def show_routing_result(
        self, agent_name: str, mission_brief: str, confidence: float = 1.0, from_cache: bool = False
    ) -> None:
        """Display routing result with mission brief."""
        if self._should_emit():
            self._emit(
                "show_routing_result",
                agent_name=agent_name,
                mission_brief=mission_brief,
                confidence=confidence,
                from_cache=from_cache,
            )
        else:
            self._render_show_routing_result(agent_name, mission_brief, confidence, from_cache)

    # ==================== RAG Visualization ====================

    def show_rag_hits(self, hits: List[Dict[str, Any]]) -> None:
        """
        Display RAG knowledge retrieval results.
        """
        if self._should_emit():
            self._emit("show_rag_hits", hits=hits)
        else:
            self._render_show_rag_hits(hits)

    # ==================== Execution Visualization ====================

    def start_execution(self, agent_name: str) -> None:
        """Show execution in progress."""
        if self._should_emit():
            self._emit("start_execution", agent_name=agent_name)
        else:
            self._render_start_execution(agent_name)

    def stop_execution(self) -> None:
        """Stop execution spinner."""
        if self._should_emit():
            self._emit("stop_execution")
        else:
            self._render_stop_execution()

    def stop_live(self) -> None:
        """Stop Rich Live display to release TTY for external processes like Claude CLI."""
        # Stop the status spinner if running
        if self._status:
            self._status.stop()
            self._status = None

        # Stop Live if running
        if self._live and self._live.is_started:
            self._live.stop()
            self._live = None

        # Print handoff message after stopping spinners (don't clear it)
        self.console.print("[bold yellow]🎮 Handoff to Claude Code...[/]")

    def start_live(self) -> None:
        """Restart Rich Live display after external process completes."""
        self.console.print("\n" + "=" * 50)
        self.console.print("[bold yellow]🔙 Control returned to Omni. Starting Post-Mortem...[/]")
        self.console.print("=" * 50 + "\n")

        # Restart status spinner for post-mortem
        if self._status:
            self._live = Live(self._status.console, refresh_per_second=4, transient=True)
            self._live.start()

    # ==================== Review Visualization ====================

    def start_review(self) -> None:
        """Show review in progress."""
        if self._should_emit():
            self._emit("start_review")
        else:
            self._render_start_review()

    def stop_review(self) -> None:
        """Stop review spinner."""
        if self._should_emit():
            self._emit("stop_review")
        else:
            self._render_stop_review()

    def show_audit_result(
        self, approved: bool, feedback: str, issues: List[str] = None, suggestions: List[str] = None
    ) -> None:
        """Display audit result with rich visual feedback."""
        if self._should_emit():
            self._emit(
                "show_audit_result",
                approved=approved,
                feedback=feedback,
                issues=issues,
                suggestions=suggestions,
            )
        else:
            self._render_show_audit_result(approved, feedback, issues, suggestions)

    # ==================== Correction Loop Visualization ====================

    def show_correction_loop(self, attempt: int, max_attempts: int) -> None:
        """Show self-correction loop entry."""
        if self._should_emit():
            self._emit("show_correction_loop", attempt=attempt, max_attempts=max_attempts)
        else:
            self._render_show_correction_loop(attempt, max_attempts)

    # ==================== Agent Response Display ====================

    def print_agent_response(self, content: str, title: str = "Agent Output") -> None:
        """Print agent response with Markdown rendering."""
        if self._should_emit():
            self._emit("print_agent_response", content=content, title=title)
        else:
            self._render_print_agent_response(content, title)

    # ==================== Progress & Status ====================

    def show_progress_table(self, rows: List[List[str]], title: str = "Progress") -> None:
        """Display a progress table."""
        if self._should_emit():
            self._emit("show_progress_table", rows=rows, title=title)
        else:
            self._render_show_progress_table(rows, title)

    def show_status_summary(self, status: Dict[str, Any]) -> None:
        """Display a summary of current status."""
        if self._should_emit():
            self._emit("show_status_summary", status=status)
        else:
            self._render_show_status_summary(status)

    # ==================== Error Handling ====================

    def show_error(self, message: str, details: str = None) -> None:
        """Display error message."""
        if self._should_emit():
            self._emit("show_error", message=message, details=details)
        else:
            self._render_show_error(message, details)

    def show_warning(self, message: str) -> None:
        """Display warning message."""
        if self._should_emit():
            self._emit("show_warning", message=message)
        else:
            self._render_show_warning(message)

    # ==================== Rendering Methods (Original Implementation) ====================

    def _render_rule(self, title: str = "", style: str = "blue") -> None:
        """Print a rule (horizontal line) with title."""
        self.console.print(Rule(title, style=style))

    def _render_start_task(self, user_query: str) -> None:
        """Start a new task - show user query and initialize UI."""
        self.task_id = user_query[:50] + "..." if len(user_query) > 50 else user_query
        self.current_state = AgentState.IDLE
        self._phase_stack = []

        self.console.print()
        self.console.print(
            Panel(
                Text(f"User Query:\n\n[bold white]{user_query}[/]", justify="left"),
                title="🚀 New Task",
                border_style="cyan",
                subtitle=f"Task ID: {self.task_id[:30]}...",
                subtitle_align="right",
            )
        )

    def _render_end_task(self, success: bool = True) -> None:
        """End the current task."""
        style = "green" if success else "red"
        title = "✅ Task Completed" if success else "❌ Task Failed"

        self.console.print(
            Panel(Text(f"Task: {self.task_id}", justify="left"), title=title, border_style=style)
        )
        self.console.print()

        self.task_id = None
        self.current_state = AgentState.IDLE

    def _render_start_routing(self) -> None:
        """Show routing in progress."""
        self.current_state = AgentState.ROUTING
        self._status = self.console.status(
            "[bold cyan]🧠 HiveRouter is analyzing request...[/]", spinner="dots"
        )
        self._status.start()

    def _render_stop_routing(self) -> None:
        """Stop routing spinner."""
        if self._status:
            self._status.stop()
            self._status = None

    def _render_show_routing_result(
        self, agent_name: str, mission_brief: str, confidence: float = 1.0, from_cache: bool = False
    ) -> None:
        """Display routing result with mission brief."""
        self._render_stop_routing()

        cache_note = " [yellow](cached)[/]" if from_cache else ""

        brief_panel = Panel(
            Text(mission_brief, justify="left"),
            title=f"📋 Mission for [bold green]{agent_name.upper()}[/]{cache_note}",
            border_style="blue",
            subtitle=f"Confidence: {confidence:.0%}" if confidence else None,
            subtitle_align="right",
        )
        self.console.print(brief_panel)

    def _render_show_rag_hits(self, hits: List[Dict[str, Any]]) -> None:
        """
        Display RAG knowledge retrieval results.
        """
        if not hits:
            return

        tree = Tree("📚 [bold cyan]Active RAG Knowledge[/]", guide_style="cyan")

        for hit in hits:
            source = hit.get("source_file", hit.get("path", "Unknown"))
            distance = hit.get("distance", 0)
            similarity = (1 - distance) * 100 if distance else 100

            # Color based on similarity
            if similarity > 80:
                color = "green"
            elif similarity > 60:
                color = "yellow"
            else:
                color = "red"

            node = tree.add(f"[{color}]{source}[/]")
            node.add(f"[dim]Similarity: {similarity:.0f}%[/]")

        self.console.print(tree)

    def _render_start_execution(self, agent_name: str) -> None:
        """Show execution in progress."""
        self.current_state = AgentState.EXECUTING
        self._status = self.console.status(
            f"[bold yellow]🛠️ {agent_name} is working...[/]", spinner="dots"
        )
        self._status.start()

    def _render_stop_execution(self) -> None:
        """Stop execution spinner."""
        if self._status:
            self._status.stop()
            self._status = None

    def _render_start_review(self) -> None:
        """Show review in progress."""
        self.current_state = AgentState.REVIEWING
        self._status = self.console.status(
            "[bold magenta]🕵️ Reviewer is auditing...[/]", spinner="dots2"
        )
        self._status.start()

    def _render_stop_review(self) -> None:
        """Stop review spinner."""
        if self._status:
            self._status.stop()
            self._status = None

    def _render_show_audit_result(
        self, approved: bool, feedback: str, issues: List[str] = None, suggestions: List[str] = None
    ) -> None:
        """Display audit result with rich visual feedback."""
        self._render_stop_review()

        color = "green" if approved else "red"
        title = "✅ Audit Approved" if approved else "❌ Audit Rejected"
        icon = "✅" if approved else "❌"

        # Build feedback content
        content_parts = [f"[{color}]{feedback}[/]"]

        if issues:
            issues_text = "\n".join(f"  • {issue}" for issue in issues)
            content_parts.append(f"\n[bold red]Issues Found:[/]\n{issues_text}")

        if suggestions:
            sugg_text = "\n".join(f"  💡 {s}" for s in suggestions)
            content_parts.append(f"\n[bold yellow]Suggestions:[/]\n{sugg_text}")

        content = "\n".join(content_parts)

        self.console.print(
            Panel(
                Text(content, justify="left"),
                title=f"{icon} {title}",
                border_style=color,
                padding=(1, 2),
            )
        )

    def _render_show_correction_loop(self, attempt: int, max_attempts: int) -> None:
        """Show self-correction loop entry."""
        self.current_state = AgentState.CORRECTING

        self.console.print(
            Panel(
                Text(
                    f"Attempt {attempt}/{max_attempts} - Refining output based on feedback",
                    justify="center",
                ),
                title="🔄 Self-Correction Loop",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    def _render_print_agent_response(self, content: str, title: str = "Agent Output") -> None:
        """Print agent response with Markdown rendering."""
        try:
            self.console.print(
                Panel(Markdown(content), title=f"🤖 {title}", border_style="white", padding=(1, 2))
            )
        except Exception:
            # Fallback to plain text if Markdown parsing fails
            self.console.print(
                Panel(Text(content, justify="left"), title=f"🤖 {title}", border_style="white")
            )

    def _render_show_progress_table(self, rows: List[List[str]], title: str = "Progress") -> None:
        """Display a progress table."""
        table = Table(title=title, box=None, show_header=False)

        # Add columns
        for i in range(len(rows[0]) if rows else 2):
            table.add_column(f"Col {i + 1}", style="dim")

        for row in rows:
            table.add_row(*row)

        self.console.print(table)

    def _render_show_status_summary(self, status: Dict[str, Any]) -> None:
        """Display a summary of current status."""
        # Create a simple text summary
        lines = [f"[bold]System Status[/]"]
        for key, value in status.items():
            lines.append(f"  • {key}: {value}")

        self.console.print(
            Panel(Text("\n".join(lines), justify="left"), title="📊 Status", border_style="dim")
        )

    def _render_show_error(self, message: str, details: str = None) -> None:
        """Display error message."""
        content = f"[bold red]Error:[/] {message}"
        if details:
            content += f"\n\n[dim]{details}[/]"

        self.console.print(
            Panel(
                Text(content, justify="left"), title="❌ Error", border_style="red", padding=(1, 2)
            )
        )

    def _render_show_warning(self, message: str) -> None:
        """Display warning message."""
        self.console.print(
            Panel(
                Text(f"[yellow]⚠️ {message}[/]", justify="left"),
                title="⚠️ Warning",
                border_style="yellow",
            )
        )


# Global UX manager instance (auto-detects mode from OMNI_UX_MODE env var)
ux_manager = UXManager()


def get_ux_manager() -> UXManager:
    """Get the global UX manager instance."""
    return ux_manager
