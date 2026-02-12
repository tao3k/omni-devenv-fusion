"""Tests for pipeline checkpointer helpers."""

from __future__ import annotations

from omni.tracer.pipeline_checkpoint import compile_workflow


class _FakeWorkflow:
    def __init__(self):
        self.calls: list[dict] = []

    def compile(self, **kwargs):
        self.calls.append(kwargs)
        return {"compiled": True, "kwargs": kwargs}


def test_compile_workflow_without_checkpointer() -> None:
    wf = _FakeWorkflow()
    out = compile_workflow(wf)

    assert out["compiled"] is True
    assert wf.calls == [{}]


def test_compile_workflow_with_explicit_checkpointer() -> None:
    wf = _FakeWorkflow()
    cp = object()

    out = compile_workflow(wf, checkpointer=cp)

    assert out["compiled"] is True
    assert wf.calls == [{"checkpointer": cp}]


def test_compile_workflow_uses_memory_saver_when_requested(monkeypatch) -> None:
    wf = _FakeWorkflow()
    expected = object()

    def _fake_create():
        return expected

    import omni.tracer.pipeline_checkpoint as module

    monkeypatch.setattr(module, "create_in_memory_checkpointer", _fake_create)
    out = module.compile_workflow(wf, use_memory_saver=True)

    assert out["compiled"] is True
    assert wf.calls == [{"checkpointer": expected}]
