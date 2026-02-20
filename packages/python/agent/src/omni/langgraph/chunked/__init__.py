"""Reusable chunked processing namespace with lazy exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "DEFAULT_MAX_PER_CHUNK": (".state", "DEFAULT_MAX_PER_CHUNK"),
    "DEFAULT_MAX_TOTAL": (".state", "DEFAULT_MAX_TOTAL"),
    "DEFAULT_MIN_TO_MERGE": (".state", "DEFAULT_MIN_TO_MERGE"),
    "ChunkConfig": (".state", "ChunkConfig"),
    "ChunkedWorkflowEngine": (".engine", "ChunkedWorkflowEngine"),
    "ChunkedWorkflowState": (".state", "ChunkedWorkflowState"),
    "build_child_work_items": (".plan", "build_child_work_items"),
    "build_chunk_plan_from_queue": (".plan", "build_chunk_plan_from_queue"),
    "build_chunked_action_error_payload": (".runner", "build_chunked_action_error_payload"),
    "build_chunked_dispatch_error_payload": (".runner", "build_chunked_dispatch_error_payload"),
    "build_chunked_session_store_adapters": (".runner", "build_chunked_session_store_adapters"),
    "build_chunked_unavailable_payload": (".runner", "build_chunked_unavailable_payload"),
    "build_chunked_workflow_error_payload": (".runner", "build_chunked_workflow_error_payload"),
    "build_full_document_payload": (".runner", "build_full_document_payload"),
    "build_summary_payload_from_chunked_result": (
        ".result",
        "build_summary_payload_from_chunked_result",
    ),
    "build_summary_payload_from_chunked_step_result": (
        ".result",
        "build_summary_payload_from_chunked_step_result",
    ),
    "build_summary_payload_from_state": (".result", "build_summary_payload_from_state"),
    "collect_chunk_progress": (".plan", "collect_chunk_progress"),
    "collect_full_document_rows": (".runner", "collect_full_document_rows"),
    "create_chunked_lazy_start_payload": (".runner", "create_chunked_lazy_start_payload"),
    "extract_chunk_plan": (".plan", "extract_chunk_plan"),
    "extract_state_or_scalar_result": (".result", "extract_state_or_scalar_result"),
    "make_process_chunk_node": (".nodes", "make_process_chunk_node"),
    "make_synthesize_node": (".nodes", "make_synthesize_node"),
    "normalize_chunks": (".normalize", "normalize_chunks"),
    "normalize_full_document_source": (".runner", "normalize_full_document_source"),
    "normalize_selected_ids": (".plan", "normalize_selected_ids"),
    "persist_chunked_lazy_start_state": (".runner", "persist_chunked_lazy_start_state"),
    "run_chunked_action_dispatch": (".runner", "run_chunked_action_dispatch"),
    "run_chunked_auto_complete": (".runner", "run_chunked_auto_complete"),
    "run_chunked_cached_batch_action": (".runner", "run_chunked_cached_batch_action"),
    "run_chunked_child_step": (".runner", "run_chunked_child_step"),
    "run_chunked_complete_from_session": (".runner", "run_chunked_complete_from_session"),
    "run_chunked_fanout_shard": (".runner", "run_chunked_fanout_shard"),
    "run_chunked_fanout_synthesize": (".runner", "run_chunked_fanout_synthesize"),
    "run_chunked_full_document_action": (".runner", "run_chunked_full_document_action"),
    "run_chunked_lazy_start_batch_dispatch": (".runner", "run_chunked_lazy_start_batch_dispatch"),
    "run_chunked_parallel_selected": (".runner", "run_chunked_parallel_selected"),
    "run_chunked_preview_action": (".runner", "run_chunked_preview_action"),
    "run_chunked_step": (".runner", "run_chunked_step"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name, package=__name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
