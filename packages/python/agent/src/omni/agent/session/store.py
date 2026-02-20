"""
Session store: load/save conversation history by session_id.

Persists under PRJ_DATA(sessions) as JSON. In-memory cache for hot path.
Single responsibility: session persistence; no orchestration.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from omni.foundation.config.dirs import PRJ_DATA

# Safe filename: replace chars that are invalid in filenames
_SESSION_ID_RE = re.compile(r"[^\w\-.]")


def _session_path(session_id: str) -> Path:
    """Path to session file under PRJ_DATA(sessions)."""
    safe = _SESSION_ID_RE.sub("_", session_id)
    if not safe:
        safe = "default"
    base = PRJ_DATA.ensure_dir("sessions")
    return base / f"{safe}.json"


class SessionStore:
    """In-memory cache + file persistence for session history."""

    def __init__(self) -> None:
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def load(self, session_id: str) -> list[dict[str, Any]]:
        """Load history for session_id. Returns list of {role, content} turns."""
        if session_id in self._cache:
            return self._cache[session_id]
        path = _session_path(session_id)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            history = data.get("history", [])
            if isinstance(history, list):
                self._cache[session_id] = history
                return history
        except (json.JSONDecodeError, OSError):
            pass
        return []

    def save(self, session_id: str, history: list[dict[str, Any]]) -> None:
        """Save history for session_id. Persists to disk and updates cache."""
        self._cache[session_id] = history
        path = _session_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"session_id": session_id, "history": history}
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def trim(self, history: list[dict[str, Any]], max_turns: int) -> list[dict[str, Any]]:
        """Keep only the last max_turns user+assistant pairs (2*max_turns entries)."""
        if len(history) <= 2 * max_turns:
            return history
        return history[-(2 * max_turns) :]


# Module-level default store for callers that do not need a custom instance
_default_store: SessionStore | None = None


def _get_store() -> SessionStore:
    global _default_store
    if _default_store is None:
        _default_store = SessionStore()
    return _default_store


def load_session(session_id: str, store: SessionStore | None = None) -> list[dict[str, Any]]:
    """Load session history. Uses default store if store is None."""
    return (store or _get_store()).load(session_id)


def save_session(
    session_id: str,
    history: list[dict[str, Any]],
    store: SessionStore | None = None,
) -> None:
    """Save session history. Uses default store if store is None."""
    (store or _get_store()).save(session_id, history)
