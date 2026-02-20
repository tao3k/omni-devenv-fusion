"""Memory protection fixtures - prevent test runs from exhausting machine memory.

Loaded via omni-test-kit pytest plugin; applies to all tests regardless of
rootdir (unlike root conftest which may not load when running from package dirs).

- OMNIDEV_TEST_MEMORY_ABORT_DELTA_MB: per-test RSS delta threshold (default 500)
- OMNIDEV_TEST_MEMORY_CAP_MB: total RSS cap (default 2048)
- RLIMIT_AS (Linux) / RLIMIT_RSS (macOS): kernel kills on overflow when supported.
  macOS often rejects setrlimit; per-test check is the reliable fallback.
- Orphaned workers: when a worker exceeds cap and os._exit(1)s, pytest-xdist
  reports "node down". Use -n 1 for memory-heavy suites to avoid multi-worker growth.
"""

from __future__ import annotations

import os
import sys
import threading
import time

import pytest


def _get_rss_mb() -> float | None:
    """Current process RSS in MiB."""
    try:
        import resource

        r = resource.getrusage(resource.RUSAGE_SELF)
        rss = getattr(r, "ru_maxrss", 0) or 0
        if sys.platform == "darwin":
            return round(rss / (1024 * 1024), 2)
        return round(rss / 1024, 2)
    except Exception:
        try:
            import psutil

            return round(psutil.Process().memory_info().rss / (1024 * 1024), 2)
        except Exception:
            return None


def _abort_on_overflow(test_id: str, after_mb: float, delta: float) -> None:
    """Exit immediately if memory exceeds thresholds."""
    abort_delta = float(
        os.environ.get("OMNIDEV_TEST_MEMORY_ABORT_DELTA_MB")
        or os.environ.get("KNOWLEDGE_TEST_MEMORY_ABORT_DELTA_MB")
        or "500"
    )
    cap_mb = float(
        os.environ.get("OMNIDEV_TEST_MEMORY_CAP_MB")
        or os.environ.get("KNOWLEDGE_TEST_MEMORY_CAP_MB")
        or "2048"
    )
    if abort_delta > 0 and delta > abort_delta:
        sys.stderr.write(
            f"[MEMORY] ABORT: {test_id} grew RSS by {delta:.1f} MiB (threshold={abort_delta})\n"
        )
        sys.stderr.flush()
        os._exit(1)
    if cap_mb > 0 and after_mb > cap_mb:
        sys.stderr.write(f"[MEMORY] ABORT: {test_id} RSS={after_mb:.1f} MiB exceeds cap={cap_mb}\n")
        sys.stderr.flush()
        os._exit(1)


def _set_memory_cap() -> None:
    """Set RLIMIT_AS (Linux) or RLIMIT_RSS (macOS). Silently skip if unsupported."""
    cap_mb = float(
        os.environ.get("OMNIDEV_TEST_MEMORY_CAP_MB")
        or os.environ.get("KNOWLEDGE_TEST_MEMORY_CAP_MB")
        or "2048"
    )
    if cap_mb <= 0:
        return
    limit_bytes = int(cap_mb * 1024 * 1024)
    try:
        import resource

        if sys.platform != "darwin" and hasattr(resource, "RLIMIT_AS"):
            resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
        elif hasattr(resource, "RLIMIT_RSS"):
            resource.setrlimit(resource.RLIMIT_RSS, (limit_bytes, limit_bytes))
    except (ValueError, OSError):
        pass  # macOS often rejects RLIMIT_AS/RSS; per-test check is fallback


def _release_heavy_memory_at_exit() -> None:
    """Evict all vector stores and run GC at session teardown.

    Reduces physical footprint (owned unmapped) that persists until the OS reclaims.
    See docs/reference/lancedb-query-release-lifecycle.md.
    """
    try:
        from omni.foundation.services.vector import evict_all_vector_stores

        evict_all_vector_stores()
    except Exception:
        pass


# Note: Do NOT register atexit here - session fixture teardown runs it.
# atexit runs during process exit when threads may block; session teardown runs earlier.

# Seconds from session start before forcing exit when process hangs (non-daemon threads).
# Must be longer than typical test run (62 knowledge tests ~60s); 0 = disabled.
_TEST_EXIT_TIMEOUT_SEC = int(os.environ.get("OMNIDEV_TEST_EXIT_TIMEOUT_SEC", "120"))


def _force_exit_after_timeout() -> None:
    """Daemon thread: force process exit if main thread blocks on non-daemon threads.

    pytest-xdist workers and skill tests can leave ThreadPoolExecutor/asyncio threads
    that block process exit. This fallback ensures the process exits within timeout.
    """
    time.sleep(_TEST_EXIT_TIMEOUT_SEC)
    sys.stderr.write(
        f"[MEMORY] Forced exit after {_TEST_EXIT_TIMEOUT_SEC}s (non-daemon threads blocking)\n"
    )
    sys.stderr.flush()
    os._exit(0)


def pytest_sessionstart(session):
    """Start forced-exit timer in both main process and xdist workers."""
    if _TEST_EXIT_TIMEOUT_SEC > 0:
        t = threading.Thread(target=_force_exit_after_timeout, daemon=True)
        t.start()


@pytest.fixture(autouse=True, scope="session")
def _memory_protection_session():
    """Set process memory cap at session start; release heavy memory at session end."""
    _set_memory_cap()
    yield
    _release_heavy_memory_at_exit()


@pytest.fixture(autouse=True)
def _memory_protection_per_test(request):
    """Check RSS after each test; exit immediately if thresholds exceeded."""
    before_mb = _get_rss_mb() or 0.0
    yield
    after_mb = _get_rss_mb()
    if after_mb is not None:
        delta = after_mb - before_mb
        _abort_on_overflow(request.node.nodeid, after_mb, delta)
