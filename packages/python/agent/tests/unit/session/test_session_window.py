"""Unit tests for session window (Rust PySessionWindow only)."""

import pytest

pytest.importorskip("omni_core_rs")


class TestSessionWindow:
    """Tests for PySessionWindow from omni_core_rs (Rust omni-window)."""

    def test_importable(self):
        from omni_core_rs import PySessionWindow

        w = PySessionWindow("s1", 100)
        assert w.session_id == "s1"

    def test_append_and_stats(self):
        from omni_core_rs import PySessionWindow

        w = PySessionWindow("s2", 10)
        w.append_turn("user", "hello")
        w.append_turn("assistant", "hi", 2)
        stats = w.get_stats()
        assert stats["total_turns"] == 2
        assert stats["total_tool_calls"] == 2
        assert stats["window_used"] == 2

    def test_get_recent_turns(self):
        from omni_core_rs import PySessionWindow

        w = PySessionWindow("s3", 10)
        w.append_turn("user", "a")
        w.append_turn("assistant", "b", 1)
        recent = w.get_recent_turns(5)
        assert len(recent) == 2
        assert recent[0]["role"] == "user"
        assert recent[0]["content"] == "a"
        assert recent[1]["tool_count"] == 1

    def test_max_turns_trim(self):
        from omni_core_rs import PySessionWindow

        w = PySessionWindow("s4", 3)
        for i in range(5):
            w.append_turn("user", str(i))
        stats = w.get_stats()
        assert stats["total_turns"] == 3
        recent = w.get_recent_turns(10)
        assert len(recent) == 3
        assert recent[0]["content"] == "2"
