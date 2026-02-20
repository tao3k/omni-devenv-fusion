# xiuxian-wendao-py

`xiuxian-wendao-py` is a standalone Python package for the `xiuxian-wendao` Rust bindings.

It provides a Python API over `omni-core-rs`, so Python users can directly use the
Rust LinkGraph engine without depending on the full Omni runtime stack.

## Quick Start

```python
from xiuxian_wendao_py import WendaoBackend, WendaoRuntimeConfig

config = WendaoRuntimeConfig(
    root_dir=".",
    include_dirs=["docs"],
    include_dirs_auto=False,
    include_dirs_auto_candidates=[],
    exclude_dirs=[".git", ".cache", ".devenv", ".run", ".venv", "target", "node_modules"],
    stats_persistent_cache_ttl_sec=120.0,
    delta_full_rebuild_threshold=256,
    cache_valkey_url="redis://127.0.0.1:6379/0",
    cache_key_prefix=None,
    cache_ttl_seconds=None,
)

backend = WendaoBackend(notebook_dir=".", runtime_config=config)
result = await backend.search_planned("link graph", limit=20, options={"match_strategy": "fts"})
print(result)
```

## Scope

- Bindings-first package (no binary subprocess wrapper).
- Standalone backend runtime (`WendaoBackend`) for search/refresh/stats flows.
- Rust remains the single source of truth for search/index logic.
