# Skills Documentation

> **Phase 33: SKILL.md Unified Format** | **Phase 32: Import Optimization** | **Phase 29: Unified Skill Manager**

## Overview

Omni-DevEnv Fusion uses a skill-based architecture where each skill is a self-contained module in the `assets/skills/` directory. Skills are accessed via the single `@omni` MCP tool.

All skill metadata is unified in `SKILL.md` using YAML Frontmatter, following the Anthropic Agent Skills standard.

## Trinity Architecture (Phase 29)

Skills are managed by the **Trinity Architecture**:

```
+-------------------------------------------------------------+
|                     SkillManager                            |
+-------------------------------------------------------------+
|  Code          |  Context           |  State                |
|  Hot-reload    |  RepomixCache      |  Protocol Registry    |
|  (ModuleLoader)|  (XML context)     |  (ISkill, ISkillCmd)  |
+-------------------------------------------------------------+
```

| Component   | Description                                         |
| ----------- | --------------------------------------------------- |
| **Code**    | Hot-reloaded via `ModuleLoader` and mtime detection |
| **Context** | XML-packed via `RepomixCache` for LLM understanding |
| **State**   | Protocol-based registry (`SkillManager`)            |

See [Trinity Architecture](./explanation/trinity-architecture.md) for details.

## SKILL.md Format (Phase 33)

All skill metadata is defined in `SKILL.md` using YAML Frontmatter:

```markdown
---
name: "skill_name"
version: "1.0.0"
description: "Brief description of the skill"
authors: ["author_name"]
execution_mode: "library"
routing_strategy: "keyword"
routing_keywords: ["keyword1", "keyword2"]
intents: ["intent1", "intent2"]
---

# Skill Documentation

Your skill guide and prompts go here.
```

### Frontmatter Schema

| Field              | Type         | Required | Description                           |
| ------------------ | ------------ | -------- | ------------------------------------- |
| `name`             | string       | Yes      | Skill identifier (directory name)     |
| `version`          | string       | Yes      | Semantic version (x.y.z)              |
| `description`      | string       | Yes      | Brief description of the skill        |
| `authors`          | list[string] | No       | List of author names                  |
| `execution_mode`   | string       | No       | `library` (default) or `subprocess`   |
| `routing_strategy` | string       | No       | `keyword`, `intent`, or `hybrid`      |
| `routing_keywords` | list[string] | No       | Keywords for skill routing            |
| `intents`          | list[string] | No       | Intent types for intent-based routing |

## Architecture

```
packages/python/agent/src/agent/core/
├── protocols.py           # ISkill, ISkillCommand, ExecutionMode protocols
├── skill_manager.py       # Trinity facade, O(1) command lookup, hot-reload
├── loader.py              # Unified skill loading pipeline
├── module_loader.py       # Clean hot-reload (no sys.modules pollution)
├── session.py             # Session persistence with tenacity
└── registry/
    ├── core.py            # SkillRegistry singleton
    ├── loader.py          # SkillLoader pipeline
    └── installer.py       # Remote skill installation
```

## Execution Modes

### Library Mode (Default)

Skills run in the main Agent process. Used for skills with minimal/no dependencies.

```yaml
---
name: "my_skill"
version: "1.0.0"
execution_mode: "library"
---
```

### Subprocess Mode (Phase 28.1)

Skills run in isolated subprocess with own virtual environment and dependencies. Used for heavy/conflicting dependencies.

```yaml
---
name: "my_skill"
version: "1.0.0"
execution_mode: "subprocess"
python_path: ".venv/bin/python"
entry_point: "implementation.py"
---
```

**Use Subprocess Mode when:**

- Skill has dependencies conflicting with Agent's (e.g., pydantic v1 vs v2)
- Skill might crash and should not affect the Agent
- Skill requires specific Python packages not in main environment

## Skill Structure

```
assets/skills/<skill_name>/
├── SKILL.md           # Unified manifest + documentation (YAML Frontmatter)
├── tools.py           # @skill_command decorated functions
├── prompts.md         # Skill rules (LLM context) - deprecated, use SKILL.md
├── guide.md           # Developer documentation
├── pyproject.toml     # Dependencies (subprocess mode only)
├── uv.lock            # Locked dependencies
└── implementation.py  # Heavy imports (subprocess mode only)
```

## Available Skills

| Skill                | Path                                  | Description                      |
| -------------------- | ------------------------------------- | -------------------------------- |
| Git                  | `assets/skills/git/`                  | Version control, commit workflow |
| Terminal             | `assets/skills/terminal/`             | Shell command execution          |
| Filesystem           | `assets/skills/filesystem/`           | File I/O operations              |
| Testing Protocol     | `assets/skills/testing_protocol/`     | Test runner                      |
| File Ops             | `assets/skills/file_ops/`             | Batch file operations            |
| Knowledge            | `assets/skills/knowledge/`            | Project context, RAG             |
| Writer               | `assets/skills/writer/`               | Writing quality                  |
| Memory               | `assets/skills/memory/`               | Vector memory                    |
| Documentation        | `assets/skills/documentation/`        | Doc management                   |
| Code Insight         | `assets/skills/code_insight/`         | Code analysis                    |
| Software Engineering | `assets/skills/software_engineering/` | Architecture                     |
| Advanced Search      | `assets/skills/advanced_search/`      | Semantic search                  |
| Python Engineering   | `assets/skills/python_engineering/`   | Python best practices            |

## Usage

Call skills via the `@omni` MCP tool:

```python
# In Claude or any MCP client
@omni("git.status")                           # Run git status
@omni("filesystem.read", {"path": "README.md"})  # Read file
@omni("git.help")                             # Get full skill context (Repomix XML)
@omni("skill.list")                           # List all skills
```

## Creating a New Skill

### 1. Copy Template

```bash
cp -r assets/skills/_template assets/skills/my_skill
```

### 2. Update SKILL.md

```yaml
---
name: "my_skill"
version: "1.0.0"
description: "Brief description of the skill"
authors: ["your_name"]
execution_mode: "library"
routing_strategy: "keyword"
routing_keywords: ["keyword1", "keyword2"]
---
# My Skill

Your skill documentation here.
```

### 3. Add Commands (`tools.py`)

```python
from agent.skills.decorators import skill_command

@skill_command(
    name="my_command",
    category="read",
    description="Brief description of the command",
)
async def my_command(param: str) -> str:
    """Detailed docstring explaining the command."""
    # Your implementation here
    return "result"
```

### 4. Add Documentation (`guide.md`)

````markdown
# My Skill Guide

## Usage

When to use this command:

- Use `my_skill.my_command` for [specific tasks]
- Remember to [relevant considerations]

## Examples

```bash
# Example usage
```
````

````

### 5. (Optional) Subprocess Mode

If the skill needs isolated dependencies:

```python
# tools.py - Lightweight shim
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

@skill_command(name="heavy_operation", description="Heavy operation")
def heavy_operation(param: str) -> str:
    return _run_isolated("heavy_op", param=param)
````

```python
# implementation.py - Heavy imports here
import heavy_library
# Business logic
```

## Skill Command Categories

| Category    | Purpose                        |
| ----------- | ------------------------------ |
| `read`      | Read/retrieve data             |
| `view`      | Visualize or display data      |
| `write`     | Create or modify data          |
| `workflow`  | Multi-step operations          |
| `evolution` | Refactoring or evolution tasks |
| `general`   | Miscellaneous commands         |

## Protocol-Based Design (Phase 29/33)

All skill components implement protocols for testability:

```python
from agent.core.protocols import ISkill, ISkillCommand, ExecutionMode

# Skill implementations conform to these protocols
class SkillCommand:
    name: str
    func: Callable[..., Any]
    description: str = ""
    category: SkillCategory = SkillCategory.GENERAL

class Skill:
    name: str
    manifest: dict
    commands: dict[str, SkillCommand]
    execution_mode: ExecutionMode = ExecutionMode.LIBRARY
```

## Performance Optimizations

### O(1) Command Lookup

SkillManager maintains a command cache for instant lookups:

```python
# "skill.command" -> SkillCommand (O(1))
command = manager.get_command("git", "status")
```

### Throttled Hot-Reload

Mtime checks are throttled to once per 100ms to avoid excessive filesystem I/O.

### Lazy Logger Initialization

Loggers are created on first use, not at import time (~100ms saved per module).

## Path Utilities (Phase 32)

Use `common.skills_path` for simplified skill path handling:

```python
from common.skills_path import SKILLS_DIR, load_skill_module
from common.gitops import get_project_root

# Get base skills directory from settings.yaml
base = SKILLS_DIR()  # -> Path("assets/skills")

# Get skill directory
git_dir = SKILLS_DIR(skill="git")  # -> Path("assets/skills/git")

# Get skill file with keyword args
git_tools = SKILLS_DIR(skill="git", filename="tools.py")  # -> Path("assets/skills/git/tools.py")

# Get nested path
known_skills = SKILLS_DIR(skill="skill", path="data/known_skills.json")

# Load skill module directly
git_tools = load_skill_module("git")
```

**Settings Configuration** (`settings.yaml`):

```yaml
assets:
  skills_dir: "assets/skills" # Read by SKILLS_DIR
```

**Benefits:**

- Single source of truth for skills path
- GitOps-aware project root detection
- Replaces verbose `Path(__file__).resolve().parent.parent.parent` patterns

## CLI Commands

```bash
# List installed skills
omni skill list

# Discover available skills from index
omni skill discover [query]

# Show skill information
omni skill info <name>

# Install a skill from URL
omni skill install <url>

# Update an installed skill
omni skill update <name>

# Run a skill command
omni skill run <command>
```

## Phase 34: Cognitive System Enhancements

### CommandResult - Structured Output

The `@skill_command` decorator now returns a `CommandResult` for structured output:

```python
from agent.skills.decorators import skill_command, CommandResult

@skill_command(name="my_command", category="read")
def my_command(value: str) -> str:
    return f"Processed: {value}"

# Returns CommandResult(success=True, data="Processed: hello", ...)
result = my_command("hello")
```

**CommandResult fields:**
| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether command succeeded |
| `data` | Any | The actual result data |
| `error` | str \| None | Error message if failed |
| `metadata` | dict | Execution metadata (duration_ms, etc.) |
| `is_retryable` | bool | Whether error is transient |
| `duration_ms` | float | Execution time in milliseconds |

### UnifiedManifestAdapter - Smart Defaults

The `UnifiedManifestAdapter` automatically injects Omni-specific defaults:

```python
from agent.core.registry.adapter import get_unified_adapter

adapter = get_unified_adapter()

# Automatically injects:
# - routing_keywords from skill name patterns
# - execution_mode: "library"
# - routing_strategy: "keyword"
```

### StateCheckpointer - Cross-Session Memory

```python
from agent.core.state import get_checkpointer, GraphState

checkpointer = get_checkpointer()

# Save state
state = GraphState(
    messages=[{"role": "user", "content": "Fix bug"}],
    current_plan="Analyze error logs",
)
checkpointer.put("session_123", state)

# Restore state on restart
saved = checkpointer.get("session_123")
if saved:
    state = saved  # Resume conversation
```

## Related Documentation

- [Trinity Architecture](./explanation/trinity-architecture.md) - Technical deep dive
- [Git Commit Workflow](../assets/skills/git/commit-workflow.md) - Git skill usage
- [mcp-core-architecture](./developer/mcp-core-architecture.md) - Shared library patterns
- [Testing Guide](./developer/testing.md) - Test system documentation
