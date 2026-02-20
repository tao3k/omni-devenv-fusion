"""
agent/server.py - Agent MCP Handler (Thin Client)

Trinity Architecture - Agent Layer

This adapter is now a pure thin client that delegates all lifecycle
and execution management to the Core Kernel.

Logging: Uses Foundation layer (omni.foundation.config.logging)
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, TypedDict

from omni.core.kernel import get_kernel
from omni.foundation.config.logging import get_logger
from omni.mcp.interfaces import MCPRequestHandler

# Logger will be configured on first use via get_logger's lazy initialization
logger = get_logger("omni.agent.server")


# JSON-RPC Response types (plain dicts for outgoing responses)
class JSONRPCError(TypedDict):
    """Error object for JSON-RPC error responses."""

    code: int
    message: str


class JSONRPCResponse(TypedDict):
    """JSON-RPC response (success or error)."""

    jsonrpc: str
    id: str | int | None
    result: dict[str, Any] | None
    error: JSONRPCError | None


# Error codes (matching MCP SDK constants)
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def _make_success_response(id_val: str | int | None, result: Any) -> JSONRPCResponse:
    """Create a success response. JSON-RPC 2.0: only 'result', no 'error' key."""
    return {
        "jsonrpc": "2.0",
        "id": id_val,
        "result": result,
    }


def _make_error_response(id_val: str | int | None, code: int, message: str) -> JSONRPCResponse:
    """Create an error response. JSON-RPC 2.0: only 'error', no 'result' key."""
    return {
        "jsonrpc": "2.0",
        "id": id_val,
        "error": {"code": code, "message": message},
    }


class AgentMCPHandler(MCPRequestHandler):
    """
    Thin MCP Adapter for the Kernel.
    """

    def __init__(self):
        self._initialized = False
        self._initializing = False
        self._initialize_lock = asyncio.Lock()
        self._verbose = False
        self._kernel = get_kernel()
        self._tools_cache: list[dict[str, Any]] | None = None
        self._tools_cache_signature: tuple[str, ...] = ()
        self._tools_cache_at_monotonic = 0.0
        self._tools_cache_ttl_secs = 1.0
        self._tools_cache_lock = asyncio.Lock()
        self._tools_list_max_in_flight = self._load_tools_list_max_in_flight()
        self._tools_list_semaphore = asyncio.Semaphore(self._tools_list_max_in_flight)
        self._tools_list_in_flight = 0
        self._tools_list_max_observed_in_flight = 0
        self._tools_log_interval_secs = 15.0
        self._tools_last_info_log_at = 0.0
        self._tools_last_logged_signature: tuple[str, ...] = ()
        self._tools_description_max_chars = self._load_tools_description_max_chars()
        self._tools_stats_log_interval_secs = 60.0
        self._tools_stats_last_log_at = 0.0
        self._tools_list_requests_total = 0
        self._tools_cache_hits_total = 0
        self._tools_cache_misses_total = 0
        self._tools_build_failures_total = 0
        self._tools_build_count = 0
        self._tools_build_latency_ms_total = 0.0
        self._tools_build_latency_ms_max = 0.0

    @staticmethod
    def _load_tools_description_max_chars() -> int:
        """Load tools/list description cap from settings with safe bounds."""
        default = 140
        minimum = 80
        maximum = 500
        try:
            from omni.foundation.config.settings import get_settings

            raw = get_settings().get("mcp.tools_list.description_max_chars", default)
            value = int(raw)
            return max(minimum, min(value, maximum))
        except Exception:
            return default

    @staticmethod
    def _load_tools_list_max_in_flight() -> int:
        """Load tools/list in-flight concurrency cap from settings with safe bounds."""
        default = 90
        minimum = 1
        maximum = 512
        try:
            from omni.foundation.config.settings import get_settings

            raw = get_settings().get("mcp.tools_list.max_in_flight", default)
            value = int(raw)
            return max(minimum, min(value, maximum))
        except Exception:
            return default

    def set_verbose(self, verbose: bool) -> None:
        """Set verbose mode before initialization."""
        self._verbose = verbose

    @property
    def is_ready(self) -> bool:
        """True when MCP handler finished kernel bootstrap and is ready for requests."""
        return self._initialized

    @property
    def is_initializing(self) -> bool:
        """True while kernel bootstrap is in progress."""
        return self._initializing

    async def initialize(self) -> None:
        """Boot the Kernel when MCP handshake completes."""
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            started = time.perf_counter()
            self._initializing = True
            try:
                logger.info("🚀 [Agent] Booting Kernel...")

                # Delegate all lifecycle management to Kernel
                await self._kernel.initialize()

                # Ensure Kernel enters RUNNING so Live-Wire watcher/hot-reload starts.
                if not self._kernel.is_running:
                    logger.info("⚡ [Agent] Starting Kernel runtime (Live-Wire watcher)...")
                    await self._kernel.start()

                if self._kernel.skill_manager and self._kernel.skill_manager.watcher:
                    logger.info("⚡ [Agent] Live-Wire watcher active")
                else:
                    logger.warning("⚠️ [Agent] Live-Wire watcher is not active")

                # Note: Embedding warmup is now handled externally by MCP server (mcp.py)
                # to ensure proper startup order: server first, then model loading

                self._initialized = True
                logger.info(
                    "✅ [Agent] Ready. Active skills: %d (init_ms=%.1f)",
                    len(self._kernel.skill_context.list_skills()),
                    (time.perf_counter() - started) * 1000.0,
                )
            finally:
                self._initializing = False

    async def handle_request(self, request: dict) -> JSONRPCResponse:
        """Handle a JSON-RPC request."""
        if not self._initialized:
            await self.initialize()

        # TypedDict access using .get() for safety
        method = request.get("method", "")
        req_id = request.get("id")

        try:
            if method == "initialize":
                return await self._handle_initialize(request)
            elif method == "tools/list":
                return await self._handle_list_tools(request)
            elif method == "tools/call":
                return await self._handle_call_tool(request)
            # Forward other methods or handle specifically
            elif method.startswith("resources/") or method.startswith("prompts/"):
                # Placeholder for future Kernel capabilities
                return _make_success_response(req_id, {method.split("/")[0]: []})
            else:
                return _make_error_response(
                    req_id,
                    METHOD_NOT_FOUND,
                    f"Method not found: {method}",
                )

        except Exception as e:
            logger.error("Request error", error=str(e))
            return _make_error_response(req_id, INTERNAL_ERROR, str(e))

    async def handle_notification(self, method: str, params: Any) -> None:
        """Handle notifications from MCP client."""
        logger.debug(f"Received notification: {method}")
        if method == "notifications/state":
            # Client is notifying that its state has changed
            # Just acknowledge, no response needed for notifications
            logger.info("Client state notification received")
        # Add other notification handlers as needed

    async def _handle_initialize(self, request: dict) -> JSONRPCResponse:
        await self.initialize()
        req_id = request.get("id")
        return _make_success_response(
            req_id,
            {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "omni-agent", "version": "2.0.0"},
                "capabilities": {
                    "tools": {"listChanged": True},  # Kernel supports dynamic loading
                },
            },
        )

    def invalidate_tools_cache(self) -> None:
        """Invalidate tools/list cache (used by hot-reload paths)."""
        self._tools_cache = None
        self._tools_cache_signature = ()
        self._tools_cache_at_monotonic = 0.0

    def _build_tool_entry_from_command(
        self,
        full_name: str,
        cmd: Any,
        description_hint: str | None = None,
    ) -> dict[str, Any]:
        """Build MCP tool entry from a command object."""
        config = getattr(cmd, "_skill_config", {})
        if not isinstance(config, dict):
            config = {}

        description = (
            (description_hint or "").strip()
            or config.get("description", "")
            or getattr(cmd, "description", "")
            or f"Run {full_name}"
        )
        description = self._compact_tool_description(description)

        raw_schema = config.get("input_schema")
        if raw_schema is None:
            raw_schema = getattr(cmd, "input_schema", None)

        input_schema = (
            self._compact_input_schema(raw_schema) if isinstance(raw_schema, dict) else {}
        )
        if "type" not in input_schema:
            input_schema["type"] = "object"

        return {
            "name": full_name,
            "description": description,
            "inputSchema": input_schema,
        }

    def _compact_tool_description(self, description: str) -> str:
        """Normalize and cap tool descriptions for tools/list payload size."""
        normalized = " ".join((description or "").split())
        if len(normalized) <= self._tools_description_max_chars:
            return normalized
        cutoff = self._tools_description_max_chars
        return normalized[: cutoff - 3].rstrip() + "..."

    def _compact_input_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Strip non-essential schema metadata to reduce tools/list payload."""
        drop_keys = {
            "description",
            "examples",
            "example",
            "title",
            "$comment",
            "markdownDescription",
            "default",
        }

        def walk(value: Any) -> Any:
            if isinstance(value, dict):
                out: dict[str, Any] = {}
                for key, item in value.items():
                    if key in drop_keys:
                        continue
                    out[key] = walk(item)
                return out
            if isinstance(value, list):
                return [walk(item) for item in value]
            return value

        compacted = walk(schema)
        return compacted if isinstance(compacted, dict) else {}

    def _build_tools_from_rust_registry(
        self,
        context: Any,
        is_filtered: Any,
    ) -> list[dict[str, Any]]:
        """Read command inventory from Rust DB registry (required path)."""
        skill_manager = getattr(self._kernel, "skill_manager", None)
        registry = getattr(skill_manager, "registry", None) if skill_manager else None
        store = getattr(registry, "store", None) if registry else None
        if store is None:
            raise RuntimeError("Rust DB registry is unavailable for tools/list")

        table_name = getattr(registry, "table_name", "skills_registry")
        try:
            raw_rows = store.list_all_tools(table_name, None)
        except Exception as exc:
            raise RuntimeError(f"Rust DB registry list_all_tools failed: {exc}") from exc

        try:
            if isinstance(raw_rows, str):
                rows = json.loads(raw_rows) if raw_rows else []
            elif isinstance(raw_rows, list):
                rows = raw_rows
            else:
                raise RuntimeError("Rust DB registry returned unsupported payload type")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Rust DB registry payload decode failed: {exc}") from exc

        if not isinstance(rows, list):
            raise RuntimeError("Rust DB registry payload is not a list")

        tools: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue

            metadata = row.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}
            if not isinstance(metadata, dict):
                metadata = {}

            record_type = str(metadata.get("type", "")).strip().lower()
            if record_type and record_type != "command":
                continue

            skill_name = str(metadata.get("skill_name") or row.get("skill_name") or "").strip()
            tool_name = str(
                metadata.get("tool_name") or row.get("tool_name") or row.get("id") or ""
            ).strip()

            if "." in tool_name:
                full_name = tool_name
            elif skill_name and tool_name:
                full_name = f"{skill_name}.{tool_name}"
            else:
                full_name = str(row.get("id") or "").strip()

            if not full_name or "." not in full_name:
                continue
            if is_filtered(full_name):
                continue
            if full_name in seen:
                continue

            cmd = context.get_command(full_name)
            if cmd is None:
                # Registry may still contain stale rows during a brief hot-reload window.
                continue

            description_hint = str(row.get("description") or row.get("content") or "").strip()
            tools.append(self._build_tool_entry_from_command(full_name, cmd, description_hint))
            seen.add(full_name)

        tools.sort(key=lambda item: item["name"])
        return tools

    def _build_tools_snapshot(self) -> list[dict[str, Any]]:
        """Build a fresh tools snapshot from Rust DB registry."""
        context = self._kernel.skill_context

        from omni.core.config.loader import is_filtered

        return self._build_tools_from_rust_registry(context, is_filtered)

    def _record_tools_build_success(self, elapsed_ms: float) -> None:
        """Track successful Rust DB snapshot build latency."""
        self._tools_build_count += 1
        self._tools_build_latency_ms_total += elapsed_ms
        if elapsed_ms > self._tools_build_latency_ms_max:
            self._tools_build_latency_ms_max = elapsed_ms

    def _record_tools_build_failure(self) -> None:
        """Track failed Rust DB snapshot build attempts."""
        self._tools_build_failures_total += 1

    def _log_tools_stats(self) -> None:
        """Periodically emit aggregated tools/list cache and build metrics."""
        now = time.monotonic()
        if now - self._tools_stats_last_log_at < self._tools_stats_log_interval_secs:
            return

        self._tools_stats_last_log_at = now
        total = self._tools_list_requests_total
        hit_rate = (self._tools_cache_hits_total / total * 100.0) if total else 0.0
        avg_build_ms = (
            self._tools_build_latency_ms_total / self._tools_build_count
            if self._tools_build_count
            else 0.0
        )
        logger.info(
            "[MCP] tools/list stats requests=%d hit_rate=%.1f%% cache_hits=%d "
            "cache_misses=%d build_count=%d build_failures=%d build_avg_ms=%.2f "
            "build_max_ms=%.2f in_flight=%d peak_in_flight=%d max_in_flight=%d",
            total,
            hit_rate,
            self._tools_cache_hits_total,
            self._tools_cache_misses_total,
            self._tools_build_count,
            self._tools_build_failures_total,
            avg_build_ms,
            self._tools_build_latency_ms_max,
            self._tools_list_in_flight,
            self._tools_list_max_observed_in_flight,
            self._tools_list_max_in_flight,
        )

    async def _get_cached_tools(self) -> tuple[list[dict[str, Any]], bool, tuple[str, ...]]:
        """Read tools snapshot from cache, rebuilding with singleflight when stale."""
        now = time.monotonic()
        if (
            self._tools_cache is not None
            and now - self._tools_cache_at_monotonic < self._tools_cache_ttl_secs
        ):
            self._tools_cache_hits_total += 1
            return self._tools_cache, True, self._tools_cache_signature

        async with self._tools_cache_lock:
            now = time.monotonic()
            if (
                self._tools_cache is not None
                and now - self._tools_cache_at_monotonic < self._tools_cache_ttl_secs
            ):
                self._tools_cache_hits_total += 1
                return self._tools_cache, True, self._tools_cache_signature

            self._tools_cache_misses_total += 1
            started = time.perf_counter()
            try:
                tools = self._build_tools_snapshot()
            except Exception:
                self._record_tools_build_failure()
                raise
            finally:
                elapsed_ms = (time.perf_counter() - started) * 1000.0

            self._record_tools_build_success(elapsed_ms)
            self._tools_cache = tools
            self._tools_cache_signature = tuple(tool.get("name", "") for tool in tools)
            self._tools_cache_at_monotonic = now
            return tools, False, self._tools_cache_signature

    def _log_tools_inventory(
        self,
        *,
        tools: list[dict[str, Any]],
        signature: tuple[str, ...],
        context: Any,
        cache_hit: bool,
        limited: bool,
    ) -> None:
        """Throttle info logs for high-frequency tools/list polling."""
        now = time.monotonic()
        should_log_info = (
            signature != self._tools_last_logged_signature
            or now - self._tools_last_info_log_at >= self._tools_log_interval_secs
        )

        if should_log_info:
            filtered_count = len(context.get_filtered_commands())
            available_count = len(context.list_commands())
            skill_count = len(context.list_skills())
            self._tools_last_logged_signature = signature
            self._tools_last_info_log_at = now
            if limited:
                logger.info(
                    "📦 [Dynamic Loader] Limited to %d tools "
                    "(cache_hit=%s, |filtered|=%d, |available|=%d, skills=%d)",
                    len(tools),
                    cache_hit,
                    filtered_count,
                    available_count,
                    skill_count,
                )
            else:
                logger.info(
                    "📦 [Dynamic Loader] %d core tools ready "
                    "(cache_hit=%s, |filtered|=%d, |available|=%d, skills=%d)",
                    len(tools),
                    cache_hit,
                    filtered_count,
                    available_count,
                    skill_count,
                )
        else:
            logger.debug(
                "[MCP] tools/list served %d tools (cache_hit=%s)",
                len(tools),
                cache_hit,
            )

        self._log_tools_stats()

    async def _handle_list_tools(self, request: dict) -> JSONRPCResponse:
        """List tools with cached, registry-first strategy for MCP polling workloads."""
        async with self._tools_list_semaphore:
            self._tools_list_in_flight += 1
            if self._tools_list_in_flight > self._tools_list_max_observed_in_flight:
                self._tools_list_max_observed_in_flight = self._tools_list_in_flight

            try:
                self._tools_list_requests_total += 1
                context = self._kernel.skill_context
                tools, cache_hit, signature = await self._get_cached_tools()

                from omni.core.config.loader import load_skill_limits

                limits = load_skill_limits()

                limited = False
                if limits.auto_optimize and len(tools) > limits.dynamic_tools:
                    tools = tools[: limits.dynamic_tools]
                    limited = True

                self._log_tools_inventory(
                    tools=tools,
                    signature=signature,
                    context=context,
                    cache_hit=cache_hit,
                    limited=limited,
                )

                filtered_commands = set(context.get_filtered_commands()) if self._verbose else set()

                if filtered_commands:
                    logger.debug("🔇 Filtered commands: %s", sorted(filtered_commands))

                req_id = request.get("id")
                return _make_success_response(req_id, {"tools": tools})
            finally:
                self._tools_list_in_flight = max(0, self._tools_list_in_flight - 1)

    async def _handle_call_tool(self, request: dict) -> JSONRPCResponse:
        """Execute skill via Kernel Context."""
        params = request.get("params") or {}
        req_id = request.get("id")
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        logger.debug("[MCP] _handle_call_tool called with name=%s", name)

        # [NEW] Handle embedding tool calls directly (both "embed_texts" and "embedding.embed_texts")
        if name == "embed_texts" or name == "embedding.embed_texts":
            logger.debug("[MCP] Calling _handle_embed_texts")
            return await self._handle_embed_with_memory(
                name, self._handle_embed_texts, req_id, arguments
            )
        elif name == "embed_single" or name == "embedding.embed_single":
            logger.debug("[MCP] Calling _handle_embed_single")
            return await self._handle_embed_with_memory(
                name, self._handle_embed_single, req_id, arguments
            )

        if "." not in name:
            return _make_error_response(req_id, INVALID_PARAMS, "Tool name must be 'skill.command'")

        skill_name, command_name = name.split(".", 1)

        skill = self._kernel.skill_context.get_skill(skill_name)
        if not skill:
            return _make_error_response(req_id, INVALID_PARAMS, f"Skill not found: {skill_name}")

        try:
            from omni.agent.mcp_server.memory_monitor import amemory_monitor_scope
            from omni.foundation.api.mcp_schema import (
                build_result,
                enforce_result_shape,
                is_canonical,
            )

            async with amemory_monitor_scope(name):
                result = await skill.execute(command_name, **arguments)
            if is_canonical(result):
                return _make_success_response(req_id, enforce_result_shape(result))
            text = "" if result is None else str(result)
            return _make_success_response(req_id, build_result(text))
        except Exception as e:
            return _make_error_response(req_id, INTERNAL_ERROR, str(e))

    async def _handle_embed_with_memory(
        self,
        name: str,
        handler: Any,
        req_id: str | int | None,
        arguments: dict,
    ) -> JSONRPCResponse:
        """Wrap embed handlers with memory monitoring when enabled."""
        from omni.agent.mcp_server.memory_monitor import amemory_monitor_scope

        async with amemory_monitor_scope(name):
            return await handler(req_id, arguments)

    async def _handle_embed_texts(
        self, req_id: str | int | None, arguments: dict
    ) -> JSONRPCResponse:
        """Handle embed_texts tool call via preloaded embedding service.

        The embedding backend is sync and can block on network IO (e.g. Ollama).
        Always offload to a worker thread so the MCP event loop stays responsive
        for tools/list, health probes, and other sessions.
        """
        texts = arguments.get("texts", [])
        if not texts:
            return _make_error_response(req_id, INVALID_PARAMS, "'texts' parameter required")

        logger.debug("[MCP] _handle_embed_texts: processing %s texts", len(texts))

        try:
            from omni.foundation.services.embedding import embed_batch, get_embedding_service

            logger.debug("[MCP] Getting embedding service...")
            embed_service = get_embedding_service()
            logger.debug("[MCP] Service dimension: %s", embed_service.dimension)

            logger.debug("[MCP] Generating embeddings...")
            vectors = await asyncio.to_thread(embed_batch, texts)
            logger.debug("[MCP] Generated %s vectors", len(vectors))

            result = {
                "success": True,
                "count": len(vectors),
                "dimension": embed_service.dimension,
                # Return full vectors for hybrid search
                "vectors": vectors,
            }

            from omni.foundation.api.mcp_schema import build_result

            logger.debug("[MCP] Returning result: count=%s", len(vectors))
            return _make_success_response(
                req_id, build_result(json.dumps(result, separators=(",", ":")))
            )
        except Exception as e:
            from omni.foundation.services.embedding import EmbeddingUnavailableError

            if isinstance(e, EmbeddingUnavailableError):
                logger.warning(
                    "[MCP] _handle_embed_texts unavailable",
                    error=str(e),
                )
            else:
                logger.exception("[MCP] _handle_embed_texts unexpected error")
            return _make_error_response(req_id, INTERNAL_ERROR, str(e))

    async def _handle_embed_single(
        self, req_id: str | int | None, arguments: dict
    ) -> JSONRPCResponse:
        """Handle embed_single tool call via preloaded embedding service.

        Offload sync embedding work to a worker thread to avoid blocking MCP.
        """
        text = arguments.get("text", "")
        if not text:
            return _make_error_response(req_id, INVALID_PARAMS, "'text' parameter required")

        try:
            from omni.foundation.services.embedding import embed_text, get_embedding_service

            embed_service = get_embedding_service()
            vector = await asyncio.to_thread(embed_text, text)

            result = {
                "success": True,
                "dimension": embed_service.dimension,
                # Return full vector
                "vector": vector,
            }

            from omni.foundation.api.mcp_schema import build_result

            return _make_success_response(
                req_id, build_result(json.dumps(result, separators=(",", ":")))
            )
        except Exception as e:
            from omni.foundation.services.embedding import EmbeddingUnavailableError

            if isinstance(e, EmbeddingUnavailableError):
                logger.warning(
                    "[MCP] _handle_embed_single unavailable",
                    error=str(e),
                )
            else:
                logger.exception("[MCP] _handle_embed_single unexpected error")
            return _make_error_response(req_id, INTERNAL_ERROR, str(e))


def create_agent_handler() -> AgentMCPHandler:
    return AgentMCPHandler()


__all__ = ["AgentMCPHandler", "JSONRPCError", "JSONRPCResponse", "create_agent_handler"]
