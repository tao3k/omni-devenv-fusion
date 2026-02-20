"""Tests for smart commit scope validation response shape."""

from __future__ import annotations

from pathlib import Path

from git.scripts.smart_commit_graphflow.commands import _validate_commit_scope


def test_validate_commit_scope_returns_status_error_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "git.scripts.smart_commit_graphflow.commands._get_cog_scopes",
        lambda _path: ["agent", "nix", "docs"],
    )

    out = _validate_commit_scope(commit_scope="agnt", project_root=str(Path.cwd()))

    assert out is not None
    assert out["status"] == "error"
    assert "Invalid scope" in str(out.get("message", ""))
    assert "suggestion" in out
