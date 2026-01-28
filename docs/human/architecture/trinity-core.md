# Trinity Core Architecture

> **Status**: Active (Core Document)
> **Version**: v1.0 | 2024-XX-XX
> **Related**: Trinity v2, Omni Loop

## Overview

The **Trinity Architecture** defines a unified skill management system that divides the agent's capabilities into three logical roles: **Orchestrator**, **Coder**, and **Executor**.

## The Trinity Concept

```
┌─────────────────────────────────────────────────────────────┐
│                    Trinity Architecture                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    🧠 Orchestrator                   │   │
│  │              (Planning & Strategy)                   │   │
│  │                                                     │   │
│  │  - Routes user requests to appropriate skills       │   │
│  │  - Maintains mission context                        │   │
│  │  - Coordinates multi-step workflows                 │   │
│  └───────────────────────┬─────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                      📝 Coder                       │   │
│  │                  (Reading & Writing)                 │   │
│  │                                                     │   │
│  │  - File system operations                           │   │
│  │  - Code search and analysis                         │   │
│  │  - Project structure understanding                  │   │
│  └───────────────────────┬─────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                      🛠️ Executor                    │   │
│  │                 (Execution & Operations)             │   │
│  │                                                     │   │
│  │  - Shell command execution                          │   │
│  │  - Git operations                                   │   │
│  │  - System tasks                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## v1.0.3: One Tool + Trinity Architecture

**Key Innovation**: Single entry point `@omni("skill.command")`

### Before v1.0.3

```python
# Multiple tool calls for different operations
await git_status()
await file_read()
await terminal_run()
```

### After v1.0.3

```python
# Single entry point with skill.command convention
@omni("git.status")
@omni("filesystem.read_files", {"path": "README.md"})
@omni("terminal.run", {"command": "ls"})
```

## Key Components

### 1. SkillContext (Facade)

```python
class SkillContext:
    """Unified interface for all skill operations."""

    async def run(self, skill_name: str, command: str, args: dict) -> Any:
        """Execute a skill command."""

    def list_skills(self) -> list[str]:
        """List all available skills."""

    def get_commands(self, skill_name: str) -> list[str]:
        """Get commands for a skill."""
```

### 2. Skill Registry

```python
# skills/git/
class GitSkill:
    name = "git"
    commands = {
        "status": git_status,
        "commit": git_commit,
        "push": git_push,
    }
```

## Architecture Evolution

| Version | Architecture         | Entry Point            |
| ------- | -------------------- | ---------------------- |
| v1.0    | Trinity v1.0         | @omni("skill.command") |
| v2.0    | Trinity v2.0 + Swarm | @omni + Hot Reload     |
| Current | Omni Loop + JIT      | @skill_command + JIT   |

## Benefits

| Benefit               | Description                                          |
| --------------------- | ---------------------------------------------------- |
| **Unified Interface** | Single @omni decorator for all operations            |
| **Role Clarity**      | Clear separation between Orchestrator/Coder/Executor |
| **Extensibility**     | Add new skills without changing core code            |
| **Testability**       | Mock skills at the role level                        |

## Related Documentation

- [Omni Loop](omni-loop.md) (CCA Runtime)
- [Skill Standard](skill-standard.md)
