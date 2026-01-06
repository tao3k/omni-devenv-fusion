# Testing Protocol Skill

Testing workflow tools following Modified-Code Protocol for intelligent test selection.

## Core Philosophy

**"Test smart, not hard"** - Run the minimum tests needed to validate changes, following the Modified-Code Protocol from agent/how-to/testing-workflows.md.

## Tools

### smart_test_runner

Execute tests following the Modified-Code Protocol:

1. Identify modified files
2. Categorize changes
3. Run MINIMUM necessary tests

Categories:

- docs_only → Skip tests
- mcp_server → Run MCP tests only
- tool_router → Run MCP tests only
- nix_config → Run full test suite
- code_changes → Run full test suite

### run_test_command

Run a test command with security:

- Only allows specific test commands
- Returns JSON result with output

Allowed commands:

- `just test`
- `just test-unit`
- `just test-int`
- `just test-mcp`
- `just test-mcp-only`
- `pytest`
- `devenv test`

### get_test_protocol

Get the testing protocol summary:

- Returns JSON summary of testing rules
- Lists available test strategies

## Usage

```python
# Auto-determine what to test
await smart_test_runner()

# Focus on specific file
await smart_test_runner(focus_file="src/agent/tests/test_phase13.py")

# Run a specific test command
await run_test_command(command="just test-mcp-only")

# Get protocol summary
await get_test_protocol()
```

## Test Levels

| Level       | Command            | Timeout |
| ----------- | ------------------ | ------- |
| unit        | just test-unit     | <30s    |
| integration | just test-int      | <2m     |
| mcp         | just test-mcp-only | <60s    |
| full        | just test          | varies  |

## Protocol Rules (from testing-workflows.md)

1. **Fast tests first** - Fail fast
2. **No feature code without test code**
3. **Modified docs only → Skip tests**
