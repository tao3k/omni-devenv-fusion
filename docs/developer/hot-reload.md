# Hot Reload

Simplified for JIT/Meta-Agent Era. Removed syntax validation - Python import catches errors, Meta-Agent handles recovery.

## Changes

| Feature              | Before (Legacy)        | Current    |
| -------------------- | ---------------------- | ---------- |
| Syntax validation    | `py_compile.compile()` | ❌ Removed |
| Transaction rollback | ✅ Yes                 | ❌ Removed |
| Lines of code        | 216                    | 145        |
| Error handling       | Fail-safe              | Fail-fast  |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      SkillManager                           │
│  ┌─────────────────┐                                        │
│  │  _ensure_fresh  │───▶ Direct reload (no validation)     │
│  │  (mtime check)  │                                        │
│  └─────────────────┘                                        │
│           │                                                 │
│           ▼                                                 │
│     Load skill or                                           │
│     reload existing                                         │
│     (Python import catches errors)                          │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Modification Detection

```python
# In HotReloadMixin._ensure_fresh()
tools_mtime = tools_path.stat().st_mtime
scripts_mtime = max(f.stat().st_mtime for f in scripts_path.glob("*.py"))

should_reload = tools_mtime >= skill.mtime or scripts_mtime >= skill.mtime
```

- **tools.py**: Checked via `mtime`
- **scripts/\*.py**: All Python files in `scripts/` directory checked
- Uses `>=` comparison (not `>`) to catch simultaneous edits

### 2. Modification Detection (Unchanged)

```python
# In HotReloadMixin._ensure_fresh()
scripts_mtime = max(f.stat().st_mtime for f in scripts_path.glob("*.py"))
```

- **scripts/\*.py**: All Python files in `scripts/` directory checked
- Uses `>` comparison (cached_mtime vs current_mtime)

### 3. Simplified Reload Cycle

```
1. Unload old skill:
   - Remove from _skills dict
   - Clear command cache entries
   - Clear sys.modules for this skill
2. Load fresh version:
   - Import new modules
   - Parse @skill_command decorators
3. If import fails: Error propagates, Meta-Agent handles recovery
```

**Philosophy**: Fail fast. Python's import mechanism catches syntax errors naturally. The Meta-Agent can then self-repair the code.

### 4. Lazy Logger

To avoid ~100ms import overhead at startup, the logger is initialized lazily:

```python
_cached_logger: Any = None

def _get_logger() -> Any:
    global _cached_logger
    if _cached_logger is None:
        import structlog
        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger
```

## What Can Be Reloaded

| Component               | Reloadable | Notes                                             |
| ----------------------- | ---------- | ------------------------------------------------- |
| Function implementation | ✅ Yes     | Changes in `scripts/*.py` take effect immediately |
| Business logic          | ✅ Yes     | Core algorithm changes apply on reload            |
| Bug fixes               | ✅ Yes     | Runtime fixes without restart                     |
| tools.py implementation | ✅ Yes     | Function body changes reload                      |

## What CANNOT Be Reloaded

| Component                 | Reloadable | Notes                                                 |
| ------------------------- | ---------- | ----------------------------------------------------- |
| `@skill_command` metadata | ❌ No      | `name`, `description`, `category` cached at MCP level |
| Decorator parameters      | ❌ No      | Parameters frozen at registration                     |
| Function signature        | ❌ No      | Type hints cached in command schema                   |
| MCP tool registration     | ❌ No      | Requires server restart to update                     |

### Why MCP Metadata Cannot Be Reloaded

MCP tools are registered once during server initialization:

```python
# In mcp_server.py
def _register_skills():
    for skill in skill_manager.list_skills():
        for cmd in skill.commands.values():
            mcp_server.register_tool(
                name=f"{skill.name}.{cmd.name}",
                description=cmd.description,  # ← Frozen at registration
                parameters=cmd.schema,        # ← Frozen at registration
            )
```

The MCP specification doesn't support dynamic tool updates. To change metadata:

```bash
# Option 1: Restart MCP server
/mcp restart

# Option 2: Restart the application
# (depends on your deployment)
```

## Cache Invalidation

When a skill reloads, the following caches are cleared:

```python
# Command cache
keys_to_remove = [k for k in self._command_cache if k.startswith(f"{skill_name}.")]
for key in keys_to_remove:
    del self._command_cache[key]

# Module cache (sys.modules)
prefix = f"agent.skills.{skill_name}."
modules_to_remove = [m for m in sys.modules if m.startswith(prefix)]
for module in modules_to_remove:
    del sys.modules[module]
```

## Usage

### Automatic Detection

Skills are checked on every command invocation:

```python
@skill_command(name="status", ...)
def status(...):
    # Before executing, _ensure_fresh() is called
    # If modified, skill reloads automatically
```

### Manual Reload

```python
skill_manager.reload("git")  # Force reload a skill
```

### Debug Logging

Enable debug logging to trace reload behavior:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# You'll see:
# DEBUG: Hot-reload check skill=git tools_mtime=1234567890.0 scripts_mtime=...
# INFO: Hot-reloading skill=git modified=['scripts/prepare.py']
```

## Testing Hot Reload

```python
# pytest assets/skills/git/tests/test_git_smart_workflow.py -v
# pytest packages/python/agent/src/agent/core/skill_manager/tests/test_hot_reload.py -v
```

### Test Coverage

- **mtime detection**: Verify `scripts/*.py` changes trigger reload
- **cache clearing**: Ensure old code doesn't persist
- **error propagation**: Syntax errors propagate to caller (Meta-Agent)

## Troubleshooting

### Changes Not Taking Effect

1. **Check file path**: Ensure modifying `<skill>/scripts/*.py` or `<skill>/tools.py`
2. **Enable logging**: Watch for reload messages
3. **Restart MCP**: If metadata changed, restart is required

### "Skill not found" After Reload

```python
# Debug: Check if skill is in _skills
print(skill_manager._skills.keys())

# Debug: Check discovery path
print(skill_manager._discover_single("git"))
```

### Stale Cache Issues

```python
# Force clear all caches
skill_manager._command_cache.clear()
skill_manager._mtime_cache.clear()
```

## Related Files

| File                                                                  | Purpose                                  |
| --------------------------------------------------------------------- | ---------------------------------------- |
| `packages/python/agent/src/agent/core/skill_manager/hot_reload.py`    | HotReloadMixin implementation            |
| `packages/python/agent/src/agent/core/skill_manager/skill_manager.py` | SkillManager with hot-reload integration |
| `packages/python/agent/src/agent/core/skill_manager/discovery.py`     | Skill discovery and loading              |

## See Also

- [Skill Architecture](../skills.md) - Skill structure and conventions
- [MCP Core Architecture](mcp-core-architecture.md) - MCP tool registration
