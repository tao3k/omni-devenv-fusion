"""
logging.py - Pretty Console Output for OmniLoop

Provides clean, human-readable logging for tool execution:
- Smart truncation: Shows a one-line preview for large content
- Step indicators: [1/10] 🔧 tool_name(args)
"""

from typing import Any
from rich.console import Console
from rich.text import Text

# [NEW] Import from foundation
from omni.foundation.utils.formatting import sanitize_tool_args, one_line_preview

_console = Console()


def log_llm_response(response: str) -> None:
    """Log LLM response (thinking process).

    Extracts and displays the <thinking> block if present.
    Example output:
        💭 <thinking>
           Current Goal: ...
           Intent: ...
           Tool: ...
           </thinking>
    """
    if not response:
        return

    # Check for thinking block
    if "<thinking>" in response:
        # Extract thinking block
        start = response.find("<thinking>")
        end = response.find("</thinking>")
        if end > start:
            thinking = response[start + len("<thinking>") : end].strip()
            _console.print()
            _console.print(Text("💭 ", style="bold magenta") + Text("<thinking>", style="dim"))
            # Print each line with indentation
            for line in thinking.split("\n"):
                _console.print(f"   {line}")
            _console.print(Text("   </thinking>", style="dim"))
            _console.print()
            return

    # No thinking block, just show first line of response
    first_line = response.strip().split("\n")[0]
    if len(first_line) > 100:
        first_line = first_line[:100] + "..."
    _console.print(f"   💭 {first_line}")


def log_step(step: int, total: int, tool_name: str, args: dict[str, Any]) -> None:
    """Log a tool call step using unified formatting.

    Example output:
        [1/10] 🔧 documentation.create_entry(category=arch, content="# Bi-directional Alias Mapping ## Overview The BAM mechanism...")
    """
    # Use shared logic
    args_display = f"({sanitize_tool_args(args)})" if args else ""

    step_text = Text()
    step_text.append(f"[{step}/{total}]", style="dim")
    step_text.append(" 🔧 ", style="cyan")
    step_text.append(tool_name, style="bold yellow")
    # Arguments use dim style to not overshadow the tool name
    step_text.append(args_display, style="dim white")
    _console.print(step_text)


def log_result(result: str, is_error: bool = False) -> None:
    """Log result using unified formatting."""
    if is_error:
        _console.print(f"    ❌ {one_line_preview(result, 150)}")
    else:
        preview = one_line_preview(result, 100)
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


__all__ = ["log_step", "log_result", "log_completion", "log_llm_response"]
