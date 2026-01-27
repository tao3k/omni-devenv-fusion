# CLI Developer Guide

> **NOTE**: Core CLI commands are documented in [CLI Reference](../reference/cli.md)
> This file covers developer-specific implementation details.

---

## Skill Analytics Module

The skill analytics commands (`omni skill analyze`, `omni skill stats`, `omni skill context`) use the Arrow-native analytics module.

### Architecture

```
CLI Commands (agent/cli/commands/skill/analyzer.py)
        │
        ▼
omni.core.skills.analyzer    ← Arrow Analytics Functions
        │
        ▼
omni.foundation.bridge.rust_vector.RustVectorStore
        │
        ▼
Rust bindings (LanceDB) → get_analytics_table()
```

### Module: `omni.core.skills.analyzer`

| Function                                | Returns          | Description              |
| --------------------------------------- | ---------------- | ------------------------ |
| `get_analytics_dataframe()`             | `pyarrow.Table`  | All tools as Arrow Table |
| `get_category_distribution()`           | `dict[str, int]` | Tool counts by category  |
| `generate_system_context(limit)`        | `str`            | LLM-ready tool list      |
| `analyze_tools(category, missing_docs)` | `dict`           | Filtered analysis        |

### Implementation Example

```python
from omni.core.skills.analyzer import (
    get_analytics_dataframe,
    get_category_distribution,
    generate_system_context,
)

# Get PyArrow Table for analytics
table = get_analytics_dataframe()
print(f"Total tools: {table.num_rows}")

# Get category distribution
categories = get_category_distribution()
for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:5]:
    print(f"  {cat}: {count}")

# Generate system context for LLM
context = generate_system_context(limit=50)
```

### CLI Integration

The CLI commands delegate to the analyzer module:

```python
# agent/cli/commands/skill/analyze.py
from omni.core.skills.analyzer import analyze_tools, get_category_distribution

@skill_app.command("analyze")
def skill_analyze(category: str = None, missing_docs: bool = False):
    result = analyze_tools(category=category, missing_docs=missing_docs)
    # ... display logic
```

---

## Historical: Old CLI Commands

The original CLI had separate subcommands (`omni route`, `omni ingest`, etc.) that have been migrated to the Trinity Architecture.

| Old Command    | New Implementation                         |
| -------------- | ------------------------------------------ |
| `omni route`   | MCP tools via `omni.core.router`           |
| `omni ingest`  | `omni.core.knowledge.librarian`            |
| `omni skill`   | MCP tools via `omni.core.skills.discovery` |
| `omni analyze` | `omni skill analyze` (Arrow-native)        |

See [CLI Reference](../reference/cli.md) for current command documentation.
