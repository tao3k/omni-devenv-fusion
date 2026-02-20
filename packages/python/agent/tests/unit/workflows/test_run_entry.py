"""Tests for run_entry session window (Rust-only)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("omni_core_rs")

from omni_core_rs import PySessionWindow

from omni.agent.workflows.run_entry import (
    _get_or_create_session_window,
    _session_window_cache,
)


class TestGetOrCreateSessionWindow:
    """Test _get_or_create_session_window (Rust PySessionWindow only)."""

    def setup_method(self) -> None:
        _session_window_cache.clear()

    def teardown_method(self) -> None:
        _session_window_cache.clear()

    def test_returns_py_session_window(self) -> None:
        w = _get_or_create_session_window("sid1")
        assert isinstance(w, PySessionWindow)
        assert w.session_id == "sid1"

    def test_creates_once_then_returns_cached(self) -> None:
        w1 = _get_or_create_session_window("cached_sid")
        w2 = _get_or_create_session_window("cached_sid")
        assert w1 is w2

    def test_uses_window_max_turns_from_settings(self) -> None:
        def get_setting_mock(key: str, default=None):
            if key == "session.window_max_turns":
                return 512
            return default

        with patch(
            "omni.foundation.config.settings.get_setting",
            side_effect=get_setting_mock,
        ):
            w = _get_or_create_session_window("sid_512")
        assert isinstance(w, PySessionWindow)
        w.append_turn("user", "x")
        stats = w.get_stats()
        assert stats["total_turns"] == 1

    def test_explicit_max_turns(self) -> None:
        w = _get_or_create_session_window("sid_explicit", max_turns=128)
        assert isinstance(w, PySessionWindow)
        assert w.session_id == "sid_explicit"
