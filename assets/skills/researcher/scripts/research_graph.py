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
from typing import Annotated, Any, NotRequired, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from omni.core.context import create_planner_orchestrator
from omni.foundation.api.handlers import graph_node
from omni.foundation.api.tool_context import run_with_heartbeat
from omni.foundation.config.logging import get_logger
from omni.foundation.context_delivery import WorkflowStateStore
from omni.foundation.runtime.skill_optimization import resolve_optional_int_from_setting
from omni.foundation.services.llm.client import InferenceClient
from omni.langgraph.parallel import build_execution_levels, run_parallel_levels
from omni.langgraph.visualize import register_workflow, visualize_workflow

logger = get_logger("researcher.graph")


# LLM call tracking
_llm_call_counter = 0


async def _llm_complete(
    client: InferenceClient,
    system_prompt: str,
    user_query: str,
    stage: str,
    extra_params: dict[str, Any] | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Make LLM call with full logging of parameters."""
    global _llm_call_counter
    _llm_call_counter += 1
    call_id = _llm_call_counter

    # Get client config (allow override for shard analysis to cap response time)
    model = client.model
    actual_max_tokens = max_tokens if max_tokens is not None else client.max_tokens
    timeout = client.timeout

    logger.info(
        f"[LLM] {stage} (call #{call_id})",
        call_id=call_id,
        stage=stage,
        model=model,
        max_tokens=actual_max_tokens,
        timeout=timeout,
        system_prompt_len=len(system_prompt),
        user_query_len=len(user_query),
        **(extra_params or {}),
    )

    # Log truncated user query preview
    query_preview = (
        user_query[:200].replace("\n", " ") + "..."
        if len(user_query) > 200
        else user_query.replace("\n", " ")
    )
    logger.debug(f"[LLM] Query preview: {query_preview}")

    start_time = time.perf_counter()
    response = await client.complete(
        system_prompt=system_prompt,
        user_query=user_query,
        max_tokens=actual_max_tokens,
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
_RESEARCH_STATE_STORE = WorkflowStateStore(_WORKFLOW_TYPE)

# Chunked workflow: one step per MCP call (like knowledge recall)
RESEARCH_CHUNKED_WORKFLOW_TYPE = "research_chunked"

# Shard analysis limits (keep each shard under MCP tool timeout ~180s)
SHARD_MAX_INPUT_CHARS = 28_000  # Truncate repomix output before LLM
SHARD_MAX_OUTPUT_TOKENS = 4096  # Cap response length for faster completion

# Efficient sharding: enforce size so each shard finishes quickly and predictably
MAX_FILES_PER_SHARD = 5  # Split any shard with more files into multiple shards
MAX_TOTAL_FILES = 30  # Cap total files across all shards (avoid huge repos in one run)
MIN_FILES_TO_MERGE = 2  # Shards with ≤ this many files can be merged into one

# Parallel shard processing (Codex-style): run all shards concurrently.
# Shard count is decided by architect (LLM); no artificial concurrency cap.


def _get_orchestrator():
    """Get cached ContextOrchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = create_planner_orchestrator()
        logger.info("ResearchContextOrchestrator initialized (Rust-powered)")
    return _orchestrator


async def _build_system_prompt(skill_name: str, state: dict[str, Any]) -> str:
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


def _get_research_module():
    """Lazy import research module functions (handles both skill loader and direct run).

    Uses SKILLS_DIR() API for consistent skill directory resolution.
    When running via skill loader: uses 'researcher.scripts.research'
    When running directly: uses relative import from scripts directory
    """
    import sys

    # Use SKILLS_DIR API for consistent skill directory resolution
    from omni.foundation.config.skills import SKILLS_DIR

    scripts_dir = SKILLS_DIR("researcher")
    research_path = str(scripts_dir)

    # Ensure scripts directory is in path
    if research_path not in sys.path:
        sys.path.insert(0, research_path)

    try:
        # Try package import first (skill loader)
        from researcher.scripts.research import (
            clone_repo,
            init_harvest_structure,
            parse_repo_url,
            repomix_compress_shard,
            repomix_map,
            save_index,
            save_shard_result,
        )
    except ImportError:
        # Fallback to direct import (direct run)
        from research import (
            clone_repo,
            init_harvest_structure,
            parse_repo_url,
            repomix_compress_shard,
            repomix_map,
            save_index,
            save_shard_result,
        )

    return {
        "clone_repo": clone_repo,
        "init_harvest_structure": init_harvest_structure,
        "parse_repo_url": parse_repo_url,
        "repomix_compress_shard": repomix_compress_shard,
        "repomix_map": repomix_map,
        "save_index": save_index,
        "save_shard_result": save_shard_result,
    }


# =============================================================================
# State Definition
# =============================================================================


class ShardDef(TypedDict):
    """Definition of an analysis shard. May include optional 'dependencies' (list of shard names)."""

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
    repo_revision: str  # Git commit hash of the analyzed revision
    repo_revision_date: str  # Git commit date
    repo_owner: str  # Repository owner (e.g., "anthropics")
    repo_name: str  # Repository name (e.g., "claude-code")
    file_tree: str  # Repository structure map

    # Planning Stage
    shards_queue: list[ShardDef]  # Shards to process (Plan output)

    # Loop Stage (per shard)
    current_shard: ShardDef | None  # Shard being processed
    shard_counter: int  # For ordering files (01_, 02_, etc.)
    shard_analyses: list[str]  # Accumulated shard summaries

    # Final Stage
    harvest_dir: str  # Path to .data/harvested/...
    final_report: str  # Complete analysis

    # Cached Context (built once in architect stage)
    system_prompt: str  # Cached system prompt (persona + skill context)

    # Optimization: when True, ignore dependencies and run all shards in parallel
    parallel_all: NotRequired[bool]
    # Max concurrent shard processing (semaphore). None = unbounded.
    max_concurrent: NotRequired[int | None]

    # Control
    messages: Annotated[list[dict], operator.add]
    steps: int
    error: str | None


# =============================================================================
# Node Functions
# =============================================================================


@graph_node(name="setup")
async def node_setup(state: ResearchState) -> dict:
    """Setup: Clone repository and generate file tree map using exa."""
    logger.info("[Graph] Setting up research...", url=state["repo_url"])

    try:
        # Lazy import research functions
        research = _get_research_module()

        # Parse owner and repo name from URL
        repo_url = state["repo_url"]
        repo_owner, repo_name = research["parse_repo_url"](repo_url)

        # Clone repository (now returns dict with path and revision)
        repo_info = research["clone_repo"](repo_url)
        path = repo_info["path"]
        revision = repo_info["revision"]
        revision_date = repo_info["date"]

        # Generate file tree map using exa with depth limit
        tree = _generate_tree_with_exa(path, max_depth=3)

        logger.info(
            "[Graph] Setup complete",
            path=path,
            owner=repo_owner,
            repo=repo_name,
            revision=revision,
            tree_length=len(tree),
        )

        return {
            "repo_path": path,
            "repo_revision": revision,
            "repo_revision_date": revision_date,
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "file_tree": tree,
            "steps": state["steps"] + 1,
        }

    except Exception as e:
        logger.error("[Graph] Setup failed", error=str(e))
        raise


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
                tree_lines.append(
                    f"{indent}{rel_path.split('/')[-1]}/"
                    if line.endswith("/")
                    else f"{indent}{rel_path}"
                )
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


@graph_node(name="architect")
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
        # Lazy import research functions
        research = _get_research_module()

        client = InferenceClient()
        file_tree = state.get("file_tree", "")
        request = state.get("request", "Analyze architecture")

        if not file_tree:
            raise ValueError("No file tree available for planning")

        prompt = f"""You are a Senior Software Architect. Analyze this repository structure and create a research plan.

RESEARCH GOAL: {request}

REPOSITORY STRUCTURE (from exa tree):
```
{file_tree}
```

YOUR TASK:
1. Identify 4-6 logical subsystems (prefer more, smaller shards so each finishes quickly).
2. For each subsystem, specify the EXACT file paths to analyze (be specific, not glob patterns).
3. Each file path must be relative to the repository root.
4. HARD LIMITS: At most 5 files per shard. Total files across all shards must not exceed 25.
   (Larger plans will be auto-split/trimmed; stay under limits for best results.)

Respond with a JSON array defining your shards:
```json
[
    {{
        "name": "Core Kernel",
        "files": ["src/core/main.py", "src/core/engine.py"],
        "description": "Main business logic and core engine",
        "dependencies": []
    }},
    {{
        "name": "API Layer",
        "files": ["src/api/routes.py", "src/api/handlers/user.go"],
        "description": "HTTP API and request handling",
        "dependencies": ["Core Kernel"]
    }}
]
```

GUIDELINES:
- BE SPECIFIC with file paths - use exact paths, not globs
- Focus on files most relevant to the research goal
- Maximum 5 files per shard; total files ≤ 25 across all shards
- Order shards from core functionality to peripheral
- OPTIONAL "dependencies": list of shard names that must be analyzed first.
  E.g. API Layer depends on Core Kernel. Shards with no deps run first; dependent shards run after.
  Omit or use [] for independent shards."""

        async def _architect_slow() -> tuple[dict, str]:
            system_prompt = await _build_system_prompt("researcher", state)
            llm_response = await _llm_complete(
                client=client,
                system_prompt=system_prompt,
                user_query=prompt,
                stage="architect",
                extra_params={"shard_planning": True},
            )
            return llm_response, system_prompt

        response, system_prompt = await run_with_heartbeat(_architect_slow())

        content = response.get("content", "").strip()
        logger.debug(
            "[Graph] Architect response",
            content_length=len(content),
            content_preview=content[:500] if content else "(empty)",
        )

        shards = _extract_json_list(content)

        if not shards:
            logger.warning(
                "[Graph] Failed to parse shards from LLM response, using fallback",
                content_preview=content[:200] if content else "(empty)",
            )
            # Fallback: single shard with repo root (let LLM analyze everything)
            shards = [
                {
                    "name": "Full Repository Analysis",
                    "files": [],  # Empty means analyze everything
                    "description": "Complete repository analysis",
                }
            ]

        # Convert to ShardDef objects (include optional dependencies from LLM)
        shard_defs: list[ShardDef] = []
        for s in shards:
            if isinstance(s, dict):
                defn: ShardDef = {
                    "name": s.get("name", "Unknown"),
                    "targets": s.get("files", []),
                    "description": s.get("description", ""),
                }
                deps = s.get("dependencies")
                if isinstance(deps, list) and deps:
                    defn["dependencies"] = [str(d) for d in deps]
                shard_defs.append(defn)
            else:
                shard_defs.append({"name": str(s), "targets": [], "description": str(s)})

        # Enforce efficient sharding: split oversized, cap total files, merge tiny
        shard_defs = _normalize_shards(shard_defs)

        logger.info("[Graph] Architecting complete", shard_count=len(shard_defs))

        # Initialize harvest directory for shard processing
        repo_owner = state.get("repo_owner", "unknown")
        repo_name = state.get("repo_name", "unknown")
        harvest_path = research["init_harvest_structure"](repo_owner, repo_name)
        harvest_dir = str(harvest_path)

        # Cache system prompt for subsequent shard processing
        result = {
            "shards_queue": shard_defs,
            "shard_counter": 0,
            "shard_analyses": [],
            "harvest_dir": harvest_dir,
            "system_prompt": system_prompt,  # Cache for shard processing
            "steps": state["steps"] + 1,
        }
        logger.info(
            f"[Graph] Architect returning: shards={len(shard_defs)}, harvest_dir={harvest_dir}"
        )
        return result

    except Exception as e:
        logger.error("[Graph] Architecting failed", error=str(e))
        raise


@graph_node(name="process_shard")
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
        logger.info(f"[Graph] Received shards_queue: {len(shards_queue)} items")
        if not shards_queue:
            raise ValueError("No shards in queue")

        # Get current shard
        shard = shards_queue[0]
        shard_name = shard["name"]
        files = shard["targets"]  # List of specific file paths chosen by LLM
        description = shard["description"]

        repo_path = state.get("repo_path", "")

        logger.info("[Graph] Processing shard", name=shard_name, file_count=len(files))

        async def _process_shard_body() -> dict:
            # Lazy import research functions
            research = _get_research_module()
            shard_id = state.get("shard_counter", 0) + 1

            # Step 1: Compress shard with repomix (run in executor so heartbeat can run)
            loop = asyncio.get_event_loop()
            compress_result = await loop.run_in_executor(
                None,
                lambda: research["repomix_compress_shard"](
                    path=repo_path,
                    targets=files,
                    shard_name=shard_name,
                    shard_id=shard_id,
                ),
            )

            xml_content = compress_result["xml_content"]
            token_count = compress_result.get("token_count", len(xml_content) // 4)

            # Step 2: Get cached system prompt (built once in architect phase)
            system_prompt = _get_cached_system_prompt(state)

            # Step 3: Analyze with LLM (tight input cap for MCP timeout)
            client = InferenceClient()
            truncated = xml_content[:SHARD_MAX_INPUT_CHARS]
            if len(xml_content) > SHARD_MAX_INPUT_CHARS:
                truncated += "\n\n[...truncated for analysis...]"

            prompt = f"""You are a Senior Tech Architect. Analyze this subsystem shard concisely.

Shard: {shard_name}
Focus: {description}

Research Goal: {state.get("request", "Analyze architecture")}

FILES IN THIS SHARD ({len(files)} files):
{", ".join(files) if files else "All files in repository"}

REPOMIX OUTPUT:
{truncated}

Produce a standalone Markdown section (concise; use bullets and short paragraphs):

## Architecture Overview
- Subsystem role and main responsibility
- Key design patterns

## Source Code Analysis
- Per significant file: purpose, key functions/classes, interactions

## Interfaces & Contracts
- Public APIs and how this subsystem communicates with others

## Key Insights
- Notable patterns, tech choices, potential concerns

Keep the section focused so it can be combined with other shard analyses."""

            response = await _llm_complete(
                client=client,
                system_prompt=system_prompt,
                user_query=prompt,
                stage=f"process_shard:{shard_name}",
                extra_params={
                    "shard_name": shard_name,
                    "file_count": len(files),
                    "files": files[:5] if files else [],
                },
                max_tokens=SHARD_MAX_OUTPUT_TOKENS,
            )

            analysis = response.get("content", "Error: No analysis generated")

            # Step 3: Save shard result
            counter = shard_id

            # Initialize harvest structure if needed
            harvest_dir = state.get("harvest_dir")
            if not harvest_dir:
                # Get owner and repo_name from state
                repo_owner = state.get("repo_owner", "unknown")
                repo_name = state.get("repo_name", "unknown")
                harvest_path = research["init_harvest_structure"](repo_owner, repo_name)
                harvest_dir = str(harvest_path)
            else:
                harvest_path = Path(harvest_dir)

            research["save_shard_result"](
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
                "shard_analyses": [*previous_summaries, summary],
                "harvest_dir": harvest_dir,
                "steps": state["steps"] + 1,
            }

        return await run_with_heartbeat(_process_shard_body())

    except Exception as e:
        logger.error("[Graph] Shard processing failed", error=str(e))
        raise


async def _process_single_shard(
    shard: ShardDef,
    shard_id: int,
    state: ResearchState,
) -> tuple[str, int]:
    """Process one shard: repomix compress + LLM analyze + save. Returns (summary, token_count)."""
    research = _get_research_module()
    shard_name = shard["name"]
    files = shard.get("targets", [])
    description = shard.get("description", "")
    repo_path = state.get("repo_path", "")
    harvest_dir = state.get("harvest_dir", "")
    repo_owner = state.get("repo_owner", "unknown")
    repo_name = state.get("repo_name", "")

    # Step 1: Compress with repomix (run in executor so event loop stays responsive)
    loop = asyncio.get_event_loop()
    compress_result = await loop.run_in_executor(
        None,
        lambda: research["repomix_compress_shard"](
            path=repo_path,
            targets=files,
            shard_name=shard_name,
            shard_id=shard_id,
        ),
    )
    xml_content = compress_result["xml_content"]
    token_count = compress_result.get("token_count", len(xml_content) // 4)

    # Step 2: LLM analyze
    system_prompt = _get_cached_system_prompt(state)
    client = InferenceClient()
    truncated = xml_content[:SHARD_MAX_INPUT_CHARS]
    if len(xml_content) > SHARD_MAX_INPUT_CHARS:
        truncated += "\n\n[...truncated for analysis...]"
    prompt = f"""You are a Senior Tech Architect. Analyze this subsystem shard concisely.

Shard: {shard_name}
Focus: {description}

Research Goal: {state.get("request", "Analyze architecture")}

FILES IN THIS SHARD ({len(files)} files):
{", ".join(files) if files else "All files in repository"}

REPOMIX OUTPUT:
{truncated}

Produce a standalone Markdown section (concise; use bullets and short paragraphs):

## Architecture Overview
- Subsystem role and main responsibility
- Key design patterns

## Source Code Analysis
- Per significant file: purpose, key functions/classes, interactions

## Interfaces & Contracts
- Public APIs and how this subsystem communicates with others

## Key Insights
- Notable patterns, tech choices, potential concerns

Keep the section focused so it can be combined with other shard analyses."""

    response = await _llm_complete(
        client=client,
        system_prompt=system_prompt,
        user_query=prompt,
        stage=f"process_shard:{shard_name}",
        extra_params={"shard_name": shard_name, "file_count": len(files), "files": files[:5]},
        max_tokens=SHARD_MAX_OUTPUT_TOKENS,
    )
    analysis = response.get("content", "Error: No analysis generated")

    # Step 3: Save shard result
    if not harvest_dir:
        harvest_path = research["init_harvest_structure"](repo_owner, repo_name)
        harvest_dir = str(harvest_path)
    else:
        harvest_path = Path(harvest_dir)
    research["save_shard_result"](
        base_dir=harvest_path,
        shard_id=shard_id,
        title=shard_name,
        content=analysis,
    )

    summary = f"- **[{shard_name}](./shards/{shard_id:02d}_{shard_name.lower().replace(' ', '_')}.md)**: {description} (~{token_count} tokens)"
    logger.info("[Graph] Shard processed (parallel)", name=shard_name, tokens=token_count)
    return summary, token_count


@graph_node(name="process_shards_parallel")
async def node_process_shards_parallel(state: ResearchState) -> dict:
    """
    Process shards with LLM-driven scheduling.

    Uses dependencies from architect: shards with no deps run first (parallel);
    dependent shards run in later levels. Within each level, shards run in parallel.
    """
    shards_queue = state.get("shards_queue", [])
    if not shards_queue:
        raise ValueError("No shards in queue")

    harvest_dir = state.get("harvest_dir", "")
    if not harvest_dir:
        research = _get_research_module()
        harvest_path = research["init_harvest_structure"](
            state.get("repo_owner", "unknown"),
            state.get("repo_name", "unknown"),
        )
        harvest_dir = str(harvest_path)

    parallel_all = state.get("parallel_all", True)
    levels = build_execution_levels(
        shards_queue,
        parallel_all=parallel_all,
        dep_key="dependencies",
        name_key="name",
    )
    if parallel_all:
        logger.info("[Graph] Processing shards (parallel_all)", shard_count=len(shards_queue))
    else:
        logger.info(
            "[Graph] Processing shards (LLM-scheduled)",
            levels=len(levels),
            level_sizes=[len(lev) for lev in levels],
        )

    max_concurrent = state.get("max_concurrent")

    async def _run_levels() -> list[str]:
        results = await run_parallel_levels(
            levels,
            _process_single_shard,
            state,
            return_exceptions=False,
            max_concurrent=max_concurrent,
        )
        return [r[0] for r in results]

    summaries = await run_with_heartbeat(_run_levels())

    return {
        "shards_queue": [],
        "shard_analyses": summaries,
        "harvest_dir": harvest_dir,
        "steps": state["steps"] + 1,
    }


def router_error(state: ResearchState) -> str:
    """Router: Check for error state and exit early."""
    if state.get("error"):
        logger.warning(f"[Graph] Aborting due to error: {state['error']}")
        return "abort"
    return "continue"


def router_loop(state: ResearchState) -> str:
    """Router: Decide whether to process another shard or synthesize."""
    if state.get("error"):
        return "abort"
    if len(state.get("shards_queue", [])) > 0:
        return "process_shard"
    return "synthesize"


@graph_node(name="synthesize")
async def node_synthesize(state: ResearchState) -> dict:
    """
    Synthesize: Generate final index.md with all shard summaries.

    Combines the accumulated shard analyses into a coherent report.
    """
    logger.info("[Graph] Synthesizing final report...")

    try:
        # Lazy import research functions
        research = _get_research_module()

        repo_name = state.get("repo_name", "")
        repo_url = state.get("repo_url", "")
        request = state.get("request", "Analyze architecture")
        harvest_dir = state.get("harvest_dir", "")
        shard_summaries = state.get("shard_analyses", [])
        revision = state.get("repo_revision", "")
        revision_date = state.get("repo_revision_date", "")

        if not harvest_dir:
            # Initialize harvest_dir from state (handles checkpoint recovery)
            repo_owner = state.get("repo_owner", "unknown")
            repo_name_for_dir = state.get("repo_name", "unknown")
            harvest_path = research["init_harvest_structure"](repo_owner, repo_name_for_dir)
            harvest_dir = str(harvest_path)
            logger.info(f"[Graph] Recovered harvest_dir from state: {harvest_dir}")

        # Generate index.md with revision info
        research["save_index"](
            base_dir=Path(harvest_dir),
            title=repo_name,
            repo_url=repo_url,
            request=request,
            shard_summaries=shard_summaries,
            revision=revision,
            revision_date=revision_date,
        )

        # Generate final summary message
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
        raise


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
        except json.JSONDecodeError as e:
            logger.debug(f"[Graph] JSON decode error: {e}, trying alternate parsing")

    # Try parsing entire response
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Log debug info for troubleshooting
    logger.debug(
        "[Graph] Failed to extract JSON list from response",
        content_preview=text[:500] if text else "(empty)",
        has_brackets=("[" in text and "]" in text),
    )

    return []


def _normalize_shards(shard_defs: list[ShardDef]) -> list[ShardDef]:
    """Enforce efficient sharding: split oversized shards, cap total files, merge tiny shards.

    Ensures each shard stays under MAX_FILES_PER_SHARD so repomix+LLM finish within
    MCP timeout, and total work is bounded by MAX_TOTAL_FILES.
    """
    if not shard_defs:
        return shard_defs

    split_map: dict[str, list[str]] = {}  # original_name -> [new names] when split

    def _with_deps(d: dict, deps: list[str] | None) -> dict:
        out = dict(d)
        if deps:
            out["dependencies"] = deps
        return out

    # Step 1: Split any shard with > MAX_FILES_PER_SHARD into multiple shards
    expanded: list[ShardDef] = []
    for shard in shard_defs:
        name = shard.get("name", "Unknown")
        targets = list(shard.get("targets", []))
        desc = shard.get("description", "")
        deps = shard.get("dependencies")
        if not targets:
            expanded.append(_with_deps({"name": name, "targets": [], "description": desc}, deps))
            continue
        new_names: list[str] = []
        for i in range(0, len(targets), MAX_FILES_PER_SHARD):
            chunk = targets[i : i + MAX_FILES_PER_SHARD]
            part_name = (
                f"{name} ({i // MAX_FILES_PER_SHARD + 1})"
                if len(targets) > MAX_FILES_PER_SHARD
                else name
            )
            new_names.append(part_name)
            expanded.append(
                _with_deps({"name": part_name, "targets": chunk, "description": desc}, deps)
            )
        if len(new_names) > 1:
            split_map[name] = new_names

    # Step 2: Cap total files (trim from end)
    total = 0
    capped: list[ShardDef] = []
    for s in expanded:
        if total >= MAX_TOTAL_FILES:
            break
        t = s.get("targets", [])
        budget = MAX_TOTAL_FILES - total
        take = t[:budget] if len(t) > budget else t
        if take or not capped:
            capped.append(
                _with_deps(
                    {
                        "name": s.get("name", "Unknown"),
                        "targets": take,
                        "description": s.get("description", ""),
                    },
                    s.get("dependencies"),
                )
            )
            total += len(take)

    # Step 3: Merge consecutive tiny shards (≤ MIN_FILES_TO_MERGE each) into one up to MAX_FILES_PER_SHARD
    merged: list[ShardDef] = []
    acc: list[str] = []
    acc_names: list[str] = []
    acc_desc = ""

    acc_deps: list[str] = []
    for s in capped:
        t = s.get("targets", [])
        n_files = len(t)
        if n_files <= MIN_FILES_TO_MERGE and len(acc) + n_files <= MAX_FILES_PER_SHARD:
            acc.extend(t)
            acc_names.append(s.get("name", ""))
            acc_desc = acc_desc or s.get("description", "")
            acc_deps = list(set(acc_deps) | set(s.get("dependencies", [])))
        else:
            if acc:
                merged.append(
                    _with_deps(
                        {
                            "name": " + ".join(acc_names)
                            if len(acc_names) > 1
                            else (acc_names[0] or "Merged"),
                            "targets": acc,
                            "description": acc_desc or "Combined small subsystems",
                        },
                        acc_deps if acc_deps else None,
                    )
                )
                acc = []
                acc_names = []
                acc_desc = ""
                acc_deps = []
            if n_files <= MIN_FILES_TO_MERGE:
                acc = list(t)
                acc_names = [s.get("name", "")]
                acc_desc = s.get("description", "")
                acc_deps = list(s.get("dependencies", []))
            else:
                merged.append(s)
    if acc:
        merged.append(
            _with_deps(
                {
                    "name": " + ".join(acc_names)
                    if len(acc_names) > 1
                    else (acc_names[0] or "Merged"),
                    "targets": acc,
                    "description": acc_desc or "Combined small subsystems",
                },
                acc_deps if acc_deps else None,
            )
        )

    # Step 4: Expand dependencies using split_map (dep "Core" -> ["Core (1)", "Core (2)"])
    final: list[ShardDef] = []
    for s in merged:
        deps = list(s.get("dependencies", []))
        expanded_deps: list[str] = []
        for d in deps:
            if d in split_map:
                expanded_deps.extend(split_map[d])
            else:
                expanded_deps.append(d)
        final.append(_with_deps(dict(s), expanded_deps if expanded_deps else None))

    logger.info(
        "[Graph] Shards normalized",
        original_count=len(shard_defs),
        normalized_count=len(final),
        total_files=sum(len(s.get("targets", [])) for s in final),
    )
    return final


# =============================================================================
# Graph Construction
# =============================================================================


def create_sharded_research_graph() -> StateGraph:
    """Create the Sharded Research StateGraph with error handling."""
    workflow = StateGraph(ResearchState)

    # Add nodes
    workflow.add_node("setup", node_setup)
    workflow.add_node("architect", node_architect)
    workflow.add_node("process_shards_parallel", node_process_shards_parallel)
    workflow.add_node("synthesize", node_synthesize)
    workflow.add_node("abort", lambda state: state)  # No-op abort node

    # Set entry point
    workflow.set_entry_point("setup")

    # setup -> architect (with error check)
    workflow.add_conditional_edges(
        "setup",
        router_error,
        {"continue": "architect", "abort": "abort"},
    )

    # architect -> process_shards_parallel (with error check)
    workflow.add_conditional_edges(
        "architect",
        router_error,
        {"continue": "process_shards_parallel", "abort": "abort"},
    )

    # process_shards_parallel -> synthesize (with error check)
    workflow.add_conditional_edges(
        "process_shards_parallel",
        router_error,
        {"continue": "synthesize", "abort": "abort"},
    )

    # synthesize -> END (with error check)
    workflow.add_conditional_edges(
        "synthesize",
        router_error,
        {"continue": END, "abort": "abort"},
    )

    # abort -> END
    workflow.add_edge("abort", END)

    return workflow


# Compile with Rust checkpoint for state persistence (shared singleton)
logger.info(f"Final checkpointer: {_memory}")
_app = create_sharded_research_graph().compile(checkpointer=_memory)
logger.info(f"Compiled app checkpointer: {_app.checkpointer}")

# =============================================================================
# Input Validation & Guardrails
# =============================================================================


class ResearchInput(BaseModel):
    """Strict input schema for the research workflow."""

    repo_url: str = Field(..., description="The GitHub URL to analyze")
    request: str = Field(..., description="The specific research question or goal")
    thread_id: str | None = Field(None, description="Optional thread ID for checkpointing")
    visualize: bool = Field(False, description="Generate diagram only")
    parallel_all: bool = Field(
        True, description="Run all shards in parallel (ignore deps); faster wall clock"
    )
    max_concurrent: int | None = Field(
        None, description="Max concurrent shard LLM calls; None = unbounded or from settings"
    )


async def run_research_workflow(
    repo_url: str,
    request: str = "Analyze the architecture",
    thread_id: str | None = None,
    visualize: bool = False,
    parallel_all: bool = True,
    max_concurrent: int | None = None,
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
            repo_url=repo_url,
            request=request,
            thread_id=thread_id,
            visualize=visualize,
            parallel_all=parallel_all,
            max_concurrent=max_concurrent,
        )
    except Exception as e:
        logger.error(f"Input Validation Error: {e}")
        return {"error": f"Invalid arguments: {e}. Required: repo_url, request", "steps": 0}

    # Resolve max_concurrent from explicit arg first, then settings.
    max_concurrent = resolve_optional_int_from_setting(
        validated.max_concurrent,
        setting_key="researcher.max_concurrent",
    )

    # Handle visualize mode
    if validated.visualize:
        return {"diagram": visualize_workflow()}

    # Generate workflow_id using repo_url hash (for resume support)
    workflow_id = f"research-{abs(hash(validated.repo_url)) % 100000}"
    logger.info(
        "Running sharded research workflow",
        repo_url=validated.repo_url,
        request=validated.request,
        workflow_id=workflow_id,
    )

    # Try to load existing state from checkpoint store
    saved_state = _RESEARCH_STATE_STORE.load(workflow_id)

    # Delete any existing failed checkpoint to start fresh
    if saved_state and saved_state.get("error"):
        logger.info(f"Deleting previous failed checkpoint: {workflow_id}")
        _RESEARCH_STATE_STORE.delete(workflow_id)
        saved_state = None

    if saved_state and saved_state.get("shards_queue"):
        logger.info(
            "Resuming workflow from checkpoint",
            workflow_id=workflow_id,
            steps=saved_state.get("steps", 0),
        )
        initial_state = ResearchState(
            request=saved_state.get("request", validated.request),
            repo_url=saved_state.get("repo_url", validated.repo_url),
            repo_path=saved_state.get("repo_path", ""),
            repo_revision=saved_state.get("repo_revision", ""),
            repo_revision_date=saved_state.get("repo_revision_date", ""),
            repo_owner=saved_state.get("repo_owner", ""),
            repo_name=saved_state.get("repo_name", ""),
            file_tree=saved_state.get("file_tree", ""),
            shards_queue=saved_state.get("shards_queue", []),
            current_shard=saved_state.get("current_shard"),
            shard_counter=saved_state.get("shard_counter", 0),
            shard_analyses=saved_state.get("shard_analyses", []),
            harvest_dir=saved_state.get("harvest_dir", ""),
            final_report=saved_state.get("final_report", ""),
            steps=saved_state.get("steps", 0),
            messages=saved_state.get("messages", []),
            error=saved_state.get("error"),
            parallel_all=saved_state.get("parallel_all", validated.parallel_all),
            max_concurrent=saved_state.get("max_concurrent", max_concurrent),
        )
    else:
        # Start fresh if no valid checkpoint
        logger.info("Starting new workflow (no valid checkpoint found)")
        initial_state = ResearchState(
            request=validated.request,
            repo_url=validated.repo_url,
            repo_path="",
            repo_revision="",
            repo_revision_date="",
            repo_owner="",
            repo_name="",
            file_tree="",
            shards_queue=[],
            current_shard=None,
            shard_counter=0,
            shard_analyses=[],
            harvest_dir="",
            final_report="",
            steps=0,
            messages=[],
            error=None,
            parallel_all=validated.parallel_all,
            max_concurrent=max_concurrent,
        )

    logger.info(f"[Graph] Initial state prepared, steps={initial_state['steps']}")

    try:
        config: dict = {"configurable": {"thread_id": workflow_id}}
        logger.info(f"[Graph] Invoking LangGraph with workflow_id={workflow_id}")
        result = await _app.ainvoke(initial_state, config=config)
        logger.info(f"[Graph] LangGraph returned, result keys={list(result.keys())}")

        # Save final state to checkpoint store
        _RESEARCH_STATE_STORE.save(
            workflow_id,
            dict(result),
            metadata={"repo_url": validated.repo_url, "request": validated.request},
        )

        return result
    except Exception as e:
        logger.error("Workflow failed", error=str(e), exc_info=True)
        raise


# =============================================================================
# Chunked workflow (one step per MCP call, like knowledge recall)
# =============================================================================


def _chunked_initial_state(repo_url: str, request: str) -> ResearchState:
    """Build initial state for chunked workflow (setup + architect)."""
    return ResearchState(
        request=request,
        repo_url=repo_url,
        repo_path="",
        repo_revision="",
        repo_revision_date="",
        repo_owner="",
        repo_name="",
        file_tree="",
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


async def run_setup_and_architect(repo_url: str, request: str) -> dict[str, Any]:
    """
    Run setup then architect only. Used for chunked action=start.

    Returns state with shards_queue, harvest_dir, system_prompt populated.
    Caller must persist state and return session_id + shard_count to the LLM.
    """
    initial = _chunked_initial_state(repo_url, request)
    after_setup = {**initial, **await node_setup(initial)}
    if after_setup.get("error"):
        return after_setup
    after_architect = {**after_setup, **await node_architect(after_setup)}
    return after_architect


async def run_one_shard(state: ResearchState) -> dict[str, Any]:
    """
    Process the next shard in queue. Used for chunked action=shard.

    State must have shards_queue with at least one item.
    Returns updated state (shards_queue popped, shard_analyses appended).
    """
    if not state.get("shards_queue"):
        return {**state, "error": "No shards in queue"}
    return {**state, **await node_process_shard(state)}


async def run_synthesize_only(state: ResearchState) -> dict[str, Any]:
    """
    Run synthesize node only. Used for chunked action=synthesize.

    State should have shard_analyses and harvest_dir; shards_queue may be empty.
    """
    return {**state, **await node_synthesize(state)}


# =============================================================================
# Visualization
# =============================================================================


def _research_diagram() -> str:
    """Generate a Mermaid diagram of the research workflow."""
    return r"""graph TD
    A[Start: researcher.run_research repo_url=...] --> B[node_setup: Clone & Map]
    B --> C[node_architect: Plan Shards]
    C --> D[node_process_shards_parallel: Process All Shards]
    D --> F[node_synthesize: Generate index.md]
    F --> G[Done]

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
    "RESEARCH_CHUNKED_WORKFLOW_TYPE",
    "ResearchState",
    "ShardDef",
    "create_sharded_research_graph",
    "node_architect",
    "node_process_shard",
    "node_process_shards_parallel",
    "node_setup",
    "node_synthesize",
    "run_one_shard",
    "run_research_workflow",
    "run_setup_and_architect",
    "run_synthesize_only",
]
