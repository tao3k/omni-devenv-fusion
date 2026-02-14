---
description: List available Omni Skills and MCP tools
---

# Omni Skill Management

## Available Commands

| Command / Resource                           | Description                                                   |
| -------------------------------------------- | ------------------------------------------------------------- |
| `skill.list_index`                           | List all skills in the known skills index                     |
| **Resource** `omni://skill/skill/list_tools` | **List all registered MCP tools** (read via `resources/read`) |
| `skill.discover`                             | Search skills by query                                        |
| `skill.jit_install`                          | Install a skill from index                                    |
| `skill.reload`                               | Reload a skill from disk                                      |

## Usage

### List All Registered MCP Tools

Read the **resource** `omni://skill/skill/list_tools` (MCP `list_resources` then `resources/read(uri)`).  
Not a callable tool; use resource read to get the tool list.

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

| Task                 | Command / Action                                         |
| -------------------- | -------------------------------------------------------- |
| View all tools       | Read resource `omni://skill/skill/list_tools`            |
| Install Docker skill | `@omni("skill.jit_install", {"skill_id": "docker-ops"})` |
| Find Python skills   | `@omni("skill.discover", {"intent": "python"})`          |
| Reload git skill     | `@omni("skill.reload", {"name": "git"})`                 |
