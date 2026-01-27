# CLI Reference

> Omni Loop CCA Runtime | Modular CLI Architecture

The `omni` CLI provides unified access to all Omni-Dev-Fusion Fusion capabilities.

## Quick Reference

| Command                        | Description                            |
| ------------------------------ | -------------------------------------- |
| `omni run`                     | Enter interactive REPL mode            |
| `omni run exec "<task>"`       | Execute single task                    |
| `omni run exec "<task>" -s 10` | Execute with custom step limit         |
| `omni mcp`                     | Start MCP server                       |
| `omni skill run <cmd>`         | Execute skill command                  |
| `omni skill list`              | List installed skills                  |
| `omni skill analyze`           | Analyze tool statistics (Arrow-native) |
| `omni skill stats`             | Quick skill database statistics        |
| `omni skill context`           | Generate LLM system context            |

---

## omni run - CCA Runtime Loop

> CCA (Context, Cognition, Action) Runtime for autonomous task execution.

The `omni run` command provides an interactive CLI and single-task execution mode powered by the **OmniAgent** - a CCA Loop agent that uses layered context assembly and autonomous reasoning.

### CCA Loop Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CCA Runtime Loop                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. OBSERVE  →  Layered Context Assembly (The Conductor)                   │
│     - System Persona + Scratchpad                                           │
│     - Environment Snapshot (omni-sniffer)                                   │
│     - Associative Memories (Librarian)                                      │
│     - Code Maps (omni-tags)                                                 │
│     - Raw Code Content (truncated)                                          │
│                                                                             │
│  2. ORIENT   →  Auto-retrieve Hindsight and Skills                          │
│                                                                             │
│  3. DECIDE   →  LLM Reasoning (MiniMax via InferenceClient)                │
│                                                                             │
│  4. ACT      →  Execute Rust tools via ToolRegistry                         │
│                                                                             │
│  5. REFLECT  →  Note-Taker distills wisdom from trajectory                 │
│                                                                             │
│  Loop until TASK_COMPLETE or max steps reached                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Commands

#### Interactive REPL Mode

```bash
# Enter interactive REPL
omni run

# Or explicitly
omni run repl
```

**Features:**

- Persistent session with conversation history
- Dynamic tool loading (Adaptive Loader)
- Real-time context analysis
- Type 'exit', 'quit', or 'q' to end

**Example Session:**

```bash
$ omni run
 CCA Runtime - Omni Loop
==================================================
Type 'exit' or 'quit' to end the session.

 You: Fix the login bug in auth.py
 🧠 Analyzing intent & loading tools...
 🛠️  Active Tools (5): filesystem.read_files, filesystem.write_file, testing.run_tests, ...

 Agent: ## CCA Loop Complete
 **Task:** Fix the login bug in auth.py
 **Steps:** 5
 **Reflection:** Successfully identified and fixed the null pointer exception...

 You: Now add unit tests for the fix
 ...
```

#### Single Task Execution

```bash
# Execute a single task and exit
omni run exec "Fix the login bug in auth.py"

# With custom step limit (default: 20)
omni run exec "Refactor context_orchestrator.py" -s 10
```

### Memory Integration

The OmniAgent integrates with **The Memory Mesh** for contextual awareness:

```bash
$ omni run exec "git commit fails with lock"
# Agent retrieves: "Previous session - Git lock error solved by removing .git/index.lock"
# Uses past experience to solve current problem
```

---

## Use Cases & Scenarios

### 1. Code Repair

```bash
# Debug and fix a bug
omni run exec "Fix the null pointer exception in user_auth.py line 42"

# The agent will:
# 1. Read the file to understand context
# 2. Identify the bug
# 3. Apply fix
# 4. Verify with tests
```

### 2. Refactoring

```bash
# Refactor a module
omni run exec "Refactor the context_orchestrator.py to use dataclasses"

# The agent will:
# 1. Read current implementation
# 2. Analyze dependencies
# 3. Apply AST-based refactoring (Structural Editing Skill)
# 4. Verify all tests pass
```

### 3. Feature Implementation

```bash
# Add a new feature
omni run exec "Add rate limiting to the API endpoint in server.py"

# The agent will:
# 1. Read current code
# 2. Design implementation
# 3. Add code with proper error handling
# 4. Add tests
```

### 4. Documentation

```bash
# Generate or update documentation
omni run exec "Update README.md with new installation instructions"

# The agent will:
# 1. Read existing README
# 2. Check current project structure
# 3. Generate updated documentation
```

### 5. Git Workflow

```bash
# Commit with automatic staging
omni run exec "Commit all changes with message 'feat: add new API endpoint'"

# The agent will:
# 1. Check git status
# 2. Stage appropriate files
# 3. Create commit
# 4. Push if configured
```

### 6. Testing

```bash
# Run and debug tests
omni run exec "Debug why test_user_auth.py is failing"

# The agent will:
# 1. Read the failing test
# 2. Run the test to see error
# 3. Analyze the issue
# 4. Fix the problem or the test
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

### `omni skill analyze`

Analyze skill/tool statistics using Arrow-native operations. Uses PyArrow for high-performance analytics on the skill database.

```bash
# Full analysis
omni skill analyze

# Filter by category
omni skill analyze -c git

# Show tools without documentation
omni skill analyze -m

# Export as JSON
omni skill analyze -j > stats.json
```

**Features:**

- Category distribution with percentages
- Documentation coverage analysis
- Top categories visualization
- JSON export for programmatic use

### `omni skill stats`

Quick skill database statistics.

```bash
omni skill stats
```

### `omni skill context`

Generate system context for LLM prompts using Arrow vectorized operations.

```bash
# Default: 50 tools
omni skill context

# Custom limit
omni skill context -n 100
```

**Output format:**

```text
@omni("tool.name") - Tool description
@omni("another.tool") - Another description
...
```

---

## MCP Server

### `omni mcp`

Start the Omni MCP server for integration with Claude Desktop, Claude Code CLI, or other MCP clients.

```bash
# Start in stdio mode (default, for Claude Desktop)
omni mcp --transport stdio

# Start in SSE mode (for Claude Code CLI / debugging)
omni mcp --transport sse --port 3000

# SSE mode with verbose logging
omni mcp --transport sse --port 8080 --verbose
```

### Options

| Option            | Description                                                         |
| ----------------- | ------------------------------------------------------------------- |
| `--transport, -t` | Transport mode: `stdio` (Claude Desktop) or `sse` (Claude Code CLI) |
| `--host, -h`      | Host to bind to (SSE only, default: `127.0.0.1`)                    |
| `--port, -p`      | Port to listen on (SSE only, default: `3000`)                       |
| `--verbose, -v`   | Enable verbose mode with hot-reload debugging                       |

### Transport Modes

**stdio mode** (default):

- Uses stdin/stdout for JSON-RPC communication
- No external port exposure (secure)
- Best for Claude Desktop integration

**SSE mode**:

- HTTP-based Server-Sent Events transport
- Allows external MCP client connections
- Supports verbose logging for debugging
- Default port: 3000

---

## Output Modes

### Terminal Mode (TTY)

When running directly in terminal, both channels are visible:

```bash
$ omni skill run git.status
  │ [CLI] Executing: git.status {}
╭── Result ──╮
│ ## Git Status
│ - Branch: main
│ - Modified: 5 files
╰───────────────────╯
```

### Pipe Mode (stdout only)

When piping to other tools (e.g., `glow`, `jq`):

```bash
$ omni skill run git.status | jq '.modified'
["Cargo.toml", "README.md"]
```

### JSON Mode (`--json` flag)

Force raw JSON output for programmatic use:

```bash
$ omni skill run git.status --json
{
  "success": true,
  "data": {...},
  "error": null,
  "metadata": {...}
}
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

## Related Documentation

- [Skills Documentation](../skills.md) - Skill architecture and usage
- [Trinity Architecture](../explanation/trinity-architecture.md) - Technical deep dive
- [Testing Guide](../developer/testing.md) - Zero-config test framework
