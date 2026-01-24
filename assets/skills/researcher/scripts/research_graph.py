"""
research_graph.py - Sharded Deep Research Workflow

Uses unified Rust LanceDB CheckpointStore for persistent state:
- State persists across skill reloads
- Supports workflow_id-based retrieval
- Centralized at path from settings (default: .cache/checkpoints.lance)

Architecture: Map -> Plan -> Loop(Process Shards) -> Synthesize

This implements a cognitive graph that:
1. Maps repository structure
2. Plans analysis shards (subsystem breakdown)
3. Iteratively processes each shard (compress + analyze)
4. Synthesizes final index

Usage:
    from research_graph import run_research_workflow
    result = await run_research_workflow(
        repo_url="https://github.com/...",
        request="Analyze security patterns"
    )
"""

from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from omni.foundation.checkpoint import (
    load_workflow_state,
    save_workflow_state,
)
from omni.foundation.config.logging import get_logger
from omni.foundation.services.llm.client import InferenceClient

logger = get_logger("researcher.graph")

# Workflow type identifier for checkpoint table
_WORKFLOW_TYPE = "research"

# Import research module functions using absolute import (PEP 420 namespace package)
from researcher.scripts.research import (
    clone_repo,
    init_harvest_structure,
    repomix_compress_shard,
    repomix_map,
    save_index,
    save_shard_result,
)

# =============================================================================
# State Definition
# =============================================================================


class ShardDef(TypedDict):
    """Definition of an analysis shard."""
    name: str
    targets: list[str]
    description: str


class ResearchState(TypedDict):
    """State for the Sharded Deep Research Workflow."""

    # Inputs
    request: str  # User's research goal
    repo_url: str  # Target repository URL

    # Setup Phase
    repo_path: str  # Local clone path
    file_tree: str  # Repository structure map
    repo_name: str  # Repository name for filenames

    # Planning Phase
    shards_queue: list[ShardDef]  # Shards to process (Plan output)

    # Loop Phase (per shard)
    current_shard: ShardDef  # Shard being processed
    shard_counter: int  # For ordering files (01_, 02_, etc.)
    shard_analyses: list[str]  # Accumulated shard summaries

    # Final Phase
    harvest_dir: str  # Path to .data/harvested/...
    final_report: str  # Complete analysis

    # Control
    messages: Annotated[list[dict], operator.add]
    steps: int
    error: str | None


# =============================================================================
# Node Functions
# =============================================================================


async def node_setup(state: ResearchState) -> dict:
    """Setup: Clone repository and generate file tree map."""
    logger.info("[Graph] Setting up research...", url=state["repo_url"])

    try:
        # Extract repo name
        repo_url = state["repo_url"]
        repo_name = repo_url.split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        # Clone repository
        path = clone_repo(repo_url)

        # Generate file tree map
        tree = repomix_map(path, max_depth=4)

        logger.info("[Graph] Setup complete", path=path, tree_length=len(tree))

        return {
            "repo_path": path,
            "file_tree": tree,
            "repo_name": repo_name,
            "steps": state["steps"] + 1,
        }

    except Exception as e:
        logger.error("[Graph] Setup failed", error=str(e))
        return {"error": f"Setup failed: {e}", "steps": state["steps"] + 1}


async def node_architect(state: ResearchState) -> dict:
    """
    Plan: Analyze file tree and define analysis shards.

    The LLM breaks down the repository into logical subsystems,
    each becoming a separate shard for analysis.
    """
    logger.info("[Graph] Architecting shards...")

    try:
        client = InferenceClient()
        file_tree = state.get("file_tree", "")
        request = state.get("request", "Analyze architecture")

        if not file_tree:
            raise ValueError("No file tree available for planning")

        prompt = f"""You are a Software Architect. Break down this repository for deep analysis.

Goal: {request}

File Tree:
```
{file_tree}
```

Task: Define 3-5 logical analysis shards (subsystems). Each shard should focus on a specific area.

Return JSON array:
```json
[
    {{
        "name": "Core Kernel",
        "targets": ["src/core/**/*.py", "crates/core/src/**/*.rs"],
        "description": "Main business logic and core types"
    }},
    {{
        "name": "API Layer",
        "targets": ["src/api/**", "src/routes/**", "**/*handler*.py"],
        "description": "HTTP handlers and route definitions"
    }},
    {{
        "name": "Infrastructure",
        "targets": ["src/db/**", "src/services/**", "**/*repository*.py"],
        "description": "Database and external service integrations"
    }}
]
```

Guidelines:
- Focus on subsystems relevant to the research goal
- Use precise glob patterns
- Keep each shard focused (avoid catch-all targets)
- Order from core to peripheral"""

        response = await client.complete(
            system_prompt="You are a software architect.",
            user_query=prompt,
            max_tokens=4096,
        )

        content = response.get("content", "").strip()
        shards = _extract_json_list(content)

        if not shards:
            # Fallback: single shard with whole src
            shards = [{
                "name": "Full Analysis",
                "targets": ["src", "lib", "packages"],
                "description": "Complete codebase analysis"
            }]

        # Convert to ShardDef objects
        shard_defs: list[ShardDef] = []
        for s in shards:
            if isinstance(s, dict):
                shard_defs.append({
                    "name": s.get("name", "Unknown"),
                    "targets": s.get("targets", ["src"]),
                    "description": s.get("description", ""),
                })
            else:
                shard_defs.append({
                    "name": str(s),
                    "targets": ["src"],
                    "description": str(s),
                })

        logger.info("[Graph] Architecting complete", shard_count=len(shard_defs))

        return {
            "shards_queue": shard_defs,
            "shard_counter": 0,
            "shard_analyses": [],
            "steps": state["steps"] + 1,
        }

    except Exception as e:
        logger.error("[Graph] Architecting failed", error=str(e))
        return {"error": f"Architecting failed: {e}", "steps": state["steps"] + 1}


async def node_process_shard(state: ResearchState) -> dict:
    """
    Process: Compress and analyze a single shard.

    For each shard in the queue:
    1. Compress code with repomix (using shard-specific config)
    2. Analyze with LLM
    3. Save shard result
    4. Accumulate summary for final index
    """
    logger.info("[Graph] Processing shard...")

    try:
        shards_queue = state.get("shards_queue", [])
        if not shards_queue:
            raise ValueError("No shards in queue")

        # Get current shard
        shard = shards_queue[0]
        shard_name = shard["name"]
        targets = shard["targets"]
        description = shard["description"]

        repo_path = state.get("repo_path", "")
        repo_name = state.get("repo_name", "")

        logger.info("[Graph] Processing shard", name=shard_name, targets=targets)

        # Step 1: Compress shard with repomix
        compress_result = repomix_compress_shard(
            path=repo_path,
            targets=targets,
            shard_name=shard_name,
        )

        xml_content = compress_result["xml_content"]
        token_count = compress_result.get("token_count", len(xml_content) // 4)

        # Step 2: Analyze with LLM
        client = InferenceClient()

        # Truncate to stay within limits (use first 60K chars for analysis)
        max_input = 60000
        truncated = xml_content[:max_input]
        if len(xml_content) > max_input:
            truncated += "\n\n[...code truncated for analysis...]"

        prompt = f"""You are a Senior Tech Architect. Analyze this subsystem shard in detail.

Shard: {shard_name}
Focus: {description}

Research Goal: {state.get("request", "Analyze architecture")}

Code Context:
{truncated}

Produce a detailed Markdown section covering:

## Architecture Patterns
- Key design patterns and patterns used
- How this subsystem fits into the larger system

## Key Components
- Main entry points and classes
- Critical functions and their responsibilities

## Interfaces & Contracts
- How this subsystem interacts with others
- Public APIs and data structures

## Technology Decisions
- Why certain libraries/approaches were chosen

Format as a standalone Markdown section that can be combined with other shard analyses."""

        response = await client.complete(
            system_prompt="You are a tech writer.",
            user_query=prompt,
            max_tokens=4096,
        )

        analysis = response.get("content", "Error: No analysis generated")

        # Step 3: Save shard result
        counter = state.get("shard_counter", 0) + 1

        # Initialize harvest structure if needed
        harvest_dir = state.get("harvest_dir")
        if not harvest_dir:
            harvest_path = init_harvest_structure(repo_name)
            harvest_dir = str(harvest_path)
        else:
            harvest_path = Path(harvest_dir)

        save_shard_result(
            base_dir=harvest_path,
            shard_id=counter,
            title=shard_name,
            content=analysis,
        )

        # Step 4: Accumulate summary for index
        summary = f"- **[{shard_name}](./shards/{counter:02d}_{shard_name.lower().replace(' ', '_')}.md)**: {description} (~{token_count} tokens)"

        # Remove processed shard from queue - accumulate shard_analyses
        remaining_queue = shards_queue[1:]
        previous_summaries = state.get("shard_analyses", [])

        logger.info("[Graph] Shard processed", name=shard_name, tokens=token_count)

        return {
            "shards_queue": remaining_queue,
            "current_shard": shard,
            "shard_counter": counter,
            "shard_analyses": previous_summaries + [summary],
            "harvest_dir": harvest_dir,
            "steps": state["steps"] + 1,
        }

    except Exception as e:
        logger.error("[Graph] Shard processing failed", error=str(e))
        return {"error": f"Shard processing failed: {e}", "steps": state["steps"] + 1}


def router_loop(state: ResearchState) -> str:
    """Router: Decide whether to process another shard or synthesize."""
    if len(state.get("shards_queue", [])) > 0:
        return "process_shard"
    return "synthesize"


async def node_synthesize(state: ResearchState) -> dict:
    """
    Synthesize: Generate final index.md with all shard summaries.

    Combines the accumulated shard analyses into a coherent report.
    """
    logger.info("[Graph] Synthesizing final report...")

    try:
        repo_name = state.get("repo_name", "")
        repo_url = state.get("repo_url", "")
        request = state.get("request", "Analyze architecture")
        harvest_dir = state.get("harvest_dir", "")
        shard_summaries = state.get("shard_analyses", [])

        if not harvest_dir:
            raise ValueError("No harvest directory available")

        # Generate index.md
        save_index(
            base_dir=Path(harvest_dir),
            title=repo_name,
            repo_url=repo_url,
            request=request,
            shard_summaries=shard_summaries,
        )

        # Generate final summary message
        index_path = Path(harvest_dir) / "index.md"
        summary_msg = f"""Research Complete!

**Output:** {harvest_dir}

## Summary
Analyzed {len(shard_summaries)} subsystems:

{chr(10).join(shard_summaries)}

View full report at: index.md"""

        logger.info("[Graph] Synthesis complete", shards=len(shard_summaries))

        return {
            "final_report": f"Research on {repo_name} complete. {len(shard_summaries)} shards analyzed.",
            "messages": [{"role": "assistant", "content": summary_msg}],
            "steps": state["steps"] + 1,
        }

    except Exception as e:
        logger.error("[Graph] Synthesis failed", error=str(e))
        return {"error": f"Synthesis failed: {e}", "steps": state["steps"] + 1}


# =============================================================================
# Helper Functions
# =============================================================================


def _extract_json_list(text: str) -> list[Any]:
    """Extract a JSON list from LLM response."""
    text = text.strip()

    # Find first [ and last ]
    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1 and end > start:
        json_str = text[start : end + 1]
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    # Try parsing entire response
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    return []


# =============================================================================
# Graph Construction
# =============================================================================


def create_sharded_research_graph() -> StateGraph:
    """Create the Sharded Research StateGraph."""
    workflow = StateGraph(ResearchState)

    # Add nodes
    workflow.add_node("setup", node_setup)
    workflow.add_node("architect", node_architect)
    workflow.add_node("process_shard", node_process_shard)
    workflow.add_node("synthesize", node_synthesize)

    # Set entry point
    workflow.set_entry_point("setup")

    # Linear: setup -> architect
    workflow.add_edge("setup", "architect")

    # Parallel: architect -> loop
    workflow.add_edge("architect", "process_shard")

    # Conditional: loop -> (process_shard | synthesize)
    workflow.add_conditional_edges(
        "process_shard",
        router_loop,
        {
            "process_shard": "process_shard",
            "synthesize": "synthesize",
        },
    )

    # Final: synthesize -> END
    workflow.add_edge("synthesize", END)

    return workflow


# Compile with memory checkpoint
_memory = MemorySaver()
_app = create_sharded_research_graph().compile(checkpointer=_memory)


async def run_research_workflow(
    repo_url: str,
    request: str = "Analyze the architecture",
    thread_id: str | None = None,
) -> dict[str, Any]:
    """
    Run the sharded research workflow.

    Uses unified Rust LanceDB CheckpointStore for persistent state:
    - State persists across skill reloads
    - Supports workflow_id-based retrieval

    Args:
        repo_url: Git repository URL to analyze.
        request: Research goal/question.
        thread_id: Optional thread ID for checkpointing.
            If not provided, generates one from repo_url hash.

    Returns:
        Final state dictionary with results.
    """
    # Generate workflow_id if not provided
    workflow_id = thread_id or f"research-{hash(repo_url) % 10000}"
    logger.info("Running sharded research workflow", repo_url=repo_url, request=request, workflow_id=workflow_id)

    # Try to load existing state from checkpoint store
    saved_state = load_workflow_state(_WORKFLOW_TYPE, workflow_id)

    if saved_state:
        logger.info("Resuming workflow from checkpoint", workflow_id=workflow_id, steps=saved_state.get("steps", 0))
        initial_state = ResearchState(
            request=saved_state.get("request", request),
            repo_url=saved_state.get("repo_url", repo_url),
            repo_path=saved_state.get("repo_path", ""),
            file_tree=saved_state.get("file_tree", ""),
            repo_name=saved_state.get("repo_name", ""),
            shards_queue=saved_state.get("shards_queue", []),
            current_shard=saved_state.get("current_shard"),
            shard_counter=saved_state.get("shard_counter", 0),
            shard_analyses=saved_state.get("shard_analyses", []),
            harvest_dir=saved_state.get("harvest_dir", ""),
            final_report=saved_state.get("final_report", ""),
            steps=saved_state.get("steps", 0),
            messages=saved_state.get("messages", []),
            error=saved_state.get("error"),
        )
    else:
        logger.info("Starting new workflow", workflow_id=workflow_id)
        initial_state = ResearchState(
            request=request,
            repo_url=repo_url,
            repo_path="",
            file_tree="",
            repo_name="",
            shards_queue=[],
            current_shard=None,
            shard_counter=0,
            shard_analyses=[],
            harvest_dir="",
            final_report="",
            steps=0,
            messages=[],
            error=None,
        )

    try:
        config: dict = {"configurable": {"thread_id": workflow_id}}
        result = await _app.ainvoke(initial_state, config=config)

        # Save final state to checkpoint store
        save_workflow_state(
            _WORKFLOW_TYPE,
            workflow_id,
            dict(result),
            metadata={"repo_url": repo_url, "request": request},
        )

        return result
    except Exception as e:
        logger.error("Workflow failed", error=str(e))
        return {"error": str(e), "steps": initial_state.get("steps", 1)}


# =============================================================================
# Export
# =============================================================================


__all__ = [
    "ResearchState",
    "ShardDef",
    "create_sharded_research_graph",
    "node_architect",
    "node_process_shard",
    "node_setup",
    "node_synthesize",
    "run_research_workflow",
]
