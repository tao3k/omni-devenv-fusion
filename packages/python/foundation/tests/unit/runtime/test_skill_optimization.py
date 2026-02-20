"""Unit tests for shared skill optimization helpers."""

from __future__ import annotations

from omni.foundation.runtime.skill_optimization import (
    BALANCED_PROFILE,
    LATENCY_PROFILE,
    build_preview_rows,
    clamp_float,
    clamp_int,
    compute_batch_count,
    filter_ranked_chunks,
    get_chunk_window_profile,
    is_low_signal_query,
    is_markdown_index_chunk,
    normalize_chunk_window,
    normalize_min_score,
    normalize_snippet_chars,
    parse_bool,
    parse_float,
    parse_int,
    parse_optional_int,
    resolve_bool_from_setting,
    resolve_float_from_setting,
    resolve_int_from_setting,
    resolve_optional_int_from_setting,
    slice_batch,
    split_into_batches,
)


def test_clamp_int_and_float() -> None:
    """Clamp helpers should parse and bound values safely."""
    assert clamp_int("9", default=1, min_value=1, max_value=5) == 5
    assert clamp_int(None, default=3, min_value=1, max_value=5) == 3
    assert clamp_float("0.9", default=0.0, min_value=0.0, max_value=1.0) == 0.9
    assert clamp_float("2.0", default=0.0, min_value=0.0, max_value=1.0) == 1.0


def test_parse_optional_int_handles_nullish_and_bounds() -> None:
    """Nullable int parser should accept null-ish strings and optional bounds."""
    assert parse_optional_int(None) is None
    assert parse_optional_int("") is None
    assert parse_optional_int("none") is None
    assert parse_optional_int("null") is None
    assert parse_optional_int("abc") is None
    assert parse_optional_int("7") == 7
    assert parse_optional_int("0", min_value=1) == 1
    assert parse_optional_int("12", max_value=10) == 10


def test_parse_bool_and_number_helpers() -> None:
    """Typed parsers should handle common string/int/float forms robustly."""
    assert parse_bool("true") is True
    assert parse_bool("false", default=True) is False
    assert parse_bool("0", default=True) is False
    assert parse_bool("unknown", default=True) is True
    assert parse_int("7", default=1, min_value=1, max_value=10) == 7
    assert parse_int("abc", default=3, min_value=1, max_value=10) == 3
    assert parse_float("0.8", default=0.0, min_value=0.0, max_value=1.0) == 0.8
    assert parse_float("x", default=0.5, min_value=0.0, max_value=1.0) == 0.5


def test_resolve_optional_int_from_setting_prefers_explicit_and_falls_back(
    monkeypatch,
) -> None:
    """Resolver should use explicit first, then setting value when explicit is null-ish."""

    def _fake_get_setting(key: str, default: object = None) -> object:
        assert default is None
        if key == "researcher.max_concurrent":
            return "5"
        return None

    monkeypatch.setattr(
        "omni.foundation.config.settings.get_setting",
        _fake_get_setting,
    )

    assert resolve_optional_int_from_setting(3, setting_key="researcher.max_concurrent") == 3
    assert resolve_optional_int_from_setting(None, setting_key="researcher.max_concurrent") == 5
    assert resolve_optional_int_from_setting("none", setting_key="researcher.max_concurrent") == 5


def test_resolve_typed_values_from_setting(monkeypatch) -> None:
    """Typed resolvers should parse setting strings and honor explicit overrides."""

    def _fake_get_setting(key: str, default: object = None) -> object:
        if key == "knowledge.ingest_pdf_fast_path":
            return "false"
        if key == "knowledge.ingest_chunk_target_tokens":
            return "2048"
        if key == "knowledge.min_score":
            return "0.35"
        return default

    monkeypatch.setattr(
        "omni.foundation.config.settings.get_setting",
        _fake_get_setting,
    )

    assert (
        resolve_bool_from_setting(
            setting_key="knowledge.ingest_pdf_fast_path",
            default=True,
        )
        is False
    )
    assert (
        resolve_bool_from_setting(
            explicit="true",
            setting_key="knowledge.ingest_pdf_fast_path",
            default=False,
        )
        is True
    )
    assert (
        resolve_int_from_setting(
            setting_key="knowledge.ingest_chunk_target_tokens",
            default=512,
            min_value=64,
            max_value=1024,
        )
        == 1024
    )
    assert (
        resolve_float_from_setting(
            setting_key="knowledge.min_score",
            default=0.0,
            min_value=0.0,
            max_value=1.0,
        )
        == 0.35
    )


def test_profile_resolution_falls_back_to_balanced() -> None:
    """Unknown profile names should not break normalization."""
    assert get_chunk_window_profile("latency") == LATENCY_PROFILE
    assert get_chunk_window_profile("unknown") == BALANCED_PROFILE


def test_normalize_chunk_window_chunked_enforces_limit_cap() -> None:
    """Chunked workflows should cap preview/max_chunks/batch by limit."""
    normalized = normalize_chunk_window(
        limit=3,
        preview_limit=10,
        batch_size=9,
        max_chunks=40,
        chunked=True,
        profile="balanced",
        enforce_limit_cap=True,
    )
    assert normalized.limit == 3
    assert normalized.preview_limit == 3
    assert normalized.max_chunks == 3
    assert normalized.batch_size == 3


def test_normalize_chunk_window_latency_profile_is_stricter() -> None:
    """Latency profile should use tighter upper bounds than balanced."""
    normalized = normalize_chunk_window(
        limit=100,
        preview_limit=100,
        batch_size=100,
        max_chunks=100,
        chunked=True,
        profile="latency",
        enforce_limit_cap=False,
    )
    assert normalized.limit == 20
    assert normalized.preview_limit == 20
    assert normalized.batch_size == 10
    assert normalized.max_chunks == 30


def test_normalize_snippet_chars_and_min_score() -> None:
    """Snippet and min-score normalizers should keep values in safe ranges."""
    assert normalize_snippet_chars("1000", profile="balanced") == 500
    assert normalize_snippet_chars(None, profile="balanced") == 150
    assert normalize_min_score("-1", default=0.2) == 0.0
    assert normalize_min_score("1.3", default=0.2) == 1.0


def test_low_signal_query_detection() -> None:
    """Very short compact queries should be marked as low-signal."""
    assert is_low_signal_query("x") is True
    assert is_low_signal_query(" x ") is True
    assert is_low_signal_query("ai") is False


def test_build_preview_rows_truncates_without_mutating_inputs() -> None:
    """Preview builder should produce copied/truncated rows."""
    rows = [
        {"content": "abcdef", "source": "a"},
        {"content": "123", "source": "b"},
    ]
    preview = build_preview_rows(rows, preview_limit=1, snippet_chars=3)
    assert preview == [{"content": "abc…", "source": "a", "preview": True}]
    assert rows[0]["content"] == "abcdef"


def test_split_into_batches() -> None:
    """Batch splitter should preserve order and produce tail batch."""
    rows = [1, 2, 3, 4, 5]
    assert split_into_batches(rows, batch_size=2) == [[1, 2], [3, 4], [5]]


def test_compute_batch_count_and_slice_batch() -> None:
    """Batch helpers should be stable for common recall/session workflows."""
    assert compute_batch_count(5, batch_size=2) == 3
    assert compute_batch_count(0, batch_size=2) == 0
    rows = [1, 2, 3, 4, 5]
    assert slice_batch(rows, batch_index=0, batch_size=2) == [1, 2]
    assert slice_batch(rows, batch_index=2, batch_size=2) == [5]
    assert slice_batch(rows, batch_index=3, batch_size=2) == []


def test_is_markdown_index_chunk_detection() -> None:
    """Index-like markdown tables should be detected as low-signal chunks."""
    toc = """
| Document | Description |
| -------- | ----------- |
| [A](./a.md) | First |
| [B](./b.md) | Second |
"""
    assert is_markdown_index_chunk(toc) is True
    assert is_markdown_index_chunk("## Real section\nmeaningful content") is False


def test_filter_ranked_chunks_demotes_index_rows() -> None:
    """Filter helper keeps substantive rows first, then fills with index rows if needed."""
    toc = "| Document | Description |\n| -------- | ----------- |\n| [A](./a.md) | Desc |\n" * 2
    rows = [
        {"content": "real content", "score": 0.9, "source": "doc"},
        {"content": toc, "score": 0.95, "source": "index"},
        {"content": "other real content", "score": 0.7, "source": "doc2"},
    ]
    out = filter_ranked_chunks(rows, limit=3, min_score=0.0)
    assert [x["source"] for x in out] == ["doc", "doc2", "index"]
