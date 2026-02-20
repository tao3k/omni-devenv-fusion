"""Unit tests for session store."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from omni.agent.session.store import SessionStore, load_session, save_session


class TestSessionStore:
    """Tests for SessionStore load/save/trim."""

    def test_load_empty_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("omni.agent.session.store.PRJ_DATA") as m_prj:
                m_prj.ensure_dir.return_value = Path(tmp)
                store = SessionStore()
                out = store.load("s1")
                assert out == []

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("omni.agent.session.store.PRJ_DATA") as m_prj:
                m_prj.ensure_dir.return_value = Path(tmp)
                store = SessionStore()
                history = [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi"},
                ]
                store.save("s1", history)
                loaded = store.load("s1")
                assert loaded == history
                # Persisted to disk
                files = list(Path(tmp).glob("*.json"))
                assert len(files) == 1
                data = json.loads(files[0].read_text(encoding="utf-8"))
                assert data["history"] == history

    def test_trim_under_limit(self):
        store = SessionStore()
        history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        out = store.trim(history, 10)
        assert out == history

    def test_trim_over_limit(self):
        store = SessionStore()
        history = [
            h
            for i in range(30)
            for h in [
                {"role": "user", "content": str(i)},
                {"role": "assistant", "content": str(i)},
            ]
        ]
        out = store.trim(history, 5)
        assert len(out) == 10  # last 5 turns = 10 entries
        assert out[0]["content"] == "25"
        assert out[-1]["content"] == "29"


class TestLoadSaveSession:
    """Tests for module-level load_session/save_session."""

    def test_load_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("omni.agent.session.store.PRJ_DATA") as m_prj:
                m_prj.ensure_dir.return_value = Path(tmp)
                save_session("roundtrip", [{"role": "user", "content": "x"}])
                loaded = load_session("roundtrip")
                assert len(loaded) == 1
                assert loaded[0]["content"] == "x"
