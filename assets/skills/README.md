# Skills Directory

> **Phase 28: Safe Ingestion / Immune System** (2026-01-06)
>
> Security layer for downloading and executing third-party skills from Git repositories.
>
> - Code pattern scanning (eval, exec, os.system, subprocess shell=True)
> - Manifest permission validation
> - Decision engine: SAFE / WARN / SANDBOX / BLOCK

> **Phase 27: JIT Skill Acquisition** (2025-12)
>
> Just-in-time skill installation from known skills index.
>
> - `omni("skill.jit_install", {"skill_id": "..."})` - Auto-download on demand
> - `omni("skill.discover", {"query": "..."})` - Search skills index
> - `omni("skill.suggest", {"task": "..."})` - AI-powered skill recommendations

> **Phase 25: One Tool Architecture**
>
> Single entry point: `@omni("skill.command")`
> Brain (prompts.md) -> Muscle (tools.py) -> Guardrails (lefthook)

> **Phase 24: The MiniMax Shift**
>
> Direct tool registration for native CLI experience.
> No `invoke_skill` middleware - tools are registered directly.

This directory contains **Skills** - composable, self-contained packages that provide specific capabilities.

## Architecture Overview

```
agent/
├── skills/              # Skill-centric knowledge (THIS DIRECTORY)
│   ├── {skill_name}/
│   │   ├── manifest.json    # Skill metadata
│   │   ├── guide.md         # Procedural knowledge
│   │   ├── tools.py         # MCP tool definitions (Phase 24: Direct registration)
│   │   └── prompts.md       # Skill-specific prompts
│   └── README.md            # This file
│
├── how-to/              # Cross-skill workflow guides (RETAINED)
│   ├── documentation-workflow.md
│   ├── testing-workflows.md
│   ├── release-process.md
│   └── rag-usage.md
│
└── instructions/        # LLM behavior standards (RETAINED)
    ├── project-conventions.md
    ├── problem-solving.md
    └── documentation-standards.md
```

## Design Principles

### Skills (in `skills/`)

**Purpose**: Provide self-contained, skill-specific knowledge and tools.

**Contents**:

- `manifest.json` - Skill metadata (name, version, tools, dependencies)
- `guide.md` - How-to procedures specific to this skill
- `tools.py` - MCP tool definitions for this skill
- `prompts.md` - Skill-specific system prompts

**When to use**:

- User needs task-specific guidance (e.g., "How do I commit?")
- LLM needs skill-specific context and tools
- Looking for validation rules within a domain

### How-To Guides (in `how-to/`)

**Purpose**: Document cross-skill workflows that involve multiple skills.

**When to use**:

- Workflow spans multiple skills (e.g., "Write docs" → involves writer + filesystem + git)
- High-level process guidance
- Integration patterns between skills

**Retained files**:

- `documentation-workflow.md` - Writer + FileSystem + Git integration
- `testing-workflows.md` - Pytest + Python Engineering + Git integration
- `release-process.md` - Multi-skill release workflow
- `rag-usage.md` - Librarian + Knowledge integration

### Instructions (in `instructions/`)

**Purpose**: Define LLM behavior standards and conventions.

**When to use**:

- Project-wide conventions
- Problem-solving patterns
- Documentation standards

## Migration Guide

### Old Structure

```
agent/how-to/git-workflow.md    # Git knowledge (DUPLICATED)
agent/skills/git_operations/guide.md  # Git knowledge (DUPLICATED)
```

### New Structure

```
agent/skills/git_operations/guide.md  # SINGLE source of truth for Git
agent/how-to/documentation-workflow.md # Cross-skill workflow
```

**Rule of thumb**: If knowledge is specific to one skill, put it in the skill. If it spans multiple skills, keep it in `how-to/`.

## Creating a New Skill

1. Create directory: `agent/skills/{skill_name}/`
2. Add `manifest.json` with skill metadata
3. Add `guide.md` with procedural knowledge
4. Add `tools.py` with MCP tool definitions (optional)
5. Add `prompts.md` with skill-specific prompts (optional)
6. Skill is automatically discovered by SkillRegistry

## Example Skill Structure

```
agent/skills/my_new_skill/
├── manifest.json
├── guide.md
├── tools.py
└── prompts.md
```

## Skill Registry

The `SkillRegistry` class (in `src/agent/capabilities/skill_registry.py`) provides:

- `list_skills()` - Discover all available skills
- `get_skill_manifest(name)` - Get skill metadata
- `load_skill(name)` - Load skill context (guide, tools, prompts)
- `find_skills_for_task(task_description)` - Recommend skills for a task

## Phase 24: The MiniMax Shift

### Key Changes

| Aspect          | Before (Phase 13)             | After (Phase 24)              |
| --------------- | ----------------------------- | ----------------------------- |
| Tool Names      | Descriptive text              | `snake_case` function names   |
| Registration    | Via `invoke_skill` middleware | Direct: `tools.register(mcp)` |
| Return Type     | `dict`                        | `str` (FastMCP auto-wraps)    |
| Operation Model | Atomic                        | Batch operations supported    |

### Direct Tool Registration Pattern

```python
# tools.py
from mcp.server.fastmcp import FastMCP

def git_status() -> str:
    """Get the current status of the git repository."""
    # Implementation
    return status_report

def git_status_report() -> str:
    """[VIEW] Returns a formatted git status report with icons."""
    # Implementation
    return formatted_report

def register(mcp: FastMCP) -> None:
    """Register all git tools with the MCP server."""
    mcp.add_tool(git_status, description="Get git status.")
    mcp.add_tool(git_status_report, description="Formatted status report.")
```

### MCP Protocol Compliance

All tools must return `str`. FastMCP auto-wraps into proper MCP format:

```python
def git_read_backlog() -> str:
    """Read the Git Skill's own backlog."""
    content = read_file("Backlog.md")
    # FastMCP auto-converts to:
    # CallToolResult(content=[TextContent(type="text", text=content)])
    return content
```

**Result in Claude CLI:**

```json
[
  {
    "type": "text",
    "text": "# Git Skill Backlog\n..."
  }
]
```

### View-Enhanced Tools (Director Pattern)

For complex UI rendering, use the View pattern:

```python
# views.py
def render_status_report(branch: str, staged: list, unstaged: list) -> str:
    """Generate Claude-friendly Markdown report."""
    # Return formatted string with icons and "Run" hints

# tools.py
from .views import render_status_report

def git_status_report() -> str:
    """[VIEW] Get formatted git status report."""
    branch, staged, unstaged = _get_status_details()
    return render_status_report(branch, staged, unstaged)
```

### Batch Operations

For multi-file operations, use Pydantic models:

```python
from pydantic import BaseModel
from typing import List, Literal

class FileOperation(BaseModel):
    action: Literal["write", "append"]
    path: str
    content: str

def apply_file_changes(changes: List[FileOperation]) -> str:
    """[BATCH] Efficiently apply changes to multiple files."""
    # Process all changes
    return summary_report
```

## Phase 27: JIT Skill Acquisition

### MCP Tools

| Tool                | Description                        |
| ------------------- | ---------------------------------- |
| `skill.jit_install` | Install skill from index on demand |
| `skill.discover`    | Search skills index                |
| `skill.suggest`     | Get AI recommendations             |
| `skill.list_index`  | List all known skills              |

### Usage

```python
# Install a skill on demand
@omni("skill.jit_install", {"skill_id": "pandas-expert"})

# Search for skills
@omni("skill.discover", {"query": "data analysis"})

# Get suggestions for task
@omni("skill.suggest", {"task": "analyze csv file"})
```

### Known Skills Index

Skills are discovered from `assets/skills_index/known_skills.json`:

```json
[
  {
    "id": "pandas-expert",
    "name": "Pandas Expert",
    "url": "https://github.com/omni-dev/skill-pandas",
    "version": "1.0.0",
    "keywords": ["python", "data", "analysis", "pandas"]
  }
]
```

## Phase 28: Safe Ingestion / Immune System

### Security Scanner

All remote skills are scanned before loading:

```python
# Security checks performed:
# 1. Code Pattern Detection
#    - Critical (+50): os.system, subprocess(shell=True), eval, exec, __import__
#    - High (+30): File write, network requests, socket.connect
#    - Medium (+10): File read, subprocess, os.popen
#    - Low (+5): System access, path operations

# 2. Manifest Permission Audit
#    - Checks for dangerous permissions: exec, shell, filesystem=write

# 3. Trusted Source Bypass
#    - Configured in assets/settings.yaml
```

### Security Thresholds

| Threshold | Score Range | Action             |
| --------- | ----------- | ------------------ |
| BLOCK     | >= 30       | Reject skill       |
| WARN      | 10-29       | Allow with warning |
| SAFE      | < 10        | Load normally      |

### Configuration

```yaml
# assets/settings.yaml
security:
  enabled: true
  block_threshold: 30
  warn_threshold: 10
  trusted_sources:
    - "github.com/omni-dev"
```

### Security Assessment Output

```python
@omni("skill.jit_install", {"skill_id": "external-skill"})
# Result includes:
# {
#   "decision": "SAFE|WARN|BLOCK",
#   "score": 15,
#   "findings": [...],
#   "warnings": [...]
# }
```

## Related Documentation

- [Phase 28 Spec](../specs/phase28-safe-ingestion.md) - Safe Ingestion specification
- [Phase 27 Spec](./skills_index/README.md) - JIT Acquisition specification
- [Phase 26 Spec](../specs/phase26-skill-network.md) - Skill Network specification
- [Phase 24 Spec](../specs/phase-24-living-skill-architecture.md) - MiniMax Shift specification
- [Phase 13 Spec](../specs/phase13_skill_architecture.md) - Original specification
- [Git Operations Skill](./git/guide.md) - Example skill with Phase 24 patterns
- [Project Conventions](../instructions/project-conventions.md) - LLM behavior standards
