# Hot Reload Mechanism

> One Tool + Trinity Architecture - Hot Reload for Skills

Hot reload enables real-time code updates without restarting the MCP server. Changes to skill scripts are automatically detected and applied on the next command invocation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SkillContext.get_skill()                         │
│                                                                          │
│  1. Get cached skill from _skills dict                                   │
│  2. Check mtime of scripts/*.py files                                    │
│  3. If modified:                                                         │
│     - Clear sys.modules cache for this skill                            │
│     - Clear old command cache (_commands, _native)                       │
│     - Reload ScriptLoader.load_all()                                     │
│     - Re-register commands                                               │
│     - Update _mtime                                                      │
│  4. Return updated skill                                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Modification Detection (mtime-based)

```python
# In SkillContext.get_skill()
current_mtime = max(f.stat().st_mtime for f in scripts_path.glob("*.py"))
cached_mtime = getattr(skill, "_mtime", 0)

if current_mtime > cached_mtime:
    # Trigger hot reload
    ...
```

**What is checked:**

- All `*.py` files in `scripts/` directory
- Comparison: `current_mtime > cached_mtime` (strictly greater)

### 2. Cache Clearing

```python
# Clear sys.modules for this skill
skill_module_prefix = f"{skill_name}."
modules_to_remove = [k for k in sys.modules if k.startswith(skill_module_prefix)]
for mod in modules_to_remove:
    del sys.modules[mod]

# Clear command cache
old_commands = [k for k in self._commands if k.startswith(f"{skill_name}.")]
for cmd in old_commands:
    del self._commands[cmd]
```

### 3. Script Reloading

```python
# Clear and reload script loader
if skill._script_loader:
    skill._script_loader.commands.clear()
    skill._script_loader.native_functions.clear()
    skill._script_loader.load_all()

# Re-register commands
for cmd_name, handler in skill._script_loader.commands.items():
    self._commands[cmd_name] = handler
```

## What Can Be Reloaded

| Component               | Reloadable | Notes                                             |
| ----------------------- | ---------- | ------------------------------------------------- |
| Function implementation | ✅ Yes     | Changes in `scripts/*.py` take effect immediately |
| Business logic          | ✅ Yes     | Core algorithm changes apply on reload            |
| Bug fixes               | ✅ Yes     | Runtime fixes without restart                     |
| New commands            | ✅ Yes     | Added commands are registered                     |
| Removed commands        | ✅ Yes     | Removed commands are unregistered                 |

## What CANNOT Be Reloaded

| Component                 | Reloadable | Notes                                                    |
| ------------------------- | ---------- | -------------------------------------------------------- |
| `@skill_command` metadata | ⚠️ Partial | `description` cached at MCP level; function code reloads |
| Decorator parameters      | ❌ No      | Requires `skill.reload` to update MCP notification       |
| MCP tool registration     | ❌ No      | Requires MCP tool list change notification               |

### Why Some Things Cannot Be Reloaded

MCP tool metadata (name, description, parameters) is registered once during server initialization. While function code changes are picked up, decorator metadata requires:

1. `skill.reload` - Sends `notifications/tools/list_changed` to MCP clients
2. Client refresh - MCP clients may cache tool descriptions

## Cache Invalidation

When a skill reloads, these caches are cleared:

```python
# 1. sys.modules - Python's module cache
modules_to_remove = [k for k in sys.modules if k.startswith(skill_name)]
for mod in modules_to_remove:
    del sys.modules[mod]

# 2. Command cache - SkillContext._commands
old_commands = [k for k in self._commands if k.startswith(f"{skill_name}.")]
for cmd in old_commands:
    del self._commands[cmd]

# 3. Native functions cache - SkillContext._native
old_native = [k for k in self._native if k.startswith(f"{skill_name}.")]
for key in old_native:
    del self._native[key]

# 4. ScriptLoader's internal caches
skill._script_loader.commands.clear()
skill._script_loader.native_functions.clear()
```

## Usage

### Automatic Detection

Skills are checked on every `get_skill()` call:

```python
# In server.py _handle_call_tool()
skill = self._kernel.skill_context.get_skill(skill_name)
# If scripts were modified, skill is automatically reloaded
result = await skill.execute(command_name, **arguments)
```

### Manual Reload (MCP Notification)

```bash
@omni("skill.reload", {"name": "git"})
```

This triggers:

1. Skill reload
2. `notifications/tools/list_changed` sent to MCP clients
3. Clients refresh their tool list

## Code Flow

```
User edits file
        │
        ▼
File mtime changes
        │
        ▼
@omni git.status  (or any command)
        │
        ▼
kernel.skill_context.get_skill("git")
        │
        ▼
Check: current_mtime > cached_mtime?
        │
        ├─ No ──▶ Return cached skill
        │
        └─ Yes ──▶
            1. Clear sys.modules[git.*]
            2. Clear _commands[git.*]
            3. Clear _native[git.*]
            4. script_loader.load_all()
            5. Re-register commands
            6. Update skill._mtime
            │
            ▼
        Return reloaded skill
        │
        ▼
skill.execute() uses new code
```

## Related Files

| File                                                            | Purpose                          |
| --------------------------------------------------------------- | -------------------------------- |
| `packages/python/core/src/omni/core/skills/runtime/__init__.py` | SkillContext with hot reload     |
| `packages/python/core/src/omni/core/skills/script_loader.py`    | ScriptLoader with cache clearing |
| `packages/python/core/src/omni/core/kernel/watcher.py`          | File watcher for auto-reload     |
| `packages/python/agent/src/omni/agent/mcp_server/lifespan.py`   | MCP notifications                |
| `packages/python/core/tests/universal/test_hot_reload.py`       | Comprehensive tests              |

## Testing

Run the hot reload tests:

```bash
uv run pytest packages/python/core/tests/universal/test_hot_reload.py -v
```

### Test Categories

- **TestMtimeDetection**: mtime caching and change detection
- **TestSysModulesClearing**: Python module cache clearing
- **TestCommandRegistration**: Command add/remove detection
- **TestEdgeCases**: Error handling and boundary conditions
- **TestScriptLoaderHotReload**: ScriptLoader reload behavior
- **TestIntegrationWithKernel**: Kernel integration

### Manual Testing

```bash
# 1. Start MCP server
uv run omni mcp --transport stdio

# 2. In another terminal, modify a skill
echo "modified" >> assets/skills/git/scripts/status.py

# 3. Invoke command - changes should be reflected
@omni git.status
```

## Troubleshooting

### Changes Not Taking Effect

1. **Check file path**: Ensure modifying `<skill>/scripts/*.py`
2. **Enable logging**: Watch for "Hot reloading skill" messages
3. **Verify mtime**: Check file modification time is newer

```python
# Debug: Check mtimes
from pathlib import Path
skill_path = Path("assets/skills/git")
scripts_path = skill_path / "scripts"
current = max(f.stat().st_mtime for f in scripts_path.glob("*.py"))
print(f"Current mtime: {current}")
```

### Stale Cache Issues

```python
# Force clear all caches
from omni.core.skills.runtime import get_skill_context
ctx = get_skill_context()
ctx._commands.clear()
ctx._native.clear()

# Clear sys.modules
import sys
for k in list(sys.modules.keys()):
    if k.startswith("git."):
        del sys.modules[k]
```

### MCP Tool Metadata Not Updated

If decorator attributes (description, etc.) changed:

```bash
@omni("skill.reload", {"name": "git"})
# Then restart Claude Code session to refresh MCP cache
```

## Best Practices

1. **Edit function code, not metadata** - Code changes reload automatically
2. **Use `skill.reload` for metadata changes** - Triggers MCP notification
3. **Test with simple changes first** - Verify hot reload works before complex edits
4. **Restart if stuck** - Claude Code session restart clears all caches

## Testing Hot Reload

### With Filesystem (Traditional)

```bash
# 1. Start MCP server
uv run omni mcp --transport stdio

# 2. In another terminal, modify a skill
echo "modified" >> assets/skills/git/scripts/status.py

# 3. Invoke command - changes should be reflected
@omni git.status
```

### Without Filesystem (Virtual Path Scanning)

For testing hot reload behavior without touching the filesystem, use the virtual path scanner:

```python
from omni_core_rs import scan_paths

def simulate_tool_change(skill_name: str, tool_name: str, new_content: str) -> dict:
    """Simulate a tool change and verify scanner detects it."""
    file_path = f"/virtual/{skill_name}/scripts/{tool_name}.py"
    files = [(file_path, new_content)]

    # Scan the updated content
    tools = scan_paths(files, skill_name, [], [])

    return {
        "detected": len(tools) > 0,
        "tool_name": tools[0].tool_name if tools else None,
        "file_hash": tools[0].file_hash if tools else None,
    }

# Test: Add a new tool
new_tool_content = '''
@skill_command(name="new_feature")
def new_feature(param: str) -> str:
    """New feature implementation."""
    return f"Result: {param}"
'''

result = simulate_tool_change("git", "new_feature", new_tool_content)
assert result["detected"] is True
assert "new_feature" in result["tool_name"]

# Test: Verify file hash changes for change detection
old_hash = result["file_hash"]

updated_content = '''
@skill_command(name="new_feature")
def new_feature(param: str) -> str:
    """Updated implementation."""
    return f"Updated: {param}"
'''

result2 = simulate_tool_change("git", "new_feature", updated_content)
assert result2["file_hash"] != old_hash  # Hash should change
```

### Testing Delete-Re-Add Scenario

The virtual path scanner enables testing the critical delete-re-add scenario:

```python
from omni_core_rs import scan_paths

def test_delete_re_add_scenario():
    """Test that deleted tools are removed and re-added correctly."""
    # Initial state: tool exists
    initial_files = [("/virtual/git/scripts/tool.py", '''
@skill_command(name="tool")
def tool():
    """Original tool."""
    pass
''')]
    tools = scan_paths(initial_files, "git", [], [])
    assert len(tools) == 1

    # Simulate delete: empty file list
    deleted_tools = scan_paths([], "git", [], [])
    assert len(deleted_tools) == 0

    # Simulate re-add: new content
    re_add_files = [("/virtual/git/scripts/tool.py", '''
@skill_command(name="tool")
def tool():
    """Re-added tool."""
    pass
''')]
    re_add_tools = scan_paths(re_add_files, "git", [], [])
    assert len(re_add_tools) == 1
    assert re_add_tools[0].tool_name == "git.tool"
```

This approach allows testing hot reload logic without creating temporary directories or modifying `assets/skills/`.
