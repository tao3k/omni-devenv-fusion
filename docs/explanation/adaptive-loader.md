# Adaptive Loader

> **Status**: Implemented | **Date**: 2026-01-14 | **Author**: Claude

## Overview

The Adaptive Loader transforms the Agent from a "preload everything" model to an "infinite toolbox" architecture. The Agent can now manage an unlimited skill library while keeping memory footprint low through:

1. **JIT Loading**: Skills load on first use, not at startup
2. **Ghost Tools**: LLM sees unloaded tools as schemas (The Librarian pattern)
3. **Adaptive Unloading (LRU)**: Memory-efficient garbage collection
4. **Simplified Hot Reload**: Lean, fast-reaction code updates

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Adaptive Loader                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐     │
│  │  User Query │────▶│ Ghost Tool       │────▶│ LLM sees:        │     │
│  └─────────────┘     │ Injection        │     │ - Loaded tools   │     │
│                      │ (context_builder)│     │ - Ghost tools    │     │
│                      └──────────────────┘     └──────────────────┘     │
│                                │                                        │
│                                ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     SkillManager                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │ JIT Loading │  │ LRU Queue   │  │ Hot Reload (Simplified) │  │   │
│  │  │             │  │             │  │                         │  │   │
│  │  │ - Direct    │  │ - Max: 15   │  │ - mtime check only     │  │   │
│  │  │   path lookup│  │ - Pinned   │  │ - No syntax validation │  │   │
│  │  │ - Fallback  │  │   skills    │  │ - Fail fast            │  │   │
│  │  │   to search │  │ - LRU order │  │                         │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                │                                        │
│                                ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     Rust-Backed VectorStore                     │   │
│  │                    (omni-vector + LanceDB)                      │   │
│  │                                                                  │   │
│  │  - Semantic search for ghost tool discovery                     │   │
│  │  - Incremental hash sync for index updates                     │   │
│  │  - Hybrid search (vector + keyword boost)                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Ghost Tool Injection

### Problem

Previously, LLM only knew about pre the skill library grew-loaded skills. As, we faced:

- **Context Window Pressure**: Can't list all 100+ skills
- **Discovery Gap**: LLM couldn't use skills it didn't know about

### Solution

Inject "Ghost Tools" - schemas of unloaded skills - into the tool list that LLM sees.

### Implementation

```python
async def fetch_ghost_tools(
    query: str,
    skill_manager: Any,
    limit: int = 5,
    exclude_tools: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve Ghost Tools (unloaded skills) relevant to the query from the index.

    Returns tool definitions with:
    - name: Tool name
    - description: Prefixed with "[GHOST]"
    - input_schema: Parsed from metadata
    - attributes: {"ghost": True, "score": ...}
    """
    ghost_tools = []
    exclude_tools = exclude_tools or set()

    # Search index via SkillManager
    results = await skill_manager.search_skills(query, limit=limit)

    for tool_doc in results:
        tool_name = tool_doc.get("name")
        if tool_name in exclude_tools:
            continue

        metadata = tool_doc.get("metadata", {})
        schema_str = metadata.get("input_schema", "{}")

        try:
            input_schema = json.loads(schema_str)
        except json.JSONDecodeError:
            input_schema = {"type": "object", "properties": {}}

        ghost_tool = {
            "name": tool_name,
            "description": f"[GHOST] {tool_doc.get('description', '')} (Auto-loads on use)",
            "input_schema": input_schema,
            "attributes": {"ghost": True, "score": tool_doc.get("score", 0)},
        }
        ghost_tools.append(ghost_tool)
        exclude_tools.add(tool_name)

    return ghost_tools


def merge_tool_definitions(
    loaded_tools: List[Dict[str, Any]],
    ghost_tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merge loaded tools and ghost tools.
    Loaded tools take priority (no duplicates).
    """
    final_tools = list(loaded_tools)
    loaded_names = {t["name"] for t in loaded_tools}

    for ghost in ghost_tools:
        if ghost["name"] not in loaded_names:
            final_tools.append(ghost)

    return final_tools
```

## JIT Loading

### Problem

Loading all skills at startup consumes memory and slows startup.

### Solution

Load skills on first use (Just-In-Time).

### Implementation

```python
async def _try_jit_load(self, skill_name: str) -> bool:
    """
    Attempt to Just-In-Time load a skill from the vector index.

    Strategy:
    1. First try direct path lookup (fastest - most common case)
    2. Then fall back to semantic search if skill not in expected location
    """
    from common.skills_path import SKILLS_DIR

    # Strategy 1: Direct path lookup using SKILLS_DIR (fastest)
    definition_path = SKILLS_DIR.definition_file(skill_name)
    if definition_path.exists():
        self.load_skill(definition_path.parent)
        return True

    # Strategy 2: Fall back to semantic search
    results = await self.search_skills(skill_name, limit=10)
    for tool in results:
        meta = tool.get("metadata", {})
        if meta.get("skill_name") == skill_name:
            script_path = Path(meta.get("file_path"))
            potential_root = script_path.parent.parent
            if (potential_root / "SKILL.md").exists():
                self.load_skill(potential_root)
                return True

    return False
```

## Adaptive Unloading (LRU)

### Problem

JIT loading without cleanup leads to memory bloat over time.

### Solution

LRU-based garbage collection with pinned core skills.

### Implementation

```python
class SkillManager(HotReloadMixin, ...):
    def __init__(self, ...):
        # Step 3: Adaptive Unloading (LRU)
        self._lru_order: list[str] = []          # Usage order queue
        self._pinned_skills: set[str] = {        # Protected from unload
            "filesystem", "terminal", "writer", "git", "note_taker"
        }
        self._max_loaded_skills: int = 15        # Memory limit

    def _touch_skill(self, skill_name: str) -> None:
        """Mark a skill as recently used (moves to end of LRU queue)."""
        if skill_name in self._lru_order:
            self._lru_order.remove(skill_name)
        self._lru_order.append(skill_name)

    def _enforce_memory_limit(self) -> None:
        """Unload LRU skills if loaded count exceeds limit."""
        if len(self._skills) <= self._max_loaded_skills:
            return

        excess = len(self._skills) - self._max_loaded_skills

        for skill_name in list(self._lru_order):
            if skill_name in self._pinned_skills:
                continue
            if skill_name not in self._skills:
                continue

            if self.unload(skill_name):
                excess -= 1
                if excess <= 0:
                    break
```

## Simplified Hot Reload

### Before vs After

| Feature              | Before | After      |
| -------------------- | ------ | ---------- |
| Lines of code        | 216    | 145        |
| `_validate_syntax()` | ✅ Yes | ❌ Removed |
| Transaction rollback | ✅ Yes | ❌ Removed |
| mtime check          | ✅ Yes | ✅ Yes     |
| Lazy logger          | ❌ No  | ✅ Yes     |

### Implementation

```python
def _ensure_fresh(self, skill_name: str) -> bool:
    """
    Check if a skill needs reloading.

    Simplified - only checks mtime, no syntax validation.
    If code has syntax errors, Python import will raise an exception.
    The Meta-Agent can then self-repair the code.
    """
    skill = self._skills.get(skill_name)
    if skill is None:
        return False

    try:
        script_files = list(skill.path.glob("*.py"))
        if not script_files:
            return True

        current_mtime = max(f.stat().st_mtime for f in script_files)
        cached_mtime = self._mtime_cache.get(skill_name, 0.0)

        if current_mtime > cached_mtime:
            self._reload_skill(skill, current_mtime)

        return True

    except Exception as e:
        _get_logger().warning("Hot reload check failed", skill=skill_name, error=str(e))
        return True  # Allow execution to try
```

## API Reference

### Context Builder Functions

| Function                                         | Description                       |
| ------------------------------------------------ | --------------------------------- |
| `fetch_ghost_tools(query, skill_manager, limit)` | Get ghost tool schemas from index |
| `merge_tool_definitions(loaded, ghosts)`         | Merge loaded and ghost tools      |

### SkillManager Methods

| Method                        | Description                 |
| ----------------------------- | --------------------------- |
| `search_skills(query, limit)` | Semantic search for skills  |
| `_try_jit_load(skill_name)`   | Load skill on first use     |
| `_touch_skill(skill_name)`    | Update LRU order            |
| `_enforce_memory_limit()`     | Unload oldest if over limit |

### LRU Configuration

| Attribute            | Default                                         | Description                   |
| -------------------- | ----------------------------------------------- | ----------------------------- |
| `_max_loaded_skills` | 15                                              | Max skills to keep in memory  |
| `_pinned_skills`     | {filesystem, terminal, writer, git, note_taker} | Skills never unloaded         |
| `_lru_order`         | []                                              | Usage order (oldest → newest) |

## Related Files

| File                                                               | Purpose               |
| ------------------------------------------------------------------ | --------------------- |
| `packages/python/agent/src/agent/core/context_builder.py`          | Ghost Tool Injection  |
| `packages/python/agent/src/agent/core/skill_manager/manager.py`    | JIT Loading + LRU     |
| `packages/python/agent/src/agent/core/skill_manager/hot_reload.py` | Simplified Hot Reload |
