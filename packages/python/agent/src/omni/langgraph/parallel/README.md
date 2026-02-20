# omni.langgraph.parallel

Reusable parallel shard execution for LangGraph workflows.

## Purpose

Skills that process content in shards (e.g. researcher, knowledge recall) need:

- **Level-based scheduling**: Run shards in parallel within each level.
- **Optional dependency ordering**: When `parallel_all=False`, respect shard dependencies (topological sort).
- **Default parallel_all=True**: Ignore dependencies; run all shards in parallel for fastest wall clock.

## API

```python
from omni.langgraph.parallel import build_execution_levels, run_parallel_levels

# Build levels (parallel_all=True by default)
levels = build_execution_levels(
    shards,
    parallel_all=True,
    dep_key="dependencies",
    name_key="name",
)

# Run levels: sequential across levels, parallel within each level
results = await run_parallel_levels(levels, process_fn, state)

# With bounded concurrency (avoids API rate limits, memory spikes)
results = await run_parallel_levels(levels, process_fn, state, max_concurrent=8)
```

## Shard Format

Each shard is a dict with at least:

- `name`: Used to resolve dependency references.
- Optional `dependencies`: List of shard names that must run first (when `parallel_all=False`).

## Usage in Skills

- **researcher**: Uses `build_execution_levels` + `run_parallel_levels` in `node_process_shards_parallel`.
- **Other workflows**: Import and use for any sharded async processing (LLM calls, repomix, etc.).

## Configuration (researcher)

In `packages/conf/settings.yaml`:

```yaml
researcher:
  max_concurrent: null # or 6–8 if API rate limits
```

## Tests

```bash
uv run pytest packages/python/agent/tests/unit/test_langgraph/test_parallel.py -v
```
