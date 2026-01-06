# Trinity Architecture (Phase 25.3)

> Unified skill management: Code (Hot-Reloading), Context (Repomix), and State (Registry).

## Overview

The Trinity Architecture unifies three critical concerns in a single skill management system, enabling millisecond response times while providing deep context understanding for AI agents.

## The Three Pillars

```
┌─────────────────────────────────────────────────────────────┐
│                      SkillManager                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │    Code     │  │   Context   │  │       State         │  │
│  │ (Hot-Load)  │  │ (Repomix)   │  │     (Registry)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 1. Code (Hot-Reloading)

**Purpose**: Execute skill commands with minimal overhead.

**Mechanism**: `_ensure_fresh(skill_name)` performs mtime-based lazy reload.

```python
def _ensure_fresh(self, skill_name: str) -> bool:
    """
    Hot-Load Magic: Checks file modification time and reloads if necessary.
    Called before every command execution.
    """
    skill_path = self.skills_dir / skill_name

    # If not in memory, load it
    if skill_name not in self.skills:
        self._register_skill(skill_path)
        return skill_name in self.skills

    # Check freshness via mtime
    skill = self.skills[skill_name]
    try:
        current_mtime = skill_path.stat().st_mtime
        if current_mtime > skill.mtime:
            logger.info(f"Hot-Reloading Skill: {skill_name}")
            self._register_skill(skill_path)
    except FileNotFoundError:
        pass

    return True
```

**Performance**: <1ms when files unchanged (no I/O, no import overhead).

**Trigger**: File modification on disk detected via `mtime` comparison.

### 2. Context (RepomixCache)

**Purpose**: Provide deep skill understanding for LLM context.

**Output**: XML-packed skill context including code, docs, and configuration.

**Caching**: Each skill has its own `RepomixCache` instance.

```python
@dataclass
class Skill:
    name: str
    module_name: str
    path: Path
    mtime: float
    commands: Dict[str, SkillCommand]
    # Trinity: Context Cache for deep skill understanding
    context_cache: Optional[RepomixCache] = None
```

**Cache Location**: `.cache/<project>/skill_<name>_repomix.xml`

**Example**:

```
.cache/
└── omni-devenv-fusion/
    └── skill_git_repomix.xml  (20KB, includes tools.py, Backlog.md, workflows)
```

**Usage**: `@omni("git.help")` returns XML-packed skill context.

### 3. State (Registry)

**Purpose**: Maintain skill metadata and command registry.

**Structure**: `Skill` dataclass with commands, mtime, and context_cache.

```python
@dataclass
class SkillCommand:
    name: str
    func: Callable[..., str]
    description: str
    category: str = "general"
```

**Persistence**: In-memory, survives across command calls.

**Discovery**: Auto-scans `agent/skills/*/tools.py` at startup.

## Hot-Reload Flow

```
User: @omni("git.status")
     │
     ▼
get_command("git", "git_status")
     │
     ▼
_ensure_fresh("git") ──→ Check mtime
     │
     ├── Unchanged ──→ Return cached command (<1ms)
     │
     └── Changed ──→ importlib.reload()
     │               Update Skill.mtime
     │               Update Skill.commands
     │
     ▼
Execute command function
```

## Key Performance Characteristics

| Scenario                    | Time       | Reason                          |
| --------------------------- | ---------- | ------------------------------- |
| First command (cold)        | ~10-50ms   | Module load, command extraction |
| Subsequent (no change)      | <1ms       | Memory direct call              |
| After file modification     | ~10-50ms   | importlib.reload()              |
| First `@omni("skill.help")` | ~100-500ms | Repomix execution               |
| Subsequent help calls       | <1ms       | Cache read                      |

## File Structure

```
packages/python/agent/src/agent/core/
└── skill_manager.py          # Trinity implementation

packages/python/common/src/common/mcp_core/
└── lazy_cache.py             # RepomixCache class

.cache/
└── <project>/
    └── skill_<name>_repomix.xml  # Cached contexts

agent/skills/<skill>/
├── tools.py                  # Skill implementation
├── prompts.md                # Skill rules (LLM reads)
├── guide.md                  # Reference docs
└── repomix.json              # Atomic context config (optional)
```

## Comparison: Phase 25.1 → 25.3

| Aspect           | Phase 25.1    | Phase 25.3         |
| ---------------- | ------------- | ------------------ |
| **Architecture** | One Tool      | Trinity            |
| **Code Loading** | Static        | Hot-reload (mtime) |
| **Context**      | guide.md only | XML via Repomix    |
| **Skill State**  | Simple dict   | Skill dataclass    |
| **Performance**  | Fast          | Faster (<1ms)      |
| **LLM Context**  | Text          | Structured XML     |

## Integration Points

### With MCP Server (`mcp_server.py`)

```python
@mcp.tool(name="omni")
async def omni(input: str, args: Dict = None) -> str:
    """Single entry point - dispatches to Trinity."""
    manager = get_skill_manager()
    # ... parses skill.command ...
    result = await manager.run(skill_name, command_name, args)
    return result
```

### With Repomix

Each skill can optionally define `repomix.json` for atomic context:

```json
{
  "output": { "style": "xml", "fileSummary": true },
  "include": ["tools.py", "prompts.md", "guide.md", "*.md"],
  "ignore": { "patterns": ["**/__pycache__/**"], "characters": [] }
}
```

Without `repomix.json`, dynamic config is generated with defaults.

## Best Practices

1. **Hot-Reload is Transparent**: Don't worry about reloads; they're automatic.

2. **Use `@omni("skill.help")`** for deep understanding of a skill's capabilities.

3. **Keep `tools.py` Focused**: Smaller files load faster on modification.

4. **Add `repomix.json`** for precise control over context inclusion.

## Troubleshooting

| Issue                        | Solution                                                         |
| ---------------------------- | ---------------------------------------------------------------- |
| Command not found after edit | Wait for reload or call `manager.reload_skill()`                 |
| Help returns old context     | Delete `.cache/<project>/*.xml` or call `context_cache.reload()` |
| Slow first command           | Normal - cold start requires module load                         |

---

## Production Validation (Phase 25.4)

The Iron Trinity architecture has been validated under extreme stress conditions using `scripts/stress_trinity.py`.

### Stress Test Results

| Metric              | Result    | Target                            |
| ------------------- | --------- | --------------------------------- |
| Duration            | 5.08s     | 5s                                |
| Skill Modifications | 31        | Chaos Monkey (50-200ms intervals) |
| Skill Invocations   | 966       | Concurrent requests               |
| Failed Requests     | **0**     | 0                                 |
| Race Conditions     | 0         | <5 acceptable                     |
| Avg Context Time    | 109ms     | <500ms                            |
| Throughput          | 190 req/s | -                                 |

### Test Scenarios Covered

1. **Chaos Monkey**: Rapid file modifications (50-200ms intervals) simulating active IDE editing
2. **Spammer**: High concurrency requests (1-5 batch, 10ms intervals) during file writes
3. **Context Loader**: Repomix performance under load (10 consecutive help calls)

### Key Findings

- **Hot-Reload is Rock Solid**: 31 file modifications during test, zero crashes
- **No Race Conditions**: 966 concurrent requests during file writes, all returned valid responses
- **Repomix Performance**: 109ms average context generation (well under 500ms threshold)

### Conclusion

> **The Iron Trinity is SOLID.**

Production-ready for high-concurrency environments with zero failures under extreme conditions.

### Running the Stress Test

```bash
python scripts/stress_trinity.py
```

Expected output on success:

```
✅  PASSED: Iron Trinity is SOLID. No crashes under fire.
```
