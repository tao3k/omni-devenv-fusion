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
| `skill.suggest`     | Get skill suggestions for a task                              |
| `skill.jit_install` | Install a skill from index                                    |
| `skill.check`       | Validate skill structure                                      |

## Usage

### List All Registered MCP Tools

```
/omni skill.list_tools
```

This shows all tools currently registered in MCP, including:

- Tool name (e.g., `terminal.run_task`)
- Tool description
- Organized by skill

### Install a New Skill

```
/omni skill.jit_install {"skill_id": "docker-ops"}
```

### Search for Skills

```
/omni skill.discover {"query": "docker"}
```

## Examples

| Task                  | Command                                                 |
| --------------------- | ------------------------------------------------------- |
| View all tools        | `/omni skill.list_tools`                                |
| Install Docker skill  | `/omni skill.jit_install {"skill_id": "docker-ops"}`    |
| Find Python skills    | `/omni skill.discover {"query": "python", "limit": 10}` |
| Check skill structure | `/omni skill.check {"skill_name": "git"}`               |
