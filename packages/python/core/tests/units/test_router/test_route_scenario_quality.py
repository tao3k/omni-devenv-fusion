"""Scenario-based tests for routing algorithm quality.

Validates that diverse user phrasings route to the expected skill/tool families
using the real skills index (assets/skills). Run after `omni sync`; uses same
fixtures as test_route_hybrid_integration (router_for_integration, sync from SKILLS_DIR).

Three kinds of scenarios:
- Short/keyword-style: "git commit", "find python files" (baseline intent).
- Realistic conversational: full sentences, e.g. "I need you to analyze a git repo,
  I'll give you some requirements" → researcher.
- Compound intent (action + follow-up requirement): one action first (e.g. crawl a
  site), then different requirements (analyze, extract data, let the model research
  further). User might say "crawl this website, then analyze it" or "爬取网站然后
  提取数据/分析" — we expect the first-step tool (crawl4ai) or follow-up (researcher
  / analyze) to appear in top results.

Flow: run tests → fix skill routing values or algorithm → re-run until green.
"""

from __future__ import annotations

import pytest

from omni.test_kit.asserts import assert_tool_family_match

from .conftest import sync_router_from_skills_async


def _full_tool_name(result) -> str:
    return f"{result.skill_name}.{result.command_name}"


# Scenarios: (query, expected_substrings, scenario_id)
# expected_substrings: at least one tool in top results must contain one of these (e.g. "git", "smart_find")
ROUTE_QUALITY_SCENARIOS = [
    # --- Git ---
    ("git commit", ["git"], "git-commit"),
    ("commit my changes", ["git"], "git-commit-phrase"),
    ("revert last commit", ["git"], "git-revert"),
    ("git status", ["git"], "git-status"),
    ("smart commit with review", ["git", "smart_commit"], "git-smart-commit"),
    ("amend last commit", ["git", "commit_amend"], "git-amend"),
    ("stash changes", ["git"], "git-stash"),
    # --- File discovery / advanced_tools ---
    ("find python files", ["smart_find", "smart_search", "advanced_tools"], "file-find-py"),
    (
        "find *.py files in project",
        ["smart_find", "smart_search", "advanced_tools"],
        "file-find-glob",
    ),
    ("list files in directory", ["smart_find", "search", "advanced_tools"], "file-list-dir"),
    ("search for TODO in code", ["smart_search", "advanced_tools"], "file-search-todo"),
    ("batch replace in files", ["batch_replace", "advanced_tools"], "file-batch-replace"),
    ("regex replace in file", ["regex_replace", "advanced_tools"], "file-regex-replace"),
    ("find all rust files", ["smart_find", "smart_search", "advanced_tools"], "file-find-rs"),
    # --- Research / Crawl ---
    ("research this repository", ["researcher", "git_repo_analyer"], "research-repo"),
    ("analyze repo from URL", ["researcher", "crawl4ai"], "research-analyze-url"),
    ("crawl URL and extract markdown", ["crawl4ai"], "crawl-url"),
    (
        "help me research https://github.com/example/repo",
        ["researcher", "crawl4ai"],
        "research-help-url",
    ),
    (
        "helo me to analzye https://github.com/nickel-lang/tf-ncl/blob/main/examples/aws/modules/aws-simple-ec2.ncl",
        ["researcher", "crawl4ai"],
        "research-typos-github-url",
    ),
    ("帮我研究一下这个仓库", ["researcher", "crawl4ai"], "research-zh"),
    # --- Realistic conversational (analyze repo + I'll give requirements) ---
    (
        "I need you to analyze a git repo for me, I'll give you some requirements.",
        ["researcher", "crawl4ai", "git_repo_analyer"],
        "real-analyze-repo-en",
    ),
    (
        "帮我分析一下这个 git 仓库，我会提供一些具体要求。",
        ["researcher", "crawl4ai", "git_repo_analyer"],
        "real-analyze-repo-zh",
    ),
    (
        "Can you research this repository? I have a few questions I want to understand.",
        ["researcher", "crawl4ai"],
        "real-research-repo-questions",
    ),
    (
        "Please analyze this GitHub repo and I'll tell you what I'm looking for.",
        ["researcher", "crawl4ai"],
        "real-analyze-github-tell-requirements",
    ),
    (
        "I want to understand this codebase. Could you analyze it and I'll give you my requirements.",
        ["researcher", "crawl4ai"],
        "real-understand-codebase-analyze",
    ),
    # --- Realistic: git (commit with context / review) ---
    (
        "I'm about to push. Can you help me commit with a good message? I'll review it.",
        ["git"],
        "real-git-commit-review",
    ),
    (
        "帮我提交一下代码，用规范的 commit message，我过一遍再推。",
        ["git"],
        "real-git-commit-zh",
    ),
    # --- Realistic: knowledge / memory ---
    (
        "I need to remember this for later. Can you save it so I can recall it next time?",
        ["memory", "save_memory"],
        "real-memory-save-recall",
    ),
    (
        "Search the project knowledge for how we do auth, I have a question.",
        ["knowledge", "recall", "search"],
        "real-knowledge-search-auth",
    ),
    # --- Realistic: file/code (find then refactor) ---
    (
        "Find all the Python files that touch config, then I want to batch replace a pattern.",
        ["advanced_tools", "smart_find", "smart_search", "batch_replace"],
        "real-find-then-batch",
    ),
    # --- Compound: crawl site + different follow-up requirements (爬取是第一步，之后分析/提取/研究) ---
    (
        "Crawl this website for me, then I need you to analyze the content.",
        ["crawl4ai", "researcher"],
        "compound-crawl-then-analyze",
    ),
    (
        "爬取这个网站，然后帮我分析里面的内容。",
        ["crawl4ai", "researcher"],
        "compound-crawl-then-analyze-zh",
    ),
    (
        "I want to crawl a site first, and then have the model do further research on what we get.",
        ["crawl4ai", "researcher"],
        "compound-crawl-then-research",
    ),
    (
        "Crawl the page and extract the key data so we can analyze it later.",
        ["crawl4ai", "researcher"],
        "compound-crawl-extract-then-analyze",
    ),
    (
        "帮我爬取这个链接，然后从里面选择提取一些数据过来。",
        ["crawl4ai", "researcher"],
        "compound-crawl-then-extract-zh",
    ),
    (
        "Fetch that URL, then I'll give you different requirements—maybe analyze it or extract sections.",
        ["crawl4ai", "researcher"],
        "compound-crawl-different-requirements",
    ),
    # --- Knowledge ---
    ("recall from knowledge base", ["knowledge", "recall"], "knowledge-recall"),
    ("search knowledge", ["knowledge", "search"], "knowledge-search"),
    ("ingest document into knowledge", ["knowledge", "ingest"], "knowledge-ingest"),
    ("consult architecture doc", ["knowledge", "consult"], "knowledge-consult"),
    ("get best practice for async", ["knowledge", "best_practice"], "knowledge-best-practice"),
    ("code search in project", ["knowledge", "code_search"], "knowledge-code-search"),
    ("dependency search for serde", ["knowledge", "dependency"], "knowledge-dependency"),
    ("search ZK notes", ["knowledge", "zk_search"], "knowledge-zk"),
    # --- Memory ---
    ("save memory", ["memory", "save_memory"], "memory-save"),
    ("search memory", ["memory", "search_memory"], "memory-search"),
    ("load skill into memory", ["memory", "load_skill"], "memory-load-skill"),
    # --- Skill ---
    ("discover tools for refactoring", ["skill", "discover"], "skill-discover"),
    ("list available tools", ["skill", "list_tools"], "skill-list-tools"),
    ("find capability for git", ["skill", "discover"], "skill-find-capability"),
    ("get template source for commit", ["skill", "template", "get_template"], "skill-template"),
    # --- Writer ---
    ("polish text", ["writer", "polish"], "writer-polish"),
    ("lint writing style", ["writer", "lint"], "writer-lint"),
    ("check markdown structure", ["writer", "check_markdown"], "writer-markdown"),
    ("run vale check", ["writer", "vale"], "writer-vale"),
    # --- OmniCell / run ---
    ("run command", ["omniCell", "execute"], "omnicell-run"),
    ("execute nushell command", ["omniCell", "execute"], "omnicell-nushell"),
    # --- Demo (optional; may not always rank top) ---
    ("hello demo", ["demo", "hello"], "demo-hello"),
    ("echo message", ["demo", "echo"], "demo-echo"),
]


@pytest.fixture(scope="module")
def _synced_router(router_for_integration):
    """Ensure skills are synced once per module (shared with other test classes)."""
    import asyncio

    router = router_for_integration
    result = asyncio.run(sync_router_from_skills_async(router._indexer._storage_path))
    if result["status"] != "success" or result.get("tools_indexed", 0) == 0:
        pytest.skip("Router database not populated (skills path or index failed)")
    return router


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query,expected_substrings,scenario_id",
    ROUTE_QUALITY_SCENARIOS,
    ids=[s[2] for s in ROUTE_QUALITY_SCENARIOS],
)
async def test_route_quality_scenario(
    _synced_router,
    query: str,
    expected_substrings: list[str],
    scenario_id: str,
):
    """Each scenario query should route to a tool in the expected family (top 10, threshold=0)."""
    router = _synced_router
    results = await router.route_hybrid(query, limit=10, threshold=0.0)
    tool_names = [_full_tool_name(r) for r in results]

    assert len(results) > 0, (
        f"[{scenario_id}] Query '{query}' returned 0 results. "
        "Check embedding/index or routing_keywords for relevant skills."
    )
    assert_tool_family_match(
        tool_names,
        substrings=expected_substrings,
        msg=f"[{scenario_id}] Query '{query}' should route to one of {expected_substrings}. Got (top 5): {tool_names[:5]}",
    )


class TestRouteQualityRanking:
    """Ranking quality: expected family should appear in top N for critical intents."""

    @pytest.mark.asyncio
    async def test_file_discovery_in_top3(self, _synced_router):
        """Find-files queries should have discovery tool in top 3."""
        router = _synced_router
        results = await router.route_hybrid("find python files", limit=5, threshold=0.0)
        top = [_full_tool_name(r) for r in results[:3]]
        assert_tool_family_match(
            top,
            substrings=["smart_find", "smart_search", "advanced_tools"],
            msg=f"File-discovery tool should be in top 3. Got: {top}",
        )

    @pytest.mark.asyncio
    async def test_git_commit_in_top3(self, _synced_router):
        """Git commit phrasing should have git tool in top 3."""
        router = _synced_router
        results = await router.route_hybrid("git commit", limit=5, threshold=0.0)
        top = [_full_tool_name(r) for r in results[:3]]
        assert_tool_family_match(
            top, substrings=["git"], msg=f"Git tool should be in top 3. Got: {top}"
        )

    @pytest.mark.asyncio
    async def test_research_url_in_top5(self, _synced_router):
        """Research/URL intent should have researcher or crawl4ai in top 5."""
        router = _synced_router
        results = await router.route_hybrid(
            "help me research https://github.com/nickel-lang/nickel",
            limit=10,
            threshold=0.0,
        )
        top = [_full_tool_name(r) for r in results[:5]]
        assert_tool_family_match(
            top,
            substrings=["researcher", "crawl4ai"],
            msg=f"Research/crawl tool should be in top 5. Got: {top}",
        )

    @pytest.mark.asyncio
    async def test_analyze_research_url_ranks_researcher_or_crawl_in_top2(self, _synced_router):
        """When user says analyze/research + URL, data-driven intent boost should put researcher or crawl4ai in top 2 (no hardcoded skill name)."""
        router = _synced_router
        results = await router.route_hybrid(
            "help me to analzye/research https://github.com/nickel-lang/tf-ncl/blob/main/examples/aws/modules/aws-simple-ec2.ncl",
            limit=10,
            threshold=0.0,
        )
        assert len(results) >= 2, "Need at least 2 results to check ranking"
        top2 = [_full_tool_name(r) for r in results[:2]]
        assert any("researcher" in t or "crawl4ai" in t for t in top2), (
            f"Analyze/research + URL should rank researcher or crawl4ai in top 2 (data-driven). Got top 3: {[_full_tool_name(r) for r in results[:3]]}"
        )

    @pytest.mark.asyncio
    async def test_knowledge_recall_in_top5(self, _synced_router):
        """Knowledge recall phrasing should have knowledge in top 5."""
        router = _synced_router
        results = await router.route_hybrid("recall from knowledge", limit=10, threshold=0.0)
        top = [_full_tool_name(r) for r in results[:5]]
        assert_tool_family_match(
            top,
            substrings=["knowledge", "recall"],
            msg=f"Knowledge/recall tool should be in top 5. Got: {top}",
        )

    @pytest.mark.asyncio
    async def test_memory_save_in_top5(self, _synced_router):
        """Save memory phrasing should have memory in top 5."""
        router = _synced_router
        results = await router.route_hybrid("save this to memory", limit=10, threshold=0.0)
        top = [_full_tool_name(r) for r in results[:5]]
        assert_tool_family_match(
            top,
            substrings=["memory", "save_memory"],
            msg=f"Memory tool should be in top 5. Got: {top}",
        )
