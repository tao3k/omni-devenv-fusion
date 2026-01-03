# mcp-server/writer.py
"""
DocuSmith - Writing Quality Tools

Tools for enforcing writing standards from agent/writing-style/:
- lint_writing_style: Check for clutter words (Module 02 - Rosenberg)
- check_markdown_structure: Validate header hierarchy (Module 03)
- run_vale_check: Wrapper for Vale CLI linting
- WritingStyleCache: Singleton cache for writing guidelines

This module re-exports from mcp_core.writing for backward compatibility.
The core implementation is now in mcp_core.writing for sharing across servers.

Usage:
    from mcp.server.fastmcp import FastMCP
    from .writer import register_writer_tools

    mcp = FastMCP("my-server")
    register_writer_tools(mcp)
"""
import asyncio
import json
import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

# Import from shared module (mcp_core.writing)
# This is the source of truth for writing quality functions
from common.mcp_core.writing import (
    WritingStyleCache,
    CLUTTER_WORDS,
    lint_writing_style as _lint_writing_style_impl,
    check_markdown_structure as _check_markdown_structure_impl,
    polish_text as _polish_text_impl,
)

# Re-export for backward compatibility
__all__ = [
    "register_writer_tools",
    "WritingStyleCache",
    "CLUTTER_WORDS",
    # Standalone implementations for testing
    "_lint_writing_style_impl",
    "_check_markdown_structure_impl",
    "_polish_text_impl",
    "_load_writing_memory_impl",
]


# =============================================================================
# Legacy Functions (for backward compatibility)
# =============================================================================

async def _load_writing_memory_impl() -> str:
    """
    Implementation of load_writing_memory tool.

    Returns:
        JSON string with full writing guidelines content
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


# =============================================================================
# MCP Tools
# =============================================================================

def register_writer_tools(mcp: Any) -> None:
    """Register all writer tools with the MCP server."""

    @mcp.tool()
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
        return await _lint_writing_style_impl(text)

    @mcp.tool()
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
        return await _check_markdown_structure_impl(text)

    @mcp.tool()
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
        return await _polish_text_impl(text)

    @mcp.tool()
    async def load_writing_memory() -> str:
        """
        Load writing guidelines into LLM context for writing tasks.

        This tool reads from agent/writing-style/ - content written FOR LLM.
        Use this when you need to write or polish documentation.

        This tool reads all files from agent/writing-style/*.md and injects
        them into your context. Use the loaded guidelines to:
        - Write new content that follows project standards
        - Polish/edit text according to style rules

        NOTE: Call this tool exactly once at the start of a writing task.
        The guidelines persist in context for that conversation.

        Returns:
            JSON with writing guidelines from agent/writing-style/*.md
        """
        return await _load_writing_memory_impl()

    @mcp.tool()
    async def run_vale_check(file_path: str) -> str:
        """
        Run Vale CLI on a markdown file and return JSON results.

        Args:
            file_path: Path to the markdown file to lint

        Returns:
            JSON string with Vale linting results
        """
        import subprocess

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
