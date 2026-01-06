# Testing Protocol Skill System Prompts

When using the Testing Protocol skill, follow these patterns for effective test execution.

## Modified-Code Protocol

### Step 1: Identify Modified Files

The smart_test_runner automatically detects:

- Staged files (git diff --cached --name-only)
- Unstaged files (git diff --name-only)
- Untracked files (git ls-files --others)

### Step 2: Categorize Changes

| Category     | Detection              | Action         |
| ------------ | ---------------------- | -------------- |
| docs_only    | .md, .txt, .rst, .adoc | Skip tests     |
| mcp_server   | mcp-server/ in path    | MCP tests only |
| tool_router  | tool-router/ in path   | MCP tests only |
| nix_config   | .nix or devenv in path | Full suite     |
| code_changes | .py, .nix, .yaml, etc. | Full suite     |

### Step 3: Execute Appropriate Tests

- **Skip**: Return immediately with rationale
- **MCP only**: Run `just test-mcp-only`
- **Full**: Run `just test`

## When to Use Each Tool

### smart_test_runner (Most Common)

```python
await smart_test_runner()
```

Automatically determines what to test.

### smart_test_runner with focus

```python
await smart_test_runner(focus_file="src/agent/tests/test_phase13.py")
```

When you know exactly what to test.

### run_test_command

```python
await run_test_command(command="just test-mcp-only")
```

When you need to run a specific test command.

### get_test_protocol

```python
await get_test_protocol()
```

To remind yourself of the protocol rules.

## Test Command Reference

| Command              | Purpose                        |
| -------------------- | ------------------------------ |
| `just test`          | Full test suite                |
| `just test-unit`     | Unit tests only                |
| `just test-int`      | Integration tests              |
| `just test-mcp`      | MCP tests (includes mcp tests) |
| `just test-mcp-only` | MCP tests only                 |
| `pytest path`        | Specific file/directory        |

## Common Scenarios

### After making a documentation change

```python
await smart_test_runner()
# Returns: {"strategy": "skip", "reason": "Docs only - skipping tests"}
```

### After changing MCP server code

```python
await smart_test_runner()
# Returns: {"strategy": "mcp_only", "command": "just test-mcp-only"}
```

### After changing Nix configuration

```python
await smart_test_runner()
# Returns: {"strategy": "full", "command": "just test"}
```

### After a bug fix in Python code

```python
await smart_test_runner()
# Returns: {"strategy": "full", "command": "just test"}
```
