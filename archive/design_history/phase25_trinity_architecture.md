# Phase 25: Trinity Architecture v1.0

> **Status**: Implemented (Legacy - Superseded by Phase 36)
> **Date**: 2024-XX-XX
> **Related**: Phase 29, Phase 36 (Trinity v2.0)

## Overview

Phase 25 established the **Trinity Architecture** - a unified skill management system that divides the agent's capabilities into three logical roles: **Orchestrator**, **Coder**, and **Executor**.

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

## Phase 25.3: One Tool + Trinity Architecture

**Key Innovation**: Single entry point `@omni("skill.command")`

### Before Phase 25.3

```python
# Multiple tool calls for different operations
await git_status()
await file_read()
await terminal_run()
```

### After Phase 25.3

```python
# Single entry point with skill.command convention
@omni("git.status")
@omni("filesystem.read_file", {"path": "README.md"})
@omni("terminal.run", {"command": "ls"})
```

## Key Components

### 1. SkillManager (Facade)

```python
class SkillManager:
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

| Phase | Architecture         | Entry Point              |
| ----- | -------------------- | ------------------------ |
| 24    | Monolithic           | Multiple tool decorators |
| 25    | Trinity v1.0         | @omni("skill.command")   |
| 29    | Trinity + Protocols  | @omni + ISkill Protocol  |
| 36    | Trinity v2.0 + Swarm | @omni + Hot Reload       |

## Benefits

| Benefit               | Description                                          |
| --------------------- | ---------------------------------------------------- |
| **Unified Interface** | Single @omni decorator for all operations            |
| **Role Clarity**      | Clear separation between Orchestrator/Coder/Executor |
| **Extensibility**     | Add new skills without changing core code            |
| **Testability**       | Mock skills at the role level                        |

## Related Specs

- `assets/specs/phase29_trinity_protocols.md` (superseded)
- `assets/specs/phase36_trinity_v2.md` (current)
