"""Unit tests for omni.foundation.bridge.types (SearchResult and score clamping)."""

from __future__ import annotations

import pytest

from omni.foundation.bridge.types import SearchResult


class TestSearchResultScoreClamping:
    """SearchResult score is clamped to [0, 1]; fusion/RRF can produce values > 1.0."""

    def test_score_above_one_is_clamped(self):
        """Score > 1.0 is clamped to 1.0 so validation does not fail."""
        r = SearchResult(score=1.2549350261688232, payload={}, id="doc-1")
        assert r.score == 1.0

    def test_score_below_zero_is_clamped(self):
        """Score < 0.0 is clamped to 0.0."""
        r = SearchResult(score=-0.1, payload={}, id="doc-2")
        assert r.score == 0.0

    def test_score_in_range_unchanged(self):
        """Score in [0, 1] is preserved."""
        r = SearchResult(score=0.88, payload={"tag": "docs"}, id="doc-3")
        assert r.score == 0.88
