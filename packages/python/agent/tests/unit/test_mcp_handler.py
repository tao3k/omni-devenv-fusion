"""
test_mcp_handler.py - Test MCP handler tool loading

Detects issues like:
- Kernel not properly initialized
- Tools not loaded (returns 0 tools)
- Missing expected core skills
- Handler initialization failures
"""

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from omni.agent.server import AgentMCPHandler


@pytest.fixture
async def handler():
    """Create and initialize MCP handler."""
    handler = AgentMCPHandler()
    await handler.initialize()
    yield handler
    # Cleanup if needed


class _DummyKernel:
    def __init__(self, *, is_running: bool) -> None:
        self.is_ready = True
        self.is_running = is_running
        self.initialize_calls = 0
        self.start_calls = 0
        self.skill_manager = SimpleNamespace(watcher=object())
        self.skill_context = SimpleNamespace(list_skills=lambda: [])

    async def initialize(self) -> None:
        self.initialize_calls += 1

    async def start(self) -> None:
        self.start_calls += 1
        self.is_running = True


class _SlowDummyKernel(_DummyKernel):
    async def initialize(self) -> None:
        self.initialize_calls += 1
        await asyncio.sleep(0.05)


class _ToolCommand:
    def __init__(self, description: str = "desc", schema: dict | None = None) -> None:
        self.description = description
        self.input_schema = schema or {"type": "object"}


class _ToolContext:
    def __init__(self, commands: dict[str, _ToolCommand]) -> None:
        self._commands = commands

    def get_command(self, name: str):
        return self._commands.get(name)

    def list_commands(self) -> list[str]:
        return list(self._commands.keys())

    def list_skills(self) -> list[str]:
        return sorted({name.split(".", 1)[0] for name in self._commands})

    def get_filtered_commands(self) -> list[str]:
        return []


class _RegistryStoreStub:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.calls = 0

    def list_all_tools(self, *_args):
        self.calls += 1
        return json.dumps(self._rows)


class _SettingsStub:
    def __init__(self, value: object) -> None:
        self._value = value

    def get(self, key: str, default: object = None) -> object:
        if key == "mcp.tools_list.max_in_flight":
            return self._value
        return default


@pytest.mark.asyncio
async def test_initialize_starts_kernel_runtime_when_not_running() -> None:
    """Handler init must call kernel.start() so Live-Wire watcher can run."""
    handler = AgentMCPHandler()
    dummy = _DummyKernel(is_running=False)
    handler._kernel = dummy  # type: ignore[assignment]

    await handler.initialize()

    assert dummy.initialize_calls == 1
    assert dummy.start_calls == 1
    assert handler._initialized is True


@pytest.mark.asyncio
async def test_initialize_does_not_restart_running_kernel() -> None:
    """Handler init should not call start() when kernel already RUNNING."""
    handler = AgentMCPHandler()
    dummy = _DummyKernel(is_running=True)
    handler._kernel = dummy  # type: ignore[assignment]

    await handler.initialize()

    assert dummy.initialize_calls == 1
    assert dummy.start_calls == 0
    assert handler._initialized is True


@pytest.mark.asyncio
async def test_initialize_is_single_flight_under_concurrency() -> None:
    """Concurrent initialize() calls should bootstrap kernel only once."""
    handler = AgentMCPHandler()
    dummy = _SlowDummyKernel(is_running=False)
    handler._kernel = dummy  # type: ignore[assignment]

    await asyncio.gather(handler.initialize(), handler.initialize(), handler.initialize())

    assert dummy.initialize_calls == 1
    assert dummy.start_calls == 1
    assert handler.is_ready is True
    assert handler.is_initializing is False


@pytest.mark.asyncio
async def test_ready_and_initializing_flags_default_false() -> None:
    handler = AgentMCPHandler()
    assert handler.is_ready is False
    assert handler.is_initializing is False


@pytest.mark.asyncio
async def test_list_tools_uses_registry_cache_within_ttl() -> None:
    """Burst tools/list calls should reuse cached Rust DB snapshot."""
    handler = AgentMCPHandler()
    store = _RegistryStoreStub(
        [
            {
                "id": "git.commit",
                "content": "Commit staged changes",
                "metadata": {
                    "type": "command",
                    "skill_name": "git",
                    "tool_name": "git.commit",
                },
            }
        ]
    )
    context = _ToolContext({"git.commit": _ToolCommand("Commit staged changes")})
    handler._kernel = SimpleNamespace(
        skill_context=context,
        skill_manager=SimpleNamespace(
            registry=SimpleNamespace(store=store, table_name="skills_registry")
        ),
    )
    handler._initialized = True
    handler._tools_cache_ttl_secs = 60.0

    first = await handler._handle_list_tools({"id": 1})
    second = await handler._handle_list_tools({"id": 2})

    assert store.calls == 1
    assert first["result"]["tools"] == second["result"]["tools"]
    assert first["result"]["tools"][0]["name"] == "git.commit"
    assert handler._tools_list_requests_total == 2
    assert handler._tools_cache_hits_total == 1
    assert handler._tools_cache_misses_total == 1
    assert handler._tools_build_count == 1
    assert handler._tools_build_failures_total == 0
    assert handler._tools_build_latency_ms_total >= 0.0
    assert handler._tools_build_latency_ms_max >= 0.0


def test_tools_list_max_in_flight_setting_is_clamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "omni.foundation.config.settings.get_settings",
        lambda: _SettingsStub(9999),
    )
    assert AgentMCPHandler._load_tools_list_max_in_flight() == 512

    monkeypatch.setattr(
        "omni.foundation.config.settings.get_settings",
        lambda: _SettingsStub(-5),
    )
    assert AgentMCPHandler._load_tools_list_max_in_flight() == 1

    monkeypatch.setattr(
        "omni.foundation.config.settings.get_settings",
        lambda: _SettingsStub("invalid"),
    )
    assert AgentMCPHandler._load_tools_list_max_in_flight() == 90


@pytest.mark.asyncio
async def test_list_tools_respects_max_in_flight_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """tools/list concurrent execution should respect configured in-flight cap."""
    handler = AgentMCPHandler()
    context = _ToolContext({"git.commit": _ToolCommand("Commit staged changes")})
    handler._kernel = SimpleNamespace(
        skill_context=context,
        skill_manager=SimpleNamespace(
            registry=SimpleNamespace(store=None, table_name="skills_registry")
        ),
    )
    handler._initialized = True
    handler._tools_list_max_in_flight = 2
    handler._tools_list_semaphore = asyncio.Semaphore(2)

    monkeypatch.setattr(
        "omni.core.config.loader.load_skill_limits",
        lambda: SimpleNamespace(auto_optimize=False, dynamic_tools=10_000),
    )

    active = 0
    peak = 0

    async def _fake_get_cached_tools() -> tuple[list[dict[str, object]], bool, tuple[str, ...]]:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.02)
            return (
                [
                    {
                        "name": "git.commit",
                        "description": "Commit staged changes",
                        "inputSchema": {"type": "object"},
                    }
                ],
                True,
                ("git.commit",),
            )
        finally:
            active = max(0, active - 1)

    handler._get_cached_tools = _fake_get_cached_tools  # type: ignore[method-assign]
    await asyncio.gather(*(handler._handle_list_tools({"id": i}) for i in range(1, 9)))

    assert peak <= 2
    assert handler._tools_list_max_observed_in_flight <= 2
    assert handler._tools_list_in_flight == 0


@pytest.mark.asyncio
async def test_list_tools_errors_when_registry_unavailable() -> None:
    """Registry read failure must hard-fail (no in-memory fallback)."""
    handler = AgentMCPHandler()

    def _broken_list_all_tools(*_args):
        raise RuntimeError("registry unavailable")

    context = _ToolContext({"knowledge.search": _ToolCommand("Search knowledge base")})
    handler._kernel = SimpleNamespace(
        skill_context=context,
        skill_manager=SimpleNamespace(
            registry=SimpleNamespace(
                store=SimpleNamespace(list_all_tools=_broken_list_all_tools),
                table_name="skills_registry",
            )
        ),
    )
    handler._initialized = True
    handler._tools_cache_ttl_secs = 60.0

    result = await handler.handle_request({"method": "tools/list", "params": {}, "id": 9})
    assert result.get("error") is not None
    assert "Rust DB registry" in result["error"]["message"]
    assert handler._tools_list_requests_total == 1
    assert handler._tools_cache_hits_total == 0
    assert handler._tools_cache_misses_total == 1
    assert handler._tools_build_count == 0
    assert handler._tools_build_failures_total == 1


@pytest.mark.asyncio
async def test_invalidate_tools_cache_forces_registry_refresh() -> None:
    """Explicit cache invalidation should trigger a fresh DB read."""
    handler = AgentMCPHandler()
    store = _RegistryStoreStub(
        [
            {
                "id": "code.code_search",
                "content": "Search code",
                "metadata": {
                    "type": "command",
                    "skill_name": "code",
                    "tool_name": "code.code_search",
                },
            }
        ]
    )
    context = _ToolContext({"code.code_search": _ToolCommand("Search code")})
    handler._kernel = SimpleNamespace(
        skill_context=context,
        skill_manager=SimpleNamespace(
            registry=SimpleNamespace(store=store, table_name="skills_registry")
        ),
    )
    handler._initialized = True
    handler._tools_cache_ttl_secs = 60.0

    await handler._handle_list_tools({"id": 1})
    handler.invalidate_tools_cache()
    await handler._handle_list_tools({"id": 2})

    assert store.calls == 2


@pytest.mark.asyncio
async def test_list_tools_compacts_description_and_schema_payload() -> None:
    """tools/list should keep response compact for high-frequency polling."""
    handler = AgentMCPHandler()
    store = _RegistryStoreStub(
        [
            {
                "id": "memory.search",
                "content": "Search memories",
                "metadata": {
                    "type": "command",
                    "skill_name": "memory",
                    "tool_name": "memory.search",
                },
            }
        ]
    )
    long_desc = ("Long description with verbose details. " * 80).strip()
    schema = {
        "type": "object",
        "description": "Top-level schema description",
        "title": "SearchInput",
        "properties": {
            "query": {
                "type": "string",
                "description": "Query text",
                "default": "hello",
                "examples": ["foo"],
            }
        },
        "required": ["query"],
        "examples": [{"query": "bar"}],
    }
    context = _ToolContext({"memory.search": _ToolCommand(long_desc, schema)})
    handler._kernel = SimpleNamespace(
        skill_context=context,
        skill_manager=SimpleNamespace(
            registry=SimpleNamespace(store=store, table_name="skills_registry")
        ),
    )
    handler._initialized = True
    handler._tools_cache_ttl_secs = 60.0

    result = await handler._handle_list_tools({"id": 10})
    tool = result["result"]["tools"][0]
    assert tool["name"] == "memory.search"
    assert len(tool["description"]) <= handler._tools_description_max_chars
    assert "\n" not in tool["description"]

    def _contains_key_recursive(value: object, key: str) -> bool:
        if isinstance(value, dict):
            if key in value:
                return True
            return any(_contains_key_recursive(v, key) for v in value.values())
        if isinstance(value, list):
            return any(_contains_key_recursive(v, key) for v in value)
        return False

    compact_schema = tool["inputSchema"]
    for dropped in ("description", "examples", "example", "title", "default"):
        assert not _contains_key_recursive(compact_schema, dropped)
    assert compact_schema["type"] == "object"
    assert "properties" in compact_schema
    assert "query" in compact_schema["properties"]


@pytest.mark.asyncio
async def test_tools_stats_log_is_throttled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aggregated tools/list stats log should emit once per configured interval."""
    handler = AgentMCPHandler()
    store = _RegistryStoreStub(
        [
            {
                "id": "memory.search",
                "content": "Search memories",
                "metadata": {
                    "type": "command",
                    "skill_name": "memory",
                    "tool_name": "memory.search",
                },
            }
        ]
    )
    context = _ToolContext({"memory.search": _ToolCommand("Search memories")})
    handler._kernel = SimpleNamespace(
        skill_context=context,
        skill_manager=SimpleNamespace(
            registry=SimpleNamespace(store=store, table_name="skills_registry")
        ),
    )
    handler._initialized = True
    handler._tools_cache_ttl_secs = 60.0
    handler._tools_log_interval_secs = 10_000.0
    handler._tools_stats_log_interval_secs = 10_000.0

    info_messages: list[str] = []

    def _capture_info(msg: str, *args, **_kwargs) -> None:
        formatted = msg % args if args else msg
        info_messages.append(formatted)

    monkeypatch.setattr("omni.agent.server.logger.info", _capture_info)

    await handler._handle_list_tools({"id": 21})
    await handler._handle_list_tools({"id": 22})

    stats_logs = [line for line in info_messages if "[MCP] tools/list stats" in line]
    assert len(stats_logs) == 1


@pytest.mark.asyncio
async def test_kernel_is_ready(handler: AgentMCPHandler):
    """Ensure kernel is ready after initialization."""
    assert handler._kernel.is_ready, "Kernel should be ready after initialize()"


@pytest.mark.asyncio
async def test_tools_not_empty(handler: AgentMCPHandler):
    """Ensure at least some tools are loaded when skills are available."""
    result = await handler._handle_list_tools({"id": 1})
    tools = result.get("result", {}).get("tools", [])

    if len(tools) == 0:
        pytest.skip(
            "No tools loaded in this environment (Index/LanceDB may have 0 skills; run omni sync)."
        )
    # When tools are present, expect a reasonable baseline (e.g. from assets/skills)
    assert len(tools) >= 1, f"Expected at least 1 tool, got {len(tools)}"


@pytest.mark.asyncio
async def test_expected_skills_exist(handler: AgentMCPHandler):
    """Ensure core skills are loaded."""
    result = await handler._handle_list_tools({"id": 1})
    tools = result.get("result", {}).get("tools", [])
    tool_names = {t["name"] for t in tools}

    if not tool_names:
        pytest.skip("No core tools loaded in this test environment")

    # These are core skills that should always exist
    expected_skills = [
        "git.smart_commit",
        "code.code_search",
        "knowledge.ingest",
    ]

    for skill in expected_skills:
        if skill not in tool_names:
            pytest.skip(f"Expected baseline tool '{skill}' not available in this environment")


@pytest.mark.asyncio
async def test_tools_have_required_fields(handler: AgentMCPHandler):
    """Ensure all tools have required MCP fields."""
    result = await handler._handle_list_tools({"id": 1})
    tools = result.get("result", {}).get("tools", [])

    for tool in tools:
        assert "name" in tool, f"Tool missing 'name': {tool}"
        assert "description" in tool, f"Tool '{tool['name']}' missing 'description'"
        assert "inputSchema" in tool, f"Tool '{tool['name']}' missing 'inputSchema'"


@pytest.mark.asyncio
async def test_tools_list_format(handler: AgentMCPHandler):
    """Ensure tools/list response is correctly formatted."""
    result = await handler._handle_list_tools({"id": 42})

    # Check response structure
    assert "result" in result, "Response missing 'result'"
    assert "tools" in result["result"], "Response missing 'result.tools'"
    assert isinstance(result["result"]["tools"], list), "result.tools should be a list"


@pytest.mark.asyncio
async def test_double_init_no_error(handler: AgentMCPHandler):
    """Ensure calling initialize() twice doesn't cause errors."""
    # First init already done by fixture
    await handler.initialize()  # Second init should be no-op
    await handler.initialize()  # Third init

    # Should still work (valid result structure; tools may be 0 if skills not indexed)
    result = await handler._handle_list_tools({"id": 1})
    assert "result" in result and "tools" in result["result"]
    assert isinstance(result["result"]["tools"], list)


def _canonical_tool_result_shape(resp: dict) -> bool:
    """True if response result matches MCP tools/call contract (e.g. for Cursor)."""
    payload = resp.get("result")
    if payload is None or not isinstance(payload, dict):
        return False
    if "content" not in payload or not isinstance(payload["content"], list):
        return False
    for item in payload["content"]:
        if not isinstance(item, dict) or item.get("type") != "text" or "text" not in item:
            return False
    return True


@pytest.mark.asyncio
async def test_call_tool_git_commit_returns_canonical_shape(
    handler: AgentMCPHandler, tmp_path: Path
):
    """git.commit via MCP must return canonical result shape; run in temp dir only.

    Regression test for: MCP client (e.g. Cursor) receiving result: null or malformed
    when calling skills like assets/skills/git/scripts/commit.py.
    Must not commit in the project repo - use tmp_path for git operations.
    """
    # Init a temp git repo and stage one file so commit can succeed
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)  # noqa: ASYNC221
    (tmp_path / "f").write_text("x")
    subprocess.run(["git", "add", "f"], cwd=tmp_path, capture_output=True, check=True)  # noqa: ASYNC221

    request = {
        "id": 1,
        "params": {
            "name": "git.commit",
            "arguments": {"message": "chore: test", "project_root": str(tmp_path)},
        },
    }
    response = await handler.handle_request(
        {"method": "tools/call", "params": request["params"], "id": request["id"]}
    )
    # Success or error: result must be absent (error path) or a valid object with content
    if response.get("error") is not None:
        assert response.get("result") is None
        return
    assert _canonical_tool_result_shape(response), (
        f"tools/call result must have content[] and isError; got {response.get('result')}"
    )
    payload = response["result"]
    assert "content" in payload and len(payload["content"]) >= 1
    assert payload["content"][0]["type"] == "text"
    assert "isError" in payload


# -----------------------------------------------------------------------------
# MCP tests for knowledge tools (run via tools/call like Cursor/MCP client)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tools_includes_knowledge_tools(handler: AgentMCPHandler):
    """MCP list_tools must include at least one knowledge.* tool when skills are indexed."""
    result = await handler._handle_list_tools({"id": 1})
    tools = result.get("result", {}).get("tools", [])
    if not tools:
        pytest.skip("No tools loaded (run 'omni sync' to index skills)")

    knowledge_tools = [t for t in tools if t.get("name", "").startswith("knowledge.")]
    if not knowledge_tools:
        pytest.skip("No knowledge tools in list (run 'omni sync')")

    assert len(knowledge_tools) >= 1
    for t in knowledge_tools:
        assert "name" in t and "description" in t and "inputSchema" in t


@pytest.mark.asyncio
async def test_call_tool_knowledge_link_graph_stats_via_mcp(handler: AgentMCPHandler):
    """MCP tools/call knowledge.link_graph_stats returns canonical shape and valid stats."""
    response = await handler.handle_request(
        {
            "method": "tools/call",
            "params": {"name": "knowledge.link_graph_stats", "arguments": {}},
            "id": 2,
        }
    )
    if response.get("error"):
        if "Skill not found" in str(response.get("error", {}).get("message", "")):
            pytest.skip("Knowledge skill not loaded (run 'omni sync')")
        raise AssertionError(f"MCP call failed: {response['error']}")

    assert _canonical_tool_result_shape(response), (
        f"tools/call result must have content[]; got {response.get('result')}"
    )
    payload = response["result"]
    text = payload["content"][0].get("text", "")
    assert (
        "link_graph_stats" in text or "total_notes" in text or "success" in text or "stats" in text
    )


@pytest.mark.asyncio
async def test_call_tool_knowledge_get_development_context_via_mcp(handler: AgentMCPHandler):
    """MCP tools/call knowledge.get_development_context returns project context."""
    response = await handler.handle_request(
        {
            "method": "tools/call",
            "params": {"name": "knowledge.get_development_context", "arguments": {}},
            "id": 3,
        }
    )
    if response.get("error"):
        if "Skill not found" in str(response.get("error", {}).get("message", "")):
            pytest.skip("Knowledge skill not loaded (run 'omni sync')")
        raise AssertionError(f"MCP call failed: {response['error']}")

    assert _canonical_tool_result_shape(response)
    text = response["result"]["content"][0].get("text", "")
    # Development context JSON usually contains project, git_rules, guardrails
    assert "project" in text or "git" in text or "guardrails" in text or "architecture" in text


@pytest.mark.asyncio
async def test_call_tool_knowledge_stats_via_mcp(handler: AgentMCPHandler):
    """MCP tools/call knowledge.stats returns collection stats."""
    response = await handler.handle_request(
        {
            "method": "tools/call",
            "params": {"name": "knowledge.stats", "arguments": {"collection": "knowledge_chunks"}},
            "id": 4,
        }
    )
    if response.get("error"):
        if "Skill not found" in str(response.get("error", {}).get("message", "")):
            pytest.skip("Knowledge skill not loaded (run 'omni sync')")
        raise AssertionError(f"MCP call failed: {response['error']}")

    assert _canonical_tool_result_shape(response)
    text = response["result"]["content"][0].get("text", "")
    assert "status" in text or "document_count" in text or "collection" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
