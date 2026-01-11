---
description: Execute Omni skill commands (Phase 36: Trinity v2.0)
argument-hint: "skill.command [json-args]"
no-auto-format: true
---

# Omni Skill Command Execution (Trinity v2.0)

**Usage:** `/omni git.status` or `/omni filesystem.read_file {"path": "file.txt"}`

> **Phase 36**: The **Executor is now a Skill**. Use `terminal.run_task` instead of legacy `mcp_core.execution`.

## How to Handle This Slash Command

When user provides: `/omni {skill}.{command} [{args}]`

**Step 1:** Parse the first word as `{skill}.{command}` (e.g., `git.status`, `filesystem.read_file`)

**Step 2:** Parse remaining text as JSON arguments if present

**Step 3:** IMMEDIATELY invoke the @omni MCP tool with `skill.command` format

## Execution Protocol (Phase 36)

### Command Execution Pattern

```python
# GOOD - Use terminal.run_task
@omni("terminal.run_task", {"command": "ls", "args": ["-la"]})

# GOOD - Using configured alias
@omni("run_command", {"command": "ls", "args": ["-la"]})

# GOOD - Direct via Swarm Engine
from agent.core.swarm import get_swarm
result = await get_swarm().execute_skill("terminal", "run_task", {"command": "ls"})
```

### Security: Check Before Execute

```python
# Terminal skill includes built-in safety checks
@omni("terminal.run_task", {"command": "rm", "args": ["-rf", "/tmp/test"]})
# Returns: "Blocked: Dangerous pattern detected"
```

## Examples

| User Input                                                       | @omni Invocation                                                     |
| ---------------------------------------------------------------- | -------------------------------------------------------------------- |
| `/omni git.status`                                               | `@omni("git.status")`                                                |
| `/omni filesystem.read_file {"path": "README.md"}`               | `@omni("filesystem.read_file", {"path": "README.md"})`               |
| `/omni terminal.run_task {"command": "git", "args": ["status"]}` | `@omni("terminal.run_task", {"command": "git", "args": ["status"]})` |
| `/omni skill.list_tools`                                         | `@omni("skill.list_tools")` - List all 90+ tools                     |

## Operational Rules (Must Follow)

1. **Web Fetching**: Use `crawl4ai.crawl_webpage` instead of `curl`/`wget`. It parses JavaScript and returns clean Markdown.

2. **File Operations**: Use `filesystem.read_file` / `write_file` / `search_files` instead of `cat`, `echo`, or `grep`.

3. **Command Execution**: Use `terminal.run_task` for shell commands - it captures stdout/stderr properly and avoids terminal issues. Contains `SafeExecutor` logic (moved from legacy `mcp_core.execution`).

4. **Git Operations**: Prefer `git.status` / `git.stage_all` / `git.commit` tools for proper state tracking.

5. **Read Tool Descriptions**: Each tool has behavioral guidance embedded in its description. These instructions override default behaviors.

6. **List Available Tools**: Use `@omni("skill.list_tools")` to see all 90+ registered MCP tools with their descriptions.

## Native Alias Extension (Configuration over Convention)

Omni MCP supports **config-driven aliases** via `settings.yaml:skills.overrides`:

```yaml
skills:
  overrides:
    terminal.run_task:
      alias: "run_command"
    crawl4ai.crawl_webpage:
      alias: "web_fetch"
      append_doc: "\n\n## ⚡️ OPERATIONAL RULE\n- **PRIMARY TOOL**: Use this tool for ALL web content retrieval."
    filesystem.read_file:
      alias: "read_file"
```

**Available Aliases:**

| Alias         | Resolves To              |
| ------------- | ------------------------ |
| `web_fetch`   | `crawl4ai.crawl_webpage` |
| `read_file`   | `filesystem.read_file`   |
| `run_command` | `terminal.run_task`      |
| `git_status`  | `git.status`             |

The server resolves aliases automatically using `settings.yaml:skills.overrides` configuration.
