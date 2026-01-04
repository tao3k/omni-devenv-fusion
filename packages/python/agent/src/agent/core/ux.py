"""
src/agent/core/ux.py
UXManager - Glass Cockpit for Omni Orchestrator

Phase 18: The Glass Cockpit
- Real-time TUI for agent state visualization
- Rich-powered terminal output
- Visual audit feedback and RAG knowledge display

Usage:
    from agent.core.ux import ux_manager

    ux_manager.start_task("Fix SQL injection")
    ux_manager.show_routing("coder", "Improve exception handling...")
    ux_manager.show_rag_hits(["standards/security.md", "lang-python.md"])
    ux_manager.update_status("coding")
    ux_manager.show_audit_result(True, "All checks passed")
    ux_manager.end_task()
"""

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
    """

    def __init__(self):
        self.console = Console()
        self.task_id: Optional[str] = None
        self.current_state: AgentState = AgentState.IDLE
        self._live: Optional[Live] = None
        self._status: Optional[Progress] = None
        self._phase_stack: List[str] = []

    def rule(self, title: str = "", style: str = "blue") -> None:
        """Print a rule (horizontal line) with title."""
        self.console.print(Rule(title, style=style))

    def start_task(self, user_query: str) -> None:
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

    def end_task(self, success: bool = True) -> None:
        """End the current task."""
        style = "green" if success else "red"
        title = "✅ Task Completed" if success else "❌ Task Failed"

        self.console.print(
            Panel(Text(f"Task: {self.task_id}", justify="left"), title=title, border_style=style)
        )
        self.console.print()

        self.task_id = None
        self.current_state = AgentState.IDLE

    # ==================== Routing Visualization ====================

    def start_routing(self) -> None:
        """Show routing in progress."""
        self.current_state = AgentState.ROUTING
        self._status = self.console.status(
            "[bold cyan]🧠 HiveRouter is analyzing request...[/]", spinner="dots"
        )
        self._status.start()

    def stop_routing(self) -> None:
        """Stop routing spinner."""
        if self._status:
            self._status.stop()
            self._status = None

    def show_routing_result(
        self, agent_name: str, mission_brief: str, confidence: float = 1.0, from_cache: bool = False
    ) -> None:
        """Display routing result with mission brief."""
        self.stop_routing()

        cache_note = " [yellow](cached)[/]" if from_cache else ""

        brief_panel = Panel(
            Text(mission_brief, justify="left"),
            title=f"📋 Mission for [bold green]{agent_name.upper()}[/]{cache_note}",
            border_style="blue",
            subtitle=f"Confidence: {confidence:.0%}" if confidence else None,
            subtitle_align="right",
        )
        self.console.print(brief_panel)

    # ==================== RAG Visualization ====================

    def show_rag_hits(self, hits: List[Dict[str, Any]]) -> None:
        """
        Display RAG knowledge retrieval results.

        Args:
            hits: List of dicts with 'source_file', 'distance', 'title'
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

    # ==================== Execution Visualization ====================

    def start_execution(self, agent_name: str) -> None:
        """Show execution in progress."""
        self.current_state = AgentState.EXECUTING
        self._status = self.console.status(
            f"[bold yellow]🛠️ {agent_name} is working...[/]", spinner="hammer"
        )
        self._status.start()

    def stop_execution(self) -> None:
        """Stop execution spinner."""
        if self._status:
            self._status.stop()
            self._status = None

    # ==================== Review Visualization ====================

    def start_review(self) -> None:
        """Show review in progress."""
        self.current_state = AgentState.REVIEWING
        self._status = self.console.status(
            "[bold magenta]🕵️ Reviewer is auditing...[/]", spinner="magnifying_glass_tilted_right"
        )
        self._status.start()

    def stop_review(self) -> None:
        """Stop review spinner."""
        if self._status:
            self._status.stop()
            self._status = None

    def show_audit_result(
        self, approved: bool, feedback: str, issues: List[str] = None, suggestions: List[str] = None
    ) -> None:
        """Display audit result with rich visual feedback."""
        self.stop_review()

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

    # ==================== Correction Loop Visualization ====================

    def show_correction_loop(self, attempt: int, max_attempts: int) -> None:
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

    # ==================== Agent Response Display ====================

    def print_agent_response(self, content: str, title: str = "Agent Output") -> None:
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

    # ==================== Progress & Status ====================

    def show_progress_table(self, rows: List[List[str]], title: str = "Progress") -> None:
        """Display a progress table."""
        table = Table(title=title, box=None, show_header=False)

        # Add columns
        for i in range(len(rows[0]) if rows else 2):
            table.add_column(f"Col {i + 1}", style="dim")

        for row in rows:
            table.add_row(*row)

        self.console.print(table)

    def show_status_summary(self, status: Dict[str, Any]) -> None:
        """Display a summary of current status."""
        # Create a simple text summary
        lines = [f"[bold]System Status[/]"]
        for key, value in status.items():
            lines.append(f"  • {key}: {value}")

        self.console.print(
            Panel(Text("\n".join(lines), justify="left"), title="📊 Status", border_style="dim")
        )

    # ==================== Error Handling ====================

    def show_error(self, message: str, details: str = None) -> None:
        """Display error message."""
        content = f"[bold red]Error:[/] {message}"
        if details:
            content += f"\n\n[dim]{details}[/]"

        self.console.print(
            Panel(
                Text(content, justify="left"), title="❌ Error", border_style="red", padding=(1, 2)
            )
        )

    def show_warning(self, message: str) -> None:
        """Display warning message."""
        self.console.print(
            Panel(
                Text(f"[yellow]⚠️ {message}[/]", justify="left"),
                title="⚠️ Warning",
                border_style="yellow",
            )
        )


# Global UX manager instance
ux_manager = UXManager()


def get_ux_manager() -> UXManager:
    """Get the global UX manager instance."""
    return ux_manager
