# Skills Directory

> **Phase 33: ODF-EP v6.0 Core Refactoring** | **Phase 32: Import Optimization** | **Phase 29: Unified Skill Manager**

This directory contains **Skills** - composable, self-contained packages that provide specific capabilities to the Omni Agent.

## Quick Reference

| Topic             | Documentation                                  |
| ----------------- | ---------------------------------------------- |
| Creating a skill  | [Creating a New Skill](#creating-a-new-skill)  |
| Execution modes   | [Library vs Subprocess Mode](#execution-modes) |
| Architecture      | [Trinity Architecture](#trinity-architecture)  |
| Command reference | See individual skill `guide.md` files          |

## Trinity Architecture

Each skill operates within the **Trinity Architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│                     SkillManager                            │
├─────────────────────────────────────────────────────────────┤
│  Code          │  Context           │  State                │
│  tools.py      │  prompts.md        │  manifest.json        │
│  (hot-reload)  │  (Repomix XML)     │  (metadata)           │
└─────────────────────────────────────────────────────────────┘
```

| Component   | File            | Purpose                           |
| ----------- | --------------- | --------------------------------- |
| **Code**    | `tools.py`      | Hot-reloaded MCP tool definitions |
| **Context** | `prompts.md`    | LLM behavior guidelines           |
| **State**   | `manifest.json` | Skill metadata and configuration  |

## Skill Structure

```
assets/skills/{skill_name}/
├── tools.py           # @skill_command decorated functions
├── prompts.md         # LLM context and guidelines
├── guide.md           # Developer documentation
├── manifest.json      # Skill metadata
├── pyproject.toml     # Dependencies (subprocess mode)
├── uv.lock            # Locked dependencies
└── repomix.json       # Atomic context config (optional)
```

## Creating a New Skill

### 1. Copy the Template

```bash
cp -r assets/skills/_template assets/skills/my_new_skill
```

### 2. Update manifest.json

```json
{
  "name": "my_new_skill",
  "version": "1.0.0",
  "description": "Brief description of the skill",
  "execution_mode": "library",
  "category": "general",
  "keywords": ["tag1", "tag2"],
  "permissions": {
    "network": false,
    "filesystem": "read"
  }
}
```

### 3. Add Commands in tools.py

```python
from agent.skills.decorators import skill_command

@skill_command(
    name="my_command",
    category="read",
    description="Brief description of what this command does",
)
async def my_command(param: str) -> str:
    """Detailed docstring explaining the command behavior."""
    # Implementation
    return "result"
```

### 4. Add LLM Context in prompts.md

```markdown
# My New Skill Prompts

When using this skill, the LLM should:

- Consider using `my_new_skill.my_command` for [specific tasks]
- Remember to [relevant considerations]
```

### 5. Update guide.md

````markdown
# My New Skill Guide

## Overview

Brief description of what this skill does.

## Usage

### When to use

- Scenario 1
- Scenario 2

### Examples

```bash
@omni("my_new_skill.my_command", {"param": "value"})
```
````

## Commands

| Command      | Description            |
| ------------ | ---------------------- |
| `my_command` | What this command does |

```

## Execution Modes

### Library Mode (Default)

Commands run directly in the Agent's main process. Use for skills with minimal dependencies.

**Use when:**
- No external dependencies (or already in main environment)
- Fast execution is critical
- No version conflicts possible

### Subprocess Mode (Phase 28.1)

Commands run in an isolated subprocess with own `.venv`. Use for skills with heavy/conflicting dependencies.

**Structure:**
```

assets/skills/{skill_name}/
├── .venv/ # Isolated Python environment
├── pyproject.toml # Skill's own dependencies
├── implementation.py # Business logic (heavy imports)
└── tools.py # Lightweight shim (no heavy imports)

````

**Implementation pattern:**

```python
# tools.py - Runs in main process (no heavy imports)
import subprocess
import json
from pathlib import Path

SKILL_DIR = Path(__file__).parent

def _run_isolated(command: str, **kwargs) -> str:
    cmd = [
        "uv", "run", "-q",
        "python", str(SKILL_DIR / "implementation.py"),
        command, json.dumps(kwargs)
    ]
    result = subprocess.run(cmd, cwd=str(SKILL_DIR), capture_output=True, text=True)
    return result.stdout.strip()

@skill_command(name="heavy_op", description="Heavy operation")
def heavy_op(param: str) -> str:
    return _run_isolated("heavy_op", param=param)
````

```python
# implementation.py - Runs in subprocess (heavy imports ok)
import heavy_library

def heavy_op(param: str) -> str:
    return heavy_library.do_something(param)
```

**Use when:**

- Dependencies conflict with Agent's (e.g., pydantic v1 vs v2)
- Skill might crash and should be isolated
- Requires specific package versions

## Skill Command Categories

| Category    | Use Case                                      |
| ----------- | --------------------------------------------- |
| `read`      | Read/retrieve data (files, git status, etc.)  |
| `view`      | Visualize or display data (formatted reports) |
| `write`     | Create or modify data (write files, commit)   |
| `workflow`  | Multi-step operations (complex tasks)         |
| `evolution` | Refactoring/code evolution tasks              |
| `general`   | Miscellaneous commands                        |

## Command Decorator

The `@skill_command` decorator registers functions as MCP tools:

```python
@skill_command(
    name="command_name",       # Tool name (required)
    category="read",           # Category from SkillCategory enum
    description="Brief desc",  # Tool description for LLM
    inject_root=False,         # Inject project_root argument
    inject_settings=()         # Inject setting values
)
async def command_name(param: str) -> str:
    """Function docstring becomes detailed description."""
    return "result"
```

## ODF-EP v6.0 Compliance

All core skill modules follow the **"Python Zenith" Engineering Protocol**:

| Pillar                             | Implementation                        |
| ---------------------------------- | ------------------------------------- |
| **A: Pydantic Shield**             | `ConfigDict(frozen=True)` on all DTOs |
| **B: Protocol-Oriented Design**    | `typing.Protocol` for testability     |
| **C: Tenacity Pattern**            | `@retry` for resilient I/O            |
| **D: Context-Aware Observability** | `logger.bind()` for structured logs   |

## Performance

### Fast Import (Phase 32)

Skill modules use lazy initialization to avoid import-time overhead:

```python
# Lazy logger - only created on first use
_cached_logger = None

def _get_logger() -> Any:
    global _cached_logger
    if _cached_logger is None:
        import structlog
        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger
```

### O(1) Command Lookup

SkillManager maintains a command cache for instant lookups:

```python
# Both formats work:
manager.get_command("git", "status")      # O(1) lookup
manager.run("git", "status", {})           # Via cache
```

### Hot Reload

Skills are automatically reloaded when `tools.py` is modified. Mtime checks are throttled to once per 100ms.

## Example Skills

| Skill                                           | Features                          |
| ----------------------------------------------- | --------------------------------- |
| [Git](./git/guide.md)                           | Status, commit, branch management |
| [Filesystem](./filesystem/guide.md)             | Read, write, search files         |
| [Terminal](./terminal/guide.md)                 | Shell command execution           |
| [Testing Protocol](./testing_protocol/guide.md) | Test runner integration           |

## Related Documentation

- [Skills Documentation](../../docs/skills.md) - Comprehensive skills guide
- [Trinity Architecture](../../docs/explanation/trinity-architecture.md) - Technical deep dive
- [ODF-EP v6.0 Planning Prompt](../../.claude/plans/odf-ep-v6-planning-prompt.md) - Refactoring guide
- [mcp-core-architecture](../../docs/developer/mcp-core-architecture.md) - Shared library patterns
