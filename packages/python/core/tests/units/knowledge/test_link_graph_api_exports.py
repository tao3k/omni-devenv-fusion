"""API export checks for LinkGraph helper symbols in omni.core.knowledge."""

from __future__ import annotations

import omni.core.knowledge as knowledge


def test_link_graph_helper_exports_present() -> None:
    """The module should expose LinkGraph helper names."""
    expected = {
        "link_graph_extract_entity_refs",
        "link_graph_get_ref_stats",
        "link_graph_count_refs",
        "link_graph_is_valid_ref",
    }
    assert expected.issubset(set(knowledge.__all__))


def test_legacy_zk_helper_exports_removed() -> None:
    """Legacy zk-prefixed helper symbols are intentionally removed."""
    legacy = {
        "zk_extract_entity_refs",
        "zk_get_ref_stats",
        "zk_count_refs",
        "zk_is_valid_ref",
    }
    assert legacy.isdisjoint(set(knowledge.__all__))
    for name in legacy:
        assert not hasattr(knowledge, name)
