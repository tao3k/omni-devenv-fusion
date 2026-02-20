# MCP Tool Timeout Specification

Formal specification for MCP tool execution timeouts. Ensures logically rigorous behavior: tools are cancelled only when stuck (no progress) or when a hard cap is reached.

## Definitions

| Term              | Config Key         | Type    | Meaning                                                                                              |
| ----------------- | ------------------ | ------- | ---------------------------------------------------------------------------------------------------- |
| **Total timeout** | `mcp.timeout`      | seconds | Hard wall-clock cap. Tool is cancelled when elapsed time ≥ this value, regardless of heartbeat.      |
| **Idle timeout**  | `mcp.idle_timeout` | seconds | Progress-based limit. Tool is cancelled when no `heartbeat()` has been called for this many seconds. |

## Invariants

The following invariants must hold for the timeout logic to be well-defined:

1. **Total cap**: `timeout ≥ 0`. `0` means no wall-clock cap (unbounded).
2. **Idle constraint**: `idle_timeout ≥ 0`. `0` means no idle check (only total cap applies).
3. **Consistency** (when both > 0): `idle_timeout ≤ timeout`.
   - Rationale: If `idle_timeout > timeout`, the total cap would always fire first, making idle detection meaningless.
   - Implementation: Config loader clamps `idle_timeout = min(idle_timeout, timeout)` when both are set.

## Cancellation Conditions

A tool is cancelled when **either** condition is met (whichever occurs first):

| Condition | Trigger                               | Error message                                                                                    |
| --------- | ------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **Idle**  | `now - last_heartbeat ≥ idle_timeout` | "No progress for {idle_timeout}s (idle timeout). Tool should call heartbeat() during long work." |
| **Total** | `now - start ≥ timeout`               | "Tool exceeded wall-clock limit of {timeout}s."                                                  |

If `idle_timeout = 0`, only the total condition applies. If `timeout = 0`, only the idle condition applies (no wall-clock cap).

## Tool Obligations

Tools that perform long-running work (e.g. LLM calls, repomix, file I/O) **must** call `heartbeat()` periodically:

- **Minimum frequency**: `heartbeat()` at least every `idle_timeout / 2` seconds.
- **Recommended**: Every 10 seconds during long work (e.g. researcher architect, process_shard).
- **Implementation**: Use `run_with_heartbeat(coro)` from `omni.foundation.api.tool_context` to wrap long work, or call `heartbeat()` inside loops.

If a tool never calls `heartbeat()` and `idle_timeout > 0`, it will be cancelled after `idle_timeout` seconds (treated as stuck).

## Runner Behavior

MCP server and CLI skill runner both use the unified interface:

```python
from omni.foundation.api.tool_context import run_with_execution_timeout

result = await run_with_execution_timeout(kernel.execute_tool(...))
```

- `run_with_execution_timeout` reads `mcp.timeout` and `mcp.idle_timeout` from config.
- It sets `tool_context` so `heartbeat()` is available.
- Callers must not read timeout config or call `run_with_idle_timeout` directly.

## Recommended Values

| Scenario            | timeout | idle_timeout | Rationale                                                                                         |
| ------------------- | ------- | ------------ | ------------------------------------------------------------------------------------------------- |
| **Default**         | 1800    | 120          | With heartbeat: allow long tasks (e.g. researcher); prevent runaway. Without: idle kills at 120s. |
| **Fast tools only** | 60      | 30           | Shorter limits for lightweight workflows.                                                         |
| **No idle check**   | 180     | 0            | No heartbeat: 180s cap as safety net for stuck tools.                                             |
| **Unbounded total** | 0       | 120          | Allow long runs; cancel only when stuck (use with caution).                                       |

## Validation Rules

When loading config:

1. If `idle_timeout > timeout` and both > 0: clamp `idle_timeout = timeout` and log a warning.
2. Reject negative values (treat as 0).

## References

- Implementation: `packages/python/foundation/src/omni/foundation/api/tool_context.py` (`run_with_execution_timeout`, `run_with_heartbeat`, `run_with_idle_timeout`)
- Config: `packages/conf/settings.yaml` under `mcp.timeout`, `mcp.idle_timeout`
- SSE transport: `session_timeout = tool_timeout + 30` (buffer for response serialization)
- Usage: `assets/skills/researcher/scripts/research_graph.py`, `assets/skills/knowledge/scripts/graph.py` (ingest_document)
