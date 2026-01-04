# Swarm Monitoring - Usage Scenarios

> **Swarm Status**: Real-time health monitoring for the MCP server cluster

## Quick Start

```python
from agent.core.swarm import get_swarm_health

# Get comprehensive health status
health = get_swarm_health()
print(f"Status: {health['status']}")
print(f"Active: {health['metrics']['active_servers']}/{health['metrics']['total_servers']}")
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              MCP Swarm (Tri-MCP)                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐│
│  │ orchestrator│  │  executor   │  │    coder    ││
│  │    🧠       │  │    🛠️       │  │    📝       ││
│  │  Planning   │  │   Git/Shell │  │ File Ops    ││
│  │  Routing    │  │   Testing   │  │  Editing    ││
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘│
│         │                │                │       │
│         └────────────────┼────────────────┘       │
│                          ▼                        │
│              ┌────────────────────┐               │
│              │  Swarm Health     │               │
│              │  (swarm.py)       │               │
│              └────────────────────┘               │
└─────────────────────────────────────────────────────┘
```

## Scenarios

### Scenario 1: Basic Health Check

**Context**: Agent starts session and wants to verify all servers are operational.

```python
from agent.core.swarm import get_swarm_health

health = get_swarm_health()

if health["healthy"]:
    print("✅ All systems operational")
else:
    print("⚠️ Some servers degraded")
    for server, status in health["servers"].items():
        if status["status"] != "running":
            print(f"  - {server}: {status['status']}")
```

**Output**:

```
✅ All systems operational
```

### Scenario 2: Async Health Check in MCP Tool

**Context**: Creating a tool that checks swarm status asynchronously.

```python
import asyncio
from agent.core.swarm import get_async_swarm_health

async def check_swarm():
    """Async version for use in MCP tools."""
    return await get_async_swarm_health()

# Usage
result = asyncio.run(check_swarm())
```

### Scenario 3: Monitoring with Metrics

**Context**: Periodic health monitoring with metric extraction.

```python
from agent.core.swarm import get_swarm_health

def monitor_swarm():
    """Extract detailed metrics from swarm health."""
    health = get_swarm_health()
    metrics = health["metrics"]

    return {
        "uptime_percentage": metrics["health_percentage"],
        "servers_online": metrics["active_servers"],
        "servers_total": metrics["total_servers"],
        "timestamp": health["timestamp"],
        "status": "healthy" if health["healthy"] else "degraded"
    }

# Run monitoring
stats = monitor_swarm()
print(f"Swarm at {stats['uptime_percentage']:.0f}% - {stats['servers_online']}/{stats['servers_total']} servers")
```

### Scenario 4: Tool Integration (swarm_status)

**Context**: Using the MCP tool directly.

```python
# In Claude Code, call the tool:
# swarm_status()

# Returns JSON:
{
  "status": "healthy",
  "servers": {
    "orchestrator": {"status": "running", "tools": "active"},
    "executor": {"status": "running", "tools": "active"},
    "coder": {"status": "running", "tools": "active"}
  },
  "metrics": {
    "total_servers": 3,
    "active_servers": 3,
    "health_percentage": 100.0
  },
  "timestamp": "2026-01-04T11:44:28.240536"
}
```

### Scenario 5: Fallback Behavior

**Context**: When called from within an async context, `get_swarm_health()` automatically falls back to simple health check.

```python
import asyncio
from agent.core.swarm import get_swarm_health

async def async_monitor():
    # This will use get_simple_swarm_health() internally
    # as fallback when event loop is already running
    return get_swarm_health()  # Returns simple version

result = asyncio.run(async_monitor())
```

## API Reference

### `get_swarm_health() -> Dict[str, Any]`

Synchronous health check. Creates a new event loop if needed.

**Returns:**

```python
{
    "healthy": bool,
    "servers": {
        "orchestrator": {"status": str, "tools": str, ...},
        "executor": {"status": str, "tools": str, ...},
        "coder": {"status": str, "tools": str, ...}
    },
    "metrics": {
        "total_servers": int,
        "active_servers": int,
        "health_percentage": float
    },
    "timestamp": str  # ISO format
}
```

### `get_async_swarm_health() -> Dict[str, Any]`

Async version for direct use in async contexts.

### `get_simple_swarm_health() -> Dict[str, Any]`

Fast synchronous check without async overhead. Returns basic status.

## Server Status Values

| Status    | Meaning                            |
| --------- | ---------------------------------- |
| `running` | Server is operational              |
| `unknown` | Server status cannot be determined |
| `error`   | Server encountered an error        |

## Troubleshooting

### "Swarm monitoring not available"

**Cause**: The `agent/core/swarm.py` module is missing.

**Solution**: Ensure the swarm module is installed:

```bash
uv pip install -e packages/python/agent/
```

### Event Loop Errors

**Cause**: Calling async functions from within an async context.

**Solution**: Use `get_swarm_health()` which handles this automatically, or use `get_simple_swarm_health()` directly.

## Performance

| Method                      | Latency |
| --------------------------- | ------- |
| `get_simple_swarm_health()` | < 1ms   |
| `get_swarm_health()`        | < 10ms  |
| `get_async_swarm_health()`  | < 50ms  |
