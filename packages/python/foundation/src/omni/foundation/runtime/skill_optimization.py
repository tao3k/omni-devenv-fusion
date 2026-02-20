"""Reusable optimization helpers for skill-level query and chunk workflows.

This module centralizes common tuning patterns so skills can share:
- Parameter normalization with bounded ranges.
- Scenario-based tuning profiles (latency/balanced/throughput).
- Low-signal query detection for skipping heavy post-processing.
- Preview generation and batch slicing for chunked delivery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ChunkWindowProfile:
    """Bounds/defaults for chunk-style retrieval workflows."""

    name: str
    limit_default: int
    limit_min: int
    limit_max: int
    preview_default: int
    preview_min: int
    preview_max: int
    batch_default: int
    batch_min: int
    batch_max: int
    max_chunks_default: int
    max_chunks_min: int
    max_chunks_max: int
    snippet_default: int
    snippet_min: int
    snippet_max: int


@dataclass(frozen=True, slots=True)
class NormalizedChunkWindow:
    """Normalized parameters for chunk retrieval."""

    limit: int
    preview_limit: int
    batch_size: int
    max_chunks: int


BALANCED_PROFILE = ChunkWindowProfile(
    name="balanced",
    limit_default=5,
    limit_min=1,
    limit_max=50,
    preview_default=10,
    preview_min=1,
    preview_max=50,
    batch_default=5,
    batch_min=1,
    batch_max=20,
    max_chunks_default=15,
    max_chunks_min=1,
    max_chunks_max=100,
    snippet_default=150,
    snippet_min=50,
    snippet_max=500,
)

LATENCY_PROFILE = ChunkWindowProfile(
    name="latency",
    limit_default=5,
    limit_min=1,
    limit_max=20,
    preview_default=8,
    preview_min=1,
    preview_max=20,
    batch_default=4,
    batch_min=1,
    batch_max=10,
    max_chunks_default=12,
    max_chunks_min=1,
    max_chunks_max=30,
    snippet_default=120,
    snippet_min=50,
    snippet_max=300,
)

THROUGHPUT_PROFILE = ChunkWindowProfile(
    name="throughput",
    limit_default=10,
    limit_min=1,
    limit_max=100,
    preview_default=20,
    preview_min=1,
    preview_max=100,
    batch_default=10,
    batch_min=1,
    batch_max=30,
    max_chunks_default=30,
    max_chunks_min=1,
    max_chunks_max=200,
    snippet_default=200,
    snippet_min=50,
    snippet_max=800,
)

_PROFILES: dict[str, ChunkWindowProfile] = {
    BALANCED_PROFILE.name: BALANCED_PROFILE,
    LATENCY_PROFILE.name: LATENCY_PROFILE,
    THROUGHPUT_PROFILE.name: THROUGHPUT_PROFILE,
}

_NULLISH_STRINGS = frozenset(("", "none", "null"))
_TRUE_STRINGS = frozenset(("1", "true", "t", "yes", "y", "on", "enabled"))
_FALSE_STRINGS = frozenset(("0", "false", "f", "no", "n", "off", "disabled"))


def _is_nullish(value: Any) -> bool:
    """Return True when value should be treated as unset."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _NULLISH_STRINGS
    return False


def get_chunk_window_profile(profile: str | None = None) -> ChunkWindowProfile:
    """Resolve a chunk tuning profile, defaulting to balanced."""
    key = (profile or "").strip().lower() or BALANCED_PROFILE.name
    return _PROFILES.get(key, BALANCED_PROFILE)


def clamp_int(
    value: Any,
    *,
    default: int,
    min_value: int,
    max_value: int,
) -> int:
    """Parse and clamp an integer into [min_value, max_value]."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed < min_value:
        return min_value
    if parsed > max_value:
        return max_value
    return parsed


def clamp_float(
    value: Any,
    *,
    default: float,
    min_value: float,
    max_value: float,
) -> float:
    """Parse and clamp a float into [min_value, max_value]."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed < min_value:
        return min_value
    if parsed > max_value:
        return max_value
    return parsed


def parse_int(
    value: Any,
    *,
    default: int,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    """Parse integer with default fallback and optional bounds."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None and parsed < min_value:
        parsed = min_value
    if max_value is not None and parsed > max_value:
        parsed = max_value
    return parsed


def parse_float(
    value: Any,
    *,
    default: float,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    """Parse float with default fallback and optional bounds."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None and parsed < min_value:
        parsed = min_value
    if max_value is not None and parsed > max_value:
        parsed = max_value
    return parsed


def parse_bool(value: Any, *, default: bool = False) -> bool:
    """Parse boolean values robustly (supports common string/int forms)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_STRINGS:
            return True
        if normalized in _FALSE_STRINGS:
            return False
        if normalized in _NULLISH_STRINGS:
            return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def parse_optional_int(
    value: Any,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int | None:
    """Parse nullable integer values; accept None/\"none\"/\"null\"/\"\" as null."""
    if _is_nullish(value):
        return None

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None

    if min_value is not None and parsed < min_value:
        parsed = min_value
    if max_value is not None and parsed > max_value:
        parsed = max_value
    return parsed


def resolve_optional_int_from_setting(
    explicit: Any,
    *,
    setting_key: str,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int | None:
    """
    Resolve optional int from explicit value first, then from config setting key.

    Returns None when both explicit and setting are null-ish/invalid.
    """
    explicit_parsed = parse_optional_int(explicit, min_value=min_value, max_value=max_value)
    if explicit_parsed is not None:
        return explicit_parsed

    try:
        from omni.foundation.config.settings import get_setting

        raw = get_setting(setting_key)
    except Exception:
        raw = None
    return parse_optional_int(raw, min_value=min_value, max_value=max_value)


def resolve_int_from_setting(
    explicit: Any = None,
    *,
    setting_key: str,
    default: int,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    """Resolve int from explicit value first, then fallback to setting/default."""
    if not _is_nullish(explicit):
        return parse_int(
            explicit,
            default=default,
            min_value=min_value,
            max_value=max_value,
        )

    try:
        from omni.foundation.config.settings import get_setting

        raw = get_setting(setting_key, default)
    except Exception:
        raw = default
    return parse_int(raw, default=default, min_value=min_value, max_value=max_value)


def resolve_float_from_setting(
    explicit: Any = None,
    *,
    setting_key: str,
    default: float,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    """Resolve float from explicit value first, then fallback to setting/default."""
    if not _is_nullish(explicit):
        return parse_float(
            explicit,
            default=default,
            min_value=min_value,
            max_value=max_value,
        )

    try:
        from omni.foundation.config.settings import get_setting

        raw = get_setting(setting_key, default)
    except Exception:
        raw = default
    return parse_float(raw, default=default, min_value=min_value, max_value=max_value)


def resolve_bool_from_setting(
    explicit: Any = None,
    *,
    setting_key: str,
    default: bool = False,
) -> bool:
    """Resolve bool from explicit value first, then fallback to setting/default."""
    if not _is_nullish(explicit):
        return parse_bool(explicit, default=default)

    try:
        from omni.foundation.config.settings import get_setting

        raw = get_setting(setting_key, default)
    except Exception:
        raw = default
    return parse_bool(raw, default=default)


def normalize_chunk_window(
    *,
    limit: Any,
    preview_limit: Any,
    batch_size: Any,
    max_chunks: Any,
    chunked: bool = True,
    profile: str | None = None,
    enforce_limit_cap: bool = True,
) -> NormalizedChunkWindow:
    """Normalize chunk workflow params with optional chunked hard-cap behavior."""
    tuning = get_chunk_window_profile(profile)
    limit_n = clamp_int(
        limit,
        default=tuning.limit_default,
        min_value=tuning.limit_min,
        max_value=tuning.limit_max,
    )
    preview_n = clamp_int(
        preview_limit,
        default=tuning.preview_default,
        min_value=tuning.preview_min,
        max_value=tuning.preview_max,
    )
    batch_n = clamp_int(
        batch_size,
        default=tuning.batch_default,
        min_value=tuning.batch_min,
        max_value=tuning.batch_max,
    )
    max_chunks_n = clamp_int(
        max_chunks,
        default=tuning.max_chunks_default,
        min_value=tuning.max_chunks_min,
        max_value=tuning.max_chunks_max,
    )

    if chunked and enforce_limit_cap:
        preview_n = min(preview_n, limit_n)
        max_chunks_n = min(max_chunks_n, limit_n)
        batch_n = min(batch_n, max_chunks_n)
    else:
        batch_n = min(batch_n, max_chunks_n)

    return NormalizedChunkWindow(
        limit=limit_n,
        preview_limit=preview_n,
        batch_size=batch_n,
        max_chunks=max_chunks_n,
    )


def normalize_snippet_chars(
    value: Any,
    *,
    profile: str | None = None,
) -> int:
    """Normalize preview snippet length for the selected profile."""
    tuning = get_chunk_window_profile(profile)
    return clamp_int(
        value,
        default=tuning.snippet_default,
        min_value=tuning.snippet_min,
        max_value=tuning.snippet_max,
    )


def normalize_min_score(value: Any, *, default: float = 0.0) -> float:
    """Normalize min-score filters into [0.0, 1.0]."""
    return clamp_float(value, default=default, min_value=0.0, max_value=1.0)


def is_low_signal_query(query: str, *, min_non_space_chars: int = 2) -> bool:
    """Return True for very short/weak queries likely to produce noisy boosts."""
    compact = "".join((query or "").split())
    return len(compact) < max(1, int(min_non_space_chars))


def build_preview_rows(
    rows: list[dict[str, Any]],
    *,
    preview_limit: int,
    snippet_chars: int,
    preview_key: str = "preview",
) -> list[dict[str, Any]]:
    """Build preview rows from full rows without mutating original records."""
    out: list[dict[str, Any]] = []
    for row in rows[: max(0, int(preview_limit))]:
        item = dict(row)
        text = item.get("content")
        if isinstance(text, str):
            item["content"] = (text[:snippet_chars] + "…") if len(text) > snippet_chars else text
        item[preview_key] = True
        out.append(item)
    return out


def split_into_batches[T](rows: list[T], *, batch_size: int) -> list[list[T]]:
    """Split rows into fixed-size batches. Empty input returns empty batches."""
    size = max(1, int(batch_size))
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def compute_batch_count(total_items: Any, *, batch_size: Any) -> int:
    """Compute batch count with safe int parsing and lower bounds."""
    total_n = max(0, clamp_int(total_items, default=0, min_value=0, max_value=10_000_000))
    size_n = max(1, clamp_int(batch_size, default=1, min_value=1, max_value=1_000_000))
    if total_n == 0:
        return 0
    return (total_n + size_n - 1) // size_n


def slice_batch[T](rows: list[T], *, batch_index: Any, batch_size: Any) -> list[T]:
    """Return one batch slice; out-of-range indexes return an empty list."""
    idx = clamp_int(batch_index, default=0, min_value=0, max_value=10_000_000)
    size = max(1, clamp_int(batch_size, default=1, min_value=1, max_value=1_000_000))
    start = idx * size
    end = start + size
    if start >= len(rows):
        return []
    return rows[start:end]


def is_markdown_index_chunk(content: str) -> bool:
    """Heuristic: markdown chunk looks like table-of-contents/index noise."""
    if not content or len(content) < 80:
        return False
    lines = content.strip().splitlines()
    table_rows = sum(
        1 for line in lines if line.strip().startswith("|") and line.strip().endswith("|")
    )
    lower = content.lower()
    if "| document |" in lower and "| description |" in lower and table_rows >= 3:
        return True
    return table_rows >= 8 and ("| [" in content or "](./" in content)


def filter_ranked_chunks(
    rows: list[dict[str, Any]],
    *,
    limit: Any,
    min_score: float = 0.0,
    index_detector: Callable[[str], bool] | None = None,
) -> list[dict[str, Any]]:
    """Filter low-score rows, demote index-like chunks, and keep top-N complete rows."""
    limit_n = max(0, clamp_int(limit, default=0, min_value=0, max_value=10_000_000))
    if limit_n == 0:
        return []

    detector = index_detector or is_markdown_index_chunk
    kept: list[dict[str, Any]] = []
    demoted: list[dict[str, Any]] = []

    for row in rows:
        try:
            score = float(row.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if score < min_score:
            continue

        content = row.get("content")
        if isinstance(content, str) and detector(content):
            demoted.append(row)
            continue
        kept.append(row)
        if len(kept) >= limit_n:
            return kept[:limit_n]

    if len(kept) >= limit_n:
        return kept[:limit_n]

    for row in demoted:
        kept.append(row)
        if len(kept) >= limit_n:
            break
    return kept[:limit_n]


__all__ = [
    "BALANCED_PROFILE",
    "LATENCY_PROFILE",
    "THROUGHPUT_PROFILE",
    "ChunkWindowProfile",
    "NormalizedChunkWindow",
    "build_preview_rows",
    "clamp_float",
    "clamp_int",
    "compute_batch_count",
    "filter_ranked_chunks",
    "get_chunk_window_profile",
    "is_low_signal_query",
    "is_markdown_index_chunk",
    "normalize_chunk_window",
    "normalize_min_score",
    "normalize_snippet_chars",
    "parse_bool",
    "parse_float",
    "parse_int",
    "parse_optional_int",
    "resolve_bool_from_setting",
    "resolve_float_from_setting",
    "resolve_int_from_setting",
    "resolve_optional_int_from_setting",
    "slice_batch",
    "split_into_batches",
]
