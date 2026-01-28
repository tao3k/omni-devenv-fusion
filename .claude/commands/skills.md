---
description: List available Omni Skills and MCP tools
---

# Omni Skill Management

## Available Commands

| Command             | Description                                                   |
| ------------------- | ------------------------------------------------------------- |
| `skill.list_index`  | List all skills in the known skills index                     |
| `skill.list_tools`  | **List all registered MCP tools** with names and descriptions |
| `skill.discover`    | Search skills by query                                        |
| `skill.jit_install` | Install a skill from index                                    |
| `skill.reload`      | Reload a skill from disk                                      |

## Usage

### List All Registered MCP Tools

`@omni("skill.list_tools")`

Shows all tools currently registered in MCP:

- Tool name (e.g., `terminal.run_task`)
- Tool description
- Organized by skill

### Install a New Skill

`@omni("skill.jit_install", {"skill_id": "docker-ops"})`

### Search for Skills

`@omni("skill.discover", {"intent": "docker", "limit": 5})`

### Reload a Skill

`@omni("skill.reload", {"name": "git"})`

## Examples

| Task                 | Command                                                  |
| -------------------- | -------------------------------------------------------- |
| View all tools       | `@omni("skill.list_tools")`                              |
| Install Docker skill | `@omni("skill.jit_install", {"skill_id": "docker-ops"})` |
| Find Python skills   | `@omni("skill.discover", {"intent": "python"})`          |
| Reload git skill     | `@omni("skill.reload", {"name": "git"})`                 |
