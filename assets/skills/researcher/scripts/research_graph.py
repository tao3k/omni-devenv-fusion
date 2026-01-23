"""
researcher/graph.py - LangGraph Deep Research Workflow

A cognitive graph that uses LLM reasoning to dynamically decide:
- What to look at (file tree mapping)
- What to read (module selection)
- How to compare (analysis synthesis)

Architecture:
    clone -> survey -> scout (LLM) -> digest -> synthesize (LLM) -> save

Usage:
    from .graph import create_research_graph, run_research_workflow
    graph = create_research_graph()
    result = await graph.ainvoke(initial_state)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, TypedDict, List, Annotated
import operator

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from omni.foundation.config.logging import get_logger
from omni.foundation.services.llm.client import InferenceClient

logger = get_logger("researcher.graph")

# =============================================================================
# Module Imports Setup
# =============================================================================

# Add scripts directory to sys.path for imports
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Import research module functions (available because scripts dir is in sys.path)
from research import clone_repo, repomix_map, repomix_compress, save_report


# =============================================================================
# State Definition
# =============================================================================


class ResearchState(TypedDict):
    """State for the Deep Research Workflow."""

    # Inputs
    request: str  # User's research goal
    repo_url: str  # Target repository URL

    # Internal State
    repo_path: str  # Local clone path
    file_tree: str  # File tree (god view)
    selected_targets: List[str]  # LLM-chosen reading targets (Glob patterns)
    ignore_patterns: List[str]  # Patterns to exclude from compression
    remove_comments: bool  # Whether to remove comments during compression
    context_xml: str  # Compressed code context
    final_report: str  # Final analysis report

    # Control
    messages: Annotated[List[dict], operator.add]
    steps: int
    error: str | None  # Allow None


# =============================================================================
# Node Functions
# =============================================================================


async def node_clone(state: ResearchState) -> dict:
    """Action: Clone the repository."""
    logger.info("[Graph] Cloning repository...", url=state["repo_url"])

    try:
        result = clone_repo(state["repo_url"])
        path = result.get("path", "") if isinstance(result, dict) else str(result)

        if not path:
            return {"error": "Failed to clone repository", "steps": state["steps"] + 1}

        logger.info("[Graph] Clone complete", path=path)
        return {"repo_path": path, "steps": state["steps"] + 1}

    except Exception as e:
        logger.error("[Graph] Clone failed", error=str(e))
        return {"error": f"Clone failed: {e}", "steps": state["steps"] + 1}


async def node_survey(state: ResearchState) -> dict:
    """Action: Map the repository structure."""
    logger.info("[Graph] Mapping structure...", path=state.get("repo_path"))

    try:
        repo_path = state.get("repo_path", "")
        if not repo_path:
            return {"error": "No repo_path available", "steps": state["steps"] + 1}

        result = repomix_map(repo_path, max_depth=4)

        if isinstance(result, dict) and "tree" in result:
            tree = result["tree"]
        else:
            tree = str(result)

        logger.info("[Graph] Survey complete", tree_length=len(tree))
        return {"file_tree": tree, "steps": state["steps"] + 1}

    except Exception as e:
        logger.error("[Graph] Survey failed", error=str(e))
        return {"error": f"Survey failed: {e}", "steps": state["steps"] + 1}


async def node_scout(state: ResearchState) -> dict:
    """Thinking: LLM designs Repomix filter strategy for precise context."""
    logger.info("[Graph] Smart Scouting (Designing Context Filter)...")

    try:
        client = InferenceClient()
        file_tree = state.get("file_tree", "")
        request = state.get("request", "Analyze architecture")

        if not file_tree:
            logger.warning("[Graph] No file tree, using fallback")
            return {
                "selected_targets": ["src"],
                "ignore_patterns": ["**/test_*", "**/*_test.py"],
                "remove_comments": False,
                "steps": state["steps"] + 1,
            }

        prompt = f"""You are a Code Context Engineer designing a precise code extraction strategy.

Goal: {request}

File Tree:
```
{file_tree}
```

Task: Design a Repomix configuration to extract ONLY the most relevant code for the goal.

Guidelines:
1. Use precise Glob patterns with full paths (e.g., "crates/agentgateway/src/lib.rs")
2. Focus on Interfaces, Abstract Classes, and Core Logic
3. Exclude tests, configs, assets, docs unless relevant
4. Decide if comments should be removed (true for architecture analysis to save tokens)

Return a JSON object with your strategy:
{{
    "targets": ["crates/agentgateway/src/lib.rs", "crates/agentgateway/src/config.rs"],
    "ignore": ["**/__init__.py", "**/*_test.py", "**/migrations/**"],
    "remove_comments": true,
    "reasoning": "Focusing on core abstract classes to understand the inheritance hierarchy"
}}

Only return valid JSON, nothing else."""

        response = await client.complete(
            system_prompt="You are a context engineer.",
            user_query=prompt,
            max_tokens=2048,
        )

        content = response.get("content", "").strip()

        # Parse the JSON response
        plan = _extract_json_dict(content)

        if not plan:
            logger.warning("[Graph] JSON parse failed, using fallback")
            return {
                "selected_targets": ["src"],
                "ignore_patterns": ["**/test_*", "**/*_test.py"],
                "remove_comments": False,
                "steps": state["steps"] + 1,
            }

        targets = plan.get("targets", ["src"])
        ignore = plan.get("ignore", [])
        remove_comments = plan.get("remove_comments", False)
        reasoning = plan.get("reasoning", "No reasoning provided")

        logger.info("[Graph] Scout Plan", reasoning=reasoning, targets=targets)
        return {
            "selected_targets": targets,
            "ignore_patterns": ignore,
            "remove_comments": remove_comments,
            "steps": state["steps"] + 1,
        }

    except Exception as e:
        logger.error("[Graph] Scout failed", error=str(e))
        return {"error": f"Scout failed: {e}", "steps": state["steps"] + 1}


async def node_digest(state: ResearchState) -> dict:
    """Action: Compress selected code with precision settings."""
    targets = state.get("selected_targets", [])
    ignore = state.get("ignore_patterns", [])
    remove_comments = state.get("remove_comments", False)

    logger.info("[Graph] Digesting context with smart filtering...", targets=targets)

    try:
        repo_path = state.get("repo_path", "")

        if not repo_path or not targets:
            return {"error": "Missing repo_path or targets", "steps": state["steps"] + 1}

        result = repomix_compress(
            path=repo_path,
            targets=targets,
            ignore=ignore,
            remove_comments=remove_comments,
        )

        if isinstance(result, dict):
            xml_content = result.get("xml_content", str(result))
            char_count = result.get("char_count", len(xml_content))
        else:
            xml_content = str(result)
            char_count = len(xml_content)

        logger.info(
            "[Graph] Digest complete", char_count=char_count, remove_comments=remove_comments
        )
        return {"context_xml": xml_content, "steps": state["steps"] + 1}

    except Exception as e:
        logger.error("[Graph] Digest failed", error=str(e))
        return {"error": f"Digest failed: {e}", "steps": state["steps"] + 1}


async def node_synthesize(state: ResearchState) -> dict:
    """Thinking: LLM generates deep analysis report."""
    logger.info("[Graph] Synthesizing report (LLM Analysis)...")

    try:
        client = InferenceClient()
        request = state.get("request", "Analyze architecture")
        context = state.get("context_xml", "")
        file_tree = state.get("file_tree", "")

        if not context:
            return {"error": "No context available", "steps": state["steps"] + 1}

        # Truncate for safety (LLM context limits)
        max_context = 40000
        truncated_context = context[:max_context]
        if len(context) > max_context:
            truncated_context += "\n\n[...context truncated for length...]"

        prompt = f"""You are a Senior Tech Architect. Analyze the codebase and produce a detailed research report.

User Request: {request}

File Tree Overview:
```
{file_tree[:2000]}
```

Code Context (XML):
{truncated_context}

Produce a Markdown report covering:

## 1. Core Architecture Patterns
- What architectural style is used (MVC, microservices, layered, etc.)?
- Key design patterns observed

## 2. Key Components
- Main entry points and their responsibilities
- Critical modules and their interactions

## 3. Technology Stack
- Frameworks and libraries used
- Infrastructure dependencies

## 4. Analysis & Comparison
- Strengths of this implementation
- Potential improvements or concerns

## 5. Relevance to Agent Systems (if applicable)
- How this relates to Omni-Dev architecture patterns

Format as clean Markdown with proper headings and code blocks."""

        response = await client.complete(
            system_prompt="You are a tech writer.",
            user_query=prompt,
            max_tokens=2048,
        )

        report = response.get("content", "Error: No report generated")

        logger.info("[Graph] Synthesis complete", report_length=len(report))
        return {"final_report": report, "steps": state["steps"] + 1}

    except Exception as e:
        logger.error("[Graph] Synthesis failed", error=str(e))
        return {"error": f"Synthesis failed: {e}", "steps": state["steps"] + 1}


async def node_save(state: ResearchState) -> dict:
    """Action: Save the research report to knowledge base."""
    logger.info("[Graph] Saving report...")

    try:
        repo_url = state.get("repo_url", "")
        report = state.get("final_report", "")

        if not repo_url or not report:
            return {"error": "Missing repo_url or report", "steps": state["steps"] + 1}

        # Extract repo name from URL
        repo_name = repo_url.split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        result = save_report(repo_name, report, category="deep-research")

        report_path = result.get("report_path", "") if isinstance(result, dict) else ""

        logger.info("[Graph] Report saved", path=report_path)

        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": f"Research Complete!\n\nReport saved to: {report_path}\n\n## Summary\n\n{report[:500]}...",
                }
            ],
            "steps": state["steps"] + 1,
        }

    except Exception as e:
        logger.error("[Graph] Save failed", error=str(e))
        return {"error": f"Save failed: {e}", "steps": state["steps"] + 1}


# =============================================================================
# Helper Functions
# =============================================================================


def _extract_json_dict(text: str) -> dict | None:
    """Extract a JSON dict from LLM response text."""
    text = text.strip()

    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        json_str = text[start : end + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # Try parsing entire response
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return None


def _extract_json_list(text: str) -> List[str]:
    """Extract a JSON list from LLM response text."""
    # Try to find JSON array pattern
    text = text.strip()

    # Find the first [ and last ]
    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1 and end > start:
        json_str = text[start : end + 1]
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                # Filter out empty strings
                return [str(x) for x in parsed if x]
        except json.JSONDecodeError:
            pass

    # Fallback: try to parse the entire response
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x) for x in parsed if x]
        if isinstance(parsed, dict) and "targets" in parsed:
            return [str(x) for x in parsed["targets"] if x]
    except json.JSONDecodeError:
        pass

    # Last resort: regex extract quoted strings
    quoted = re.findall(r'"([^"]+)"', text)
    if quoted:
        return quoted

    return []


# =============================================================================
# Graph Construction
# =============================================================================


def create_research_graph() -> StateGraph:
    """Create the Deep Research StateGraph."""
    workflow = StateGraph(ResearchState)

    # Add nodes
    workflow.add_node("clone", node_clone)
    workflow.add_node("survey", node_survey)
    workflow.add_node("scout", node_scout)
    workflow.add_node("digest", node_digest)
    workflow.add_node("synthesize", node_synthesize)
    workflow.add_node("save", node_save)

    # Set entry point
    workflow.set_entry_point("clone")

    # Add edges (linear flow for now)
    workflow.add_edge("clone", "survey")
    workflow.add_edge("survey", "scout")
    workflow.add_edge("scout", "digest")
    workflow.add_edge("digest", "synthesize")
    workflow.add_edge("synthesize", "save")
    workflow.add_edge("save", END)

    return workflow


# Compile with memory checkpoint for state persistence
_memory = MemorySaver()
_app = create_research_graph().compile(checkpointer=_memory)


async def run_research_workflow(
    repo_url: str,
    request: str = "Analyze the architecture",
    thread_id: str = "research-default",
) -> dict[str, Any]:
    """
    Convenience function to run the research workflow.

    Args:
        repo_url: Git repository URL to analyze
        request: Research goal/question
        thread_id: Optional thread ID for checkpointing

    Returns:
        Final state dictionary with results
    """
    logger.info("Running research workflow", repo_url=repo_url, request=request)

    initial_state = ResearchState(
        request=request,
        repo_url=repo_url,
        repo_path="",
        file_tree="",
        selected_targets=[],
        ignore_patterns=[],
        remove_comments=False,
        context_xml="",
        final_report="",
        steps=0,
        messages=[],
        error=None,
    )

    try:
        # Use typed config dict
        config: dict = {"configurable": {"thread_id": thread_id}}
        result = await _app.ainvoke(initial_state, config=config)
        return result
    except Exception as e:
        logger.error("Workflow failed", error=str(e))
        return {"error": str(e), "steps": 1}


# =============================================================================
# Export
# =============================================================================


__all__ = [
    "ResearchState",
    "create_research_graph",
    "run_research_workflow",
    "node_clone",
    "node_survey",
    "node_scout",
    "node_digest",
    "node_synthesize",
    "node_save",
]
