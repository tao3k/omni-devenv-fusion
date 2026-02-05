#!/usr/bin/env python3
"""
graph.py - Skeleton Extraction Utilities for crawl4ai

This module provides utilities for extracting document skeleton (TOC) from markdown.
Used by crawl_url.py in the main MCP environment.

Note: This module runs in the main MCP environment where langgraph is available.
"""

from typing import Any, Dict, List, TypedDict


# ============================================================================
# STATE DEFINITION
# ============================================================================


class CrawlChunkState(TypedDict, total=False):
    """State for crawl-chunk workflow."""

    url: str
    skeleton: List[Dict[str, Any]]
    stats: Dict[str, Any]
    chunk_plan: List[Dict[str, Any]]
    processed_chunks: List[Dict[str, Any]]
    results: List[Dict[str, Any]]
    current_chunk_index: int
    metadata: Dict[str, Any]
    final_summary: str
    raw_content: str
    error: str


# ============================================================================
# PROMPTS
# ============================================================================

CHUNKING_PLANNER_PROMPT = """
You are an intelligent document chunking planner.

## Document
- Title: {title}
- Total Sections: {section_count}

## Skeleton
{skeleton}

## Task
Create a chunking plan. Return JSON only:

{{
    "chunks": [
        {{
            "chunk_id": 0,
            "section_indices": [0, 1],
            "reason": "Introduction and overview"
        }}
    ]
}}
"""


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def create_initial_state(url: str, chunk_plan: list | None = None) -> Dict[str, Any]:
    """Create initial state for the workflow."""
    return {
        "url": url,
        "skeleton": [],
        "stats": {},
        "chunk_plan": chunk_plan or [],
        "processed_chunks": [],
        "results": [],
        "current_chunk_index": 0,
        "metadata": {},
        "final_summary": "",
        "error": "",
    }


def extract_chunk_from_skeleton(markdown_text: str, line_start: int, line_end: int = None) -> str:
    """Extract a specific chunk by line numbers."""
    lines = markdown_text.split("\n")
    if line_end is None:
        line_end = len(lines) - 1
    line_start = max(0, line_start)
    line_end = min(len(lines) - 1, line_end)
    return "\n".join(lines[line_start : line_end + 1])
