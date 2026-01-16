# Vector-Enhanced Skill Discovery

> **Core Capabilities**: Wisdom-Aware Routing | Automated Reinforcement | Self-Evolving Feedback | Auto-Route Discovery | Hot Reload | Vector-Enhanced Discovery

> **Virtual Loading** - Intelligent skill discovery using ChromaDB vector search.

## Overview

**Vector-Enhanced Skill Discovery** enables semantic matching between user requests and available skills. This system bridges the gap between "what users ask for" and "what skills can do" even when keywords don't exactly match.

### Key Capabilities

- **Semantic Search**: Find skills by meaning, not just keywords
- **Virtual Loading**: Discover unloaded skills without installation
- **Local-Only Mode**: Search only installed skills (privacy-conscious)
- **Automatic Fallback**: Router triggers vector search when LLM routing is weak

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     User Request                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1️⃣ Semantic Cortex (Fuzzy Cache)                                │
│    "Fix bug" ≈ "Fix the bug"                                    │
└─────────────────────────────────────────────────────────────────┘
         ❌ Miss                    ✅ Hit → Return Cached
                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2️⃣ Exact Match Cache                                            │
│    "git commit" → exact string match                            │
└─────────────────────────────────────────────────────────────────┘
         ❌ Miss                    ✅ Hit → Return Cached
                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3️⃣ LLM Routing (Hot Path)                                       │
│    Analyze request → Select skills → Generate Mission Brief     │
└─────────────────────────────────────────────────────────────────┘
         ✅ High Confidence        ⚠️ Low Confidence / Generic Skills
                ↓                              ↓
┌─────────────────────────┐    ┌─────────────────────────────────┐
│ Return Result           │    │ 4️⃣ Vector Fallback (Cold Path)  │
│ (No Vector Search)      │    │    • Search ChromaDB            │
│                         │    │    • Filter: installed_only=True │
│                         │    │    • Return suggested_skills     │
└─────────────────────────┘    └─────────────────────────────────┘
                                        ↓
                              ┌─────────────────────────────────┐
                              │      RoutingResult              │
                              │  • selected_skills              │
                              │  • suggested_skills (NEW)       │
                              │  • confidence                   │
                              └─────────────────────────────────┘
```

## Vector Skill Discovery

### `VectorSkillDiscovery` Class

Located in `agent/core/skill_discovery.py`.

```python
from agent.core.skill_discovery import VectorSkillDiscovery

discovery = VectorSkillDiscovery()

# Search local skills only
results = await discovery.search(
    query="git operations",
    limit=5,
    installed_only=True  # Default: True
)

# Search all skills (local + remote)
results = await discovery.search(
    query="docker containers",
    limit=10,
    installed_only=False
)
```

### Return Format

```python
[
    {
        "id": "git",
        "name": "git",
        "description": "Git version control system...",
        "score": 0.85,           # Similarity score (0-1)
        "installed": True,       # Local or remote
        "keywords": "git, commit, branch",
    },
    # ...
]
```

### Constants

```python
from agent.core.skill_discovery import SKILL_REGISTRY_COLLECTION
# Value: "skill_registry"
```

## Index Management

### Building the Index

The index is built from all `SKILL.md` files:

```python
from agent.core.skill_discovery import reindex_skills_from_manifests

# Incremental update
stats = await reindex_skills_from_manifests(clear_existing=False)

# Full rebuild
stats = await reindex_skills_from_manifests(clear_existing=True)

# Result:
# {
#     "local_skills_indexed": 19,
#     "remote_skills_indexed": 20,
#     "total_skills_indexed": 39,
#     "errors": []
# }
```

### What Gets Indexed

For each skill, the following is embedded:

```markdown
Skill: git
Description: Git version control system for managing code changes.
Keywords: git, commit, branch, merge, push, pull
Intents: commit, push, pull, branch management
```

## CLI Commands

### `omni skill reindex`

Rebuild the vector index from all installed skills.

```bash
# Incremental update (default)
omni skill reindex

# Full rebuild (clear existing)
omni skill reindex --clear

# Verbose output
omni skill reindex -v

# JSON output
omni skill reindex --json
```

**Output:**

```
╭──────────────────────────────── ✅ Complete ─────────────────────────────────╮
│ Indexed 39 skills (19 local, 20 remote)                                     │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### `omni skill index-stats`

Show statistics about the vector index.

```bash
# Human readable
omni skill index-stats

# JSON output
omni skill index-stats --json
```

**Output:**

```
╭──────────────────────────────── 📊 Index Statistics ────────────────────────╮
│ Collection: skill_registry                                                   │
│ Indexed Skills: 39                                                           │
│ Available Collections: [skill_registry, project_knowledge]                  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## User Tools

### `skill.discover`

Semantic search for skills.

```python
@omni("skill.discover", {
    "query": "git workflow",
    "limit": 5,
    "local_only": true
})
```

| Parameter    | Type   | Default  | Description           |
| ------------ | ------ | -------- | --------------------- |
| `query`      | string | required | Search query          |
| `limit`      | int    | 5        | Max results           |
| `local_only` | bool   | false    | Only installed skills |

**Example Output:**

```markdown
# 🔍 Discovery Results: 'git operations'

## ✅ git (Match: 85%)

**ID**: `git`
**Description**: Git version control system...
**Keywords**: git, commit, branch, merge

## ✅ file_ops (Match: 45%)

**ID**: `file_ops`
**Description**: File operations including AST-based refactoring...
```

### `skill.suggest`

Get task-based skill recommendations.

```python
@omni("skill.suggest", {"task": "analyze nginx logs"})
```

| Parameter | Type   | Description      |
| --------- | ------ | ---------------- |
| `task`    | string | Task description |

**Example Output:**

```markdown
# 💡 Skill Recommendation

**Task**: analyze nginx logs

## Top Matches

1. ✅ **HTTP Client** - HTTP requests... (85%)
2. ☁️ **Network Analysis** - PCAP analysis... (64%)

## Best Match: HTTP Client

**Confidence**: 85%
**Description**: HTTP requests, API testing...
```

### `skill.reindex`

Rebuild the vector index (user tool version).

```python
@omni("skill.reindex", {"clear": true})
```

| Parameter | Type | Description                |
| --------- | ---- | -------------------------- |
| `clear`   | bool | Clear existing index first |

## Router Integration

### Trigger Conditions

Vector Fallback is triggered when:

```python
# semantic_router.py:444-450
is_weak_route = (
    not valid_skills or                    # No valid skills found
    confidence < 0.5 or                    # Low confidence
    (len(valid_skills) == 1 and            # Only 1 skill
     valid_skills[0] in ["writer", "knowledge"])  # Generic fallback
)
```

### `suggested_skills` Field

The `RoutingResult` now includes `suggested_skills`:

```python
from agent.core.router.models import RoutingResult

result = RoutingResult(
    selected_skills=["writer"],        # Currently selected
    suggested_skills=["documentation"], # Recommended to load
    mission_brief="...",
    confidence=0.7,
    reasoning="..."
)
```

### Example Flow

```python
# User: "write documentation about this project"
# LLM: confidence=0.7, selects "writer" (generic)

# Vector Fallback triggers
# Searches for "write documentation" in local skills
# Finds: documentation (score=0.92)

# Result:
result.suggested_skills = ["documentation"]
result.confidence = 0.85  # Boosted!
result.reasoning += " [Vector Fallback] Found local skill: documentation"
```

## Testing

### Test File

`packages/python/agent/src/agent/tests/scenarios/test_discovery_flow.py`

### Scenarios

| Test                                            | Description                        |
| ----------------------------------------------- | ---------------------------------- |
| `test_scenario1_explicit_tool_discover`         | skill.discover tool rendering      |
| `test_scenario2_cold_path_virtual_loading`      | Router falls back to vector search |
| `test_scenario3_hot_path_performance_guardrail` | No unnecessary vector search       |
| `test_scenario4_ambiguous_graceful_fail`        | Graceful handling of nonsense      |
| `test_scenario5_vector_filtering`               | installed_only filter works        |
| `test_scenario6_cache_hit`                      | Cache integration                  |
| `test_scenario7_discovery_search_interface`     | Discovery API interface            |

### Running Tests

```bash
# Run all discovery flow tests
uv run pytest packages/python/agent/src/agent/tests/scenarios/test_discovery_flow.py -v

# Run specific test
uv run pytest packages/python/agent/src/agent/tests/scenarios/test_discovery_flow.py::test_scenario2_cold_path_virtual_loading -v

# Run with verbose output
uv run pytest packages/python/agent/src/agent/tests/scenarios/test_discovery_flow.py -v -s
```

## Architecture Decisions

### Why ChromaDB?

- **Performance**: O(log N) ANN search vs O(N) linear scan
- **Persistence**: Index survives restarts
- **Filtering**: Support for `where_filter` metadata queries
- **Simplicity**: Easy integration with existing VectorMemory

### Why Local-Only Default?

The `installed_only=True` default ensures:

- **Privacy**: No metadata about remote skills leaves the system
- **Reliability**: Only skills that can actually be loaded are suggested
- **Phased Rollout**: Remote skill installation is TBD

### Hot Path vs Cold Path

| Path | Trigger                     | Speed  | Use Case           |
| ---- | --------------------------- | ------ | ------------------ |
| Hot  | Cache hit / High confidence | ~1ms   | Common requests    |
| Cold | Weak LLM routing            | ~100ms | Ambiguous requests |

## Related Files

| File                                     | Purpose                             |
| ---------------------------------------- | ----------------------------------- |
| `agent/core/skill_discovery.py`          | VectorSkillDiscovery class          |
| `agent/core/router/semantic_router.py`   | Router with Vector Fallback         |
| `agent/cli/commands/skill.py`            | CLI commands (reindex, index-stats) |
| `agent/core/vector_store.py`             | ChromaDB wrapper                    |
| `tests/scenarios/test_discovery_flow.py` | Integration tests                   |
| `tests/fakes/fake_vectorstore.py`        | Test double for vector store        |

## See Also

- [Skills Overview](../skills.md) - Complete skill documentation
- [Trinity Architecture](../explanation/trinity-architecture.md) - System architecture
- [ODF-EP Protocol](../reference/odf-ep-protocol.md) - Engineering protocol

---

## Hot Reload & Index Sync

> **Zero-Downtime Skill Reloading** - Bridge between Vector Discovery and Runtime.

### Overview

Connects the Vector Discovery system with Hot Reload, ensuring the ChromaDB index stays in sync with runtime skill changes.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SkillManager (Runtime)                       │
├─────────────────────────────────────────────────────────────────┤
│  _observers: [MCP Observer, Index Sync Observer]               │
│  _pending_changes: [(skill_name, change_type), ...]            │
│  _debounced_notify(): 200ms batch window                       │
└─────────────────────────────────────────────────────────────────┘
           ↓                              ↓
┌────────────────────────┐    ┌──────────────────────────────┐
│  MCP Observer          │    │  Index Sync Observer         │
│  (Tool List Update)    │    │  (ChromaDB Sync)             │
├────────────────────────┤    ├──────────────────────────────┤
│ send_tool_list_        │    │ index_single_skill()         │
│ changed()              │    │ remove_skill_from_index()    │
└────────────────────────┘    └──────────────────────────────┘
```

### Observer Pattern

**Callback Signature**:

```python
# (skill_name: str, change_type: str) -> None
# change_type: "load", "unload", or "reload"

async def on_skill_change(skill_name: str, change_type: str):
    if change_type == "load":
        await index_single_skill(skill_name)
    elif change_type == "unload":
        await remove_skill_from_index(skill_name)
    elif change_type == "reload":
        await index_single_skill(skill_name)  # Re-index

manager.subscribe(on_skill_change)
```

### Debounced Notifications

Multiple rapid skill changes are batched into a single notification:

```python
# Loading 10 skills - sends ONE notification after 200ms
for skill in skills_to_load:
    manager._notify_change(skill, "load")
# → 200ms delay
# → Notifies all observers once with [(skill1, "load"), (skill2, "load"), ...]
```

**Benefits**:

- Prevents notification storms (N→1 notifications)
- Reduces MCP client tool list refreshes
- Better performance during batch operations

### Hot Reload Flow

```
File Modified (tools.py)
        ↓
manager.reload(skill_name)
        ↓
1. Syntax Validation (py_compile)
        ↓
2. Inline Unload (no notification)
        ↓
3. Load Fresh
        ↓
4. Debounced Notification → [Index Sync → ChromaDB upsert]
```

### Transactional Safety

Syntax validation prevents "bricked" skills:

```python
def _validate_syntax(skill_path: Path) -> bool:
    """Validate Python syntax BEFORE destructive reload."""
    import py_compile

    # Check tools.py
    tools_path = skill_path / "tools.py"
    if tools_path.exists():
        try:
            py_compile.compile(tools_path, doraise=True)
        except py_compile.PyCompileError:
            return False  # Abort reload!

    # Check scripts/*.py
    for py_file in (skill_path / "scripts").glob("*.py"):
        if py_file.name.startswith("_"):
            continue  # Skip __init__.py
        try:
            py_compile.compile(py_file, doraise=True)
        except py_compile.PyCompileError:
            return False

    return True
```

### Index Sync Functions

```python
from agent.core.skill_discovery import (
    index_single_skill,
    remove_skill_from_index,
)

# Called when skill is loaded or reloaded
await index_single_skill("git")  # Atomic upsert to ChromaDB

# Called when skill is unloaded
await remove_skill_from_index("git")
```

---

## Production Stability

> **Production Hardening** - Optimizations for 100+ skill scale.

### 1. Async Task GC Protection

**Problem**: Python's GC can prematurely collect background tasks.

**Solution**: Track tasks in a set with auto-cleanup callbacks.

```python
class SkillManager:
    _background_tasks: set[asyncio.Task] = set()

    def _fire_and_forget(self, coro: asyncio.coroutine) -> asyncio.Task:
        """Fire-and-forget with GC protection."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task
```

**Usage in `_debounced_notify`**:

```python
for skill_name, change_type in changes:
    for cb in self._observers:
        if asyncio.iscoroutinefunction(cb):
            self._fire_and_forget(cb(skill_name, change_type))
        else:
            cb(skill_name, change_type)
```

### 2. Atomic Upsert (ChromaDB)

**Problem**: Delete+Add creates race conditions in concurrent reloads.

**Solution**: Use ChromaDB's atomic `upsert` operation.

```python
# Before (Legacy): Two separate operations
collection.delete(ids=[skill_id])
collection.add(documents=[...], ids=[skill_id])

# After (Current): Single atomic operation
collection.upsert(
    documents=[semantic_text],
    ids=[skill_id],
    metadatas=[...],
)
```

**Benefits**:

- Atomic: No window for race conditions
- Faster: One disk operation instead of two
- Simpler: No error handling for missing entries

### 3. Startup Reconciliation

**Problem**: "Phantom Skills" after crash or unclean shutdown.

**Solution**: Diff index against loaded skills at startup.

```python
async def reconcile_index(loaded_skills: list[str]) -> dict[str, int]:
    """
    Cleanup phantom skills after crash/unclean shutdown.
    Returns: {"removed": N, "reindexed": N}
    """
    # 1. Get all local skill IDs from ChromaDB
    all_docs = collection.get(where={"type": "local"})
    indexed_ids = set(all_docs.get("ids", []))

    # 2. Compare with loaded skills
    expected_ids = {f"skill-{name}" for name in loaded_skills}

    # 3. Remove phantoms (in index but not loaded)
    phantom_ids = indexed_ids - expected_ids
    if phantom_ids:
        collection.delete(ids=list(phantom_ids))

    # 4. Re-index missing skills (in loaded but not index)
    missing = [name for name in loaded_skills
               if f"skill-{name}" not in indexed_ids]
    for name in missing:
        await index_single_skill(name)

    return {"removed": len(phantom_ids), "reindexed": len(missing)}
```

**Called during server startup**:

```python
# mcp_server.py - server_lifespan()
from agent.core.skill_discovery import reconcile_index

async def server_lifespan():
    # ... load skills ...

    # Reconcile index
    loaded = manager.list_loaded()
    stats = await reconcile_index(loaded)
    logger.info(f"🔄 [Reconciliation] {stats}")
```

### Performance at Scale

| Metric                        | Before           | After          | Improvement      |
| ----------------------------- | ---------------- | -------------- | ---------------- |
| Concurrent reload (10 skills) | 10 notifications | 1 notification | 90% reduction    |
| Reload time (with sync)       | 150ms            | 80ms           | 47% faster       |
| Phantom skill detection       | Manual           | Automatic      | Zero-touch       |
| Task GC safety                | Unreliable       | Guaranteed     | Production-ready |

### Test Coverage

```bash
# All hot reload tests (13 tests)
uv run pytest packages/python/agent/src/agent/tests/scenarios/test_hot_reload.py -v

# Key tests:
# - test_scenario1_recursive_sys_modules_cleanup
# - test_scenario2_observer_pattern_basic
# - test_scenario3_reload_orchestration
# - test_scenario4_full_reload_cycle
```

### Related Files

| File                                       | Purpose                                   |
| ------------------------------------------ | ----------------------------------------- |
| `agent/core/skill_manager.py`              | Observer pattern, debounce, GC protection |
| `agent/core/skill_discovery.py`            | Index sync, upsert, reconciliation        |
| `agent/mcp_server.py`                      | Observer registration                     |
| `agent/tests/scenarios/test_hot_reload.py` | 13 comprehensive tests                    |

---

## Auto-Route Skill Discovery

> **Auto-Trigger Skill Discovery** - When users express intent through natural language, the system can automatically discover and prepare skills.

### Overview

introduces `skill.auto_route`, a unified command that:

1. Searches for matching skills (local + remote)
2. Auto-loads unloaded local skills
3. Returns ALL relevant skills (not just one)
4. Shows remote skill suggestions when no local match

### Auto-Route Command

```python
@omni("skill.auto_route", {"task": "update documentation"})
@omni("skill.auto_route", {"task": "polish text", "auto_install": true})
```

### Flow

```
User: "update documentation"
    ↓
@omni("skill.auto_route", {"task": "update documentation"})
    ↓
┌─────────────────────────────────────────────────────────┐
│ Step 1: Search all skills (installed + remote)          │
│ Step 2: Categorize: loaded / unloaded_local / remote    │
│ Step 3: Auto-load unloaded local skills that exist      │
│ Step 4: Return ALL relevant skills                      │
└─────────────────────────────────────────────────────────┘
```

### Output Examples

**Multiple Skills Loaded**

```markdown
# 🎯 Auto-Route: Task Preparation

**Task**: update documentation

## ✅ Relevant Skills (4 loaded)

### ✅ Loaded: documentation (40%)

- **Try**: `@omni("documentation.help")`

### ✅ Loaded: writer (34%)

- **Try**: `@omni("writer.help")`

### ✅ Loaded: knowledge (34%)

- **Try**: `@omni("knowledge.help")`

### ✅ Loaded: git (32%)

- **Try**: `@omni("git.help")`
```

**Auto-Loaded Skills**

```markdown
## 🔄 Auto-loaded: new-skill (75%)

- **Try**: `@omni("new-skill.help")`
```

**Remote Suggestions**

```markdown
## ☁️ Remote Skills (not installed)

1. **network-analysis** - Analyze network traffic... (85%)
2. **packet-capture** - Capture packets... (72%)

**To install**:
@omni("skill.jit_install", {"skill_id": "network-analysis"})
```

### Parameters

| Parameter      | Type   | Default  | Description                       |
| -------------- | ------ | -------- | --------------------------------- |
| `task`         | string | required | Natural language task description |
| `auto_install` | bool   | false    | Auto-install remote skills        |

### Index Optimization

also improves vector index quality:

**1. Rich Semantic Documents**

```python
# Before (minimal document)
"Skill: git\nDescription: Git version control..."

# After (rich document)
"""## Skill: git
## Description: Git version control system for managing code changes.
## Keywords: git, commit, branch, merge, push, pull
## Usage Examples: how to git, git task, work with git, how to commit...
## Use Cases: I need to commit, Help me merge, I need to push...
## Category: Software Development Tool"""
```

**2. Cosine Distance Metric**

Changed ChromaDB collection to use cosine distance for better semantic similarity:

```python
# vector_store.py
return client.get_or_create_collection(
    name=collection_name,
    metadata={
        "description": f"Project knowledge base: {collection_name}",
        "hnsw:space": "cosine",  # Cosine instead of L2
    },
)
```

**3. Confidence Calculation**

Distance-to-similarity conversion with clamping:

```python
# Convert distance to similarity (clamp between 0 and 1)
raw_score = 1.0 - res.distance
similarity = max(0.0, min(1.0, raw_score))
```

### Test Results

| Query                  | Top Skill     | Confidence |
| ---------------------- | ------------- | ---------- |
| "update documentation" | documentation | 45%        |
| "polish text"          | writer        | 52%        |
| "commit changes"       | git           | 32%        |

### Related Files

| File                                     | Purpose                           |
| ---------------------------------------- | --------------------------------- |
| `assets/skills/skill/tools.py`           | `skill.auto_route` implementation |
| `agent/core/skill_discovery/indexing.py` | Rich document building            |
| `agent/core/vector_store.py`             | Cosine distance configuration     |
| `assets/skills/skill/tests/...`          | Auto-Route tests                  |

---

## Feedback Boost in Vector Search

> **Self-Evolving Discovery** - Vector search now includes feedback boost from past successful routings.

### Overview

integrates the FeedbackStore with vector search to boost scores based on learned experience:

```python
# vector.py - hybrid_search with feedback boost
def hybrid_search(query: str, limit: int = 5) -> list[dict]:
    # ... base vector + keyword search ...

    # Add feedback boost
    for skill in results:
        feedback_bonus = get_feedback_boost(query, skill["id"])
        skill["score"] += feedback_bonus
        skill["feedback_bonus"] = feedback_bonus

    return sorted(results, key=lambda x: x["score"], reverse=True)
```

### Scoring Formula

```
Final Score = Vector Similarity
            + Keyword Bonus (+0.1-0.3)
            + Verb Priority Boost (+0.2 for CORE_ACTION_VERBS)
            + Feedback Boost (+0.1 per past success, max +0.3)
            + Sigmoid Calibration (stretch 0.3-0.95 range)
```

### Example

**First query: "commit code"**

```
Vector: 0.65
Keyword: +0.10 (commit)
Verb: +0.15 (git push, git commit)
Feedback: +0.00 (no history)
Final: 0.90
```

**After 3 successful "git.commit" executions:**

```
Vector: 0.65
Keyword: +0.10 (commit)
Verb: +0.15 (git push, git commit)
Feedback: +0.20 (3 successes × 0.1)
Final: 1.10 → clamped to 0.95 (max)
```

### CLI Integration

```bash
# Each successful command updates feedback
omni git.status     # → {"git.status": {"git": 0.1}}
omni git.status     # → {"git.status": {"git": 0.2}}
omni git.status     # → {"git.status": {"git": 0.3}} (max)
```

### Time-Based Decay

Scores decay by 1% each time they are read to prevent stale data from dominating:

```python
# Each get_boost() call applies decay
current_score = 0.10
decayed_score = 0.10 * 0.99  # 0.099
# After 68 reads: < 0.01 → removed
```

### Viewing Feedback Data

```bash
# Check learned feedback
cat .memory/routing_feedback.json
```

### Related Files

| File                                       | Purpose                           |
| ------------------------------------------ | --------------------------------- |
| `agent/core/skill_discovery/vector.py`     | Hybrid search with feedback boost |
| `agent/capabilities/learning/harvester.py` | FeedbackStore with decay          |
| `agent/core/router/semantic_router.py`     | Router with feedback reasoning    |

### See Also

- [Routing](routing.md) - SemanticRouter with feedback loop
- [Skills Overview](../skills.md) - Complete skill documentation
- `assets/specs/phase39_self_evolving_feedback_loop.md`
- `assets/specs/phase40_automated_reinforcement_loop.md`

---

## Incremental Sync vs Full Reindex

> **0.2s Performance** - Diff-based incremental sync for rapid iteration.

### Overview

introduces `omni skill sync`, a high-performance incremental update that only processes changed files. This is contrasted with `omni skill reindex` which performs a full rebuild.

### Sync vs Reindex Comparison

| Aspect        | `omni skill sync`           | `omni skill reindex`     |
| ------------- | --------------------------- | ------------------------ |
| **Speed**     | ~0.2s                       | ~5-10s                   |
| **Algorithm** | Diff (mtime + content hash) | Full scan + rebuild      |
| **Use Case**  | CLI quick sync, Auto-watch  | Manual rebuild, Recovery |
| **Memory**    | O(1) per file               | O(N) all at once         |

### The Diff Algorithm

```python
def sync_skills(self, skills_dir: str, source: str) -> SyncStats:
    """
    1. Scan all .skill.md files in skills_dir
    2. For each file:
       - Check mtime (fast path: skip if unchanged)
       - Compute content hash (accurate: detect renames)
    3. Compare against tracked files in LanceDB
    4. Batch operations: delete → upsert → commit
    5. Return diff stats
    """
    # Step 1: Scan and hash
    scanned = self._scan_manifest_files(skills_dir)

    # Step 2: Get tracked files from LanceDB
    tracked = self._get_tracked_files(source)

    # Step 3: Compute diff
    added = scanned - tracked
    deleted = tracked - scanned
    modified = tracked ∩ scanned

    # Step 4: Batch operations
    stats = self._batch_sync(added, modified, deleted)

    return stats
```

### CLI Commands

```bash
# Incremental sync (fast, recommended for development)
omni skill sync

# Full reindex (slow, use for recovery or initial setup)
omni skill reindex

# Force full rebuild
omni skill reindex --clear

# Verbose output
omni skill sync -v
omni skill reindex -v
```

### Output Examples

**Sync (Incremental)**:

```
=== Quick Sync ===
Scanned: 92 files
Tracked: 86 files
Diff: +1 added, ~0 modified, -0 deleted
Sync complete: +1 added, ~0 modified, -0 deleted, 86 total
```

**Reindex (Full)**:

```
=== Full Reindex ===
Scanning assets/skills...
Indexed 92 skills (72 local, 20 remote)
Reindex complete: 92 total
```

### Performance Comparison

| Scenario          | Sync Time | Reindex Time | Speedup |
| ----------------- | --------- | ------------ | ------- |
| No changes        | 0.05s     | 5.2s         | 104x    |
| 1 file modified   | 0.2s      | 5.2s         | 26x     |
| 10 files modified | 0.4s      | 5.3s         | 13x     |
| Initial setup     | N/A       | 5.5s         | 1x      |

### Related Files

| File                                       | Purpose                        |
| ------------------------------------------ | ------------------------------ |
| `agent/core/vector_store.py`               | `sync_skills()` implementation |
| `packages/rust/crates/omni-vector/src/...` | RustLanceDB backend            |
| `agent/cli/commands/skill.py`              | CLI commands                   |

---

## Reactive Indexing & Zero-Compute MCP

> **Auto感知 (The Watcher)** - File save triggers automatic sync.<br>
> **极速响应 (The Reader)** - O(1) MCP tool listing from LanceDB.

### Overview

introduces automatic skill synchronization when files change, plus optimized MCP server startup with direct LanceDB reads.

### Skill Watcher Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    omni mcp start                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCPServer.lifespan()                         │
├─────────────────────────────────────────────────────────────────┤
│  1. Initial Sync: sync_skills()                                 │
│  2. Start Watcher: BackgroundWatcher.start()                    │
│     ↓ (background thread)                                       │
│  3. MCP Server Running (Stdio/SSE)                              │
└─────────────────────────────────────────────────────────────────┘
           │                    │
           │ on_file_change     │ list_tools()
           ▼                    ▼
┌─────────────────────┐   ┌─────────────────────┐
│  SkillSyncHandler   │   │   LanceDB (O(1))    │
│  → sync_skills()    │   │   直接返回 Schema   │
└─────────────────────┘   └─────────────────────┘
```

### File Watcher Implementation

**`agent/core/skill_manager/watcher.py`**:

```python
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from agent.core.vector_store import get_vector_memory

logger = logging.getLogger(__name__)

class SkillSyncHandler(FileSystemEventHandler):
    """Listens for file changes and triggers incremental sync."""

    def __init__(self, skills_dir: str):
        self.skills_dir = skills_dir
        self.last_sync = 0
        self.cooldown = 1.0  # 1 second debounce

    def on_any_event(self, event):
        if event.is_directory:
            return

        filename = Path(event.src_path).name
        # Ignore non-Python files and temp files
        if not filename.endswith(".py") or filename.startswith("__"):
            return

        # Debounce: ignore events within cooldown
        current_time = time.time()
        if current_time - self.last_sync < self.cooldown:
            return

        self.last_sync = current_time
        logger.info(f"file_change_detected: {filename}")

        try:
            vm = get_vector_memory()
            stats = asyncio.run(vm.sync_skills(self.skills_dir, "skills"))

            if any(v > 0 for v in [stats.get("added", 0),
                                   stats.get("modified", 0),
                                   stats.get("deleted", 0)]):
                logger.info(f"auto_sync_complete: +{stats.get('added', 0)} "
                           f"~{stats.get('modified', 0)} -{stats.get('deleted', 0)}")
        except Exception as e:
            logger.error(f"auto_sync_failed: {e}")
```

### CLI Watch Command

```bash
# Start file watcher (blocking mode)
omni skill watch

# Output:
# 2024-01-15 10:30:45,123 - INFO - file_change_detected: git/scripts/commit.py
# 2024-01-15 10:30:45,234 - INFO - auto_sync_complete: +0 ~1 -0
```

### MCP Server Integration

**`agent/mcp_server.py`**:

```python
from agent.core.skill_manager.watcher import (
    start_global_watcher,
    stop_global_watcher
)

@asynccontextmanager
async def server_lifespan():
    """MCP Server lifecycle management."""
    # Startup
    logger.info("mcp_server_starting")

    # Initial sync
    try:
        vm = get_vector_memory()
        await vm.sync_skills("assets/skills", "skills")
    except Exception as e:
        logger.error("initial_sync_failed", error=str(e))

    # Start Watcher
    start_global_watcher()

    yield

    # Shutdown
    logger.info("mcp_server_shutting_down")
    stop_global_watcher()
```

### Zero-Compute Tool Listing

Direct LanceDB read for O(1) `list_tools` performance:

```python
async def list_tools(self):
    """
    O(1) Speed: Direct LanceDB read, no Python imports, no inspect.
    """
    # Direct from LanceDB - no vector search overhead
    records = self.vector_store.scan_skill_tools_raw("assets/skills")

    tools = []
    for rec_json in records:
        tool = json.loads(rec_json)
        tools.append({
            "name": tool["tool_name"],
            "description": tool["description"],
            "inputSchema": json.loads(tool["input_schema_json"])
        })

    return tools
```

### Usage Flow

```bash
# Terminal 1: Start MCP server (with auto-sync)
omni mcp start

# Terminal 2: Edit a skill file
#   assets/skills/git/scripts/commit.py
#   (save file)

# Terminal 1: See auto-sync log
# 2024-01-15 10:30:45,123 - INFO - file_change_detected: commit.py
# 2024-01-15 10:30:45,234 - INFO - auto_sync_complete: +0 ~1 -0

# Terminal 3: Query agent
# User: "@omni(git.commit, message="fix bug")"
# Agent: Uses updated commit tool immediately
```

### Configuration

**Dependencies**:

```toml
# pyproject.toml
[project.dependencies]
watchdog = ">=3.0.0"
```

**Settings** (in `common/settings.py`):

```python
DEFAULT_SETTINGS = {
    "skills": {
        "path": "assets/skills",
        "watch_enabled": True,
    },
    "watcher": {
        "cooldown_seconds": 1.0,
    }
}
```

### Benefits

| Aspect             | Before (Legacy)          | Current                  |
| ------------------ | ------------------------ | ------------------------ |
| File change → sync | Manual `omni skill sync` | Automatic on save        |
| MCP list_tools     | ~100ms (vector search)   | ~1ms (direct DB read)    |
| Developer workflow | 2-3 commands per change  | 1 command (save file)    |
| Tool list refresh  | Manual trigger           | Automatic on file change |

### Related Files

| File                                       | Purpose                             |
| ------------------------------------------ | ----------------------------------- |
| `agent/core/skill_manager/watcher.py`      | SkillSyncHandler, BackgroundWatcher |
| `agent/cli/commands/skill.py`              | `skill watch` command               |
| `agent/mcp_server.py`                      | Watcher lifecycle integration       |
| `packages/rust/crates/omni-vector/src/...` | Rust delete with LIKE pattern       |

### See Also

- [Skills Overview](../skills.md) - Complete skill documentation
- `assets/specs/phase64_incremental_sync.md`
- `assets/specs/phase65_reactive_indexing.md`
