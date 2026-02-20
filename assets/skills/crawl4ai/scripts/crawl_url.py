"""
crawl4ai/scripts/ - Crawl4ai Skill Interface

This module exposes command interfaces for the main agent.
Commands are executed via Foundation's Isolation Pattern.

IMPORTANT: These function signatures are scanned by Rust AST Scanner
for command discovery. The actual implementation is in engine.py.
"""

import json
from pathlib import Path
from typing import Any

import structlog

from omni.foundation.api.decorators import skill_command
from omni.foundation.context_delivery import validate_chunked_action
from omni.foundation.runtime.isolation import run_skill_command
from omni.foundation.services.llm.client import InferenceClient

log = structlog.get_logger("omni.skill.crawl4ai")


def _get_skill_dir() -> Path:
    """Get the skill directory for isolation."""
    return Path(__file__).parent.parent


# LLM prompt for chunk planning
CHUNKING_PROMPT = """You are an intelligent document chunking planner.

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


async def _generate_chunk_plan(skeleton: list, title: str) -> list | None:
    """Generate chunk plan using LLM (runs in main environment)."""
    try:
        # Format skeleton for LLM
        skeleton_lines = []
        for i, section in enumerate(skeleton[:30]):
            indent = "  " * (section.get("level", 1) - 1)
            skeleton_lines.append(f"{indent}- [{i}] {section.get('title', '')}")
        skeleton_text = "\n".join(skeleton_lines)

        # Build prompt
        prompt = CHUNKING_PROMPT.format(
            title=title or "Untitled",
            section_count=len(skeleton),
            skeleton=skeleton_text,
        )

        # Call LLM - InferenceClient.complete() expects system_prompt and user_query
        llm = InferenceClient()
        response = llm.complete(
            system_prompt="You are an intelligent document chunking planner. Return valid JSON only.",
            user_query=prompt,
            max_tokens=2000,
        )

        # Parse JSON response
        content = response.get("content", "")
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        plan_data = json.loads(content)

        # Build chunk plan
        chunk_plan = []
        for chunk in plan_data.get("chunks", []):
            chunk_plan.append(
                {
                    "chunk_id": chunk.get("chunk_id", len(chunk_plan)),
                    "section_indices": chunk.get("section_indices", []),
                    "reason": chunk.get("reason", ""),
                    "estimated_tokens": chunk.get("estimated_tokens", 0),
                }
            )

        return chunk_plan

    except Exception as e:
        log.error("LLM chunk planning failed", error=str(e))
        return None


@skill_command(
    name="crawl_url",
    category="read",
    description="""
    Crawl a web page with intelligent chunking.

    Uses Skeleton Planning Pattern - LLM sees only the TOC (~500 tokens)
    instead of full content (~10k+ tokens).

    Modes:
    - Smart Crawl (default): Uses LLM to plan optimal chunking
    - Skeleton: Extract lightweight TOC without full content
    - Basic: Crawl URL and extract full markdown content

    Auto-Upgrade: When max_depth > 1, action is automatically upgraded to "smart"
    because smart mode uses LLM to plan optimal chunking for multi-page crawls.

    Args:
        - url: str - Target URL to crawl (required)
        - action: str = "smart" - Action: smart (default), skeleton, crawl (auto-upgraded if max_depth > 1)
        - fit_markdown: bool = true - Clean and simplify the markdown output
        - max_depth: int = 0 - Maximum crawling depth (0 = single page, >1 auto-upgrades to smart)
        - return_skeleton: bool = false - Also return document skeleton (TOC)
        - chunk_indices: list[int] - List of section indices to extract

    Returns:
        - action=smart: dict with chunk_plan, processed_chunks, final_summary
        - action=skeleton: dict with skeleton, stats, content summary
        - action=crawl: dict with content, metadata, success

    Example:
        @omni("crawl4ai.CrawlUrl", {"url": "https://example.com"})
        @omni("crawl4ai.CrawlUrl", {"url": "https://example.com", "action": "skeleton"})
        @omni("crawl4ai.CrawlUrl", {"url": "https://example.com", "action": "crawl"})
        @omni("crawl4ai.CrawlUrl", {"url": "https://example.com", "action": "crawl", "max_depth": 2})
        #                                           ^ auto-upgraded to "smart" internally
    """,
    read_only=True,
    destructive=False,
    idempotent=False,
    open_world=True,
)
async def CrawlUrl(
    url: str,
    action: str = "smart",
    fit_markdown: bool = True,
    max_depth: int = 0,
    return_skeleton: bool = False,
    chunk_indices: list[int] | None = None,
) -> dict[str, Any] | str:
    """
    Crawl URL with intelligent chunking.

    Args:
        - url: Target URL to crawl
        - action: "smart" (default, LLM-planned), "skeleton" (TOC only), "crawl" (full content)
        - fit_markdown: Clean markdown output
        - max_depth: Crawl depth (0 = single page)
        - return_skeleton: Include skeleton in response
        - chunk_indices: Specific sections to extract
    """
    action_name, action_error = validate_chunked_action(
        action,
        allowed_actions={"smart", "skeleton", "crawl"},
        allow_empty=False,
    )
    if action_error is not None:
        return action_error

    # Auto-upgrade to smart mode when crawling depth > 1
    # Smart mode uses LLM to plan optimal chunking for multi-page crawls
    if max_depth > 1 and action_name == "crawl":
        action_name = "smart"
        log.info("Auto-upgraded to smart mode", max_depth=max_depth)
    # For smart action, we need to:
    # 1. First crawl to get skeleton
    # 2. Generate chunk plan with LLM
    # 3. Pass chunk_plan to engine for execution
    chunk_plan = None
    if action_name == "smart":
        # First crawl to get skeleton
        crawl_result = run_skill_command(
            skill_dir=_get_skill_dir(),
            script_name="engine.py",
            args={
                "url": url,
                "action": "crawl",
                "fit_markdown": fit_markdown,
                "max_depth": max_depth,
            },
        )

        if not crawl_result.get("success"):
            return crawl_result

        # Generate chunk plan with LLM (in main environment)
        skeleton = crawl_result.get("skeleton", [])
        title = crawl_result.get("metadata", {}).get("title", "")

        if skeleton:
            chunk_plan = await _generate_chunk_plan(skeleton, title)

    # Pass to engine (with chunk_plan if available)
    result = run_skill_command(
        skill_dir=_get_skill_dir(),
        script_name="engine.py",
        args={
            "url": url,
            "action": action_name,
            "fit_markdown": fit_markdown,
            "max_depth": max_depth,
            "return_skeleton": return_skeleton,
            "chunk_indices": chunk_indices or [],
            "chunk_plan": chunk_plan,
        },
    )
    return result


# Legacy alias for backward compatibility
crawl_url = CrawlUrl
