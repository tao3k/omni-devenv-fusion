# Skills Directory

> **Phase 63+**: @skill_command Pattern - No tools.py Required

This directory contains **Skills** - composable, self-contained packages that provide specific capabilities to the Omni Agent.

## Quick Reference

| Topic             | Documentation                                 |
| ----------------- | --------------------------------------------- |
| Creating a skill  | [Creating a New Skill](#creating-a-new-skill) |
| Architecture      | [Skill Structure](#skill-structure)           |
| Command reference | See individual skill `SKILL.md` files         |

## Skill Structure

```
assets/skills/{skill_name}/
├── SKILL.md           # Metadata + LLM context (YAML frontmatter)
├── scripts/           # Commands (@skill_command decorated functions)
│   ├── __init__.py    # Dynamic module loader (importlib.util)
│   └── commands.py    # All skill commands
├── README.md          # Human-readable documentation
├── templates/         # Jinja2 templates (cascading pattern)
├── references/        # Additional documentation
└── tests/             # Test files
```

## Pure MCP Server

Omni uses **pure `mcp.server.Server`** instead of FastMCP for better control and performance:

```python
# mcp_server.py - Pure MCP Server (no FastMCP)
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("omni-agent")

@server.list_tools()
async def list_tools(): ...

@server.call_tool()
async def call_tool(name, arguments): ...
```

**Benefits:**

- Direct control over tool listing/execution
- Explicit error handling for TaskGroup
- Optional uvloop (SSE mode) + orjson for performance
- No FastMCP dependency overhead

## Cascading Templates

Skills support **cascading template loading** with "User Overrides > Skill Defaults" pattern:

```
assets/skills/git/                    # Skill Directory
├── templates/                         # Skill defaults (Fallback)
│   ├── commit_message.j2
│   ├── workflow_result.j2
│   └── error_message.j2
└── scripts/
    ├── __init__.py                   # Package marker (required!)
    └── commands.py                    # @skill_command decorated commands

assets/templates/                      # User overrides (Priority)
└── git/
    ├── commit_message.j2              # Overrides skill default
    └── workflow_result.j2
```

**Template Resolution Order:**

1. `assets/templates/{skill}/` - User customizations (highest priority)
2. `assets/skills/{skill}/templates/` - Skill defaults (fallback)

## Creating a New Skill

### 1. Copy the Template

```bash
cp -r assets/skills/_template assets/skills/my_new_skill
```

### 2. Add Commands in scripts/commands.py

```python
from agent.skills.decorators import skill_command

@skill_command(
    name="my_command",
    category="read",
    description="Brief description of what this command does",
)
async def my_command(param: str) -> str:
    """Detailed docstring explaining the command behavior."""
    return "result"
```

**Note:** Command name is just `my_command`, not `my_new_skill.my_command`. MCP Server auto-prefixes.

## Command Categories

| Category   | Use Case                                      |
| ---------- | --------------------------------------------- |
| `read`     | Read/retrieve data (files, git status, etc.)  |
| `view`     | Visualize or display data (formatted reports) |
| `write`    | Create or modify data (write files, commit)   |
| `workflow` | Multi-step operations (complex tasks)         |
| `general`  | Miscellaneous commands                        |

## @skill_command Decorator

The `@skill_command` decorator registers functions as MCP tools:

```python
@skill_command(
    name="command_name",       # Tool name (required)
    category="read",           # Category from SkillCategory enum
    description="Brief desc",  # Tool description for LLM
)
async def command_name(param: str) -> str:
    """Function docstring becomes detailed description."""
    return "result"
```

## Hot Reload

Skills are automatically reloaded when `scripts/commands.py` is modified. Mtime checks are throttled to once per 100ms.

## Skill Metadata (SKILL.md)

Each skill has a `SKILL.md` with YAML frontmatter for system integration:

```yaml
---
name: "git"
version: "2.0.0"
description: "Git integration with LangGraph workflow support"
routing_keywords: ["git", "commit", "push", "branch"]
intents: ["hotfix", "pr", "commit", "status"]
authors: ["omni-dev-fusion"]
---

# Git Skill

> **Code is Mechanism, Prompt is Policy**

## Available Commands

| Command         | Description                              |
| --------------- | ---------------------------------------- |
| `git.status`    | Show working tree status                 |
| `git.commit`    | Commit staged changes                    |
| `git.smart_commit` | Smart Commit workflow (human-in-loop) |
```

## Example Skills

| Skill                                           | Features                          |
| ----------------------------------------------- | --------------------------------- |
| [Git](./git/SKILL.md)                           | Status, commit, branch management |
| [Filesystem](./filesystem/SKILL.md)             | Read, write, search files         |
| [Terminal](./terminal/SKILL.md)                 | Shell command execution           |
| [Testing Protocol](./testing_protocol/SKILL.md) | Test runner integration           |

## Related Documentation

- [Skill Standard](../../docs/human/architecture/skill-standard.md) - Living Skill Architecture
- [Skill Lifecycle](../../docs/human/architecture/skill-lifecycle.md) - LangGraph workflow support
- [Trinity Architecture](../../docs/explanation/trinity-architecture.md) - Technical deep dive
