"""Tests for checkpointer passthrough in pipeline runtime factories."""

from __future__ import annotations

from omni.tracer.pipeline_runtime import (
    _resolve_state_schema,
    create_langgraph_from_pipeline,
    create_langgraph_from_pipeline_with_defaults,
    create_langgraph_from_yaml,
)
from omni.tracer.pipeline_schema import PipelineConfig
from omni.tracer import ExecutionTracer, DispatchMode


def test_create_langgraph_passes_checkpointer_to_compiler(monkeypatch) -> None:
    captured = {}

    def _fake_compile(workflow, *, checkpointer=None, use_memory_saver=False):
        del workflow
        captured["checkpointer"] = checkpointer
        captured["use_memory_saver"] = use_memory_saver
        return {"ok": True}

    import omni.tracer.pipeline_runtime as module

    monkeypatch.setattr(module, "compile_workflow", _fake_compile)
    app = create_langgraph_from_pipeline(
        PipelineConfig(pipeline=["demo.run"]),
        state_schema=dict,
        checkpointer="cp",
        use_memory_saver=True,
    )

    assert app == {"ok": True}
    assert captured["checkpointer"] == "cp"
    assert captured["use_memory_saver"] is True


def test_create_langgraph_with_defaults_passes_checkpointer(monkeypatch) -> None:
    captured = {}

    def _fake_create_default_invoker_stack(**kwargs):
        captured["stack_kwargs"] = kwargs
        return object()

    def _fake_create_langgraph_from_pipeline(**kwargs):
        captured["pipeline_kwargs"] = kwargs
        return {"ok": True}

    import omni.tracer.pipeline_runtime as module

    monkeypatch.setattr(
        module, "create_langgraph_from_pipeline", _fake_create_langgraph_from_pipeline
    )
    import omni.tracer.invoker_stack as stack_module

    monkeypatch.setattr(
        stack_module, "create_default_invoker_stack", _fake_create_default_invoker_stack
    )

    out = create_langgraph_from_pipeline_with_defaults(
        PipelineConfig(pipeline=["demo.run"]),
        state_schema=dict,
        include_retrieval=False,
        checkpointer="cp2",
        use_memory_saver=True,
    )

    assert out == {"ok": True}
    assert captured["pipeline_kwargs"]["checkpointer"] == "cp2"
    assert captured["pipeline_kwargs"]["use_memory_saver"] is True


def test_create_langgraph_from_yaml_uses_runtime_defaults(tmp_path, monkeypatch) -> None:
    captured = {}
    yaml_content = """
runtime:
  checkpointer:
    type: memory
  invoker:
    include_retrieval: false
  retrieval:
    default_backend: hybrid
  tracer:
    callback_dispatch_mode: background
  state:
    schema: builtins:dict

pipeline:
  - demo.run
"""
    yaml_file = tmp_path / "pipeline.yaml"
    yaml_file.write_text(yaml_content)

    def _fake_with_defaults(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    import omni.tracer.pipeline_runtime as module

    monkeypatch.setattr(module, "create_langgraph_from_pipeline_with_defaults", _fake_with_defaults)

    tracer = ExecutionTracer(trace_id="yaml_runtime_tracer")
    out = create_langgraph_from_yaml(yaml_file, tracer=tracer)

    assert out == {"ok": True}
    assert captured["include_retrieval"] is False
    assert captured["retrieval_default_backend"] == "hybrid"
    assert captured["use_memory_saver"] is True
    assert captured["state_schema"] is dict
    assert tracer.callback_dispatch_mode == DispatchMode.BACKGROUND


def test_create_langgraph_from_yaml_allows_override(tmp_path, monkeypatch) -> None:
    captured = {}
    yaml_content = """
runtime:
  checkpointer:
    type: none
  invoker:
    include_retrieval: true
  retrieval:
    default_backend: lance
  tracer:
    callback_dispatch_mode: inline

pipeline:
  - demo.run
"""
    yaml_file = tmp_path / "pipeline_override.yaml"
    yaml_file.write_text(yaml_content)

    def _fake_with_defaults(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    import omni.tracer.pipeline_runtime as module

    monkeypatch.setattr(module, "create_langgraph_from_pipeline_with_defaults", _fake_with_defaults)

    tracer = ExecutionTracer(trace_id="yaml_override_tracer")
    out = create_langgraph_from_yaml(
        yaml_file,
        tracer=tracer,
        state_schema=dict,
        include_retrieval=False,
        retrieval_default_backend="hybrid",
        use_memory_saver=True,
        callback_dispatch_mode="background",
    )

    assert out == {"ok": True}
    assert captured["include_retrieval"] is False
    assert captured["retrieval_default_backend"] == "hybrid"
    assert captured["use_memory_saver"] is True
    assert captured["state_schema"] is dict
    assert tracer.callback_dispatch_mode == DispatchMode.BACKGROUND


def test_resolve_state_schema_from_dotted_path() -> None:
    assert _resolve_state_schema("builtins:dict") is dict


def test_resolve_state_schema_rejects_invalid_format() -> None:
    import pytest

    with pytest.raises(ValueError):
        _resolve_state_schema("builtins.dict")
