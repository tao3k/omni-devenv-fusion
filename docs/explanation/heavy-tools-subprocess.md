# Knowledge Store: Query-Release Lifecycle

> After each tool run the kernel evicts the knowledge vector store and runs GC so the long-lived MCP process does not retain LanceDB memory.

---

## 1. Why CLI is fine, MCP is not

- **CLI**: `omni knowledge recall ...` runs in a short-lived process. It opens the knowledge store, runs the query, then the process exits and the OS reclaims all memory.
- **MCP**: The server process never exits. If we cached the knowledge store after first use and never evicted it, the process would keep holding that memory.

So we **evict the knowledge store after each tool run** (and run `gc.collect()`). That matches the lance lifecycle: open → use → drop. See `docs/reference/lancedb-query-release-lifecycle.md`.

---

## 2. Implementation

| Piece                           | Location                                              | Role                                                                                               |
| ------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| After each tool                 | `packages/python/core/src/omni/core/kernel/engine.py` | In `execute_tool()`, after `target_skill.execute(...)`, calls `evict_knowledge_store_after_use()`. |
| evict_knowledge_store_after_use | `omni.foundation.services.vector.store`               | Evicts knowledge path from `_vector_stores`, clears VectorStoreClient refs, runs `gc.collect()`.   |
| evict_vector_store_cache        | `omni.foundation.bridge.rust_vector`                  | Removes store(s) from the process cache so the next use opens a new instance.                      |

No configuration: release is unconditional after every tool execution.

---

## 3. References

- **Lifecycle doc**: `docs/reference/lancedb-query-release-lifecycle.md`
- **Query-release lifecycle** (avoids MCP retaining vector memory): `docs/reference/lancedb-query-release-lifecycle.md`
