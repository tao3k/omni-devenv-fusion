# CLI Reference

> **Phase 35.2**: Modular CLI Architecture with UNIX Philosophy | **Phase 35.1**: Zero-Config Tests | **Phase 26**: Skill Network

The `omni` CLI provides unified access to all Omni-DevEnv Fusion capabilities with **atomic module structure** and **strict output separation**.

## Module Structure

```
agent/cli/
├── __init__.py          # Main exports (app, main, err_console)
├── app.py               # Typer application and configuration
├── console.py           # Console and output formatting
├── runner.py            # Skill execution logic
└── commands/
    ├── __init__.py
    └── skill.py         # Skill command group (run, list, etc.)
```

### Key Exports

```python
from agent.cli import app, main, err_console
from agent.cli.console import cli_log_handler, print_result, print_metadata_box
from agent.cli.runner import run_skills
```

## Quick Reference

| Command                  | Description            |
| ------------------------ | ---------------------- |
| `omni mcp`               | Start MCP server       |
| `omni skill run <cmd>`   | Execute skill command  |
| `omni skill list`        | List installed skills  |
| `omni skill info <name>` | Show skill information |
| `omni --help`            | Show help              |

---

## UNIX Philosophy: Output Separation

The CLI strictly follows UNIX philosophy for output streams:

- **stdout**: Only skill results (pure data for pipes)
- **stderr**: Logs, progress, and UI elements (visible to user, invisible to pipes)

### Output Modes

#### Terminal Mode (TTY)

When running directly in terminal, both channels are visible:

- **stderr**: Logs, metadata panel, content panel
- **stdout**: Content (for copy/paste)

```bash
$ omni skill run crawl4ai.crawl_webpage '{"url": "https://example.com"}'
  │ [CLI] Executing: crawl4ai.crawl_webpage {"url": "..."}
╭── Skill Metadata ──╮
│ {                  │
│   "success": true, │
│   "url": "..."     │
│ }                  │
╰────────────────────╯
╭── Result ──╮
│ # Example Domain  │
│ ...               │
╰───────────────────╯
```

#### Pipe Mode (stdout only)

When piping to other tools (e.g., `glow`, `jq`):

- **stderr**: Hidden from pipe
- **stdout**: Pure content (markdown)

```bash
$ omni skill run crawl4ai.crawl_webpage '{"url": "https://example.com"}' | glow
# Example Domain
...
```

#### JSON Mode (`--json` flag)

Force raw JSON output for programmatic use:

```bash
$ omni skill run crawl4ai.crawl_webpage '{"url": "..."}' --json
{
  "success": true,
  "data": {...},
  "error": null,
  "metadata": {...}
}
```

---

## Skill Commands

### `omni skill run`

Execute a skill command directly from CLI.

```bash
# Basic usage
omni skill run git.status

# With arguments (JSON format)
omni skill run 'git.commit' '{"message": "feat: add new feature"}'

# With JSON output
omni skill run crawl4ai.crawl_webpage '{"url": "https://example.com"}' --json
```

**Options:**
| Option | Description |
|--------|-------------|
| `--json`, `-j` | Output raw JSON instead of markdown content |

### `omni skill list`

List all installed skills with status.

```bash
omni skill list
```

### `omni skill info`

Show detailed information about a skill.

```bash
omni skill info git
```

---

## Global Options

```bash
omni --help              # Show help
omni --version           # Show version
```

---

## MCP Server

### `omni mcp`

Start the MCP server for integration with Claude Desktop or other MCP clients.

```bash
# Start in stdio mode (default)
omni mcp
```

---

## Exit Codes

| Code | Description                              |
| ---- | ---------------------------------------- |
| 0    | Success                                  |
| 1    | Error (invalid command, not found, etc.) |

---

## Environment Variables

| Variable    | Description                                      |
| ----------- | ------------------------------------------------ |
| `PRJ_ROOT`  | Project root directory (overrides git detection) |
| `OMNI_CONF` | Configuration directory (default: `assets`)      |

---

## Testing

Run CLI module tests:

```bash
cd packages/python/agent/src/agent
uv run python testing/test_cli.py
```

---

## Related Documentation

- [Skills Documentation](../skills.md) - Skill architecture and usage
- [Trinity Architecture](../explanation/trinity-architecture.md) - Technical deep dive
- [Testing Guide](../developer/testing.md) - Zero-config test framework
