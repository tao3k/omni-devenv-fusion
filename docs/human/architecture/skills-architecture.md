# Skills Architecture

> **Status**: Active | **Version**: 2.0 | **Date**: 2026-01-16

## Overview

Skills are composable, self-contained packages that provide specific capabilities to the Omni Agent. Each skill follows the Omni Skill Standard (OSS) 2.0 and is accessed via the single `@omni("skill.command")` entry point.

**Key Principles:**

- **Everything is a Skill**: Execution is a logical role, not a module
- **Living Architecture**: Skills can be hot-reloaded without restart
- **Atomic Commands**: Each command is a single-purpose async function
- **Cascading Templates**: User overrides take precedence over skill defaults

## Directory Structure

```
assets/skills/{skill_name}/
├── SKILL.md              # [REQUIRED] Metadata + YAML Frontmatter + LLM context
├── README.md             # [REQUIRED] Human-readable documentation
├── scripts/              # [REQUIRED] Command implementations
│   ├── __init__.py       # Package marker (required for import)
│   └── commands.py       # @skill_script decorated functions
├── templates/            # Jinja2 templates (skill defaults)
│   ├── command_result.j2
│   └── error_message.j2
├── references/           # Additional documentation
└── tests/                # Test files
```

### File Responsibilities

| File                  | Role          | Purpose                                               |
| --------------------- | ------------- | ----------------------------------------------------- |
| `SKILL.md`            | Identity      | YAML frontmatter for routing, command list, LLM rules |
| `README.md`           | Documentation | Usage examples, command reference                     |
| `scripts/commands.py` | Execution     | @skill_script decorated async functions               |
| `templates/*.j2`      | Output        | Jinja2 templates for formatting                       |
| `tests/`              | Quality       | Unit and integration tests                            |

## SKILL.md Format

Every skill MUST have a `SKILL.md` with YAML frontmatter:

````yaml
---
name: "git"
version: "2.0.0"
description: "Git integration with LangGraph workflow support, Smart Commit V2, and Spec-Awareness"
routing_keywords:
  - "git"
  - "commit"
  - "push"
  - "branch"
  - "hotfix"
intents:
  - "hotfix"
  - "pr"
  - "commit"
  - "status"
authors: ["omni-dev-fusion"]
---

# Git Skill

> **Code is Mechanism, Prompt is Policy**

## Available Commands

| Command | Description |
| ------- | ----------- |
| `git.status` | Show working tree status |
| `git.commit` | Commit staged changes |
| `git.smart_commit` | Smart Commit workflow (human-in-loop) |

## Usage Guidelines

### Read Operations (Safe - Use Claude-native bash)

```bash
git status
git diff --cached
git log --oneline
````

### Write Operations (Use MCP Tools)

| Operation    | Tool                               |
| ------------ | ---------------------------------- |
| Stage all    | `git.stage_all()`                  |
| Commit       | `git.commit(message="...")`        |
| Smart Commit | `git.smart_commit(action="start")` |

````

## @skill_script Pattern

Commands are defined in `scripts/commands.py` with the `@skill_script` decorator:

```python
from agent.skills.decorators import skill_script

@skill_script(
    name="status",
    category="read",
    description="Show working tree status",
)
async def git_status() -> str:
    """Display the working tree status."""
    import subprocess
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True,
        text=True
    )
    return result.stdout or "Working tree clean"

@skill_script(
    name="commit",
    category="write",
    description="Commit staged changes",
)
async def git_commit(message: str) -> str:
    """Commit staged changes with the given message."""
    import subprocess
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True
    )
    return result.stdout + result.stderr
````

### Decorator Parameters

| Parameter     | Type | Description                                    |
| ------------- | ---- | ---------------------------------------------- |
| `name`        | str  | Command name (auto-prefixed by skill name)     |
| `category`    | str  | "read", "write", "view", "workflow", "general" |
| `description` | str  | Brief description for LLM context              |

### Command Name Note

Command name is just `my_command`, not `my_new_skill.my_command`. The MCP Server auto-prefixes with the skill name.

## Command Categories

| Category   | Use Case                                      |
| ---------- | --------------------------------------------- |
| `read`     | Read/retrieve data (files, git status, etc.)  |
| `view`     | Visualize or display data (formatted reports) |
| `write`    | Create or modify data (write files, commit)   |
| `workflow` | Multi-step operations (complex tasks)         |
| `general`  | Miscellaneous commands                        |

## Pure MCP Server

Omni uses **pure `mcp.server.Server`** instead of FastMCP for better control and performance:

```python
# mcp_server.py - Pure MCP Server (no FastMCP)
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("omni-agent")

@server.list_tools()
async def list_tools():
    """Dynamic tool discovery from SkillManager."""
    ...

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Execute via SkillManager."""
    ...
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
    ├── __init__.py                   # Package marker
    └── commands.py                    # @skill_script decorated commands

assets/templates/                      # User overrides (Priority)
└── git/
    ├── commit_message.j2              # Overrides skill default
    └── workflow_result.j2
```

**Template Resolution Order:**

1. `assets/templates/{skill}/` - User customizations (highest priority)
2. `assets/skills/{skill}/templates/` - Skill defaults (fallback)

## Hot Reload

Skills are automatically reloaded when `scripts/commands.py` is modified:

- **Mtime Check**: Modified time is checked on each invocation
- **Throttling**: Checks are throttled to once per 100ms
- **Atomic Swap**: Old module is replaced with new version seamlessly

```python
# When commands.py is modified:
# 1. Syntax validation (py_compile)
# 2. Inline unload (sys.modules cleanup)
# 3. Load fresh (from disk)
# 4. Update skill commands
```

## Skill Lifecycle

### 1. Discovery

Skills are discovered from `assets/skills/` directories:

```
assets/skills/
├── git/              # Git skill
├── filesystem/       # File operations
├── terminal/         # Shell execution
├── knowledge/        # Knowledge base
└── ...
```

### 2. Loading

Skills are loaded on-demand via SkillManager:

```python
from agent.core.skill_manager import get_skill_manager

manager = get_skill_manager()
await manager.load_skill("git")
```

### 3. Hot Reload

Skills support hot reload when `scripts/commands.py` is modified.

### 4. JIT Loading (Phase 67)

Skills can be loaded Just-In-Time on first use:

```python
# Strategy 1: Direct path lookup (fastest)
definition_path = SKILLS_DIR.definition_file(skill_name)
if definition_path.exists():
    load_skill(definition_path.parent)

# Strategy 2: Semantic search fallback
results = await search_skills(skill_name, limit=10)
```

### 5. Adaptive Unloading (LRU)

Memory-efficient garbage collection with pinned core skills:

```python
class SkillManager:
    _max_loaded_skills: int = 15
    _pinned_skills: set[str] = {
        "filesystem", "terminal", "writer", "git", "note_taker"
    }
    _lru_order: list[str] = []  # Usage order queue
```

## Creating a New Skill

### 1. Copy the Template

```bash
cp -r assets/skills/_template assets/skills/my_new_skill
```

### 2. Update SKILL.md Frontmatter

```yaml
---
name: "my_skill"
version: "1.0.0"
description: "My custom skill for..."
routing_keywords: ["my_skill", "custom", "example"]
intents: ["custom_operation"]
authors: ["your-name"]
---
```

### 3. Add Commands in scripts/commands.py

```python
from agent.skills.decorators import skill_script

@skill_script(
    name="my_command",
    category="read",
    description="Brief description of what this command does",
)
async def my_command(param: str) -> str:
    """Detailed docstring explaining the command behavior."""
    return "result"
```

### 4. Add Tests in tests/

```python
# tests/test_my_skill.py
import pytest

@pytest.mark.asyncio
async def test_my_command():
    result = await my_command("test_param")
    assert "result" in result
```

## Ghost Tools (Lazy Discovery)

Unloaded skills appear as "Ghost Tools" with `[GHOST]` prefix:

```
[GHOST] advanced_tools.search_project_code
Description: Searches for a regex pattern in code files...

[GHOST] code_tools.count_lines
Description: Counts lines of code in a file...
```

When you use a ghost tool, it **auto-loads on first use**.

## Compliance Checklist

A skill is OSS 2.0 compliant when:

- [ ] `SKILL.md` exists with valid YAML frontmatter
- [ ] `README.md` exists with usage documentation
- [ ] `scripts/` directory exists with commands
- [ ] `scripts/__init__.py` exists (package marker)
- [ ] No deprecated files (`manifest.json`, `tools.py`, `prompts.md`)

## Anti-Patterns

| Wrong                          | Correct                                      |
| ------------------------------ | -------------------------------------------- |
| Use MCP for `git status`       | Use Claude-native bash                       |
| Use bash for `git add -A`      | Use `git.stage_all()` for security           |
| Heavy imports in `commands.py` | Use `scripts/` submodules or sidecar pattern |

## Related Documentation

- [Trinity Architecture](../explanation/trinity-architecture.md)
- [Adaptive Loader](../explanation/adaptive-loader.md)
- [LangGraph Workflow Guide](../llm/langgraph-workflow-guide.md)
- [LLM Skill Discovery](../llm/skill-discovery.md)
