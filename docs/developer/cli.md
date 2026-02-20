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

1. `<git-root>/packages/conf/settings.yaml` (system defaults)
2. `$PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml` (user override layer)

For LinkGraph/Wendao settings, a dedicated config is merged with the same
priority order:

1. `<git-root>/packages/conf/wendao.yaml` (system defaults)
2. `$PRJ_CONFIG_HOME/omni-dev-fusion/wendao.yaml` (user override layer)

Route defaults and confidence profile settings live under `router.search.*`, including:

- `router.search.default_limit`
- `router.search.default_threshold`
- `router.search.rerank`
- `router.search.active_profile`
- `router.search.profiles.<name>`

See [CLI Reference](../reference/cli.md) for user-facing command usage.

---

## Declarative Load Requirements

Each command group declares what bootstrap services it needs. The entry point uses this registry to load only what's required, keeping light commands (e.g. `omni skill list`) fast.

### Module: `omni.agent.cli.load_requirements`

| Function                                   | Description                                   |
| ------------------------------------------ | --------------------------------------------- |
| `register_requirements(command, **kwargs)` | Declare load requirements for a command group |
| `get_requirements(command)`                | Get requirements (used by entry_point)        |
| `LoadRequirements`                         | Dataclass: `ollama`, `embedding_index`        |

### Usage (in `register_*_command`)

```python
from omni.agent.cli.load_requirements import register_requirements

def register_skill_command(app_instance: typer.Typer) -> None:
    register_requirements("skill", ollama=False, embedding_index=False)
    app_instance.add_typer(skill_app, name="skill")
```

### Requirements

| Field             | Default | Description                                               |
| ----------------- | ------- | --------------------------------------------------------- |
| `ollama`          | `True`  | Ensure Ollama is running for embedding                    |
| `embedding_index` | `True`  | Run `ensure_embedding_index_compatibility` (auto-reindex) |

### Command requirements (audit)

| Command     | ollama | embedding_index | Notes                        |
| ----------- | ------ | --------------- | ---------------------------- |
| version     | False  | False           | Version info only            |
| completions | False  | False           | Shell completion script      |
| commands    | False  | False           | List CLI commands            |
| dashboard   | False  | False           | Session metrics from file    |
| skill       | False  | False           | LanceDB list_all_tools only  |
| route       | False  | True            | Route test uses embedding    |
| reindex     | False  | False           | Handles own reindex          |
| db          | True   | True            | Query/search need embedding  |
| knowledge   | True   | True            | Ingest/recall need embedding |
| sync        | True   | True            | Syncs skills, router         |
| mcp         | True   | True            | MCP server, knowledge.recall |
| run         | True   | True            | CCA loop                     |
| gateway     | True   | True            | Agent loop                   |
| agent       | True   | True            | Agent loop                   |

### When adding a new command

1. Call `register_requirements(name, ...)` in your `register_*_command` **before** `add_typer`.
2. Set `ollama=False` if the command does not need embedding (e.g. light list/info).
3. Set `embedding_index=False` if the command handles its own reindex or needs no vector store.
4. Omit fields to keep defaults (full bootstrap).
