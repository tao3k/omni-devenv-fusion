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

## Current Command Architecture

Current CLI command modules are implemented under:

- `packages/python/agent/src/omni/agent/cli/commands/route.py`
- `packages/python/agent/src/omni/agent/cli/commands/sync.py`
- `packages/python/agent/src/omni/agent/cli/commands/reindex.py`
- `packages/python/agent/src/omni/agent/cli/commands/db.py`
- `packages/python/agent/src/omni/agent/cli/commands/skill/`

The `route` command is active and includes diagnostics + schema export:

- `omni route test "<query>"`
- `omni route stats`
- `omni route cache`
- `omni route schema`

Quick examples:

```bash
# Required positional argument: QUERY
omni route test "git commit"

# Debug score breakdown
omni route test "refactor rust module" --debug --number 8

# JSON with per-result score breakdown (raw_rrf, vector_score, keyword_score, final_score)
omni route test "git commit" --local --json --explain

# Use named profile from settings
omni route test "git commit" --confidence-profile precision

# Default behavior: omit profile flags and let system auto-select
omni route test "git commit"

# Missing QUERY shows a CLI error:
omni route test
# -> Error: Missing argument 'QUERY'
```

Configuration resolution follows the CLI `--conf` option:

1. `<git-root>/assets/settings.yaml` (base defaults)
2. `$PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml` (override layer)

Route defaults and confidence profile settings live under `router.search.*`, including:

- `router.search.default_limit`
- `router.search.default_threshold`
- `router.search.rerank`
- `router.search.active_profile`
- `router.search.profiles.<name>`

See [CLI Reference](../reference/cli.md) for user-facing command usage.
