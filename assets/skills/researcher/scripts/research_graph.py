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

Uses Rust-Powered Cognitive Pipeline for system prompt assembly:
- Parallel I/O via rayon
- Template rendering via minijinja
- Token counting via omni-tokenizer

Usage:
    from research_graph import run_research_workflow
    result = await run_research_workflow(
        repo_url="https://github.com/...",
        request="Analyze security patterns"
    )
"""

from __future__ import annotations

import asyncio
import json
import operator
import time
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from omni.foundation.checkpoint import (
    load_workflow_state,
    save_workflow_state,
)
from omni.foundation.config.logging import get_logger
from omni.foundation.services.llm.client import InferenceClient
from omni.langgraph.visualize import register_workflow, visualize_workflow
from omni.core.context import create_planner_orchestrator

logger = get_logger("researcher.graph")


# LLM call tracking
_llm_call_counter = 0


async def _llm_complete(
    client: InferenceClient,
    system_prompt: str,
    user_query: str,
    stage: str,
    extra_params: dict = None,
) -> dict:
    """Make LLM call with full logging of parameters."""
    global _llm_call_counter
    _llm_call_counter += 1
    call_id = _llm_call_counter

    # Get client config
    model = client.model
    max_tokens = client.max_tokens
    timeout = client.timeout

    logger.info(
        f"[LLM] {stage} (call #{call_id})",
        call_id=call_id,
        stage=stage,
        model=model,
        max_tokens=max_tokens,
        timeout=timeout,
        system_prompt_len=len(system_prompt),
        user_query_len=len(user_query),
        **(extra_params or {}),
    )

    # Log truncated user query preview
    query_preview = user_query[:200].replace("\n", " ") + "..." if len(user_query) > 200 else user_query.replace("\n", " ")
    logger.debug(f"[LLM] Query preview: {query_preview}")

    start_time = time.perf_counter()
    response = await client.complete(
        system_prompt=system_prompt,
        user_query=user_query,
    )
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    success = response.get("success", False)
    content_len = len(response.get("content", ""))

    logger.info(
        f"[LLM] {stage} complete",
        call_id=call_id,
        stage=stage,
        success=success,
        elapsed_ms=round(elapsed_ms, 2),
        content_len=content_len,
        **(extra_params or {}),
    )

    return response

# Import Rust checkpoint saver for LangGraph (use shared singleton)
try:
    from omni.langgraph.checkpoint.saver import get_default_checkpointer as _get_checkpointer

    _CHECKPOINT_AVAILABLE = True
    _memory = _get_checkpointer()  # Get shared singleton (logs once)
except ImportError as e:
    _CHECKPOINT_AVAILABLE = False
    _memory = None
    logger.warning(f"RustCheckpointSaver import failed: {e}")

# Cache the orchestrator instance for reuse
_orchestrator = None

# Workflow type identifier for checkpoint table
_WORKFLOW_TYPE = "research"


def _get_orchestrator():
    """Get cached ContextOrchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = create_planner_orchestrator()
        logger.info("ResearchContextOrchestrator initialized (Rust-powered)")
    return _orchestrator


async def _build_system_prompt(skill_name: str, state: dict) -> str:
    """
    Build system prompt using Rust-Powered Cognitive Pipeline.

    This triggers:
    - Parallel file I/O via rayon
    - Template rendering via minijinja
    - Token counting via omni-tokenizer

    Args:
        skill_name: Name of the skill (e.g., "researcher")
        state: Current workflow state

    Returns:
        Assembled system prompt string
    """
    orchestrator = _get_orchestrator()
    if orchestrator is None:
        logger.error("Failed to get ContextOrchestrator")
        return f"[Error: Failed to initialize ContextOrchestrator for {skill_name}]"

    # Build state for context building
    context_state = {
        **state,
        "active_skill": skill_name,
        "request": state.get("request", "Analyze the architecture"),
    }

    start_time = asyncio.get_running_loop().time()
    logger.info(f"[Graph] Building context for {skill_name}")
    try:
        system_prompt = await orchestrator.build_context(context_state)
        duration_ms = (asyncio.get_running_loop().time() - start_time) * 1000
        logger.info(
            f"[Graph] Context built for {skill_name}",
            tokens=len(system_prompt) // 4,
            duration_ms=round(duration_ms, 2),
        )
    except Exception as e:
        logger.error(f"Error building context: {e}", exc_info=True)
        return f"[Error: Failed to build context for {skill_name}: {e}]"

    return system_prompt


def _get_cached_system_prompt(state: ResearchState) -> str:
    """
    Get system prompt from state cache, building if not present.

    Args:
        state: Current workflow state

    Returns:
        Cached system prompt string
    """
    cached = state.get("system_prompt")
    if cached:
        logger.debug("[Graph] Using cached system prompt")
        return cached

    logger.warning("[Graph] System prompt not in state cache!")
    return ""


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

    # Setup Stage
    repo_path: str  # Local clone path
    file_tree: str  # Repository structure map
    repo_name: str  # Repository name for filenames

    # Planning Stage
    shards_queue: list[ShardDef]  # Shards to process (Plan output)

    # Loop Stage (per shard)
    current_shard: ShardDef  # Shard being processed
    shard_counter: int  # For ordering files (01_, 02_, etc.)
    shard_analyses: list[str]  # Accumulated shard summaries

    # Final Stage
    harvest_dir: str  # Path to .data/harvested/...
    final_report: str  # Complete analysis

    # Cached Context (built once in architect stage)
    system_prompt: str  # Cached system prompt (persona + skill context)

    # Control
    messages: Annotated[list[dict], operator.add]
    steps: int
    error: str | None


# =============================================================================
# Node Functions
# =============================================================================


async def node_setup(state: ResearchState) -> dict:
    """Setup: Clone repository and generate file tree map using exa."""
    logger.info("[Graph] Setting up research...", url=state["repo_url"])

    try:
        # Extract repo name
        repo_url = state["repo_url"]
        repo_name = repo_url.split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        # Clone repository
        path = clone_repo(repo_url)

        # Generate file tree map using exa with depth limit
        tree = _generate_tree_with_exa(path, max_depth=3)

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


def _generate_tree_with_exa(path: str, max_depth: int = 3) -> str:
    """Generate repository structure using exa -T command.

    Uses exa for a cleaner, more readable tree output than traditional tree.
    Falls back to simple find if exa is not available.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["exa", "-T", path, "-L", str(max_depth), "--color=never", "--icons=never"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Remove the first line (root path) for cleaner output
            lines = result.stdout.strip().split("\n")
            if lines:
                # Skip the first line which is the root directory itself
                tree_output = "\n".join(lines[1:]) if len(lines) > 1 else result.stdout.strip()
                return tree_output
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    # Fallback: use find with tree-like output
    try:
        result = subprocess.run(
            ["find", path, "-maxdepth", str(max_depth), "-type f", "-o", "-type d"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            # Convert paths to relative and add basic indentation
            prefix_len = len(path.rstrip("/")) + 1
            tree_lines = []
            for line in sorted(lines):
                if not line:
                    continue
                rel_path = line[prefix_len:] if line.startswith(path) else line
                depth = rel_path.count("/")
                indent = "  " * depth
                tree_lines.append(f"{indent}{rel_path.split('/')[-1]}/" if line.endswith("/") else f"{indent}{rel_path}")
            return "\n".join(tree_lines)
    except Exception:
        pass

    # Ultimate fallback: simple ls -R
    try:
        result = subprocess.run(
            ["ls", "-R", path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout or "[Error: Could not generate tree]"
    except Exception:
        return "[Error: Could not generate repository tree]"


async def node_architect(state: ResearchState) -> dict:
    """
    Plan: Analyze file tree and define analysis shards.

    The LLM breaks down the repository into logical subsystems based on
    the directory structure, and decides which specific files to include
    in each shard for deep analysis.

    Uses Rust-Powered Cognitive Pipeline for system prompt assembly.
    """
    logger.info("[Graph] Architecting shards...")

    try:
        client = InferenceClient()
        file_tree = state.get("file_tree", "")
        request = state.get("request", "Analyze architecture")
        repo_path = state.get("repo_path", "")

        if not file_tree:
            raise ValueError("No file tree available for planning")

        # Build system prompt using Rust-Powered Cognitive Pipeline
        system_prompt = await _build_system_prompt("researcher", state)

        prompt = f"""You are a Senior Software Architect. Analyze this repository structure and create a research plan.

RESEARCH GOAL: {request}

REPOSITORY STRUCTURE (from exa tree):
```
{file_tree}
```

YOUR TASK:
1. Identify 3-5 logical subsystems/components based on the directory structure
2. For each subsystem, specify the EXACT file paths to analyze (be specific, not glob patterns)
3. Each file path should be relative to the repository root

Respond with a JSON array defining your shards:
```json
[
    {{
        "name": "Core Kernel",
        "files": [
            "src/core/main.py",
            "src/core/engine.py",
            "src/core/types.rs"
        ],
        "description": "Main business logic and core engine components"
    }},
    {{
        "name": "API Layer",
        "files": [
            "src/api/routes.py",
            "src/api/handlers/user.go",
            "src/api/middleware/auth.go"
        ],
        "description": "HTTP API and request handling"
    }}
]
```

GUIDELINES:
- BE SPECIFIC with file paths - use exact paths, not globs
- Focus on files most relevant to the research goal
- Each shard should have 3-7 key files for deep analysis
- Order shards from core functionality to peripheral
- Consider the tech stack implied by file extensions"""

        response = await _llm_complete(
            client=client,
            system_prompt=system_prompt,
            user_query=prompt,
            stage="architect",
            extra_params={"shard_planning": True},
        )

        content = response.get("content", "").strip()
        shards = _extract_json_list(content)

        if not shards:
            # Fallback: single shard with repo root (let LLM analyze everything)
            shards = [
                {
                    "name": "Full Repository Analysis",
                    "files": [],  # Empty means analyze everything
                    "description": "Complete repository analysis",
                }
            ]

        # Convert to ShardDef objects
        shard_defs: list[ShardDef] = []
        for s in shards:
            if isinstance(s, dict):
                shard_defs.append(
                    {
                        "name": s.get("name", "Unknown"),
                        "targets": s.get("files", []),  # Use "files" instead of "targets"
                        "description": s.get("description", ""),
                    }
                )
            else:
                shard_defs.append(
                    {
                        "name": str(s),
                        "targets": [],
                        "description": str(s),
                    }
                )

        logger.info("[Graph] Architecting complete", shard_count=len(shard_defs))

        # Cache system prompt for subsequent shard processing
        return {
            "shards_queue": shard_defs,
            "shard_counter": 0,
            "shard_analyses": [],
            "system_prompt": system_prompt,  # Cache for shard processing
            "steps": state["steps"] + 1,
        }

    except Exception as e:
        logger.error("[Graph] Architecting failed", error=str(e))
        return {"error": f"Architecting failed: {e}", "steps": state["steps"] + 1}


async def node_process_shard(state: ResearchState) -> dict:
    """
    Process: Compress and analyze a single shard.

    For each shard in the queue:
    1. Use repomix to compress the specific files chosen by LLM
    2. Analyze with LLM
    3. Save shard result
    4. Accumulate summary for final index

    Uses Rust-Powered Cognitive Pipeline for system prompt assembly.
    """
    logger.info("[Graph] Processing shard...")

    try:
        shards_queue = state.get("shards_queue", [])
        if not shards_queue:
            raise ValueError("No shards in queue")

        # Get current shard
        shard = shards_queue[0]
        shard_name = shard["name"]
        files = shard["targets"]  # List of specific file paths chosen by LLM
        description = shard["description"]

        repo_path = state.get("repo_path", "")
        repo_name = state.get("repo_name", "")

        logger.info("[Graph] Processing shard", name=shard_name, file_count=len(files))

        # Step 1: Compress shard with repomix (using specific file paths)
        compress_result = repomix_compress_shard(
            path=repo_path,
            targets=files,
            shard_name=shard_name,
        )

        xml_content = compress_result["xml_content"]
        token_count = compress_result.get("token_count", len(xml_content) // 4)

        # Step 2: Get cached system prompt (built once in architect phase)
        system_prompt = _get_cached_system_prompt(state)

        # Step 3: Analyze with LLM
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

FILES IN THIS SHARD ({len(files)} files):
{', '.join(files) if files else 'All files in repository'}

REPOMIX OUTPUT:
{truncated}

Your task: Produce a detailed Markdown section covering:

## Architecture Overview
- What this subsystem does and its role in the larger system
- Key design patterns and architectural decisions

## Source Code Analysis
For each significant file, explain:
- Main purpose and responsibilities
- Key functions/classes and their roles
- How it interacts with other parts of the system

## Interfaces & Contracts
- Public APIs and data structures
- How this subsystem communicates with others

## Key Insights
- Notable patterns, idioms, or anti-patterns
- Technology choices and rationale
- Potential concerns or improvements

Format as a standalone Markdown section that can be combined with other shard analyses into a comprehensive report."""

        response = await _llm_complete(
            client=client,
            system_prompt=system_prompt,
            user_query=prompt,
            stage=f"process_shard:{shard_name}",
            extra_params={
                "shard_name": shard_name,
                "file_count": len(files),
                "files": files[:5] if files else [],  # Log first 5 files
            },
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
            # Preserve these fields for result extraction
            "harvest_dir": harvest_dir,
            "shard_analyses": shard_summaries,
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


# Compile with Rust checkpoint for state persistence (shared singleton)
logger.info(f"Final checkpointer: {_memory}")
_app = create_sharded_research_graph().compile(checkpointer=_memory)
logger.info(f"Compiled app checkpointer: {_app.checkpointer}")


from pydantic import BaseModel, Field

# =============================================================================
# Input Validation & Guardrails
# =============================================================================


class ResearchInput(BaseModel):
    """Strict input schema for the research workflow."""

    repo_url: str = Field(..., description="The GitHub URL to analyze")
    request: str = Field(..., description="The specific research question or goal")
    thread_id: str | None = Field(None, description="Optional thread ID for checkpointing")
    visualize: bool = Field(False, description="Generate diagram only")


async def run_research_workflow(
    repo_url: str,
    request: str = "Analyze the architecture",
    thread_id: str | None = None,
    visualize: bool = False,
) -> dict[str, Any]:
    """
    Run the sharded research workflow with safety guardrails.

    Uses unified Rust LanceDB CheckpointStore for persistent state.
    Auto-corrects common LLM hallucinations (e.g., 'query' -> 'request').
    """
    # 1. Self-Correction Layer: Validate and cast inputs
    try:
        # If called from Kernel, arguments might be a dict or kwargs
        # This wrapper handles the canonical implementation
        validated = ResearchInput(
            repo_url=repo_url, request=request, thread_id=thread_id, visualize=visualize
        )
    except Exception as e:
        logger.error(f"Input Validation Error: {e}")
        return {"error": f"Invalid arguments: {e}. Required: repo_url, request", "steps": 0}

    # Handle visualize mode
    if validated.visualize:
        return {"diagram": visualize_workflow()}

    # Generate unique workflow_id using timestamp to avoid reusing old checkpoints
    workflow_id = validated.thread_id or f"research-{int(time.time() * 1000)}"
    logger.info(
        "Running sharded research workflow",
        repo_url=validated.repo_url,
        request=validated.request,
        workflow_id=workflow_id,
    )

    # Try to load existing state from checkpoint store
    saved_state = load_workflow_state(_WORKFLOW_TYPE, workflow_id)

    if saved_state:
        logger.info(
            "Resuming workflow from checkpoint",
            workflow_id=workflow_id,
            steps=saved_state.get("steps", 0),
        )
        initial_state = ResearchState(
            request=saved_state.get("request", validated.request),
            repo_url=saved_state.get("repo_url", validated.repo_url),
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
            request=validated.request,
            repo_url=validated.repo_url,
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

    logger.info(f"[Graph] Initial state prepared, steps={initial_state['steps']}")

    try:
        config: dict = {"configurable": {"thread_id": workflow_id}}
        logger.info(f"[Graph] Invoking LangGraph with workflow_id={workflow_id}")
        result = await _app.ainvoke(initial_state, config=config)
        logger.info(f"[Graph] LangGraph returned, result keys={list(result.keys())}")

        # Save final state to checkpoint store
        save_workflow_state(
            _WORKFLOW_TYPE,
            workflow_id,
            dict(result),
            metadata={"repo_url": validated.repo_url, "request": validated.request},
        )

        return result
    except Exception as e:
        logger.error("Workflow failed", error=str(e), exc_info=True)
        return {"error": str(e), "steps": initial_state.get("steps", 1)}


# =============================================================================
# Visualization
# =============================================================================


def _research_diagram() -> str:
    """Generate a Mermaid diagram of the research workflow."""
    return r"""graph TD
    A[Start: researcher.run_research repo_url=...] --> B[node_setup: Clone & Map]
    B --> C[node_architect: Plan Shards]
    C --> D[node_process_shard: Process First Shard]
    D --> E{Router: More Shards?}
    E -->|Yes| D
    E -->|No| F[node_synthesize: Generate index.md]
    F --> G[Done]

    subgraph Loop [Shard Processing Loop]
        D
        E
    end

    style A fill:#e1f5fe
    style B fill:#f3e5f5
    style C fill:#e8f5e8
    style D fill:#fff3e0
    style F fill:#e0f7fa
    style G fill:#fce4ec"""


# Register workflow for visualization
_RESEARCH_DIAGRAM = _research_diagram()
register_workflow("research", _RESEARCH_DIAGRAM)


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
