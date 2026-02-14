"""Tests for rule-based and optional LLM-driven tool search intent classification."""

import pytest

from omni.core.router.query_intent import (
    ToolSearchIntentResult,
    classify_tool_search_intent,
    classify_tool_search_intent_full,
    classify_tool_search_intent_with_llm,
)


def test_classify_exact_like_command():
    assert classify_tool_search_intent("git.commit") == "exact"
    assert classify_tool_search_intent("knowledge.recall") == "exact"
    assert classify_tool_search_intent("skill.discover") == "exact"
    assert classify_tool_search_intent("advanced_tools.smart_find") == "exact"


def test_classify_hybrid_natural_language():
    assert classify_tool_search_intent("git commit my changes") == "hybrid"
    assert classify_tool_search_intent("find files matching pattern") == "hybrid"
    assert classify_tool_search_intent("how do I commit") == "hybrid"
    assert classify_tool_search_intent("commit") == "hybrid"  # no dot
    assert classify_tool_search_intent("ab") == "hybrid"  # too short


def test_classify_hybrid_empty_or_invalid():
    assert classify_tool_search_intent("") == "hybrid"
    assert classify_tool_search_intent("   ") == "hybrid"
    assert classify_tool_search_intent("a.b") == "exact"  # min 3 chars, has dot
    assert classify_tool_search_intent("x.y") == "exact"  # 3 chars, dot, valid id
    assert classify_tool_search_intent("a b") == "hybrid"  # space
    assert classify_tool_search_intent("x" * 81) == "hybrid"  # too long


def test_classify_exact_with_dot_only():
    assert classify_tool_search_intent("git.commit") == "exact"
    assert classify_tool_search_intent("a.b") == "exact"


# --- classify_tool_search_intent_full (sample-aligned with report + Rust) ---


def test_full_exact_no_category_filter():
    r = classify_tool_search_intent_full("git.commit")
    assert r == ToolSearchIntentResult("exact", None)
    r = classify_tool_search_intent_full("advanced_tools.smart_find")
    assert r.intent == "exact" and r.category_filter is None


def test_full_file_discovery_category_filter():
    """File-discovery queries get category_filter=file_discovery (same terms as Rust fusion.rs)."""
    r = classify_tool_search_intent_full("find files matching pattern")
    assert r.intent == "hybrid" and r.category_filter == "file_discovery"
    r = classify_tool_search_intent_full("list directory")
    assert r.intent == "hybrid" and r.category_filter == "file_discovery"
    r = classify_tool_search_intent_full("find *.py")
    assert r.intent == "hybrid" and r.category_filter == "file_discovery"
    r = classify_tool_search_intent_full("list files in path")
    assert r.intent == "hybrid" and r.category_filter == "file_discovery"
    r = classify_tool_search_intent_full("search for .py files")
    assert r.intent == "hybrid" and r.category_filter == "file_discovery"
    r = classify_tool_search_intent_full("glob for *.rs")
    assert r.intent == "hybrid" and r.category_filter == "file_discovery"


def test_full_hybrid_no_file_discovery():
    r = classify_tool_search_intent_full("git commit my changes")
    assert r.intent == "hybrid" and r.category_filter is None
    r = classify_tool_search_intent_full("how do I commit")
    assert r.intent == "hybrid" and r.category_filter is None


def test_tool_capability_intent_overrides_file_discovery():
    """Queries about tools/capabilities (list tools, find capability) should not get file_discovery filter."""
    r = classify_tool_search_intent_full("list available tools")
    assert r.intent == "hybrid" and r.category_filter is None
    r = classify_tool_search_intent_full("find capability for git")
    assert r.intent == "hybrid" and r.category_filter is None
    r = classify_tool_search_intent_full("what commands are available")
    assert r.intent == "hybrid" and r.category_filter is None


# --- classify_tool_search_intent_with_llm (optional LLM path) ---


@pytest.mark.asyncio
async def test_llm_intent_disabled_returns_none():
    """When enabled=False, LLM intent returns None (caller uses rule-based)."""
    r = await classify_tool_search_intent_with_llm("git commit", enabled=False)
    assert r is None


@pytest.mark.asyncio
async def test_llm_intent_empty_query_returns_none():
    r = await classify_tool_search_intent_with_llm("", enabled=True)
    assert r is None
    r = await classify_tool_search_intent_with_llm("   ", enabled=True)
    assert r is None


def _fake_get_setting_intent_llm(key: str, default=None):
    if key == "router.intent.use_llm":
        return True
    if key == "router.intent.model":
        return None
    return default


@pytest.mark.asyncio
async def test_llm_intent_parses_valid_json(monkeypatch: pytest.MonkeyPatch):
    """When provider returns valid JSON, we get ToolSearchIntentResult."""

    class StubProvider:
        async def complete_async(self, *args, **kwargs):
            return '{"intent": "hybrid", "category_filter": "file_discovery"}'

        def is_available(self):
            return True

    monkeypatch.setattr(
        "omni.foundation.config.settings.get_setting",
        _fake_get_setting_intent_llm,
    )
    monkeypatch.setattr(
        "omni.foundation.services.llm.provider.get_llm_provider",
        lambda: StubProvider(),
    )

    r = await classify_tool_search_intent_with_llm("find *.py files", enabled=True)
    assert r is not None
    assert r.intent == "hybrid"
    assert r.category_filter == "file_discovery"


@pytest.mark.asyncio
async def test_llm_intent_invalid_json_returns_none(monkeypatch: pytest.MonkeyPatch):
    """When provider returns invalid JSON, we get None (fallback to rule-based)."""

    class StubProvider:
        async def complete_async(self, *args, **kwargs):
            return "not json"

        def is_available(self):
            return True

    monkeypatch.setattr(
        "omni.foundation.config.settings.get_setting",
        _fake_get_setting_intent_llm,
    )
    monkeypatch.setattr(
        "omni.foundation.services.llm.provider.get_llm_provider",
        lambda: StubProvider(),
    )

    r = await classify_tool_search_intent_with_llm("git commit", enabled=True)
    assert r is None


@pytest.mark.asyncio
async def test_llm_intent_provider_unavailable_returns_none(monkeypatch: pytest.MonkeyPatch):
    """When provider is not available, we get None."""

    class StubProvider:
        def is_available(self):
            return False

    monkeypatch.setattr(
        "omni.foundation.config.settings.get_setting",
        _fake_get_setting_intent_llm,
    )
    monkeypatch.setattr(
        "omni.foundation.services.llm.provider.get_llm_provider",
        lambda: StubProvider(),
    )

    r = await classify_tool_search_intent_with_llm("git commit", enabled=True)
    assert r is None
