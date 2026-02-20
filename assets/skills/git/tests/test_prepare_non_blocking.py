"""Tests for non-blocking pre-commit hook handling in git.prepare."""


def test_stage_and_scan_downgrades_missing_pre_commit_hook(monkeypatch, tmp_path) -> None:
    """Missing pre-commit hook should not block commit preparation."""
    from git.scripts import prepare

    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "file.txt").write_text("content\n")

    def _fake_run(cmd: list[str], cwd=None) -> tuple[str, str, int]:
        if cmd[:3] == ["git", "hook", "run"]:
            return "", "error: cannot find a hook named pre-commit", 1
        if cmd == ["git", "diff", "--cached", "--name-only"]:
            return "file.txt", "", 0
        if cmd == ["git", "diff", "--name-only"]:
            return "", "", 0
        if cmd == ["git", "ls-files", "--others", "--exclude-standard"]:
            return "", "", 0
        if cmd[:4] == ["git", "--no-pager", "diff", "--cached"]:
            return "diff --git a/file.txt b/file.txt\n", "", 0
        return "", "", 0

    monkeypatch.setattr(prepare, "_run", _fake_run)
    monkeypatch.setattr(prepare.shutil, "which", lambda _name: None)
    monkeypatch.setattr(prepare, "_get_cog_scopes", lambda *_args, **_kwargs: [])

    result = prepare.stage_and_scan(str(repo))

    assert result["lefthook_error"] == ""
    assert "skipped" in result["lefthook_summary"].lower()
    assert "file.txt" in result["staged_files"]


def test_non_blocking_error_matcher() -> None:
    """Matcher should only downgrade known missing-hook messages."""
    from git.scripts.prepare import _is_non_blocking_pre_commit_error

    assert _is_non_blocking_pre_commit_error("error: cannot find a hook named pre-commit")
    assert not _is_non_blocking_pre_commit_error("pre-commit failed: lint errors")
