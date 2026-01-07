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

## Phase 28.1: Subprocess/Shim Architecture

> **Philosophy**: "Don't import what you can't isolate."

For skills with heavy/conflicting dependencies (e.g., `crawl4ai` with `pydantic v1` vs Omni's `pydantic v2`), use **subprocess isolation** instead of library import.

### Problem: Dependency Hell

```
Omni Agent: langchain → pydantic v2
Skill: crawl4ai → pydantic v1  # CONFLICT!
```

If we import `crawl4ai` directly into the Agent's memory:

- Version conflicts crash the Agent
- Memory leaks in the skill affect the entire system
- No user control over skill dependencies

### Solution: Shim Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Omni Agent (Main Process)                    │
│                                                                  │
│  ┌─────────────┐     subprocess     ┌─────────────────────┐    │
│  │ tools.py    │ ──────────────────▶ │ .venv/bin/python   │    │
│  │ (Shim)      │                     │                     │    │
│  │             │                     │ implementation.py   │    │
│  └─────────────┘                     │ (Heavy deps here)   │    │
│                                        └─────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Skill Directory Structure

```
assets/skills/{skill_name}/
├── .venv/                      # Isolated Python environment
│   └── bin/python
├── manifest.json               # Execution mode declaration
├── pyproject.toml              # Skill's own dependencies
├── implementation.py           # Real business logic (heavy imports)
└── tools.py                    # Lightweight shim (no heavy imports)
```

### Manifest Configuration

```json
{
  "name": "crawl4ai",
  "version": "1.0.0",
  "execution_mode": "subprocess",
  "entry_point": "implementation.py",
  "permissions": {
    "network": true,
    "filesystem": "read"
  }
}
```

### Shim Pattern: tools.py

**Key principle**: This file runs in Omni's main process. It MUST NOT import heavy dependencies.
Uses `uv run --directory` for cross-platform, self-healing environment management.

```python
# assets/skills/{skill_name}/tools.py
import subprocess
import json
import os
from pathlib import Path
from agent.skills.decorators import skill_command

# Skill directory (computed at import time)
SKILL_DIR = Path(__file__).parent
IMPLEMENTATION_SCRIPT = "implementation.py"  # Relative path for uv run

def _run_isolated(command: str, **kwargs) -> str:
    """Execute command in skill's isolated Python environment using uv run.

    uv run --directory automatically:
    - Discovers the virtual environment in SKILL_DIR
    - Creates .venv if missing (self-healing)
    - Handles cross-platform paths (Windows/Linux/Mac)
    """

    # Build command: uv run --directory <skill_dir> python implementation.py <command> <json_args>
    cmd = [
        "uv", "run",
        "--directory", str(SKILL_DIR),
        "-q",  # Quiet mode, reduce uv's own output
        "python",
        IMPLEMENTATION_SCRIPT,
        command,
        json.dumps(kwargs),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
            env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")}
        )
        return result.stdout.strip()

    except subprocess.CalledProcessError as e:
        return f"Error (Exit {e.returncode}):\n{e.stderr}"

@skill_command(name="crawl_webpage", description="Crawl a URL using crawl4ai.")
def crawl_webpage(url: str, fit_markdown: bool = True) -> str:
    """Crawl webpage - delegates to isolated subprocess."""
    return _run_isolated("crawl", url=url, fit_markdown=fit_markdown)
```

### Testing the Shim Pattern

To test if the Shim Pattern works (without LLM involvement):

```bash
# Test crawl4ai directly via omni skill run command
uv run omni skill run crawl4ai.crawl_webpage '{"url": "https://example.com", "fit_markdown": true}'
```

This tests: `tools.py` → `uv run --directory` → `implementation.py` → crawl4ai

### Implementation: implementation.py

**Key principle**: This file runs in the subprocess. It CAN import anything.

```python
# assets/skills/{skill_name}/implementation.py
import sys
import json
import asyncio
from crawl4ai import AsyncWebCrawler

async def crawl(url, fit_markdown):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url)
        return result.markdown.fit_markdown if fit_markdown else result.markdown.raw

def main():
    command = sys.argv[1]
    args = json.loads(sys.argv[2])

    if command == "crawl":
        result = asyncio.run(crawl(args["url"], args.get("fit_markdown", True)))
        print(result)
    else:
        raise ValueError(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
```

### User Setup Workflow

```bash
# User sees error when trying to use crawl4ai (if no venv)
@omni("crawl4ai.crawl_webpage", {"url": "https://example.com"})
# → uv run auto-creates .venv if missing

# Manual setup (optional, for faster first run)
cd assets/skills/crawl4ai
uv venv && uv sync  # Pre-install dependencies

# Now it works
@omni("crawl4ai.crawl_webpage", {"url": "https://example.com"})
# → uv run implementation.py crawl '{"url": "..."}'
```

### Comparison: Library Mode vs Subprocess Mode

| Aspect            | Library Mode      | Subprocess Mode (Shim) |
| ----------------- | ----------------- | ---------------------- |
| Dependencies      | Shared with Agent | Isolated in .venv      |
| Version Conflicts | High risk         | Zero risk              |
| Crash Impact      | Crashes Agent     | Isolated subprocess    |
| User Control      | None              | Full (uv pip install)  |
| Startup Time      | Fast (import)     | Slower (process spawn) |
| Memory Usage      | Shared            | Extra process overhead |

### When to Use Each Mode

**Use Library Mode (Default) for:**

- Skills with minimal dependencies
- Skills that Omni already supports (git, filesystem)
- Performance-critical operations

**Use Subprocess Mode for:**

- Skills with heavy/conflicting dependencies (crawl4ai, playwright)
- Skills that might crash (untrusted code)
- Skills requiring specific Python versions

## Related Documentation

- [Phase 28 Spec](../specs/phase28-safe-ingestion.md) - Safe Ingestion specification
- [Phase 27 Spec](./skills_index/README.md) - JIT Acquisition specification
- [Phase 26 Spec](../specs/phase26-skill-network.md) - Skill Network specification
- [Phase 24 Spec](../specs/phase-24-living-skill-architecture.md) - MiniMax Shift specification
- [Phase 13 Spec](../specs/phase13_skill_architecture.md) - Original specification
- [Git Operations Skill](./git/guide.md) - Example skill with Phase 24 patterns
- [Project Conventions](../instructions/project-conventions.md) - LLM behavior standards
