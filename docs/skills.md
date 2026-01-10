# Skills Documentation

> **Phase 35.2: Cascading Templates & Router-Controller** | **Phase 35.1: Simplified Test Framework** | **Phase 34: Cognitive System** | **Phase 33: SKILL.md Unified Format** | **Phase 32: Import Optimization** | **Phase 29: Unified Skill Manager**

## Overview

Omni-DevEnv Fusion uses a skill-based architecture where each skill is a self-contained module in the `assets/skills/` directory. Skills are accessed via the single `@omni` MCP tool.

All skill metadata is unified in `SKILL.md` using YAML Frontmatter, following the Anthropic Agent Skills standard.

## Phase 35.2: Cascading Templates & Router-Controller

### Template Structure (Cascading Pattern)

Skills support **cascading template loading** with "User Overrides > Skill Defaults" pattern:

```
assets/skills/git/                    # Skill Directory
├── templates/                         # [新增] Skill defaults (Fallback)
│   ├── commit_message.j2
│   ├── workflow_result.j2
│   └── error_message.j2
└── scripts/
    ├── __init__.py                   # Package marker (required!)
    └── rendering.py                   # Template rendering layer

assets/templates/                      # User overrides (Priority)
└── git/
    ├── commit_message.j2              # Overrides skill default
    └── workflow_result.j2
```

**Template Resolution Order:**

1. `assets/templates/{skill}/` - User customizations (highest priority)
2. `assets/skills/{skill}/templates/` - Skill defaults (fallback)

### Router-Controller Pattern (Isolated Sandbox)

Complex skills use **Router-Controller** architecture for namespace isolation:

```
assets/skills/git/
├── tools.py           # Router Layer (dispatches only)
└── scripts/           # Controller Layer (isolated implementations)
    ├── __init__.py    # Package marker (required!)
    ├── rendering.py   # Template rendering
    ├── workflow.py    # Git workflow logic
    └── status.py      # Git status implementation
```

**Why Isolated Sandbox?**

- Prevents namespace conflicts when scaling to 100+ skills
- `agent.skills.git.scripts.status` ≠ `agent.skills.docker.scripts.status`
- Each `scripts/` is a separate Python package

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

### Complete Structure (Phase 35.2)

```
assets/skills/<skill_name>/
├── SKILL.md           # Unified manifest + documentation (YAML Frontmatter)
├── tools.py           # @skill_command decorated functions (Router Layer)
├── guide.md           # Developer documentation
├── templates/         # Skill default templates (Phase 35.2 - Cascading)
│   ├── commit_message.j2
│   ├── workflow_result.j2
│   └── error_message.j2
├── scripts/           # Atomic implementations (Phase 35.2 - Isolated Sandbox)
│   ├── __init__.py    # Package marker (required!)
│   ├── rendering.py   # Template rendering layer
│   └── <command>.py   # Command implementations
├── references/        # Markdown documentation for RAG
├── assets/            # Static resources
├── data/              # Data files (JSON, CSV)
├── tests/             # Skill tests (Phase 35.1 - zero config!)
│   └── test_*.py      # Pure pytest, fixtures auto-injected
├── pyproject.toml     # Dependencies (subprocess mode only)
└── uv.lock            # Locked dependencies
```

### Directory Specifications

| Path          | Required | Description                                 |
| ------------- | -------- | ------------------------------------------- |
| `SKILL.md`    | ✅ Yes   | Skill metadata and LLM context              |
| `tools.py`    | ✅ Yes   | @skill_command decorated functions          |
| `templates/`  | ❌ No    | Jinja2 templates (enables cascading)        |
| `scripts/`    | ❌ No    | Atomic implementations (isolated namespace) |
| `references/` | ❌ No    | RAG documentation                           |
| `tests/`      | ❌ No    | Pytest tests (zero-config)                  |

### Cascading Template Structure

```
# Skill Defaults (Fallback)
assets/skills/git/templates/
├── commit_message.j2
├── workflow_result.j2
└── error_message.j2

# User Overrides (Priority - if exists, takes precedence)
assets/templates/git/
├── commit_message.j2    # Overrides skill default
└── workflow_result.j2
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

### 5. Add Tests (Phase 35.1)

Create a `tests/` directory with pure pytest test files - **no imports, no decorators needed**:

```bash
mkdir -p assets/skills/my_skill/tests
```

```python
# assets/skills/my_skill/tests/test_my_skill_commands.py

# No imports needed! Fixtures are auto-injected.
def test_my_command_exists(my_skill):
    """Verify my_command is available."""
    assert hasattr(my_skill, "my_command")
    assert callable(my_skill.my_command)


def test_my_command_executes(my_skill):
    """Verify my_command executes successfully."""
    result = my_skill.my_command("test_value")
    assert result.success


# Cross-skill tests work too!
def test_integration(my_skill, git):
    """Test interaction between skills."""
    my_skill.prepare()
    assert git.status().success
```

**How it works:**
- Pytest plugin (`agent.testing.plugin`) auto-loads via `pyproject.toml`
- All skills in `assets/skills/` are automatically discovered
- Fixtures like `git`, `my_skill`, `knowledge` are auto-injected
- No `conftest.py` needed in skill directories

### 6. (Optional) Subprocess Mode

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

# Run skill tests (Phase 35.1)
omni skill test <skill_name>     # Test specific skill
omni skill test --all            # Test all skills with tests/

# Validate skill structure (Phase 35.2)
omni skill check                 # Check all skills
omni skill check git             # Check specific skill
omni skill check git --examples  # Check with structure examples

# Manage skill templates (Phase 35.2)
omni skill templates git --list          # List templates
omni skill templates git --eject commit_message.j2  # Copy default to user dir
omni skill templates git --info commit_message.j2   # Show template content

# Create a new skill from template (Phase 35.2)
omni skill create my-skill --description "My new skill"
```

### Skill Check Command (Phase 35.2)

Validate skill structure against `settings.yaml` configuration:

```python
@omni("skill.check")                       # Check all skills
@omni("skill.check", {"skill_name": "git"})  # Check specific skill
@omni("skill.check", {"skill_name": "git", "show_examples": true})  # With examples
```

**Output includes:**

- Valid/Invalid status
- Score (0-100%)
- Current directory structure
- Missing required files
- Disallowed files
- Ghost files (non-standard)
- Optional structure examples (with `--examples`)

### Template Management Commands (Phase 35.2)

Manage cascading templates with "User Overrides > Skill Defaults" pattern:

```python
@omni("skill.templates", {"skill_name": "git", "action": "list"})
# Output:
# # 📄 Skill Templates: git
# 🟢 `commit_message.j2` (User Override)
# ⚪ `workflow_result.j2` (Skill Default)

@omni("skill.templates", {"skill_name": "git", "action": "eject", "template_name": "commit_message.j2"})
# Copies skill default to user override directory

@omni("skill.templates", {"skill_name": "git", "action": "info", "template_name": "commit_message.j2"})
# Shows template content and source location
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

## Phase 35.1: Zero-Configuration Test Framework

Zero-configuration testing for skill commands with auto-discovered fixtures.

### How It Works

The test framework is implemented as a **first-class Pytest plugin** that:

1. Auto-discovers all skills in `assets/skills/`
2. Registers each skill as a pytest fixture
3. Loads via `pyproject.toml` - no per-file configuration needed

```toml
# pyproject.toml
[tool.pytest.ini_options]
addopts = "-p agent.testing.plugin --tb=short"
```

### Directory Structure

```
assets/skills/
├── git/
│   ├── tools.py             # @skill_command decorated functions
│   └── tests/
│       ├── test_git_commands.py   # Pure pytest - no imports!
│       └── test_git_status.py     # Pure pytest - no imports!
└── knowledge/
    ├── tools.py
    └── tests/
        └── test_knowledge_commands.py  # Pure pytest - no imports!

packages/python/agent/src/agent/testing/
└── plugin.py                # Pytest plugin (auto-fixture registration)
```

### Writing Tests

```python
# assets/skills/git/tests/test_git_commands.py

# No imports needed! 'git' fixture is auto-injected.
def test_status_exists(git):
    """Git status command should exist."""
    assert hasattr(git, "status")
    assert callable(git.status)


# Cross-skill tests work too!
def test_integration(git, knowledge):
    """Test interaction between skills."""
    assert git.status().success
    assert knowledge.get_development_context().success
```

### Available Fixtures

All skill fixtures are auto-registered:

| Fixture        | Description                      |
| -------------- | -------------------------------- |
| `git`          | Git skill module                 |
| `knowledge`    | Knowledge skill module           |
| `filesystem`   | Filesystem skill module          |
| `<skill_name>` | Any skill in assets/skills/      |
| `skills_root`  | Skills directory (assets/skills) |
| `project_root` | Project root directory           |

### Running Skill Tests

```bash
# Test all skills
uv run omni skill test --all

# Test specific skill
uv run omni skill test git

# Run directly with pytest
uv run pytest assets/skills/ -v
```

### Non-Intrusive Design

The plugin is **opt-in** - fixtures are only injected when explicitly requested:

```python
# This uses skill fixture - plugin provides 'git'
def test_git_status(git):
    assert git.status().success

# This is completely independent - plugin is transparent!
def test_math_logic():
    assert 1 + 1 == 2
```

### Legacy Support

The `@test` decorator from `agent.skills.core.test_framework` is still available for backward compatibility:

```python
from agent.skills.core.test_framework import test

@test
def test_with_decorator(git):
    assert git.status().success
```

---

## Sidecar Execution Pattern

For skills with heavy dependencies (e.g., `crawl4ai`, `playwright`), use the **Sidecar Execution Pattern** to avoid polluting the main agent runtime.

### Core Concept

```
┌─────────────────────────────────────────────────────────────┐
│                    Omni Core (Main Agent)                   │
│                                                             │
│  tools.py (lightweight) ──────┐                             │
│  - imports only from common   │                             │
│  - no heavy dependencies      │                             │
│                              ↓                              │
│                      uv run --directory skill/              │
│                      python scripts/engine.py               │
│                              ↓                              │
│              ┌──────────────────────────────┐               │
│              │    Skill Isolated Env        │               │
│              │    (Independent .venv)       │               │
│              │                              │               │
│              │  scripts/engine.py           │               │
│              │  - crawl4ai                  │               │
│              │  - pydantic                  │               │
│              │  - fire                      │               │
│              └──────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

**1. Use `SwarmEngine`** - Unified execution via agent.core.swarm:

```python
from agent.core.swarm import get_swarm
from agent.skills.decorators import skill_command

@skill_command
def crawl_webpage(url: str, fit_markdown: bool = True) -> dict:
    """Crawl a webpage using isolated environment."""
    return get_swarm().execute_skill(
        skill_name="crawl4ai",
        command="engine.py",
        args={"url": url, "fit_markdown": fit_markdown},
        mode="sidecar_process",
        timeout=30,
    )
```

**2. Skill `pyproject.toml`** - Skill-specific dependencies:

```toml
[project]
name = "skill-crawl4ai"
dependencies = ["crawl4ai>=0.5.0", "fire>=0.5.0"]
```

**3. `scripts/engine.py`** - Actual implementation (runs in isolation):

```python
import asyncio
import json
from crawl4ai import AsyncWebCrawler

async def crawl(url: str):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
        print(json.dumps({"success": result.success, "markdown": result.markdown}))
```

### Example Skill: crawl4ai

The `crawl4ai` skill demonstrates this pattern:

```
assets/skills/crawl4ai/
├── pyproject.toml        # Skill dependencies (crawl4ai, fire, pydantic)
├── tools.py              # Lightweight interface (uses agent.core.swarm)
├── scripts/
│   └── engine.py         # Heavy implementation (imports crawl4ai)
├── SKILL.md              # Skill documentation
└── prompts.md            # Routing prompts
```

**Usage:**

```python
# Direct call - recommended for known skills
@omni("crawl4ai.crawl_webpage", {"url": "https://example.com"})

# Via skill.run - for dynamic/experimental skill calls
@omni("skill.run", {"skill": "crawl4ai", "command": "crawl_webpage", "url": "https://example.com"})
```

**What's the difference?**

| Call Style                    | When to Use                                                            |
| ----------------------------- | ---------------------------------------------------------------------- |
| `crawl4ai.crawl_webpage(...)` | Direct, known skill commands                                           |
| `skill.run(...)`              | Dynamic skill discovery or when you don't know the skill ahead of time |

### Benefits

1. **Zero Pollution**: Main agent doesn't install heavy dependencies
2. **Version Isolation**: Each skill can use different library versions
3. **Hot Swappable**: Add/remove skills without restarting
4. **Security**: Limited blast radius for compromised code

---

## Related Documentation

- [Trinity Architecture](./explanation/trinity-architecture.md) - Technical deep dive
- [Git Commit Workflow](../assets/skills/git/commit-workflow.md) - Git skill usage
- [mcp-core-architecture](./developer/mcp-core-architecture.md) - Shared library patterns
- [Testing Guide](./developer/testing.md) - Test system documentation
