---
description: "[MASTER] High-authority tool execution via omni MCP proxy"
---

## `/omni` Slash Command

Direct text routing to omni master tool (Claude Desktop / Claude Code CLI):

```
/omni git status
/omni search for "def test" in python files
/omni start smart commit
```

## Universal Format

`@omni("skill.command", {"param1": "value1", "param2": 2})`

## `omni` Tool Parameters

| Parameter | Type   | Description                          |
| --------- | ------ | ------------------------------------ |
| `command` | `str`  | Exact tool name (e.g., `git.status`) |
| `intent`  | `str`  | Natural language task description    |
| `args`    | `dict` | Arguments for the target tool        |

## Intent-Based Routing

Let the router auto-discover the right tool:

| Intent                                            | Result                             |
| ------------------------------------------------- | ---------------------------------- |
| `@omni("omni", {"intent": "check git status"})`   | Routes to `git.status`             |
| `@omni("omni", {"intent": "run pytest"})`         | Routes to `testing.run_pytest`     |
| `@omni("omni", {"intent": "find TODO comments"})` | Routes to `code_tools.search_code` |

## Claude Code CLI vs Claude Desktop

| Platform        | Syntax                                              |
| --------------- | --------------------------------------------------- |
| Claude Desktop  | `@omni("git.smart_commit", {"action": "start"})`    |
| Claude Code CLI | `mcp__omniAgent__git_smart_commit` (full tool name) |

## Common Examples

| Task         | Claude Desktop                                             | Claude Code CLI                                      |
| ------------ | ---------------------------------------------------------- | ---------------------------------------------------- |
| Git status   | `@omni("git.status")`                                      | `mcp__omniAgent__git_status`                         |
| Run command  | `@omni("terminal.run", {"command": "ls -la"})`             | `mcp__omniAgent__terminal_run_task`                  |
| Read files   | `@omni("filesystem.read_files", {"paths": ["file.py"]})`   | -                                                    |
| Search code  | `@omni("code_tools.search_code", {"pattern": "def test"})` | `mcp__omniAgent__code_tools_search_code`             |
| Smart commit | `@omni("git.smart_commit", {"action": "start"})`           | `mcp__omniAgent__git_smart_commit`                   |
| Test project | `@omni("testing_protocol.smart_test_runner")`              | `mcp__omniAgent__testing_protocol_smart_test_runner` |

## Pro Tips

- Use `@omni("skill.discover", {"intent": "what you want to do"})` to find the right tool
- Check `@omni("skill.list_tools")` or run `mcp__omniAgent__skill_list_tools` for all available tools

## MCP Tool Name Format

Claude Code CLI requires full MCP tool names:

```
mcp__<server>__<tool_name>
```

Example: `mcp__omniAgent__git_smart_commit`
