#!/usr/bin/env python3
"""
engine.py - Crawl4ai execution engine

This script runs in an isolated uv environment, allowing heavy dependencies
like crawl4ai without polluting the main agent runtime.

Output Format:
    JSON to stdout: {"success": true, "content": "...", "metadata": {...}}

Architecture:
    - Heavy imports are lazy-loaded inside functions
    - Called via run_skill_command from crawl_url.py

Features:
    - Skeleton extraction for large documents (Skeleton Planning Pattern)
    - Token-aware chunking
    - Lazy loading of large content

Usage:
    # Via run_skill_command (automatic uv run):
    from omni.foundation.runtime.isolation import run_skill_command
    result = run_skill_command(skill_dir, "engine.py", {"url": "..."})

    # Direct CLI (for testing):
    cd assets/skills/crawl4ai && VIRTUAL_ENV=.venv UV_PROJECT_ENVIRONMENT=.venv uv run python scripts/engine.py --url https://example.com
"""

import asyncio
import io
import json
import re
import sys
from pathlib import Path
from typing import Any


# ============================================================================
# SKELETON EXTRACTION - Fast Markdown Structure Analysis
# ============================================================================


def extract_skeleton(markdown_text: str, content_handle: str = None) -> dict:
    """
    Extract document skeleton (TOC) without loading full content.

    This is the core of the Skeleton Planning Pattern - it provides LLM with
    a lightweight view of document structure (~500 tokens) instead of
    dumping entire content (~100k tokens).

    Args:
        markdown_text: The markdown content to analyze
        content_handle: Optional file path or ID for lazy loading content later

    Returns:
        dict with:
        - skeleton: List of section headers with metadata
        - stats: Document statistics
        - content_handle: Reference for lazy loading chunks
    """
    lines = markdown_text.split("\n")
    skeleton = []
    current_section = None

    for i, line in enumerate(lines):
        # Detect headers (# ## ### etc)
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2).strip()

            # Calculate approximate position in document
            position = i / len(lines) if lines else 0

            skeleton.append(
                {
                    "index": len(skeleton),
                    "level": level,
                    "title": title,
                    "line_start": i,
                    "position": position,
                }
            )

    # Estimate tokens per section (rough approximation: 4 chars per token)
    for section in skeleton:
        if section["index"] < len(skeleton) - 1:
            next_start = skeleton[section["index"] + 1]["line_start"]
            section["line_end"] = next_start - 1
        else:
            section["line_end"] = len(lines) - 1

        # Count actual characters in this section
        section_lines = lines[section["line_start"] : section["line_end"] + 1]
        char_count = sum(len(line) for line in section_lines)
        section["approx_chars"] = char_count
        section["approx_tokens"] = max(1, char_count // 4)  # At least 1 token

    # Document statistics
    total_chars = len(markdown_text)
    stats = {
        "total_chars": total_chars,
        "total_tokens_approx": total_chars // 4,
        "total_lines": len(lines),
        "header_count": len(skeleton),
        "max_depth": max((s["level"] for s in skeleton), default=0),
        "content_handle": content_handle,
    }

    return {
        "skeleton": skeleton,
        "stats": stats,
    }


def extract_chunk(markdown_text: str, line_start: int, line_end: int = None) -> str:
    """
    Extract a specific chunk of the markdown by line numbers.

    This enables lazy loading - we only extract the sections LLM
    decided to process, not the entire document.

    Args:
        markdown_text: Full markdown content
        line_start: Starting line index
        line_end: Ending line index (inclusive, optional)

    Returns:
        str: The extracted chunk content
    """
    lines = markdown_text.split("\n")
    if line_end is None:
        line_end = len(lines) - 1

    # Ensure bounds
    line_start = max(0, line_start)
    line_end = min(len(lines) - 1, line_end)

    return "\n".join(lines[line_start : line_end + 1])


# ============================================================================
# MAIN CRAWL IMPLEMENTATION
# ============================================================================


async def _crawl_url_impl(
    url: str,
    fit_markdown: bool = True,
    max_depth: int = 0,
) -> dict:
    """
    Internal implementation - runs in isolated uv environment.

    Args:
        url: Target URL to crawl
        fit_markdown: Whether to clean and simplify the markdown (default: True)
        max_depth: Maximum crawling depth (0 = single page only, >0 = crawl linked pages)

    Returns:
        dict with keys:
        - success: bool
        - url: str
        - content: str (markdown)
        - error: str (if success is False)
        - metadata: dict (title, description)
        - crawled_urls: list[str] (urls crawled when max_depth > 0)
    """
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
    from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

    # Basic config for single page
    config = CrawlerRunConfig()

    # Capture stdout during crawl to prevent progress bars from polluting JSON output
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            if max_depth > 0:
                # Deep crawl config
                deep_config = CrawlerRunConfig(
                    deep_crawl_strategy=BFSDeepCrawlStrategy(
                        max_depth=max_depth,
                        include_external=False,
                        max_pages=20,
                    ),
                )
                result = await crawler.arun(url=url, config=deep_config)
                # Deep crawl may return a generator - convert to list
                results = (
                    list(result)
                    if hasattr(result, "__iter__") and not isinstance(result, dict)
                    else [result]
                )
                # Combine markdown from all pages
                all_content = []
                all_urls = []
                for r in results:
                    if r.success:
                        all_content.append(r.markdown if fit_markdown else r.raw_markdown)
                        all_urls.append(r.url)
                combined_content = "\n\n---\n\n".join(all_content)
                first_result = results[0] if results else None
                success = len([r for r in results if r.success]) > 0
                error_msg = first_result.error_message if first_result else ""
                metadata = first_result.metadata if first_result else None
                sys.stdout = old_stdout  # Restore stdout before return
                return {
                    "success": success,
                    "url": url,
                    "content": combined_content,
                    "error": error_msg,
                    "metadata": {
                        "title": metadata.get("title") if metadata else None,
                        "description": metadata.get("description") if metadata else None,
                    },
                    "crawled_urls": all_urls if all_urls else None,
                }
            else:
                # Single page crawl
                result = await crawler.arun(url=url, config=config)

        # Discard captured stdout (progress bars)
        sys.stdout = old_stdout

        # Collect crawled URLs if available
        crawled_urls = []
        if hasattr(result, "crawled_urls") and result.crawled_urls:
            crawled_urls = result.crawled_urls
        elif hasattr(result, "downloaded_urls") and result.downloaded_urls:
            crawled_urls = result.downloaded_urls

        return {
            "success": result.success,
            "url": result.url,
            "content": result.markdown if fit_markdown else result.raw_markdown,
            "error": result.error_message or "",
            "metadata": {
                "title": result.metadata.get("title") if result.metadata else None,
                "description": result.metadata.get("description") if result.metadata else None,
            },
            "crawled_urls": crawled_urls if crawled_urls else None,
        }

    except Exception as e:
        sys.stdout = old_stdout
        return {
            "success": False,
            "url": url,
            "content": "",
            "error": str(e),
            "metadata": None,
            "crawled_urls": None,
        }


# ============================================================================
# ACTION HANDLERS
# ============================================================================


def _handle_skeleton_action(result: dict) -> None:
    """Handle skeleton extraction action."""
    if not result["success"]:
        print(json.dumps(result, default=str))
        return

    skeleton_result = extract_skeleton(result["content"])
    skeleton = skeleton_result["skeleton"]
    stats = skeleton_result["stats"]

    # Format skeleton preview
    skeleton_preview = []
    for section in skeleton[:30]:
        indent = "  " * (section.get("level", 1) - 1)
        skeleton_preview.append(
            f"{indent}- [{section['index']}] {section['title']} (~{section.get('approx_tokens', 0)} tokens)"
        )

    print(
        json.dumps(
            {
                "success": True,
                "url": result["url"],
                "skeleton": skeleton,
                "stats": stats,
                "metadata": result["metadata"],
            },
            default=str,
        )
    )


def _handle_smart_action(result: dict, url: str, chunk_plan: list | None = None) -> None:
    """Handle smart crawl action - extract chunks based on pre-computed chunk_plan.

    The chunk_plan is generated by LLM in the main MCP environment.
    This function simply executes the extraction in the isolated environment.
    """
    if not result["success"]:
        print(json.dumps(result, default=str))
        return

    try:
        # Extract skeleton from content (already crawled)
        content = result.get("content", "")
        skeleton_result = extract_skeleton(content)
        skeleton = skeleton_result["skeleton"]
        stats = skeleton_result["stats"]
        metadata = result.get("metadata", {})
        title = metadata.get("title", url)

        # Use provided chunk_plan or fallback
        plan = chunk_plan
        if not plan:
            # Fallback: each section as its own chunk
            plan = [
                {
                    "chunk_id": i,
                    "section_indices": [i],
                    "reason": f"Section: {s.get('title', '')}",
                }
                for i, s in enumerate(skeleton)
            ]

        # Process chunks based on chunk_plan
        processed_chunks = []
        for chunk_info in plan:
            section_indices = chunk_info.get("section_indices", [])
            chunk_content_parts = []
            for sec_idx in section_indices:
                if sec_idx < len(skeleton):
                    section = skeleton[sec_idx]
                    line_start = section.get("line_start", 0)
                    line_end = section.get("line_end", line_start)
                    content_chunk = extract_chunk(content, line_start, line_end)
                    chunk_content_parts.append(f"## {section.get('title', '')}\n{content_chunk}")

            combined_content = "\n\n".join(chunk_content_parts)
            processed_chunks.append(
                {
                    "chunk_id": chunk_info.get("chunk_id", len(processed_chunks)),
                    "reason": chunk_info.get("reason", ""),
                    "content": combined_content,
                    "section_indices": section_indices,
                }
            )

        # Build final summary
        final_summary = f"# {title}\n\n"
        for chunk in processed_chunks:
            final_summary += f"## Chunk {chunk.get('chunk_id', 0)}: {chunk.get('reason', '')}\n\n"
            final_summary += chunk.get("content", "") + "\n\n"

        # Format output
        chunk_plan_text = []
        for chunk in plan[:10]:
            indices = chunk.get("section_indices", [])
            chunk_plan_text.append(
                f"  - Chunk {chunk.get('chunk_id', '?')}: sections {indices} - {chunk.get('reason', '')}"
            )
        if len(plan) > 10:
            chunk_plan_text.append(f"  ... and {len(plan) - 10} more chunks")

        chunks_text = []
        for chunk in processed_chunks:
            content_preview = chunk.get("content", "")[:200].replace("\n", " ")
            chunks_text.append(f"  - Chunk {chunk.get('chunk_id', '?')}: {content_preview}...")

        output = f"""# Crawl Result: {title}

**URL:** {url}
**Status:** Success

## Workflow Execution

### 1. Crawl + Skeleton
Extracted {len(skeleton)} sections from document

### 2. LLM Chunking Plan
{chr(10).join(chunk_plan_text) if chunk_plan_text else "  No chunks planned"}

### 3. Processed Chunks ({len(processed_chunks)} total)
{chr(10).join(chunks_text) if chunks_text else "  No chunks processed"}

---

## Final Summary

{final_summary if final_summary else "(No summary generated)"}

---

## Raw Data

**Skeleton:** {len(skeleton)} sections
**Chunk Plan:** {len(plan)} chunks
**Processed:** {len(processed_chunks)} chunks
"""
        print(output)

    except Exception as e:
        print(
            json.dumps(
                {
                    "success": False,
                    "url": url,
                    "error": str(e),
                },
                default=str,
            )
        )


def _handle_chunk_action(result: dict, chunk_indices: list[int]) -> None:
    """Handle chunk extraction action."""
    if not result["success"]:
        print(json.dumps(result, default=str))
        return

    skeleton_result = extract_skeleton(result["content"])
    skeleton = skeleton_result["skeleton"]
    chunks = []

    for idx in chunk_indices:
        if 0 <= idx < len(skeleton):
            section = skeleton[idx]
            chunk = extract_chunk(result["content"], section["line_start"], section["line_end"])
            chunks.append(
                {
                    "chunk_id": idx,
                    "title": section["title"],
                    "content": chunk,
                    "approx_tokens": section["approx_tokens"],
                }
            )

    print(
        json.dumps(
            {
                "success": True,
                "url": result["url"],
                "chunks": chunks,
                "metadata": result["metadata"],
            },
            default=str,
        )
    )


def main():
    """CLI entry point - supports both stdin JSON and command line args."""
    import argparse

    parser = argparse.ArgumentParser(description="Crawl4AI Engine")
    parser.add_argument("--url", type=str, help="URL to crawl")
    parser.add_argument(
        "--action", type=str, default="crawl", help="Action: crawl, skeleton, smart"
    )
    parser.add_argument(
        "--fit_markdown", type=str, default="true", help="Clean markdown (true/false)"
    )
    parser.add_argument(
        "--max_depth", type=int, default=0, help="Maximum crawling depth (0=single page)"
    )
    parser.add_argument(
        "--return_skeleton",
        nargs="?",  # Optional value
        const="true",  # Value when flag is present without argument
        default="false",  # Default value
        help="Only return document skeleton (TOC), not full content",
    )
    parser.add_argument(
        "--chunk_indices",
        type=str,
        default="",
        help="Comma-separated chunk indices to extract (e.g., '0,1,3')",
    )
    parser.add_argument(
        "--chunk_plan",
        type=str,
        default="",
        help="JSON-encoded chunk plan from LLM (for smart action)",
    )
    parser.add_argument("--stdin", action="store_true", help="Read JSON from stdin")

    args = parser.parse_args()

    # Parse URL and fit_markdown
    url = ""
    action = "crawl"
    fit_markdown = True
    max_depth = 0
    return_skeleton = False
    chunk_indices = []
    chunk_plan = None

    if args.stdin and not sys.stdin.isatty():
        # Read JSON from stdin (for uv run with pipe)
        try:
            stdin_data = sys.stdin.read()
            if stdin_data.strip():
                json_args = json.loads(stdin_data)
                url = json_args.get("url", "")
                action = json_args.get("action", "crawl")
                fit_markdown = json_args.get("fit_markdown", True)
                max_depth = json_args.get("max_depth", 0)
                return_skeleton = json_args.get("return_skeleton", False)
                if json_args.get("chunk_indices"):
                    chunk_indices = json_args["chunk_indices"]
                if json_args.get("chunk_plan"):
                    chunk_plan = json_args["chunk_plan"]
        except json.JSONDecodeError:
            pass
    else:
        # Use command line args (for run_skill_command)
        url = args.url or ""
        action = args.action or "crawl"
        fit_markdown = args.fit_markdown.lower() == "true" if args.fit_markdown else True
        max_depth = args.max_depth or 0
        # return_skeleton is now a string "true"/"false" due to nargs="?"
        return_skeleton = (
            str(args.return_skeleton).lower() == "true" if args.return_skeleton else False
        )
        if args.chunk_indices:
            chunk_indices = [int(x.strip()) for x in args.chunk_indices.split(",")]
        if args.chunk_plan:
            try:
                chunk_plan = json.loads(args.chunk_plan)
            except json.JSONDecodeError:
                chunk_plan = None

    if not url:
        print(json.dumps({"success": False, "error": "Missing URL"}, default=str))
        return

    try:
        result = asyncio.run(_crawl_url_impl(url, fit_markdown, max_depth))

        # Handle different actions
        if action == "skeleton" or return_skeleton:
            _handle_skeleton_action(result)
        elif action == "smart":
            _handle_smart_action(result, url, chunk_plan)
        elif chunk_indices:
            _handle_chunk_action(result, chunk_indices)
        else:
            # Default: return full content
            print(json.dumps(result, default=str))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, default=str))


if __name__ == "__main__":
    main()
