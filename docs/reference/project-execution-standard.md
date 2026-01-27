# Project Execution Standard

> Cross-language (Rust/Python) development workflow and debugging protocols.

## Overview

This document defines the **strict workflow** for developing features that span Rust and Python components. Following this standard prevents wasted time and ensures efficient debugging.

---

## Rust/Python Cross-Language Development Workflow

### The Correct Debugging Flow

```
1. Rust Implementation → Add Rust Test → cargo test PASSED
                     ↓
2. Python Integration → Add Python Test → pytest PASSED
                     ↓
3. Build & Verify → just build-rust-dev → Full integration test
```

### Why This Order Matters

| Reason                      | Impact                                               |
| --------------------------- | ---------------------------------------------------- |
| **Rust tests are fast**     | ~0.3s for 24 tests vs ~30s for Python integration    |
| **Compiler catches errors** | Type errors caught before Python even runs           |
| **Isolates problems**       | If Rust passes but Python fails, issue is in binding |
| **Avoids slow loops**       | `uv run omni ...` is ~10-30s per iteration           |

---

## Fast Iteration Commands

### Rust Development

```bash
# Run all Rust tests
cargo test -p omni-vector

# Run specific test (fastest feedback)
cargo test -p omni-vector test_delete_by_file_path

# Build debug bindings (~10s)
just build-rust-dev

# Build release bindings (~60s, use only for final release)
just build
```

### Python Development

```bash
# Run sync tests only
uv run pytest packages/python/agent/src/omni/agent/tests/unit/test_vector_store_sync.py -v

# Run all agent tests
just test

# Run skill tests
just test-skills

# Debug sync command directly
uv run omni skill sync
```

### Full Validation

```bash
# Fast path: Rust tests first
cargo test -p omni-vector && just build-rust-dev

# Full validation: All tests
just validate
```

---

## Workflow Examples

### Example: Fixing SQL Query Logic in Rust

```bash
# Step 1: Add Rust test with expected behavior
# File: packages/rust/crates/omni-vector/src/lib.rs

#[tokio::test]
async fn test_delete_by_file_path_with_underscores() {
    let store = VectorStore::new(db_path, Some(1536)).await.unwrap();
    let test_path = "temp_skill/scripts/hello.py";
    store.add_documents(...).await.unwrap();
    store.delete_by_file_path("skills", vec![test_path]).await.unwrap();
    assert_eq!(store.count("skills").await.unwrap(), 0);
}

# Run Rust tests first - MUST PASS before moving on
cargo test -p omni-vector test_delete_by_file_path_with_underscores

# Step 2: Python integration test
# File: packages/python/agent/src/omni/agent/tests/unit/test_vector_store_sync.py

def test_sync_idempotency_with_underscores(tmp_path):
    """Sync should handle paths with underscores correctly."""
    # Create temp skill with underscore in path
    # Run sync twice
    # Verify second sync shows "no changes"
    pass

uv run pytest test_vector_store_sync.py::TestSyncIdempotency -v

# Step 3: Build and verify
just build-rust-dev
uv run omni skill sync
```

### Example: Fixing Search Filter in Rust

```bash
# Step 1: Rust unit test
# packages/rust/crates/omni-vector/src/search.rs

#[tokio::test]
async fn test_filter_by_metadata_domain() {
    let store = VectorStore::new(db_path, Some(1536)).await.unwrap();
    store.add_documents(
        &["Python code", "Rust code"],
        &["py_1", "rust_1"],
        &[HashMap::from([("domain", "python")]), HashMap::from([("domain", "rust")])],
    ).await.unwrap();

    let results = store.search("code", 5, Some(json!({"domain": "python"}))).await.unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].id, "py_1");
}

cargo test -p omni-vector test_filter_by_metadata_domain

# Step 2: Python integration test
# packages/python/agent/src/omni/agent/tests/test_vector_search.py

@pytest.mark.asyncio
async def test_rag_domain_filtering(vector_memory):
    results = await vector_memory.search("code", n_results=5, where_filter={"domain": "python"})
    assert len(results) == 1

# Step 3: Build and verify
just build-rust-dev
```

---

## Anti-Patterns (What NOT To Do)

### ❌ Don't: Skip Rust tests and go straight to Python

```bash
# WRONG - Just modified Rust, immediately testing in Python
uv run omni skill sync  # Takes 30s, may fail due to Rust compilation error
```

**Why it's wrong**: If there's a type error or logic bug, you wait 30s to discover it. Rust test would catch it in 0.3s.

### ❌ Don't: Modify Rust code without adding tests

```rust
// WRONG - Modified delete_by_file_path but no test added
pub async fn delete_by_file_path(&self, table_name: &str, file_paths: Vec<String>) {
    // ... implementation ...
}
```

**Why it's wrong**: No regression protection, no documentation of expected behavior.

### ❌ Don't: Use full `just validate` for every iteration

```bash
# WRONG - Running fmt + lint + test for every small change
just validate  # Takes 60s+
```

**Why it's wrong**: Slow iteration. Use `cargo test` for Rust, `pytest` for Python.

---

## Common Issues and Solutions

### Issue: Rust test passes but Python integration fails

**Diagnosis path**:

1. Check Python binding: `packages/rust/bindings/python/src/lib.rs`
2. Check argument order and types
3. Check error handling in Python wrapper

### Issue: Data mismatch between Rust and Python

**Diagnosis path**:

1. Add debug output to Rust: `eprintln!("DEBUG: {:?}", value);`
2. Add logging to Python: `log::debug!("value: {:?}", value);`
3. Verify serialization/deserialization

### Issue: Underscores in paths not matching

**Solution**: Always scan table and use ID-based deletion, never SQL LIKE with path strings.

---

## Lessons Learned (Case Study: delete_by_file_path Fix)

### The Problem

Sync command repeatedly showed "-1 deleted" for paths with underscores like `temp_skill/scripts/hello.py`.

### Root Cause Analysis

| What Went Wrong                              | Why It Cost Time                                  |
| -------------------------------------------- | ------------------------------------------------- |
| No Rust unit test for `delete_by_file_path`  | Bug existed without regression protection         |
| Used SQL LIKE with path strings              | `_` in `temp_skill` interpreted as wildcard       |
| Debugged in Python first                     | `uv run omni skill sync` takes ~30s per iteration |
| No code comments explaining SQL LIKE pitfall | Later maintainers could make same mistake         |

### Timeline of Waste

```
Day 1: Rust implementation (no test) → Build
Day 2: Python integration test fails → "Why is delete not working?"
       → Multiple uv run omni skill sync (~30s each)
       → Add Rust test → cargo test passes
       → Realize issue is in Rust
Day 3: Fix Rust code → cargo test passes → Build → Works
```

**Cost**: ~5+ minutes of debugging, multiple 30s iterations.

### Correct Approach (Now Documented)

```rust
// Step 1: BEFORE implementing, add test that documents expected behavior
// packages/rust/crates/omni-vector/src/lib.rs

/// Regression test: SQL LIKE treats _ as single-char wildcard.
/// Paths like "temp_skill/scripts/hello.py" would NOT match with LIKE '%temp_skill%'.
#[tokio::test]
async fn test_delete_by_file_path_with_underscores() {
    let store = VectorStore::new(db_path, Some(1536)).await.unwrap();
    let test_path = "temp_skill/scripts/hello.py";  // Contains underscore
    store.add_documents(...).await.unwrap();
    store.delete_by_file_path("test", vec![test_path]).await.unwrap();
    assert_eq!(store.count("test").await.unwrap(), 0);
}

// Step 2: Implement to make test pass
// Step 3: cargo test -p omni-vector
// Step 4: Python integration test
// Step 5: just build-rust-dev
```

### Key Takeaways

1. **Add tests before or with implementation** - Tests document expected behavior
2. **Cover edge cases** - Underscores, percent signs, dots in paths
3. **Comment implementation decisions** - "Why scan instead of LIKE?" in code
4. **Rust tests first** - 0.3s vs 30s feedback loop
5. **Regression tests prevent recurrence** - Document the bug that was fixed

---

## Project Namespace Conventions

This section defines the **actual namespace structure** used in this project.

### Current Package Structure

```
packages/python/
├── common/src/common/          # Shared utilities
│   ├── config/                 # Configuration (settings.py)
│   ├── mcp_core/               # MCP core functionality
│   ├── skills_path.py          # SKILLS_DIR() utility
│   ├── prj_dirs.py             # PRJ_DATA, PRJ_CACHE
│   └── gitops.py               # Git operations
│
└── agent/src/omni/agent/        # Agent implementation (Note: omni/agent prefix)
    ├── core/                   # Core logic
    │   ├── skill_registry/     # Skill loading/management
    │   ├── skill_discovery/    # Skill discovery
    │   ├── memory/             # Memory management
    │   ├── security/           # Security validation
    │   ├── planner/            # Task planning
    │   ├── orchestrator/       # Execution orchestration
    │   └── swarm.py            # Process isolation
    │
    ├── tools/                  # MCP tools
    │   ├── router.py           # Tool routing
    │   ├── context.py          # Context tools
    │   └── orchestrator/       # Orchestrator tools
    │
    ├── mcp_server/             # MCP server
    ├── cli/                    # CLI commands
    └── tests/                  # Agent tests
```

### Namespace Layers

| Layer                   | Import Pattern                                     | Example                                                         |
| ----------------------- | -------------------------------------------------- | --------------------------------------------------------------- |
| **common**              | `from common.{module} import ...`                  | `from common.skills_path import SKILLS_DIR`                     |
| **omni.agent.core**     | `from omni.agent.core.{module} import ...`         | `from omni.agent.core.skill_registry.core import SkillRegistry` |
| **omni.agent.core.sub** | `from omni.agent.core.{submodule} import ...`      | `from omni.agent.core.skill_registry.loader import SkillLoader` |
| **agent.tools**         | `from omni.agent.tools.{module} import ...`        | `from omni.agent.tools.router import ToolRouter`                |
| **agent.mcp_server**    | `from omni.agent.mcp_server.{module} import ...`   | `from omni.agent.mcp_server.server import MCPServer`            |
| **agent.cli**           | `from omni.agent.cli.{command} import ...`         | `from omni.agent.cli.run import run_agent`                      |
| **agent.tests**         | `from omni.agent.tests.{type}.{module} import ...` | `from omni.agent.tests.unit.test_skill_manager import ...`      |

### Correct Import Examples

```python
# Cross-layer imports (always use absolute)
from common.skills_path import SKILLS_DIR
from common.config.settings import get_setting
from common.prj_dirs import PRJ_DATA, PRJ_CACHE
from common.gitops import get_project_root

from omni.agent.core.skill_registry import SkillRegistry
from omni.agent.core.skill_registry.loader import SkillLoader
from omni.agent.core.skill_registry.adapter import SkillAdapter
from omni.agent.core.swarm import get_swarm
from omni.agent.core.memory.manager import MemoryManager

from omni.agent.tools.router import ToolRouter
from omni.agent.tools.orchestrator.core import OrchestratorCore

from omni.agent.mcp_server.server import MCPServer
```

### Import Anti-Patterns

```python
# WRONG - Deep relative imports (confusing, hard to trace)
from ..common.skills_path import SKILLS_DIR

# WRONG - Importing from wrong layer
from omni.agent.core.skills_path import SKILLS_DIR  # Should be from common!

# WRONG - Using old namespace (agent.core instead of omni.agent.core)
from agent.core.skill_registry import SkillRegistry  # OLD pattern

# WRONG - Circular imports by importing in wrong order
from omni.agent.core.omni_agent import get_agent  # If agent imports this too early
```

### Common Modules

| Module            | Location                           | Purpose                        |
| ----------------- | ---------------------------------- | ------------------------------ |
| `skills_path`     | `common/skills_path.py`            | Path to skills directory       |
| `prj_dirs`        | `common/prj_dirs.py`               | Runtime data/cache/config dirs |
| `settings`        | `common/config/settings.py`        | SSOT configuration             |
| `gitops`          | `common/gitops.py`                 | Git operations                 |
| `skill_registry`  | `omni/agent/core/skill_registry/`  | Skill loading/management       |
| `skill_discovery` | `omni/agent/core/skill_discovery/` | Skill discovery/reconciliation |
| `swarm`           | `omni/agent/core/swarm.py`         | Process isolation/execution    |
| `memory`          | `omni/agent/core/memory/`          | Memory/vector store            |
| `planner`         | `omni/agent/core/planner/`         | Task decomposition/planning    |

### Key SSOT Utilities

```python
# Always use these from common/, never hardcode!
from common.skills_path import SKILLS_DIR
from common.config.settings import get_setting
from common.prj_dirs import PRJ_DATA, PRJ_CACHE
from common.gitops import get_project_root

# Usage
skills_dir = SKILLS_DIR("git")              # assets/skills/git
data_dir = PRJ_DATA("knowledge")            # .data/knowledge
cache_file = PRJ_CACHE("vector_store.db")   # .cache/vector_store.db
timeout = get_setting("mcp.timeout", 30)    # From settings.yaml
```

---

## Related Documents

- [Testing Guide](../developer/testing.md) - Test structure and patterns
- [ODF-EP Protocol](odf-ep-protocol.md) - Engineering protocol
- [Justfile](../justfile) - Build and test commands
