"""CLI commands module resilience tests."""

from __future__ import annotations

import importlib
import sys

_MISSING = object()


def test_commands_module_gracefully_handles_missing_run_module() -> None:
    """commands package should remain importable even if run module is unavailable."""
    import omni.agent.cli.commands as commands

    original_run_module = sys.modules.get("omni.agent.cli.commands.run", _MISSING)
    sys.modules["omni.agent.cli.commands.run"] = None
    try:
        reloaded = importlib.reload(commands)
        assert callable(reloaded.register_run_command)
        reloaded.register_run_command(None)
    finally:
        if original_run_module is _MISSING:
            sys.modules.pop("omni.agent.cli.commands.run", None)
        else:
            sys.modules["omni.agent.cli.commands.run"] = original_run_module
        importlib.reload(commands)
