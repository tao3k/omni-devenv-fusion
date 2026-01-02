# Spec: Phase 10 - The Hive Architecture

> **Status**: Completed
> **Complexity**: L3
> **Owner**: @omni-orchestrator

## 1. Context & Goal (Why)

**The Hive** is a distributed multi-process architecture solving critical issues:

- **Deadlock**: Worker processes stuck waiting for stdout flush
- **Buffering**: Python's output buffering causing IPC deadlock
- **Path Resolution**: Worker subprocess unable to find modules

**Goal**: Enable safe code execution in isolated subprocesses with proper IPC, timeout protection, and fallback modes.

## 2. Architecture & Interface (What)

### 2.1 Components

| Component   | File                        | Purpose                                  |
| ----------- | --------------------------- | ---------------------------------------- |
| SwarmNode   | `services/swarm.py`         | Neural Link v2 - Process lifecycle & IPC |
| CoderWorker | `services/coder_service.py` | Worker Protocol v2 - Tool delegation     |
| HiveManager | `orchestrator.py`           | Lazy loading & fallback routing          |

### 2.2 Key Design Decisions

1. **Environment Isolation**: `PYTHONUNBUFFERED=1` prevents buffering deadlock
2. **PYTHONPATH Injection**: Worker finds modules via `PYTHONPATH={server_root}:{current}`
3. **Lazy Loading**: Worker starts on first use, reused for subsequent calls
4. **Graceful Fallback**: Returns instruction strings when Worker unavailable

### 2.3 Flow Diagram

```
Orchestrator (Main Process)
    │
    ├─── delegate_to_coder(task, details)
    │
    ├────────────────┬──────────────────┐
    │                │                  │
    Worker Available    Worker Unavailable
    │                │                  │
    ▼                │                  ▼
SwarmNode.connect()   │            Fallback Mode
    │                │            (Return instructions)
    ▼                │
IPC Established       │
    │                │
    ▼                │
node.call_tool()      │
    │                │
    ▼                ▼
Return Result    ─────┘
```

## 3. Implementation (How)

### 3.1 SwarmNode (services/swarm.py)

```python
class SwarmNode:
    async def connect(self) -> bool:
        # Environment: PYTHONUNBUFFERED=1, PYTHONPATH injection
        # Timeout: 10s for connection
```

### 3.2 Authorization Guard (git_ops.py)

```python
class AuthorizationGuard:
    # Token-based commit authorization
    # Token expires after 5 minutes
    # Single-use validation
```

## 4. Testing Strategy

| Level       | Test File                   | Coverage                             |
| ----------- | --------------------------- | ------------------------------------ |
| Unit        | `test_hive_architecture.py` | Connection lifecycle, tool execution |
| Unit        | `test_git_ops_v2.py`        | AuthorizationGuard (6 tests)         |
| Integration | `test_basic.py`             | Full delegation flow                 |

## 5. Trade-offs & Constraints

- **Trade-off**: IPC overhead vs. isolation safety → Acceptable
- **Constraint**: Worker must be MCP-compatible
- **Fallback**: Always works without subprocess (instructions mode)

## 6. Rollout Plan

1. Phase 10 merged to main
2. Monitor `swarm_status()` for worker health
3. Enable direct mode by default (currently opt-in via env var)
