"""
Writer Skill Tools
Migrated from src/mcp_server/executor/writer.py
Provides writing quality enforcement using common/mcp_core.writing.
"""
import json
import subprocess
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Import from shared module (common.mcp_core.writing is the source of truth)
from common.mcp_core.writing import (
    WritingStyleCache,
    lint_writing_style as _lint_impl,
    check_markdown_structure as _check_struct_impl,
    polish_text as _polish_impl,
)

import structlog

logger = structlog.get_logger(__name__)


async def lint_writing_style(text: str) -> str:
    """
    Check text against Module 02 (Rosenberg Mechanics) style guide.

    Checks for:
    - Clutter words (utilize -> use, facilitate -> help)
    - Passive voice
    - Weak language (basically, essentially)

    Args:
        text: The text to lint

    Returns:
        JSON string with violations and suggestions
    """
    return await _lint_impl(text)


async def check_markdown_structure(text: str) -> str:
    """
    Check Markdown structure against Module 03 (Structure & AI).

    Checks for:
    - H1 uniqueness (only one # at top)
    - Hierarchy jumping (H2 -> H4 not allowed)
    - Code block labels (Input/Output style)
    - Proper spacing

    Args:
        text: The markdown text to check

    Returns:
        JSON string with structure violations
    """
    return await _check_struct_impl(text)


async def polish_text(text: str) -> str:
    """
    Polish text using writing guidelines from agent/writing-style/.

    Guidelines are automatically injected into the LLM context.
    Checks against: concise.md, formatting.md, technical.md rules.

    Args:
        text: The text to polish

    Returns:
        JSON string with polished text and any style issues found
    """
    return await _polish_impl(text)


async def load_writing_memory() -> str:
    """
    Load writing guidelines into LLM context for writing tasks.

    This tool reads from agent/writing-style/ - content written FOR LLM.
    Use this when you need to write or polish documentation.

    NOTE: Call this tool exactly once at the start of a writing task.
    The guidelines persist in context for that conversation.

    Returns:
        JSON with writing guidelines from agent/writing-style/*.md
    """
    guidelines_dict = WritingStyleCache.get_guidelines_dict()
    full_content = "\n\n".join(guidelines_dict.values())

    return json.dumps({
        "status": "loaded",
        "source": "agent/writing-style/*.md",
        "files_loaded": list(guidelines_dict.keys()),
        "total_files": len(guidelines_dict),
        "content": full_content,
        "note": "Full writing guidelines loaded into context. Apply these rules to all writing tasks."
    }, indent=2)


async def run_vale_check(file_path: str) -> str:
    """
    Run Vale CLI on a markdown file and return JSON results.

    Args:
        file_path: Path to the markdown file to lint

    Returns:
        JSON string with Vale linting results
    """
    # Check if vale is available
    try:
        subprocess.run(
            ["vale", "--version"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return json.dumps({
            "status": "error",
            "message": "Vale CLI not found. Install with: brew install vale",
            "violations": [],
        })

    # Run vale in JSON format
    try:
        result = subprocess.run(
            ["vale", "--output=JSON", file_path],
            capture_output=True,
            text=True,
        )

        # Parse Vale JSON output
        if result.returncode == 0:
            vale_results = json.loads(result.stdout) if result.stdout else {}
        else:
            # Vale returns non-zero when errors found
            vale_results = json.loads(result.stdout) if result.stdout else {}

        # Extract files from Vale output
        violations = []
        for file_path_key, alerts in vale_results.items():
            for alert in alerts:
                violations.append({
                    "type": "vale",
                    "file": file_path_key,
                    "line": alert.get("Line", 0),
                    "severity": alert.get("Severity", "info"),
                    "message": alert.get("Message", ""),
                    "check": alert.get("Check", ""),
                })

        return json.dumps({
            "status": "success",
            "message": f"Vale found {len(violations)} issue(s)",
            "violations": violations,
        }, indent=2)

    except json.JSONDecodeError:
        return json.dumps({
            "status": "error",
            "message": "Failed to parse Vale output",
            "violations": [],
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Vale error: {str(e)}",
            "violations": [],
        })


def register(mcp: FastMCP):
    """Register Writer tools."""

    @mcp.tool()
    async def lint_writing_style_tool(text: str) -> str:
        return await lint_writing_style(text)

    @mcp.tool()
    async def check_markdown_structure_tool(text: str) -> str:
        return await check_markdown_structure(text)

    @mcp.tool()
    async def polish_text_tool(text: str) -> str:
        return await polish_text(text)

    @mcp.tool()
    async def load_writing_memory_tool() -> str:
        return await load_writing_memory()

    @mcp.tool()
    async def run_vale_check_tool(file_path: str) -> str:
        return await run_vale_check(file_path)

    logger.info("Writer skill tools registered")
