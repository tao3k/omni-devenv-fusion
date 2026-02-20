"""Tests for writer run_vale_check error response payload shape."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from omni.foundation.config.skills import SKILLS_DIR


def _load_writer_text_module():
    script_path = SKILLS_DIR(skill="writer", path="scripts/text.py")
    module_name = "writer_skill_text_response_adapter"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load writer text module from: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _unwrap_skill_output(payload: object) -> dict:
    if isinstance(payload, dict) and "content" in payload:
        content = payload.get("content") or []
        if content and isinstance(content, list):
            first = content[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                return json.loads(first["text"])
    if isinstance(payload, str):
        return json.loads(payload)
    if isinstance(payload, dict):
        return payload
    raise TypeError(f"unexpected payload type: {type(payload)}")


@pytest.mark.asyncio
async def test_run_vale_check_missing_vale_returns_status_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer_text = _load_writer_text_module()

    def _fake_run(*_args, **_kwargs):
        raise FileNotFoundError("vale not installed")

    monkeypatch.setattr(writer_text.subprocess, "run", _fake_run)

    out = _unwrap_skill_output(await writer_text.run_vale_check(file_path=str(Path("README.md"))))
    assert out["status"] == "error"
    assert "Vale CLI not found" in str(out.get("message", ""))
    assert out["violations"] == []
