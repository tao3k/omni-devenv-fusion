# common/mcp_core/rich_utils.py
"""
Rich Terminal Output Utilities

Provides beautiful terminal formatting using the Rich library.
All output goes to stderr to avoid interfering with JSON-RPC communication.
Replaces verbose print statements with styled output.
"""
from typing import Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text
from rich.box import ROUNDED
from rich.traceback import Traceback

# Use stderr to avoid interfering with JSON-RPC stdout communication
console = Console(stderr=True)


def banner(
    title: str,
    role: str,
    emoji: str = "🔧",
    border_style: str = "green",
    title_style: str = "bold green",
) -> Panel:
    """
    Generate a styled server startup banner.

    Args:
        title: Server name/title
        role: Description of the server's role
        emoji: Emoji icon for the banner
        border_style: Color of the border
        title_style: Style for the title

    Returns:
        Panel renderable
    """
    content = Text()
    content.append(f"{emoji}  ", "cyan")
    content.append(title, title_style)
    content.append("\n\n", "")
    content.append(role, "dim")

    return Panel(
        content,
        title=f"[{title_style}]{title}[/]",
        subtitle="System Ready",
        border_style=border_style,
        box=ROUNDED,
        padding=(1, 2),
    )


def section(title: str, style: str = "rule.line") -> None:
    """
    Print a section separator with title.

    Args:
        title: Section title
        style: Rich style for the rule
    """
    console.rule(title, style=style)


def success(message: str) -> None:
    """
    Print a success message.

    Args:
        message: Message to display
    """
    console.print(f"[green]✅[/] {message}")


def error(message: str) -> None:
    """
    Print an error message.

    Args:
        message: Error to display
    """
    console.print(f"[red]❌[/] {message}")


def warning(message: str) -> None:
    """
    Print a warning message.

    Args:
        message: Warning to display
    """
    console.print(f"[yellow]⚠️[/] {message}")


def info(message: str) -> None:
    """
    Print an info message.

    Args:
        message: Info to display
    """
    console.print(f"[blue]ℹ️[/] {message}")


def tool_registered(module: str, count: int) -> None:
    """
    Print tool registration status.

    Args:
        module: Module name
        count: Number of tools registered
    """
    console.print(f"[green]✓[/] [bold]{module}[/] tools registered ({count} tools)")


def tool_failed(module: str, error: str) -> None:
    """
    Print tool registration failure.

    Args:
        module: Module name
        error: Error message
    """
    console.print(f"[red]✗[/] [bold]{module}[/] tools failed: {error}")


def status_table(title: str, rows: list[dict], columns: list[str] = None) -> Table:
    """
    Create a styled status table.

    Args:
        title: Table title
        rows: List of dicts with column data
        columns: Optional column names (derived from first row if not provided)

    Returns:
        Rich Table object
    """
    if not rows:
        return None

    if columns is None:
        columns = list(rows[0].keys()) if rows else []

    table = Table(title=title, box=ROUNDED, style="cyan")
    for col in columns:
        table.add_column(col.title(), style="bold cyan")

    for row in rows:
        values = [str(row.get(col, "")) for col in columns]
        table.add_row(*values)

    return table


def simple_table(title: str, *columns: str) -> Table:
    """
    Create a simple table with column headers.

    Args:
        title: Table title
        *columns: Column header names

    Returns:
        Rich Table object
    """
    table = Table(title=title, box=ROUNDED, style="cyan")
    for col in columns:
        table.add_column(col, style="bold cyan")
    return table


def tree_structure(root_label: str, entries: dict[str, list[str]] | None = None) -> Tree:
    """
    Create a tree structure for directory/file display.

    Args:
        root_label: Root node label
        entries: Optional dict of {parent: [children]} to build tree

    Returns:
        Rich Tree object
    """
    tree = Tree(f"[bold blue]{root_label}[/]", guide_style="dim")

    if entries:
        for parent, children in entries.items():
            branch = tree.add(f"[bold]{parent}[/]")
            for child in children:
                branch.add(child)

    return tree


def progress_status(current: int, total: int, task: str = "") -> str:
    """
    Format a progress status message.

    Args:
        current: Current progress value
        total: Total value
        task: Task description

    Returns:
        Formatted progress string
    """
    percent = (current / total * 100) if total > 0 else 0
    bar_width = 20
    filled = int(bar_width * percent / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    return f"[cyan]{bar}[/] {percent:.1f}% {task}"


def panel(
    content: str,
    title: str = None,
    style: str = "blue",
    emoji: str = None,
) -> Panel:
    """
    Create a styled panel.

    Args:
        content: Panel content
        title: Optional title
        style: Border/style color
        emoji: Optional emoji prefix

    Returns:
        Rich Panel object
    """
    text = Text(content)
    if emoji:
        text = Text(emoji) + Text("  ") + text

    return Panel(
        text,
        title=title,
        border_style=style,
        box=ROUNDED,
        padding=(1, 2),
    )


def json_summary(data: dict[str, Any], title: str = "Summary") -> Panel:
    """
    Create a panel displaying JSON-like summary.

    Args:
        data: Dictionary to display
        title: Panel title

    Returns:
        Rich Panel object
    """
    lines = []
    for key, value in data.items():
        lines.append(f"[bold]{key}:[/] {value}")
    content = Text("\n".join(lines))

    return Panel(
        content,
        title=title,
        border_style="cyan",
        box=ROUNDED,
        padding=(1, 2),
    )


# =============================================================================
# Traceback Handling
# =============================================================================

def install_traceback_handler(
    width: int = 100,
    extra_lines: int = 3,
    theme: str = "monokai",
    show_locals: bool = True,
) -> None:
    """
    Install Rich traceback handler for beautiful exception formatting.

    Args:
        width: Maximum line width
        extra_lines: Extra context lines around the traceback
        theme: Color theme name
        show_locals: Whether to show local variables in traceback
    """
    from rich import traceback
    traceback.install(
        width=width,
        extra_lines=extra_lines,
        theme=theme,
        show_locals=show_locals,
        console=console,
    )


def print_exception(
    error: Exception,
    message: Optional[str] = None,
    title: str = "Error",
) -> None:
    """
    Print a beautiful exception traceback.

    Args:
        error: The exception to display
        message: Optional message to display before the traceback
        title: Title for the traceback panel
    """
    if message:
        console.print(f"[red]❌[/] {message}")

    tb = Traceback.from_exception(
        type(error),
        error,
        error.__traceback__,
        width=100,
        extra_lines=3,
        theme="monokai",
        show_locals=True,
    )
    console.print(Panel(tb, title=f"[bold red]{title}[/]", border_style="red", padding=(1, 2)))
