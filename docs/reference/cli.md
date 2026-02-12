# CLI Reference

> Omni Loop CCA Runtime | Modular CLI Architecture

The `omni` CLI provides unified access to all Omni-Dev-Fusion Fusion capabilities.

## Quick Reference

| Command                        | Description                                            |
| ------------------------------ | ------------------------------------------------------ |
| `omni run`                     | Enter interactive REPL mode                            |
| `omni run exec "<task>"`       | Execute single task                                    |
| `omni run exec "<task>" -s 10` | Execute with custom step limit                         |
| `omni route test "<query>"`    | Run router diagnostics for a query                     |
| `omni route schema`            | Export router search settings schema                   |
| `omni route schema --stdout`   | Print router schema JSON to stdout                     |
| `omni sync`                    | Synchronize symbols, skills, router, knowledge, memory |
| `omni reindex all --clear`     | Rebuild vector indexes from scratch                    |
| `omni db stats`                | Inspect vector database status                         |
| `omni mcp`                     | Start MCP server                                       |
| `omni skill run <cmd>`         | Execute skill command                                  |
| `omni skill list`              | List installed skills                                  |
| `omni skill analyze`           | Analyze tool statistics (Arrow-native)                 |
| `omni skill stats`             | Quick skill database statistics                        |
| `omni skill context`           | Generate LLM system context                            |

---

## Global Options & Config Resolution

Global options apply to all subcommands:

- `--conf, -c`: set active configuration directory.
- `--verbose, -v`: enable debug logging.

Configuration is resolved as a merged view:

1. `<git-root>/assets/settings.yaml` (repository base defaults)
2. `$PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml` (active override layer)

By default, `PRJ_CONFIG_HOME=.config`. You can switch it per run:

```bash
# default conf dir (.config)
omni route schema

# custom conf dir
omni --conf ./.config.dev route schema
```

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

## Router Utilities

### `omni route test`

Run router diagnostics for a query and inspect ranked matches.

Usage:

```bash
omni route test "<query>"
```

`QUERY` is required. Running `omni route test` without it will fail with a missing argument error.

```bash
# Basic route diagnostics
omni route test "git commit"

# Show detailed scoring columns
omni route test "git commit" --debug

# Filter by score threshold and limit
omni route test "git commit" --threshold 0.4 --number 5

# Force embedding source
omni route test "git commit" --mcp
omni route test "git commit" --local
```

Defaults:

- `--number` uses `router.search.default_limit` (default `10`)
- `--threshold` uses `router.search.default_threshold` (default `0.2`)
- Rust metadata rerank stage is controlled by `router.search.rerank` (default `true`)

Detailed examples:

```bash
# 1) Find best tool matches for a Git intent
omni route test "commit staged changes"
```

```bash
# 2) Narrow results to higher-confidence candidates
omni route test "search python symbols" --threshold 0.45 --number 5
```

```bash
# 2b) Use a named profile from settings
omni route test "search python symbols" --confidence-profile precision
```

```bash
# 2c) Default behavior: no profile flag required (auto selection)
omni route test "git commit"
```

```bash
# 3) Debug score breakdown while tuning query wording
omni route test "refactor rust module" --debug --number 8
```

```bash
# 4) Force MCP embedding path (when MCP embedding service is running)
omni route test "index knowledge docs" --mcp
```

```bash
# 5) Force local embedding path
omni route test "git status" --local
```

```bash
# 6) Common error (missing required QUERY)
omni route test
# -> Error: Missing argument 'QUERY'
```

How to read output:

- `Tool`: candidate command in `skill.command` form.
- `Score`: fused relevance score.
- `Confidence`: mapped band (`high` / `medium` / `low`) from configured thresholds.
- Use `--debug` to inspect additional scoring details for troubleshooting.

Router confidence mapping is configurable in `settings.yaml` under
`router.search.profiles.<profile_name>` and selected with
`router.search.active_profile`.

These parameters are consumed by Rust-side payload calibration. Python CLI and router
read canonical `confidence` / `final_score` fields from Rust and do not re-map them locally.

Recommended tuning profiles:

```yaml
# Precision profile (higher precision, fewer false positives)
router:
  search:
    active_profile: "precision"
    profiles:
      precision:
        high_threshold: 0.82
        medium_threshold: 0.58
        high_base: 0.92
        high_scale: 0.04
        high_cap: 0.99
        medium_base: 0.62
        medium_scale: 0.24
        medium_cap: 0.88
        low_floor: 0.10
```

```yaml
# Recall profile (higher recall, more candidates)
router:
  search:
    active_profile: "recall"
    profiles:
      recall:
        high_threshold: 0.68
        medium_threshold: 0.42
        high_base: 0.88
        high_scale: 0.06
        high_cap: 0.99
        medium_base: 0.56
        medium_scale: 0.35
        medium_cap: 0.90
        low_floor: 0.08
```

Apply profile via override config:

```bash
# Use override config directory (loads <dir>/omni-dev-fusion/settings.yaml)
omni --conf ./.config.dev route test "git commit" --debug
```

Sniffer activation threshold is also configurable:

- `router.sniffer.score_threshold` controls dynamic sniffer activation (`0.0` to `1.0`).
- Higher values reduce false activations, lower values increase sensitivity.

```yaml
router:
  sniffer:
    score_threshold: 0.60
```

Options:

- `--debug, -d`: include detailed scoring output.
- `--number, -n`: max result count (default: `10`).
- `--threshold, -t`: minimum score threshold (default: `0.0`).
- `--mcp, -m`: use MCP embedding path.
- `--local, -l`: force local embedding path.

### `omni route stats`

Show current hybrid router stats (weights, strategy, boosting metadata).

```bash
omni route stats
```

### `omni route cache`

Inspect or clear router query cache.

```bash
# Show cache stats
omni route cache

# Clear cache entries
omni route cache --clear
```

### `omni route schema`

Export router search settings JSON schema for tooling/validation.

```bash
# Export to configured schema path (resolved from settings + --conf)
omni route schema

# Export to custom path
omni route schema --path ./schemas/router.search.schema.json

# Print schema JSON
omni route schema --stdout

# Emit command result as JSON metadata
omni route schema --json
```

### Notes

- Relative schema paths are resolved from the active config directory.
- Use `--conf <dir>` to switch the active config directory.

---

## Sync & Reindex

### `omni sync`

Synchronize runtime indexes and knowledge artifacts.

```bash
# Full sync (default behavior)
omni sync

# Targeted sync
omni sync skills
omni sync router
omni sync knowledge
omni sync memory
omni sync symbols
```

Common options:

- `--json, -j`: emit machine-readable output.
- `--verbose, -v`: show detailed logs (root sync command).
- `--clear, -c`: supported by `sync knowledge` and `sync symbols`.

Subcommands:

- `knowledge`
- `skills`
- `router`
- `memory`
- `symbols`

### `omni reindex`

Rebuild vector databases.

```bash
# Reindex all databases
omni reindex all

# Clear then rebuild everything
omni reindex all --clear

# Reindex only router index
omni reindex router

# Router-only rebuild (advanced use; skips atomic skills+router snapshot)
omni reindex router --only-router
```

Implementation note:

- `omni reindex all` now rebuilds `skills` and `router` from a single Rust-side scan (`index_skill_tools_dual`) to keep both indexes on the same snapshot and avoid count drift.

When index state is unknown/corrupted, prefer `omni reindex all --clear`.

Embedding/index compatibility:

- Omni persists an embedding signature at `<vector-db>/.embedding_signature.json`.
- On CLI startup, if `embedding.model` or `embedding.dimension` changed, Omni auto-rebuilds `skills` and `router` indexes.
- This behavior is controlled by `embedding.auto_reindex_on_change` in `settings.yaml` (default: `true`).
- Use `--conf <dir>` to apply this policy from an override config directory.

Common options:

- `--json, -j`: emit machine-readable output.
- `--clear, -c`: clear before reindexing (where supported).

Subcommands:

- `skills`
- `router`
- `knowledge`
- `status`
- `clear`
- `all`

---

## Database Utilities

### `omni db`

Inspect and query vector databases (`skills`, `router`, `knowledge`, `memory`).

```bash
# List available databases/tables
omni db list

# Show statistics for all databases
omni db stats

# Search in router database (query then database name)
omni db search "git commit" router --limit 5

# Query knowledge database
omni db query "langgraph checkpoint" --limit 5
```

Use `--json` for scripting-friendly output.

Useful subcommands:

- `list`
- `stats`
- `query`
- `search`
- `table-info`
- `versions`
- `fragments`
- `count`

---

## Command Output Snapshots

Representative output examples for quick orientation.

### `omni route test "git commit" --number 3 --threshold 0.2`

```text
Auto-detecting embedding source...
✓ Embedding HTTP server found on port 18501 (model preloaded)
Searching for: 'git commit'
     Routing Results for: git commit
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━┓
┃ Tool             ┃ Score ┃ Confidence ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━┩
│ git.commit_amend │ 0.642 │ medium     │
│ git.smart_commit │ 0.616 │ medium     │
│ git.commit       │ 0.615 │ medium     │
└──────────────────┴───────┴────────────┘
```

### `omni route schema --json`

```json
{
  "status": "success",
  "path": "/path/to/.config/schemas/router.search.schema.json",
  "resolved_from": "/path/to/.config/schemas/router.search.schema.json"
}
```

### `omni db stats`

```text
Database Statistics
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ Database       ┃ Records ┃ Size   ┃ Status ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ skills.lance   │ 1200    │ 18.2MB │ OK     │
│ router.lance   │ 1200    │ 19.1MB │ OK     │
│ knowledge.lance│ 53000   │ 412MB  │ OK     │
│ memory.lance   │ 340     │ 6.1MB  │ OK     │
└────────────────┴─────────┴────────┴────────┘
```

### `omni sync router`

```text
[SYNC] Router Index
status: success
details: Synced 1200 tools to router
```

### `omni reindex all --clear`

```text
Reindexing skills...
Syncing router...
Reindexing knowledge...
All databases reindexed successfully.
```

Notes:

- Exact scores/counts vary with indexed content and model state.
- Use `--json` where available for stable scripting output.

---

## MCP Server

### `omni mcp`

Start the Omni MCP server for integration with Claude Desktop, Claude Code CLI, or other MCP clients.

```bash
# Start with default transport (currently: sse)
omni mcp

# Start in SSE mode (for Claude Code CLI / debugging)
omni mcp --transport sse --port 3000

# Start in stdio mode (for Claude Desktop style stdio integration)
omni mcp --transport stdio

# Verbose logging
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

**stdio mode**:

- Uses stdin/stdout for JSON-RPC communication
- No external port exposure (secure)
- Best for Claude Desktop integration

**SSE mode**:

- HTTP-based Server-Sent Events transport
- Allows external MCP client connections
- Supports verbose logging for debugging
- Default port: 3000

Current default transport is `sse` (check with `omni mcp --help` in case of future changes).

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
| `OMNI_CONF` | Configuration directory (default: `.config`)     |

---

## Related Documentation

- [Skills Documentation](../skills.md) - Skill architecture and usage
- [System Layering](../explanation/system-layering.md) - Technical deep dive
- [Testing Guide](../developer/testing.md) - Zero-config test framework
