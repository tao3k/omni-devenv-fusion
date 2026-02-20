"""Response-shape adapter tests for demo skill commands."""

from __future__ import annotations

import json

import pytest


def _unwrap_skill_output(payload: object) -> dict:
    if isinstance(payload, dict) and "content" in payload:
        content = payload.get("content") or []
        if content and isinstance(content, list):
            first = content[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                return json.loads(first["text"])
    if isinstance(payload, dict):
        return payload
    raise TypeError(f"unexpected payload type: {type(payload)}")


@pytest.mark.asyncio
async def test_test_yaml_pipeline_missing_file_returns_status_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import demo.scripts.commands as commands

    monkeypatch.setattr(commands, "SKILLS_DIR", lambda **_kwargs: tmp_path)

    out = _unwrap_skill_output(await commands.test_yaml_pipeline(pipeline_type="simple"))

    assert out["status"] == "error"
    assert "Pipeline file not found" in str(out.get("error", ""))
    assert out["pipeline_type"] == "simple"
