"""Session metrics persistence for dashboard.

Writes last-run session metrics to project cache so `omni dashboard` can show them.
Path: .cache/omni/session_metrics.json (via get_cache_dir).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omni.foundation.config.prj import get_cache_dir

_FILENAME = "session_metrics.json"


def _metrics_path() -> Path:
    """Path to last-session metrics file."""
    d = get_cache_dir("omni")
    d.mkdir(parents=True, exist_ok=True)
    return d / _FILENAME


def write_session_metrics(metrics: dict[str, Any]) -> None:
    """Persist session metrics for the dashboard.

    Call after a run completes. Overwrites previous file.
    """
    path = _metrics_path()
    payload = dict(metrics)
    if "timestamp" not in payload:
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_session_metrics() -> dict[str, Any] | None:
    """Read last session metrics, or None if missing/invalid."""
    path = _metrics_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None
