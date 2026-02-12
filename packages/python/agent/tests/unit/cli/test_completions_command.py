"""Unit tests for completions command scripts."""

from __future__ import annotations

from typer.testing import CliRunner

from omni.agent.cli.app import app
from omni.agent.cli.commands.completions import (
    COMPLETION_SCRIPT_FISH,
    COMPLETION_SCRIPT_ZSH,
)


def test_fish_completion_uses_omni_commands():
    """Fish completion script should call `omni commands`."""
    assert "(omni commands 2>/dev/null)" in COMPLETION_SCRIPT_FISH
    assert "(omi commands 2>/dev/null)" not in COMPLETION_SCRIPT_FISH


def test_zsh_completion_includes_route_subcommands():
    """Zsh completion script should expose route actions."""
    assert "1:action:(test stats cache schema)" in COMPLETION_SCRIPT_ZSH
    assert "--stdout[Print schema JSON to stdout]" in COMPLETION_SCRIPT_ZSH
    assert "--confidence-profile" in COMPLETION_SCRIPT_ZSH


def test_commands_list_includes_version():
    """`omni commands` should include top-level version command."""
    runner = CliRunner()
    result = runner.invoke(app, ["commands"])
    assert result.exit_code == 0
    assert "version" in result.output.splitlines()
