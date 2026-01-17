# ODF-EP (Python Zenith) Engineering Protocol

> Omni-DevEnv Fusion Engineering Protocol
> Version: v1.1 | Last Updated: 2026-01-15

---

## Table of Contents

- [Overview](#overview)
- [SSOT: Single Source of Truth](#ssot-single-source-of-truth)
- [Code Style](#code-style)
- [Architecture Principles](#architecture-principles)
- [Skill Development](#skill-development)
- [Naming Conventions](#naming-conventions)
- [Error Handling](#error-handling)
- [Testing Standards](#testing-standards)
- [Documentation](#documentation)
- [Git Workflow](#git-workflow)
- [TL;DR Cheat Sheet](#tldr-cheat-sheet)

---

## Overview

### What is ODF-EP?

ODF-EP (Omni-DevEnv Fusion Engineering Protocol) is the comprehensive engineering standard for the Omni-DevEnv Fusion project. It defines:

- **How to write code**: Style, patterns, conventions
- **How to organize**: Project structure, module boundaries
- **How to configure**: SSOT principles, settings management
- **How to test**: Standards, patterns, coverage requirements
- **How to document**: Where to write what, and for whom

### Core Philosophy

1. **Explicit over Implicit**: Configuration drives behavior
2. **SSOT**: Single Source of Truth for all paths and settings
3. **Composition over Inheritance**: Prefer functional composition
4. **Fail Fast**: Validate early, fail loudly
5. **Document Decisions**: Architecture Decision Records (ADRs)

---

## SSOT: Single Source of Truth

### Core Principles

#### 1. Never Hardcode Paths

**Rule**: All path references must derive from `assets/settings.yaml` via SSOT utilities.

```python
# BAD
PROJECT_ROOT = "/Users/username/project"

# BAD
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# GOOD
from common.config.settings import get_setting
PROJECT_ROOT = get_setting("project.root", fallback=Path.cwd())
```

#### 2. Use SSOT Utilities for Path Resolution

**Skills Directory (SKILLS_DIR)**:

```python
from common.skills_path import SKILLS_DIR

# Get base skills directory
skills_dir = SKILLS_DIR()

# Get specific skill directory
SKILLS_DIR("git")

# Get subpath within skill
SKILLS_DIR("git", path="templates")
SKILLS_DIR("git", path="scripts")
```

**Runtime Data Directories (PRJ_SPEC - PRJ_DATA, PRJ_CACHE)**:

```python
from common.prj_dirs import PRJ_DATA, PRJ_CACHE, PRJ_CONFIG

# Runtime data (git-ignored)
session_dir = PRJ_DATA("knowledge", "sessions")
harvested_dir = PRJ_DATA("knowledge", "harvested")

# Cache directories
cache_file = PRJ_CACHE("user_custom.md")

# Config directories
config_file = PRJ_CONFIG("settings.json")
```

**Environment Variables (from direnv)**:
| Variable | Default | Purpose |
| ------------ | ---------- | ------------------------------ |
| `PRJ_ROOT` | - | Project root |
| `PRJ_DATA` | `.data` | Runtime data (git-ignored) |
| `PRJ_CACHE` | `.cache` | Cache files |
| `PRJ_CONFIG` | `.config` | Configuration files |
| `PRJ_RUNTIME`| `.run` | Runtime artifacts |
| `PRJ_PATH` | `.bin` | Executable binaries |

````

#### 3. Configuration Drives Behavior

```python
# BAD
TIMEOUT = 120

# GOOD
from common.config.settings import get_setting
timeout = get_setting("mcp.timeout", 120)
````

#### 4. Cascading Configuration Pattern

**User Override > Skill Default > System Fallback**

```python
from common.skills_path import SKILLS_DIR
from common.config.settings import get_setting

# User override (highest priority)
user_templates = get_setting("assets.templates_dir") / skill_name

# Skill default (fallback)
skill_templates = SKILLS_DIR(skill_name, path="templates")
```

### SSOT Utilities Reference

#### Skills Directory (SKILLS_DIR)

| Utility                                   | Purpose                  | Returns                               |
| ----------------------------------------- | ------------------------ | ------------------------------------- |
| `SKILLS_DIR()`                            | Base skills directory    | `Path("assets/skills")`               |
| `SKILLS_DIR("skill_name")`                | Specific skill directory | `Path("assets/skills/git")`           |
| `SKILLS_DIR("skill_name", path="subdir")` | Subpath within skill     | `Path("assets/skills/git/templates")` |

#### Runtime Data Directories (PRJ_SPEC - PRJ_DIRS)

| Utility               | Purpose             | Returns                            |
| --------------------- | ------------------- | ---------------------------------- |
| `PRJ_DATA`            | Base data directory | `Path(".data")`                    |
| `PRJ_DATA("subdir")`  | Data subdirectory   | `Path(".data/knowledge")`          |
| `PRJ_DATA("a", "b")`  | Nested path         | `Path(".data/knowledge/sessions")` |
| `PRJ_CACHE("file")`   | Cache file          | `Path(".cache/file.json")`         |
| `PRJ_CONFIG("file")`  | Config file         | `Path(".config/settings.json")`    |
| `PRJ_RUNTIME("file")` | Runtime file        | `Path(".run/process.json")`        |

#### Configuration & Project

| Utility                       | Purpose      | Returns                        |
| ----------------------------- | ------------ | ------------------------------ |
| `get_setting("key", default)` | Config value | Typed value from settings.yaml |
| `get_project_root()`          | Git toplevel | `Path` to repository root      |

### Anti-Patterns

| Anti-Pattern           | Example                           | Fix             |
| ---------------------- | --------------------------------- | --------------- |
| Hardcoded path         | `"/Users/..."`                    | `get_setting()` |
| `__file__` navigation  | `Path(__file__).parent.parent`    | `SKILLS_DIR()`  |
| Scattered config       | Same value in 3 files             | SSOT            |
| Environment detection  | `if os.path.exists("/nix/store")` | `get_setting()` |
| Hardcoded runtime data | `Path(".data/knowledge")`         | `PRJ_DATA()`    |
| Hardcoded cache path   | `Path(".cache/user_custom.md")`   | `PRJ_CACHE()`   |
| Hardcoded assets path  | `Path("assets/knowledge/...")`    | `PRJ_DATA()`    |

---

## Code Style

### Python Standards

1. **Type Hints Required**: All functions must have type annotations
2. **Async-First**: Use `async/await` for I/O operations
3. **No Mutable Defaults**: Use `None` and initialize in body
4. **Docstrings**: Google-style for all public functions

### Examples

```python
# Type hints required
def process_git_status(repo_path: Path, verbose: bool = False) -> str:
    """Process git status for a repository.

    Args:
        repo_path: Path to the git repository
        verbose: Whether to include untracked files

    Returns:
        Formatted status string
    """
    if not repo_path.exists():
        raise ValueError(f"Repository not found: {repo_path}")
    # ...

# Async-first
async def fetch_remote_data(url: str, timeout: int = 30) -> dict:
    """Fetch data from remote URL asynchronously."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=timeout) as response:
            return await response.json()

# No mutable defaults
def create_tool(name: str, config: dict | None = None) -> Tool:
    """Create a tool instance."""
    config = config or {}  # Initialize here
    return Tool(name=name, **config)
```

### Import Order

```python
# Standard library
import asyncio
from pathlib import Path
from typing import Any

# Third party
import aiohttp
from pydantic import BaseModel

# Local - absolute from common/
from common.gitops import get_project_root
from common.skills_path import SKILLS_DIR
from common.prj_dirs import PRJ_DATA, PRJ_CACHE

# Local - relative within skill
from .scripts.rendering import render_template
```

---

## Architecture Principles

### Trinity Architecture

```
┌─────────────────────────────────────────────────┐
│                 SKILL.md                        │
│         (State: Definition & Prompts)           │
├─────────────────────────────────────────────────┤
│                 tools.py                        │
│           (Code: MCP Tools)                     │
├─────────────────────────────────────────────────┤
│              scripts/*.py                       │
│         (Execution: Controllers)                │
└─────────────────────────────────────────────────┘
```

### Module Boundaries

| Layer                              | Purpose                | Examples                                                    |
| ---------------------------------- | ---------------------- | ----------------------------------------------------------- |
| `common/`                          | Shared utilities, SSOT | `gitops.py`, `skills_path.py`, `prj_dirs.py`, `settings.py` |
| `agent/skills/{skill}/`            | Skill implementation   | `git/`, `filesystem/`, `skill/`                             |
| `agent/core/`                      | Core agent logic       | `skill_manager.py`, `orchestrator.py`, `swarm.py`           |
| `packages/python/agent/src/agent/` | Agent packages         | `cli.py`, `tests/`                                          |

### Agent Runtime Swarm (ARS)

The **Swarm** is the execution layer (Muscle) of the Trinity Architecture. It manages **how** skills are executed.

#### Core Responsibilities

| Responsibility               | Description                                                   |
| ---------------------------- | ------------------------------------------------------------- |
| **Execution Mode Selection** | Decide `in_process`, `sidecar_process`, or `docker_container` |
| **Process Management**       | Spawn, monitor, and terminate skill processes                 |
| **Resource Isolation**       | Prevent dependency conflicts between skills                   |
| **Health Monitoring**        | Track MCP server and process status                           |

#### Execution Modes

```python
from agent.core.swarm import get_swarm

result = await get_swarm().execute_skill(
    skill_name="crawl4ai",
    command="engine.py",
    args={"url": "https://example.com"},
    mode="sidecar_process"  # Request isolated execution
)
```

| Mode               | Use Case                 | Example Skills                         |
| ------------------ | ------------------------ | -------------------------------------- |
| `in_process`       | Lightweight, fast skills | `git`, `filesystem`, `knowledge`       |
| `sidecar_process`  | Heavy dependencies       | `crawl4ai` (crawl4ai), `data` (pandas) |
| `docker_container` | Complete isolation       | Security-critical operations           |

#### Sidecar Pattern (Heavy Dependencies)

Skills with heavy dependencies (like `crawl4ai`, `playwright`) use the **Sidecar Pattern**:

```
┌─────────────────────────────────────────────────────────────┐
│                      Main Agent                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  tools.py (lightweight interface)                       ││
│  │  - No heavy imports                                     ││
│  │  - Calls Swarm.execute_skill()                          ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Swarm (Execution Layer)                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  run_skill_command() via uv isolation                    ││
│  │  - Uses skill's own pyproject.toml                      ││
│  │  - No dependency conflicts with main agent              ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

#### Integration Example

```python
# assets/skills/crawl4ai/tools.py
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
    )
```

### Dependency Rule

**Dependencies flow inward**: `common` → `agent/core` → `agent/skills/*`

Never: `common` importing from `skills` or `agent` importing from `skills/core`

---

## Skill Development

### Skill Structure (ODF-EP v7.0)

```
assets/skills/{skill_name}/
├── SKILL.md              # Required: Metadata + prompts
├── tools.py              # Required: @skill_command decorators
├── scripts/              # Optional: Atomic implementations
│   ├── __init__.py
│   ├── command1.py
│   └── command2.py
├── templates/            # Optional: Jinja2 templates
│   └── template.j2
├── references/           # Optional: RAG documentation
│   └── README.md
├── assets/               # Optional: Static resources
├── data/                 # Optional: Data files
├── tests/                # Optional: Pytest tests
└── README.md             # Optional: Developer docs (alternative location)
```

### SKILL.md Template

````markdown
---
name: { skill_name }
description: Brief description of the skill
category: workflow | git | file | system
version: 1.0.0
author: omni-dev
---

# {Skill Name}

## Overview

Brief description...

## Commands

### command_name

Description of what this command does.

**Arguments:**

- `arg1` (str): Description
- `arg2` (int, optional): Description

**Example:**

```python
@omni("skill.command_name", {"arg1": "value"})
```
````

## Integration Points

What other skills/tools does this skill integrate with?

````

### tools.py Pattern

```python
from agent.skills.decorators import skill_command


@skill_command(category="git")
def status(repo_path: str = ".", verbose: bool = False) -> str:
    """Show git working tree status."""
    from .scripts.status import git_status

    return git_status(repo_path=repo_path, verbose=verbose)


@skill_command(category="git")
def commit(message: str, amend: bool = False) -> str:
    """Create a git commit."""
    from .scripts.commit import make_commit

    return make_commit(message=message, amend=amend)
````

---

## Naming Conventions

| Element           | Convention       | Example                                   |
| ----------------- | ---------------- | ----------------------------------------- |
| Skill name        | kebab-case       | `git`, `filesystem`, `skill`              |
| Command name      | snake_case       | `git_status`, `list_files`                |
| Python module     | snake_case       | `skill_manager.py`, `rendering.py`        |
| Class name        | PascalCase       | `SkillManager`, `GitStatus`               |
| Variable/Function | snake_case       | `repo_path`, `get_setting()`              |
| Constant          | UPPER_SNAKE_CASE | `DEFAULT_TIMEOUT`, `MAX_RETRIES`          |
| Configuration key | dot notation     | `mcp.timeout`, `assets.skills_dir`        |
| Template file     | snake_case + .j2 | `commit_message.j2`, `workflow_result.j2` |

---

## Error Handling

### Principles

1. **Fail Fast**: Validate inputs early
2. **Fail Loudly**: Use exceptions, not silent returns
3. **Recover Gracefully**: Wrap external calls in try/except
4. **Context Matters**: Include relevant information in errors

### Patterns

```python
# Input validation
def git_clone(url: str, target_dir: str | None = None) -> str:
    if not url:
        raise ValueError("URL is required")
    if not url.startswith(("http://", "https://", "git@")):
        raise ValueError(f"Invalid git URL: {url}")
    # ...

# Wrap external calls
async def fetch_with_retry(url: str, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        try:
            return await fetch_url(url)
        except aiohttp.ClientError as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed after {max_retries} attempts: {e}")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    raise RuntimeError("Unexpected error in fetch_with_retry")

# Rich error context
def parse_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Project root: {get_project_root()}"
        )
    # ...
```

### Error Categories

| Category         | Exception Type       | Recovery             |
| ---------------- | -------------------- | -------------------- |
| Invalid input    | `ValueError`         | Caller fixes input   |
| Missing resource | `FileNotFoundError`  | Caller provides path |
| External failure | `RuntimeError`       | Retry or escalate    |
| Configuration    | `ConfigurationError` | Check settings.yaml  |
| Security         | `SecurityError`      | Block and log        |

---

## Testing Standards

### Directory Structure

```
agent/tests/
├── conftest.py              # Pytest config + backward aliases
├── factories/               # Pydantic Factories (polyfactory)
│   ├── __init__.py
│   ├── manifest_factory.py  # SkillManifestFactory
│   ├── context_factory.py   # AgentContextFactory
│   └── mcp_factory.py       # MCPToolFactory
├── fixtures/                # Pytest Fixtures (plugin-loaded)
│   ├── core.py              # project_root, skills_path
│   ├── registry.py          # isolated_registry
│   ├── mocks.py             # mock_mcp_server
│   └── skills_data.py       # skill_factory
├── unit/                    # Fast, isolated tests
├── integration/             # Full-stack tests
│   ├── skills/
│   ├── core/
│   └── ai/
└── utils/                   # Helpers, assertions
```

### Key Principles

1. **No Path Hacking** - Use `SKILLS_DIR()`, `PRJ_DATA()`, `get_project_root()`
2. **No For Loops** - Use `@pytest.mark.parametrize`
3. **No Manual Dicts** - Use `polyfactory` factories

### Pydantic Factories

```python
# factories/manifest_factory.py
from polyfactory.factories.pydantic_factory import ModelFactory
from agent.core.schema.skill import SkillManifest

class SkillManifestFactory(ModelFactory[SkillManifest]):
    __model__ = SkillManifest
    name = "test_skill"
    version = "0.1.0"

# Usage
manifest = SkillManifestFactory.build()
custom = SkillManifestFactory.build(name="my_skill", version="2.0.0")
batch = SkillManifestFactory.batch(size=5)
```

### Parametrized Tests

```python
from common.skills_path import get_all_skill_paths

_ALL_SKILLS = get_all_skill_paths(SKILLS_DIR())

@pytest.mark.parametrize("skill_dir", _ALL_SKILLS, ids=[p.name for p in _ALL_SKILLS])
def test_skill_has_tools_py(skill_dir: Path):
    assert (skill_dir / "tools.py").exists()
```

### Skill Tests (Zero-Config)

Skills use `agent/testing/plugin.py` for auto-fixtures:

```python
# assets/skills/git/tests/test_commands.py
def test_status_exists(git):  # 'git' fixture auto-injected
    assert hasattr(git, "status")
    assert callable(git.status)
```

No imports, no conftest.py needed.

### Coverage

| Component | Min Coverage |
| --------- | ------------ |
| Core      | 90%          |
| Common    | 95%          |
| Factories | 100%         |

---

## Documentation

### Documentation Role Matrix

| Location                            | Reader           | Purpose                | Frequency |
| ----------------------------------- | ---------------- | ---------------------- | --------- |
| `CLAUDE.md`                         | Claude (auto)    | Quick reference, rules | Low       |
| `docs/reference/odf-ep-protocol.md` | All LLMs         | Engineering standards  | High      |
| `docs/index.md`                     | Human devs       | Navigation portal      | Low       |
| `docs/tutorials/*.md`               | New devs         | Learning paths         | Medium    |
| `docs/reference/*.md`               | Developers       | API/config reference   | Medium    |
| `docs/explanation/*.md`             | Architects       | Design decisions       | Low       |
| `SKILL.md`                          | Claude (on load) | Skill rules            | High      |
| `README.md`                         | Human devs       | Implementation guide   | Medium    |

### Docstring Style

```python
def calculate_commit_score(
    additions: int,
    deletions: int,
    files_changed: int,
    scope_weight: dict | None = None,
) -> tuple[float, str]:
    """Calculate a score for commit quality based on change metrics.

    This function evaluates commit quality by analyzing the diff metrics
    and providing both a numeric score and a qualitative assessment.

    Args:
        additions: Number of lines added
        deletions: Number of lines deleted
        files_changed: Number of files modified
        scope_weight: Optional dict mapping scope names to weight multipliers

    Returns:
        Tuple of (score: float 0-100, assessment: str)

    Raises:
        ValueError: If any metric is negative

    Example:
        >>> score, assessment = calculate_commit_score(50, 20, 3)
        >>> print(f"Score: {score}, Assessment: {assessment}")
    """
    if additions < 0 or deletions < 0 or files_changed < 0:
        raise ValueError("Metrics cannot be negative")
    # ...
```

---

## Git Workflow

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type       | Description                 |
| ---------- | --------------------------- |
| `feat`     | New feature                 |
| `fix`      | Bug fix                     |
| `docs`     | Documentation only          |
| `style`    | Formatting (no code change) |
| `refactor` | Code restructuring          |
| `perf`     | Performance improvement     |
| `test`     | Adding tests                |
| `chore`    | Maintenance                 |

### Example

```
feat(git): Add commit message template rendering

Implement Jinja2-based commit message templates with cascading
override support (User Override > Skill Default).

- Add templates.py with render_template()
- Support for user templates in assets/templates/git/
- Default templates in assets/skills/git/templates/

Closes #123
```

### Branch Naming

| Branch Type | Pattern     | Example                     |
| ----------- | ----------- | --------------------------- |
| Feature     | `feature/*` | `feature/commit-templates`  |
| Bugfix      | `bugfix/*`  | `bugfix/git-status-timeout` |
| Hotfix      | `hotfix/*`  | `hotfix/security-patch`     |
| Release     | `release/*` | `release/v1.0.0`            |

---

## TL;DR Cheat Sheet

### SSOT Path Resolution

```python
# DO ✅
from common.skills_path import SKILLS_DIR
from common.config.settings import get_setting
from common.gitops import get_project_root
from common.prj_dirs import PRJ_DATA, PRJ_CACHE

skills = SKILLS_DIR("git")
timeout = get_setting("mcp.timeout", 120)
project_root = get_project_root()
session_dir = PRJ_DATA("knowledge", "sessions")
cache_file = PRJ_CACHE("user_custom.md")

# DON'T ❌
Path(__file__).parent.parent
"/Users/..." or "/home/..."
os.path.expanduser("~")
Path(".data/knowledge")          # Hardcoded runtime data
Path(".cache/user_custom.md")    # Hardcoded cache path
```

### Code Style

```python
# Type hints + async + docstrings
async def process_data(input_path: Path) -> dict:
    """Process data from file."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")
    # ...
```

### Skill Structure

```
assets/skills/{skill}/
├── SKILL.md              # Required
├── tools.py              # Required
├── scripts/              # Optional
├── templates/            # Optional
└── tests/                # Optional
```

### Import Order

```python
import asyncio
from pathlib import Path
from typing import Any

import aiohttp
from pydantic import BaseModel

from common.gitops import get_project_root
from common.skills_path import SKILLS_DIR

from .scripts.rendering import render_template
```

---

## Related Documents

- [Settings YAML](../../assets/settings.yaml) - The actual SSOT configuration
- [Documentation Standards](../reference/documentation-standards.md) - Documentation guidelines
- [MCP Best Practices](../reference/mcp-best-practices.md) - MCP server development
- [Trinity Architecture](../../docs/explanation/trinity-architecture.md) - Architecture overview

---

## Quick Commands

```bash
# Validate code style
just fmt

# Run linters
just lint

# Run tests
just test

# Full validation suite
just validate

# Check skill structure
@omni("skill.check", {"skill_name": "git"})
```
