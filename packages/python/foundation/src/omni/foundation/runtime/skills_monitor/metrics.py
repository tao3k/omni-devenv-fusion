"""Process metrics collection (RSS, CPU)."""

from __future__ import annotations

import os
import resource
import sys

from .types import Sample


def _ru_maxrss_mb() -> float:
    """Return process max RSS (ru_maxrss) in MiB."""
    r = resource.getrusage(resource.RUSAGE_SELF)
    rss = getattr(r, "ru_maxrss", 0) or 0
    if sys.platform == "darwin":
        return round(rss / (1024 * 1024), 2)
    return round(rss / 1024, 2)


def get_rss_mb() -> float:
    """Current process RSS in MiB."""
    try:
        import psutil

        p = psutil.Process(os.getpid())
        return round(float(p.memory_info().rss) / (1024 * 1024), 2)
    except ImportError:
        return _ru_maxrss_mb()
    except Exception:
        return _ru_maxrss_mb()


def get_rss_peak_mb() -> float:
    """Peak process RSS (ru_maxrss) in MiB."""
    try:
        return _ru_maxrss_mb()
    except Exception:
        return 0.0


def get_cpu_percent() -> float | None:
    """Current process CPU percent (requires psutil)."""
    try:
        import psutil

        p = psutil.Process(os.getpid())
        return round(p.cpu_percent(interval=0.1) or 0.0, 1)
    except ImportError:
        return None
    except Exception:
        return None


def take_sample(elapsed_s: float) -> Sample:
    """Take a single process metric sample."""
    return Sample(
        elapsed_s=elapsed_s,
        rss_mb=get_rss_mb(),
        rss_peak_mb=get_rss_peak_mb(),
        cpu_percent=get_cpu_percent(),
    )
