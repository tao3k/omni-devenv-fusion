"""High-precision namespace for retrieval backends and shared recall helpers.

This module uses lazy exports to keep `omni skill run ...` startup overhead low.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "HybridRetrievalBackend": (".hybrid", "HybridRetrievalBackend"),
    "HybridRetrievalUnavailableError": (".errors", "HybridRetrievalUnavailableError"),
    "LanceRetrievalBackend": (".lancedb", "LanceRetrievalBackend"),
    "RetrievalBackend": (".interface", "RetrievalBackend"),
    "RetrievalConfig": (".interface", "RetrievalConfig"),
    "RetrievalResult": (".interface", "RetrievalResult"),
    "apply_recall_postprocess": (".postprocess", "apply_recall_postprocess"),
    "build_recall_chunked_response": (".response", "build_recall_chunked_response"),
    "build_recall_error_response": (".response", "build_recall_error_response"),
    "build_recall_row": (".rows", "build_recall_row"),
    "build_recall_search_response": (".response", "build_recall_search_response"),
    "build_status_error_response": (".response", "build_status_error_response"),
    "build_status_message_response": (".response", "build_status_message_response"),
    "create_hybrid_node": (".node_factory", "create_hybrid_node"),
    "create_retrieval_backend": (".factory", "create_retrieval_backend"),
    "create_retriever_node": (".node_factory", "create_retriever_node"),
    "extract_graph_confidence": (".response", "extract_graph_confidence"),
    "filter_recall_rows": (".postprocess", "filter_recall_rows"),
    "override_retrieval_plan_mode": (".response", "override_retrieval_plan_mode"),
    "recall_rows_from_hybrid_json": (".rows", "recall_rows_from_hybrid_json"),
    "recall_rows_from_vector_results": (".rows", "recall_rows_from_vector_results"),
    "run_recall_hybrid_rows": (".executor", "run_recall_hybrid_rows"),
    "run_recall_query_rows": (".executor", "run_recall_query_rows"),
    "run_recall_semantic_rows": (".executor", "run_recall_semantic_rows"),
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
