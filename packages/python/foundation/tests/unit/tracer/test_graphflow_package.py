"""Graphflow package modularity tests."""

from __future__ import annotations


def test_graphflow_public_api_available() -> None:
    """Public graphflow entrypoint is exposed from package namespace."""
    from omni.tracer.graphflow import run_graphflow_pipeline

    assert callable(run_graphflow_pipeline)


def test_graphflow_internal_modules_importable() -> None:
    """Core graphflow modules can be imported independently."""
    from omni.tracer.graphflow import run_graphflow_pipeline
    from omni.tracer.graphflow.evaluation import _jaccard_similarity
    from omni.tracer.graphflow.llm_service import get_llm_service
    from omni.tracer.graphflow.tracer import LangGraphTracer
    from omni.tracer.graphflow.types import DemoState

    assert callable(run_graphflow_pipeline)
    assert _jaccard_similarity("a b", "a b") == 1.0
    assert callable(get_llm_service)
    tracer = LangGraphTracer("t", "th", "simple")
    assert tracer.trace.trace_id == "t"
    assert isinstance(DemoState.__annotations__, dict)
