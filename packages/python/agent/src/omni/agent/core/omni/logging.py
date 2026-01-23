"""
logging.py - Pretty Console Output for OmniLoop

Provides clean, human-readable logging for tool execution:
- Step indicators: [1/10] 🔧 tool_name(args)
- Result previews: → Result preview...
- Completion summaries: ✅ Completed in N steps, M tool calls
"""

from typing import Any, Dict

from rich.console import Console
from rich.text import Text

_console = Console()


def _truncate(text: Any, max_len: int = 50) -> str:
    """Truncate text for display."""
    s = str(text)
    return s[:max_len] + "..." if len(s) > max_len else s


def log_step(step: int, total: int, tool_name: str, args: Dict[str, Any]) -> None:
    """Log a tool call step with clean format.

    Example output:
        [1/10] 🔧 filesystem.read_file(path=test.txt)
    """
    # Format args for display (show first 3 args)
    if args:
        args_str = ", ".join(f"{k}={_truncate(v, 30)}" for k, v in list(args.items())[:3])
        args_display = f"({args_str})"
    else:
        args_display = ""

    step_text = Text()
    step_text.append(f"[{step}/{total}]", style="dim")
    step_text.append(" 🔧 ", style="cyan")
    step_text.append(tool_name, style="bold yellow")
    step_text.append(args_display, style="dim")
    _console.print(step_text)


def log_result(result: str, is_error: bool = False) -> None:
    """Log a tool result.

    Example output:
        → Result: Successfully wrote 11 bytes
        ❌ Error: Permission denied
    """
    if is_error:
        _console.print(f"    ❌ {_truncate(result, 100)}")
    else:
        preview = _truncate(result, 100)
        _console.print(f"    → {preview}")


def log_completion(step_count: int, tool_count: int) -> None:
    """Log completion summary.

    Example output:
        ✅ Completed in 2 steps, 1 tool calls
    """
    _console.print()
    _console.print(
        f"✅ Completed in [bold]{step_count}[/bold] steps, [bold]{tool_count}[/bold] tool calls"
    )
