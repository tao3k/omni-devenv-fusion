"""
research_entry.py - Entry point for Sharded Deep Research Workflow

Uses shared WorkflowStateStore for persistent chunk state:
- Master and child chunk sessions share one common persistence API

Chunked mode (like knowledge recall): action=start | shard | synthesize
so the LLM can drive one step per call instead of one blocking run.
"""

from __future__ import annotations

import asyncio
from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.api.tool_context import run_with_heartbeat
from omni.foundation.config.logging import get_logger
from omni.foundation.context_delivery import WorkflowStateStore
from omni.foundation.runtime.skill_optimization import resolve_optional_int_from_setting
from omni.langgraph.chunked import (
    ChunkedWorkflowEngine,
    build_child_work_items,
    build_chunk_plan_from_queue,
    build_chunked_workflow_error_payload,
    build_summary_payload_from_chunked_result,
    build_summary_payload_from_chunked_step_result,
    extract_chunk_plan,
    normalize_selected_ids,
    run_chunked_action_dispatch,
    run_chunked_auto_complete,
    run_chunked_child_step,
    run_chunked_complete_from_session,
    run_chunked_fanout_shard,
    run_chunked_fanout_synthesize,
)

from .research_graph import (
    _WORKFLOW_TYPE,
    RESEARCH_CHUNKED_WORKFLOW_TYPE,
    run_one_shard,
    run_research_workflow,
    run_setup_and_architect,
    run_synthesize_only,
)

logger = get_logger("researcher.entry")
_RESEARCH_CHUNKED_STORE = WorkflowStateStore(RESEARCH_CHUNKED_WORKFLOW_TYPE)


def _get_workflow_id(repo_url: str) -> str:
    """Generate consistent workflow_id from repo_url."""
    return f"research-{hash(repo_url) % 10000}"


def _chunk_state_id(session_id: str, chunk_id: str) -> str:
    """Build child workflow id for one shard chunk."""
    return f"{session_id}:{chunk_id}"


def _save_chunked_state(workflow_id: str, state: dict[str, Any]) -> None:
    """Persist chunked state via common workflow store."""
    _RESEARCH_CHUNKED_STORE.save(workflow_id, state)


def _load_chunked_state(workflow_id: str) -> dict[str, Any] | None:
    """Load chunked state from common workflow store."""
    loaded = _RESEARCH_CHUNKED_STORE.load(workflow_id)
    return loaded if isinstance(loaded, dict) else None


def _build_research_chunked_engine(
    repo_url: str,
    request: str,
) -> ChunkedWorkflowEngine:
    """Create common chunked engine bound to researcher workflow handlers."""

    def _prepare_start_state(state: dict[str, Any], _session_id: str) -> dict[str, Any]:
        return {
            **state,
            "chunk_plan": _build_chunk_plan(state),
        }

    def _after_start_save(session_id: str, state: dict[str, Any]) -> None:
        chunk_plan = _get_chunk_plan(state)
        for child_id, child_state in build_child_work_items(
            session_id=session_id,
            chunk_plan=chunk_plan,
            base_state=state,
            build_child_id=_chunk_state_id,
        ):
            _save_chunked_state(child_id, child_state)

    def _build_start_response(_session_id: str, state: dict[str, Any]) -> dict[str, Any]:
        chunk_plan = _get_chunk_plan(state)
        shard_count = len(chunk_plan)
        return {
            "shard_count": shard_count,
            "chunk_plan": chunk_plan,
            "harvest_dir": state.get("harvest_dir", ""),
            "next_action": (
                "Call action=shard with session_id + chunk_id (or chunk_ids for batch parallel), "
                f"then action=synthesize with the same session_id once all {shard_count} chunks finish."
            ),
        }

    return ChunkedWorkflowEngine(
        workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
        run_start=lambda: run_setup_and_architect(repo_url, request),
        run_step=run_one_shard,
        run_synthesize=run_synthesize_only,
        queue_key="shards_queue",
        store=_RESEARCH_CHUNKED_STORE,
        prepare_start_state=_prepare_start_state,
        after_start_save=_after_start_save,
        build_start_response=_build_start_response,
    )


def _build_chunk_plan(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Build deterministic chunk ids from architect shards_queue."""
    queue = state.get("shards_queue", [])
    if not isinstance(queue, list):
        return []
    return build_chunk_plan_from_queue(queue)


def _get_chunk_plan(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract validated chunk plan from state."""
    return extract_chunk_plan(state)


def _normalize_requested_chunk_ids(
    chunk_id: str = "",
    chunk_ids: list[str] | None = None,
) -> list[str]:
    """Merge single and multi chunk selectors into one deduplicated list."""
    return normalize_selected_ids(single_id=chunk_id, selected_ids=chunk_ids)


async def _run_research_chunked(
    repo_url: str,
    request: str,
    action: str,
    session_id: str,
    chunk_id: str = "",
    chunk_ids: list[str] | None = None,
    max_concurrent: int | None = None,
) -> dict[str, Any]:
    """
    Execute one step of the chunked research workflow.
    action=start: run setup + architect, persist state, return session_id and shard_count.
    action=shard: load state, process next shard, persist, return shard result and remaining count.
    action=synthesize: load state, run synthesize, return final summary.
    """

    async def _on_start() -> dict[str, Any]:
        engine = _build_research_chunked_engine(repo_url, request)
        return await engine.run_step(
            session_id="",
            action="start",
            auto_complete=False,
        )

    async def _on_shard(sid: str, loaded: dict[str, Any]) -> dict[str, Any]:
        chunk_plan = _get_chunk_plan(loaded)
        requested_chunk_ids = _normalize_requested_chunk_ids(chunk_id=chunk_id, chunk_ids=chunk_ids)

        if chunk_plan:
            resolved_max_concurrent = resolve_optional_int_from_setting(
                max_concurrent,
                setting_key="researcher.max_concurrent",
            )

            async def _process_selected(selected_chunk_id: str) -> dict[str, Any]:
                return await run_chunked_child_step(
                    session_id=sid,
                    chunk_id=selected_chunk_id,
                    load_state=_load_chunked_state,
                    save_state=_save_chunked_state,
                    run_step=run_one_shard,
                    build_child_id=_chunk_state_id,
                    queue_key="shards_queue",
                    current_key="current_shard",
                )

            return await run_with_heartbeat(
                run_chunked_fanout_shard(
                    workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
                    session_id=sid,
                    chunk_plan=chunk_plan,
                    requested_chunk_ids=requested_chunk_ids,
                    process_selected=_process_selected,
                    load_state=_load_chunked_state,
                    build_child_id=_chunk_state_id,
                    id_key="chunk_id",
                    queue_key="shards_queue",
                    summaries_key="shard_analyses",
                    max_concurrent=resolved_max_concurrent,
                ),
            )

        # Try common engine path first.
        engine = _build_research_chunked_engine(repo_url, request)
        step_result = await engine.run_step(
            session_id=sid,
            action="shard",
            auto_complete=False,
        )
        if step_result.get("success"):
            return step_result

        error_text = str(step_result.get("error", "") or "")
        if "No state found for this session_id" not in error_text:
            return step_result

        # Recovery fallback for legacy/master-only state without persisted session:
        # run one shard directly and persist back to the same session id.
        state_or_coro = run_one_shard(loaded)
        state = await state_or_coro if asyncio.iscoroutine(state_or_coro) else state_or_coro
        if not isinstance(state, dict):
            return build_chunked_workflow_error_payload(
                error=f"run_one_shard must return dict state, got {type(state).__name__}",
                workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
                extra={"session_id": sid},
            )
        if state.get("error"):
            return build_chunked_workflow_error_payload(
                error=str(state["error"]),
                workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
                extra={"session_id": sid},
            )

        _save_chunked_state(sid, state)
        queue = state.get("shards_queue", [])
        chunks_remaining = len(queue) if isinstance(queue, list) else 0
        current = state.get("current_shard") or {}
        return {
            "success": True,
            "session_id": sid,
            "chunk_processed": str(current.get("name", "")),
            "chunks_remaining": chunks_remaining,
            "workflow_type": RESEARCH_CHUNKED_WORKFLOW_TYPE,
            "next_action": (
                "Call action=shard again with this session_id"
                if chunks_remaining > 0
                else "Call action=synthesize with this session_id"
            ),
        }

    async def _on_synthesize(sid: str, loaded: dict[str, Any]) -> dict[str, Any]:
        chunk_plan = _get_chunk_plan(loaded)
        if chunk_plan:
            return await run_with_heartbeat(
                run_chunked_fanout_synthesize(
                    workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
                    session_id=sid,
                    loaded_state=loaded,
                    chunk_plan=chunk_plan,
                    run_synthesize=run_synthesize_only,
                    load_state=_load_chunked_state,
                    build_child_id=_chunk_state_id,
                    id_key="chunk_id",
                    queue_key="shards_queue",
                    summaries_key="shard_analyses",
                )
            )
        # Try common engine path first.
        engine = _build_research_chunked_engine(repo_url, request)
        step_result = await engine.run_step(
            session_id=sid,
            action="synthesize",
            auto_complete=False,
        )
        if step_result.get("success"):
            return build_summary_payload_from_chunked_step_result(
                step_result,
                workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
                session_id=sid,
                state_error_key="error",
            )

        error_text = str(step_result.get("error", "") or "")
        if "No state found for this session_id" not in error_text:
            return step_result

        # Recovery fallback for legacy/master-only state without persisted session.
        synth_or_coro = run_synthesize_only(loaded)
        synth_state = await synth_or_coro if asyncio.iscoroutine(synth_or_coro) else synth_or_coro
        step_result = (
            {"success": True, "state": synth_state}
            if isinstance(synth_state, dict)
            else {"success": True, "result": synth_state}
        )
        return build_summary_payload_from_chunked_step_result(
            step_result,
            workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
            session_id=sid,
            state_error_key="error",
        )

    return await run_chunked_action_dispatch(
        action=action,
        session_id=session_id,
        workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
        load_state=_load_chunked_state,
        on_start=_on_start,
        on_shard=_on_shard,
        on_synthesize=_on_synthesize,
    )


async def _run_research_chunked_complete_remainder(session_id: str) -> dict[str, Any]:
    """
    Load state, run all remaining shards + synthesize, return final result.

    Used when LLM continues with action=shard/synthesize (e.g. user retries after
    max_tool_rounds). Completes in one call instead of N rounds.
    """
    result = await run_chunked_complete_from_session(
        workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
        session_id=session_id,
        run_start=lambda: {},
        run_step=run_one_shard,
        run_synthesize=run_synthesize_only,
        queue_key="shards_queue",
        store=_RESEARCH_CHUNKED_STORE,
    )

    # Recovery path: if checkpoint session is missing but master state still exists,
    # resume directly from the stored state and complete remaining shards.
    if not result.get("success"):
        error_text = str(result.get("error", "") or "")
        if "No state found for this session_id" in error_text:
            loaded = _load_chunked_state(session_id)
            if isinstance(loaded, dict):
                state = loaded
                loop_guard = 0
                while True:
                    queue = state.get("shards_queue", [])
                    if not isinstance(queue, list) or not queue:
                        break
                    loop_guard += 1
                    if loop_guard > 256:
                        return build_chunked_workflow_error_payload(
                            error="Too many shard iterations while resuming chunked research workflow.",
                            workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
                            extra={"session_id": session_id},
                        )
                    step_or_coro = run_one_shard(state)
                    stepped = (
                        await step_or_coro if asyncio.iscoroutine(step_or_coro) else step_or_coro
                    )
                    if not isinstance(stepped, dict):
                        return build_chunked_workflow_error_payload(
                            error=f"run_one_shard must return dict state, got {type(stepped).__name__}",
                            workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
                            extra={"session_id": session_id},
                        )
                    if stepped.get("error"):
                        return build_chunked_workflow_error_payload(
                            error=str(stepped["error"]),
                            workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
                            extra={"session_id": session_id},
                        )
                    state = stepped

                synth_or_coro = run_synthesize_only(state)
                synth_state = (
                    await synth_or_coro if asyncio.iscoroutine(synth_or_coro) else synth_or_coro
                )
                result = (
                    {"success": True, "state": synth_state}
                    if isinstance(synth_state, dict)
                    else {"success": True, "result": synth_state}
                )

    return build_summary_payload_from_chunked_result(
        result,
        workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
    )


async def _run_research_chunked_auto_complete(
    repo_url: str,
    request: str,
) -> dict[str, Any]:
    """
    Run full research workflow in one call (helper path, not default entry behavior).

    Uses core run_chunked_auto_complete to avoid N+2 agent rounds.
    """

    def _run_start() -> Any:
        return run_setup_and_architect(repo_url, request)

    result = await run_chunked_auto_complete(
        RESEARCH_CHUNKED_WORKFLOW_TYPE,
        _run_start,
        run_one_shard,
        run_synthesize_only,
        queue_key="shards_queue",
    )
    return build_summary_payload_from_chunked_result(
        result,
        workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
    )


@skill_command(
    name="git_repo_analyer",
    description="""
    Research a git repository: clone, analyze by shards, and produce an index.

    This autonomously analyzes large repositories using a Map-Plan-Loop-Synthesize pattern:

    1. **Setup**: Clone repository and generate file tree map
    2. **Architect (Plan)**: LLM breaks down the repo into 3-5 logical shards (subsystems)
    3. **Process Shard (Loop)**: For each shard - compress with repomix + analyze with LLM
    4. **Synthesize**: Generate index.md linking all shard analyses

    This approach handles large codebases that exceed LLM context limits by analyzing
    one subsystem at a time, then combining results.

    Args:
        - repo_url: str - Git repository URL to analyze (required)
        - request: str = "Analyze the architecture" - Specific analysis goal
        - visualize: bool = false - If true, return the workflow diagram instead of running
        - chunked: bool = false - If true, use step-by-step actions (start -> shard -> synthesize).
          action=start runs setup+architect only and returns session_id + chunk_plan.
        - action: str = "" - When chunked: "start" | "shard" | "synthesize"
        - session_id: str = "" - When chunked: required for "shard" and "synthesize" (from start)
        - chunk_id: str = "" - When chunked + action=shard: run exactly this chunk id (e.g. "c1")
        - chunk_ids: list[str] | None = None - When chunked + action=shard: run selected chunk ids in parallel
          (if omitted, all pending chunk ids run in parallel)
        - parallel_all: bool = true - Run all shards in parallel (ignore deps); faster wall clock
        - max_concurrent: int | null - Max concurrent shard LLM calls; null = unbounded (or from settings)

    Returns:
        dict with success status, harvest directory path, and shard summaries
    """,
    # MCP Annotations for LLM context
    category="research",
    read_only=False,
    destructive=False,
    idempotent=True,
    open_world=True,
)
async def run_research_graph(
    repo_url: str,
    request: str = "Analyze the architecture",
    visualize: bool = False,
    chunked: bool = False,
    action: str = "",
    session_id: str = "",
    chunk_id: str = "",
    chunk_ids: list[str] | None = None,
    parallel_all: bool = True,
    max_concurrent: int | None = None,
) -> dict[str, Any]:
    """
    Execute the Sharded Deep Research workflow.

    When chunked=False (default): blocking run (setup -> architect -> shards -> synthesize).
    When chunked=True: one step per call via action=start | shard | synthesize.
    """
    logger.info(
        "Sharded research workflow invoked",
        repo_url=repo_url,
        request=request,
        chunked=chunked,
        action=action or "(full)",
    )

    workflow_id = _get_workflow_id(repo_url)

    # Chunked mode: one step per MCP call (like knowledge recall).
    # action=start runs setup+architect only, then caller drives shard/synthesize.
    if chunked and action:
        try:
            return await _run_research_chunked(
                repo_url=repo_url,
                request=request,
                action=action,
                session_id=session_id,
                chunk_id=chunk_id,
                chunk_ids=chunk_ids,
                max_concurrent=max_concurrent,
            )
        except Exception as e:
            logger.error("Chunked research step failed", error=str(e))
            return build_chunked_workflow_error_payload(
                error=str(e),
                workflow_type=RESEARCH_CHUNKED_WORKFLOW_TYPE,
            )

    # Full blocking run
    logger.info("Locking context for Research Workflow", repo_url=repo_url, workflow_id=workflow_id)
    try:
        result = await run_research_workflow(
            repo_url=repo_url,
            request=request,
            visualize=visualize,
            parallel_all=parallel_all,
            max_concurrent=max_concurrent,
        )

        if visualize and "diagram" in result:
            return {
                "success": True,
                "diagram": result["diagram"],
                "workflow_id": workflow_id,
                "workflow_type": _WORKFLOW_TYPE,
            }

        error = result.get("error")
        if error:
            return build_chunked_workflow_error_payload(
                error=str(error),
                workflow_type=_WORKFLOW_TYPE,
                extra={
                    "steps": result.get("steps", 0),
                    "workflow_id": workflow_id,
                },
            )

        # Extract harvest directory from messages
        harvest_dir = result.get("harvest_dir", "")
        shard_analyses = result.get("shard_analyses", [])
        revision = result.get("repo_revision", "")

        # Format summary from messages
        messages = result.get("messages", [])
        summary = ""
        if messages:
            summary = messages[0].get("content", "")

        return {
            "success": True,
            "harvest_dir": harvest_dir,
            "revision": revision,
            "shards_analyzed": len(shard_analyses),
            "shard_summaries": shard_analyses,
            "summary": summary,
            "steps": result.get("steps", 0),
            "workflow_id": workflow_id,
            "workflow_type": _WORKFLOW_TYPE,
        }

    except Exception as e:
        logger.info("Workflow failed. Releasing lock.")
        logger.error("Research workflow failed", error=str(e))
        return build_chunked_workflow_error_payload(
            error=str(e),
            workflow_type=_WORKFLOW_TYPE,
            extra={"workflow_id": workflow_id},
        )


__all__ = ["run_research_graph"]
