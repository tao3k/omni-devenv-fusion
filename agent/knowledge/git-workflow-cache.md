# GitWorkflowCache Auto-Load

This document describes the automatic memory loading mechanism for git workflow protocol.

## Overview

The `GitWorkflowCache` is a singleton that loads and caches `agent/how-to/git-workflow.md` at MCP server startup. All git tools automatically include `workflow_protocol` in their responses.

## Implementation

### Cache Location

```
mcp-server/git_ops.py
├── GitWorkflowCache  # Singleton class
├── _git_workflow_cache  # Module-level instance
└── register_git_ops_tools()  # Triggers auto-load
```

### Auto-Load Trigger

```python
def register_git_ops_tools(mcp: Any) -> None:
    """Register all git operations tools.

    Automatically loads git-workflow.md memory on first call.
    """
    # Trigger workflow memory load - any git action will now have protocol context
    _ = _git_workflow_cache.get_protocol()
```

### Loading Timing

| Event               | Action                                     |
| ------------------- | ------------------------------------------ |
| MCP Server Start    | `register_git_ops_tools()` called          |
| First Git Tool Call | `GitWorkflowCache` reads `git-workflow.md` |
| Subsequent Calls    | Returns cached protocol                    |

## Response Format

All git tools return `workflow_protocol`:

```json
{
  "status": "success",
  "workflow_protocol": "stop_and_ask",
  "has_staged_changes": true,
  "staged_diff": "diff --git a/example.py..."
}
```

## Tools Including Protocol

| Tool              | File       | Line |
| ----------------- | ---------- | ---- |
| `git_status`      | git_ops.py | 701  |
| `git_log`         | git_ops.py | 720  |
| `git_diff`        | git_ops.py | 737  |
| `git_diff_staged` | git_ops.py | 752  |

## Benefits

1. **Consistency**: All git tools share protocol understanding
2. **Performance**: Single load, session-cached
3. **Robustness**: No repeated file reads

## Testing

See `mcp-server/tests/test_git_ops_v2.py::TestGitWorkflowCache` for comprehensive tests.
