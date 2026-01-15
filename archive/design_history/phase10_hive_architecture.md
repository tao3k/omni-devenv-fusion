# Spec: Phase 10 - The Hive Architecture (Antifragile Edition)

> **Status**: Completed (Milestone Reached)
> **Complexity**: L3
> **Owner**: @omni-orchestrator
> **Version**: 3.0 Antifragile (includes Phase 10.5)

## 1. Context & Goal (Why)

**The Hive** is a distributed multi-process architecture solving critical issues:

- **Deadlock**: Worker processes stuck waiting for stdout flush
- **Buffering**: Python's output buffering causing IPC deadlock
- **Path Resolution**: Worker subprocess unable to find modules
- **Resilience**: Worker crashes without automatic recovery

**Goals**:

1. Enable safe code execution in isolated subprocesses with proper IPC
2. **Phase 10.5**: Add auto-healing, circuit breaker, and health monitoring

## 2. Architecture & Interface (What)

### 2.1 Components

| Component   | File                        | Purpose                                         |
| ----------- | --------------------------- | ----------------------------------------------- |
| SwarmNode   | `services/swarm.py` v3      | Neural Link v3 - Auto-healing & Circuit Breaker |
| CoderWorker | `services/coder_service.py` | Worker Protocol v2 - Tool delegation            |
| HiveManager | `orchestrator.py`           | Lazy loading & fallback routing                 |

### 2.2 Phase 10.5 New Features (v3)

| Feature         | Description                                    |
| --------------- | ---------------------------------------------- |
| Auto-Reconnect  | Worker automatically reconnects after crash    |
| Circuit Breaker | Opens after 3 failures, cooldown 30s           |
| Health Checks   | `swarm_status()` returns full metrics          |
| Node Metrics    | Latency, success/fail counts, restarts tracked |

### 2.3 Key Design Decisions

1. **Environment Isolation**: `PYTHONUNBUFFERED=1` prevents buffering deadlock
2. **PYTHONPATH Injection**: Worker finds modules via `PYTHONPATH={server_root}:{current}`
3. **Lazy Loading**: Worker starts on first use, reused for subsequent calls
4. **Graceful Fallback**: Returns instruction strings when Worker unavailable
5. **Circuit Breaker**: Prevents cascading failures by blocking requests after repeated failures

### 2.4 Flow Diagram

```
Orchestrator (Main Process)
    │
    ├─── swarm_status()  ───→ Health Check Response
    │                         (latency, restarts, circuit state)
    │
    ├─── delegate_to_coder(task, details)
    │
    ├────────────────┬──────────────────┐
    │                │                  │
    Worker Available    Circuit OPEN        Worker Unavailable
    │                │                  │
    ▼                ▼                  ▼
SwarmNode.connect()   Wait/Retry       Fallback Mode
    │                                     (Return instructions)
    ▼
IPC Established
    │
    ▼
node.call_tool()
    │
    ├─── Success → Update metrics
    │
    ├─── Failure → Retry (auto-healing)
    │              └── 3 failures → Open Circuit (30s cooldown)
    │
    ▼
Return Result
```

## 3. Implementation (How)

### 3.1 SwarmNode (services/swarm.py v3)

```python
class NodeMetrics:
    total_calls: int
    success_count: int
    failure_count: int
    restarts: int
    avg_latency_ms: float

class SwarmNode:
    async def connect(self) -> bool:
        # Environment: PYTHONUNBUFFERED=1, PYTHONPATH injection
        # Auto-reconnect if previously connected

    async def call_tool(self, name, args, retries=2) -> CallToolResult:
        # Circuit breaker: fail 3 times → OPEN (30s cooldown)
        # Auto-reconnect on connection loss
        # Metrics tracking: latency, success/fail counts
```

### 3.2 Authorization Guard (git_ops.py)

```python
class AuthorizationGuard:
    # Token-based commit authorization
    # Token expires after 5 minutes
    # Single-use validation
    # Prevents bypass via run_task
```

## 4. Testing Strategy

| Level       | Test File                   | Coverage                                    |
| ----------- | --------------------------- | ------------------------------------------- |
| Unit        | `test_hive_architecture.py` | Connection lifecycle, tool execution        |
| Unit        | `test_git_ops_v2.py`        | AuthorizationGuard (6 tests)                |
| **Chaos**   | `test_hive_robustness.py`   | **Auto-healing, Circuit Breaker (6 tests)** |
| Integration | `test_basic.py`             | Full delegation flow                        |
| Router      | `test_router.py`            | Tool routing classification                 |

## 5. Trade-offs & Constraints

- **Trade-off**: IPC overhead vs. isolation safety → Acceptable
- **Constraint**: Worker must be MCP-compatible
- **Fallback**: Always works without subprocess (instructions mode)
- **Circuit Breaker**: May delay retry attempts during cooldown

## 6. Rollout Plan

1. ✅ Phase 10 merged to main
2. ✅ `swarm_status()` monitors worker health
3. ✅ Auto-healing and circuit breaker active
4. ✅ Chaos engineering tests pass (`test_hive_robustness.py`)
5. ⏳ Enable direct mode by default (future)

## 7. Related Documents

| Document                                | Purpose                           |
| --------------------------------------- | --------------------------------- |
| `agent/how-to/git-workflow.md`          | Git commit authorization protocol |
| `agent/instructions/problem-solving.md` | Deep reasoning framework          |
| `agent/standards/lang-python.md`        | Python development practices      |
