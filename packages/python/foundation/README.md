# Omni Foundation

Shared kernel and utilities for omni-dev-fusion MCP servers.

## Overview

This package provides shared components used by both the orchestrator and executor agents.

## Core Modules

| Module                     | Purpose                        |
| -------------------------- | ------------------------------ |
| `omni.foundation.config`   | Settings, paths, logging       |
| `omni.foundation.api`      | Decorators, protocols, types   |
| `omni.foundation.bridge`   | Rust-Python interop            |
| `omni.foundation.services` | LLM, memory, embedding, vector |
| `omni.foundation.runtime`  | Context, isolation, gitops     |

## Services Submodules

### Memory Module (`omni.foundation.services.memory`)

Project memory storage using ADR pattern with LanceDB backend.

```
omni.foundation.services.memory/
├── base.py                    # Public API exports
├── core/
│   ├── interface.py           # Abstract interfaces and data types
│   ├── project_memory.py      # ProjectMemory main class
│   └── utils.py               # Shared utilities
└── stores/
    └── lancedb.py             # LanceDB storage (single backend)
```

### Key Classes

```python
from omni.foundation.services.memory import ProjectMemory

# Create memory instance (LanceDB by default)
memory = ProjectMemory()

# Add decision
memory.add_decision(
    title="Use LanceDB for Memory Storage",
    problem="File-based storage is slow",
    solution="Migrate to LanceDB",
    status="accepted",
)

# List decisions
decisions = memory.list_decisions()
```

See [Memory Module Reference](../../../../docs/reference/memory-module.md) for full documentation.

## Dependencies

- Anthropic SDK for LLM integration
- Structlog for structured logging
- LanceDB for vector storage
