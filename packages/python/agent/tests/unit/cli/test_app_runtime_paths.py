"""Regression tests for CLI app runtime path resolution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def test_get_git_commit_uses_project_root_for_cwd() -> None:
    from omni.agent.cli.app import _get_git_commit

    fake_root = Path("/tmp/omni-project")
    fake_result = MagicMock()
    fake_result.returncode = 0
    fake_result.stdout = "12345678abcdef\n"

    with patch("omni.agent.cli.app.get_project_root", return_value=fake_root):
        with patch("omni.agent.cli.app.subprocess.run", return_value=fake_result) as mock_run:
            commit = _get_git_commit()

    assert commit == "12345678"
    assert mock_run.call_args.kwargs["cwd"] == fake_root
