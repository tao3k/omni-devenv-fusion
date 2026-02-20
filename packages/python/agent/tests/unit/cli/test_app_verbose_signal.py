"""Tests for CLI verbose signal propagation to common layers."""

from __future__ import annotations

import os

import structlog


def test_bootstrap_sets_common_verbose_signal(monkeypatch) -> None:
    """_bootstrap_configuration(verbose=True) should enable monitor signal for core/foundation."""
    import omni.foundation.config.logging as logging_module
    from omni.agent.cli.app import _bootstrap_configuration, _is_verbose

    monkeypatch.delenv("OMNI_CLI_VERBOSE", raising=False)

    # Ensure we observe a fresh logging setup in this process.
    logging_module._configured = False
    structlog.reset_defaults()

    _bootstrap_configuration(None, verbose=True)

    assert _is_verbose() is True
    assert logging_module.is_verbose() is True
    assert os.environ.get("OMNI_CLI_VERBOSE") == "1"
