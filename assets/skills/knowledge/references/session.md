# Session Summarization

## Overview

Capture session trajectory for future reference and learning.

## Data Structure

```json
{
  "session_id": "unique-session-identifier",
  "trajectory": [
    {
      "step": 1,
      "action": "search",
      "decision": "Used keyword 'error handling'",
      "result": "Found 3 relevant files",
      "success": true
    },
    {
      "step": 2,
      "action": "read",
      "decision": "Examined first result",
      "result": "Found relevant pattern",
      "success": true
    }
  ],
  "failures": [
    {
      "step": 3,
      "action": "modify",
      "error": "Permission denied",
      "resolution": "Used sudo"
    }
  ]
}
```

## Usage

```python
@omni("knowledge.summarize_session", {
    "session_id": "session-123",
    "trajectory": trajectory,
    "include_failures": true
})
```

## Benefits

- Preserve decision rationale
- Learn from failures
- Enable session continuity
- Build institutional memory
