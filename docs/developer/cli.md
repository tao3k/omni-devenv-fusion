# CLI Developer Guide

> **Phase 42: State-Aware Routing** | **Phase 41: Wisdom-Aware Routing** | **Phase 40: Automated Reinforcement Loop** | **Phase 35.2: Modular CLI Architecture** | **Phase 35.1: Simplified Test Framework**

> **Phase 42**: CLI route command now displays environment state from ContextSniffer.

## Phase 41/42: Route Command

The `omni route` command tests and demonstrates the Semantic Router with wisdom-aware and state-aware routing.

### Commands

| Command                     | Description                         |
| --------------------------- | ----------------------------------- |
| `omni route invoke <query>` | Route a query and show results      |
| `omni route wisdom <query>` | Search harvested wisdom for a query |
| `omni route status`         | Show routing system status          |

### Options

| Option            | Description              |
| ----------------- | ------------------------ |
| `--verbose, -v`   | Show detailed reasoning  |
| `--no-wisdom, -n` | Disable wisdom injection |
| `--json, -j`      | Output as JSON           |

### Examples

```bash
# Route a query with wisdom and environment state
omni route invoke "run tests for this project" --verbose

# Search for wisdom without routing
omni route wisdom "python testing"

# Check system status
omni route status

# Route without wisdom injection
omni route invoke "commit my changes" --no-wisdom
```

### Output Example

```
$ omni route invoke "commit my changes" --verbose

╭─────────────────────────────────── Input ────────────────────────────────────╮
│ Query: commit my changes                                                     │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────── [Phase 42] Environment State ────────────────────────╮
│ [ENVIRONMENT STATE]                                                          │
│ - Branch: main | Modified: 51 files (M assets/references.yaml, ...)          │
│ - Active Context: Empty                                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
┏━━━━━━━┓
┃ Skill ┃
┡━━━━━━━┩
│ git   │
└───────┘
╭─────────────────────────────── Mission Brief ────────────────────────────────╮
│ Commit staged changes.                                                       │
│ IMPORTANT: Use git_stage_all for bulk staging...                             │
╰──────────────────────────────────────────────────────────────────────────────╯
Confidence: 0.95
```

### Related Files

| File                                   | Purpose                                    |
| -------------------------------------- | ------------------------------------------ |
| `agent/cli/commands/route.py`          | Route command implementation               |
| `agent/core/router/semantic_router.py` | SemanticRouter with wisdom/state awareness |

---

## Phase 40: Automatic Feedback Recording

When a skill command executes successfully via CLI, the system automatically records positive feedback:

```python
# runner.py - After successful command execution
def _record_cli_success(command: str, skill_name: str) -> None:
    """Record CLI execution success as positive feedback.

    This is a lightweight signal - CLI success doesn't guarantee
    the routing was correct, but it's still useful data.
    """
    try:
        from agent.capabilities.learning.harvester import record_routing_feedback
        # Use command as pseudo-query, record mild positive feedback
        record_routing_feedback(command, skill_name, success=True)
    except Exception:
        # Silently ignore if feedback system not available
        pass
```

### How It Works

1. User runs: `omni git.status`
2. Command executes successfully
3. `_record_cli_success("git.status", "git")` is called
4. Feedback stored in `.memory/routing_feedback.json`:

```json
{
  "git.status": {
    "git": 0.1
  }
}
```

5. Future "git status" queries get +0.1 confidence boost

### Viewing Feedback Data

```bash
# Check learned feedback
cat .memory/routing_feedback.json

# Monitor feedback during development
tail -f .memory/routing_feedback.json
```

---

## MCP Server Command

The `omni mcp` command starts the Omni MCP Server with dual transport support:

```bash
# SSE mode (default, for Claude Code CLI)
omni mcp --transport sse --host 127.0.0.1 --port 3000

# Stdio mode (for Claude Desktop)
omni mcp --transport stdio

# Multi-instance development (different ports)
omni mcp --transport sse --port 3001  # Project A
omni mcp --transport sse --port 3002  # Project B
```

### Options

| Option            | Default     | Description                                      |
| ----------------- | ----------- | ------------------------------------------------ |
| `--transport, -t` | `sse`       | Transport mode (`stdio` or `sse`)                |
| `--host, -h`      | `127.0.0.1` | Host to bind to (SSE only, local security)       |
| `--port, -p`      | `3000`      | Port to listen on (SSE only, use `0` for random) |

### Security

- **Default binding**: `127.0.0.1` (local only, no network exposure)
- **Never use `0.0.0.0`** in development (exposes your Agent)

## Quick Reference

### Running Tests

```bash
cd packages/python/agent/src/agent
uv run python testing/test_cli.py
```

### Testing Specific Components

```bash
# Test console output
python -c "
from agent.cli.console import print_result
# Test CommandResult format (from @skill_command)
class MockResult:
    data = {'content': 'test', 'metadata': {'url': 'example.com'}}
print_result(MockResult(), is_tty=True)
"

# Test runner
python -c "
from agent.cli.runner import run_skills
from agent.cli.console import cli_log_handler
run_skills(['git.status'], log_handler=cli_log_handler)
"
```

---

## Module Structure

```
agent/cli/
├── __init__.py          # Main exports (backward compatibility)
├── app.py               # Typer application configuration
├── console.py           # Console and output formatting
├── runner.py            # Skill execution logic
└── commands/
    ├── __init__.py
    ├── skill.py         # Skill command group (run, list, etc.)
    └── route.py         # Route command (Phase 41/42)
```

---

## Output Formats

The CLI handles three result formats from skills:

### 1. CommandResult Format (from @skill_command decorator)

```python
# @skill_command decorated functions return CommandResult
result.data = {
    "content": "markdown content",
    "metadata": {"url": "...", "title": "..."}
}
```

### 2. Dict Format (from isolation.py sidecar execution)

```python
# Sidecar/script execution returns
{
    "success": True,
    "content": "...",
    "metadata": {...}
}
```

### 3. String Format (direct string return)

```python
# Simple skill functions may return strings
"Git status output..."
```

---

## Output Channels (UNIX Philosophy)

| Channel    | Content                 | Use Case                |
| ---------- | ----------------------- | ----------------------- |
| **stdout** | Skill results (content) | Pipes, scripting        |
| **stderr** | Logs, metadata panels   | User display, debugging |

### TTY Mode (interactive terminal)

- Results printed to stderr via Rich panels
- Metadata panel + Content panel

### Pipe Mode (stdout redirect)

- Content only printed to stdout
- stderr hidden from pipe

### JSON Mode (`--json` flag)

- Full result object printed to stdout as JSON
- Used for programmatic access

---

## Debugging Common Issues

### Issue: No output from skill command

**Symptoms**: Command runs but returns nothing

**Debugging Steps**:

1. Check if result format is correct:

```python
from agent.cli.console import print_result

# Debug print_result
print_result(result, is_tty=True)  # TTY mode shows panels
print_result(result, is_tty=False)  # Pipe mode shows content
```

2. Verify result type:

```python
print(type(result))  # Should be dict, CommandResult, or str
print(result.data if hasattr(result, 'data') else result)
```

### Issue: Content not extracted from CommandResult

**Symptoms**: Metadata shows but content is empty

**Cause**: `print_result` needs to handle `result.data.content`

**Debug**:

```python
result.data = {"content": "...", "metadata": {...}}
# print_result should extract:
# content = result.data.get('content')
```

### Issue: Module import fails

**Symptoms**: `ModuleNotFoundError: No module named 'agent.skills.*'`

**Cause**: ModuleLoader not properly initialized

**Debug**:

```python
from agent.core.module_loader import ModuleLoader
from common.skills_path import SKILLS_DIR

loader = ModuleLoader(SKILLS_DIR())
loader._ensure_parent_packages()
loader._preload_decorators()
```

### Issue: Skill not found

**Symptoms**: "Skill not found: xxx"

**Debug**:

```python
from common.skills_path import SKILLS_DIR
skill_path = SKILLS_DIR(skill="git", filename="tools.py")
print(f"Skill path: {skill_path}")
print(f"Exists: {skill_path.exists()}")
```

---

## Key Functions

### `print_result(result, is_tty=False, json_output=False)`

Main output function handling all three result formats.

**Parameters**:

- `result`: CommandResult, dict, or str
- `is_tty`: Whether stdout is a terminal
- `json_output`: Force JSON output to stdout

### `cli_log_handler(message)`

Log callback for structlog integration.

**Message prefixes**:

- `[Swarm]` → 🚀 emoji
- `Error` → ❌ emoji
- Default → dim style

### `run_skills(commands, json_output=False, log_handler=None)`

Execute skill commands directly.

**Args**:

- `commands`: List like `['crawl4ai.crawl_webpage', '{"url": "..."}']`
- `json_output`: Force JSON mode
- `log_handler`: Optional logging callback

---

## Common Debug Commands

```bash
# List available skills
uv run omni skill run help

# Test specific skill
uv run omni skill run git.status
uv run omni skill run git.status --json

# Debug with verbose output
uv run omni skill run crawl4ai.crawl_webpage '{"url": "..."}' 2>&1 | cat -A

# Check module loading
python -c "
from agent.core.module_loader import ModuleLoader
from common.skills_path import SKILLS_DIR
loader = ModuleLoader(SKILLS_DIR())
loader._ensure_parent_packages()
print('Module paths set up')
"
```

---

## Test Categories

| Category            | Tests | Description                              |
| ------------------- | ----- | ---------------------------------------- |
| Module Imports      | 2     | Verify all modules import correctly      |
| Console Output      | 5     | Test print_result, log_handler, metadata |
| Command Integration | 4     | Test skill commands, help, entry point   |
| Runner              | 3     | Test run_skills function                 |
| Edge Cases          | 2     | Test None, empty strings, stderr config  |

**Total: 16 tests**

---

## Related Documentation

- [CLI Reference](../reference/cli.md) - User-facing CLI documentation
- [Skills Documentation](../skills.md) - Skill architecture
- [Trinity Architecture](../explanation/trinity-architecture.md) - Technical deep dive
