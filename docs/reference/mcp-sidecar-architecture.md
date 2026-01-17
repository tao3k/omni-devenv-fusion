# MCP Sidecar Architecture

> **Status**: Implemented | **Date**: 2024-XX-XX
> **Related**: Phase 29 (Trinity + Protocols), Phase 36 (Trinity v2.0)

## Overview

The Sidecar Pattern provides heavy dependency isolation for skills with large runtime requirements (crawl4ai, playwright, etc.).

## The Problem

Skills with heavy dependencies pollute the main agent environment:

```python
# Problem: Main agent must install ALL skill dependencies
# This causes:
# 1. Version conflicts between skills
# 2. Large memory footprint
# 3. Slow startup time
# 4. Dependency hell
```

## The Solution: Sidecar Pattern

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
│              │  - playwright                │               │
│              └──────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

## Skill Structure

```
assets/skills/crawl4ai/
├── pyproject.toml        # Skill dependencies (crawl4ai, fire, pydantic)
├── tools.py              # Lightweight interface (uses common.isolation)
├── scripts/
│   └── engine.py         # Heavy implementation (imports crawl4ai)
└── SKILL.md              # Skill documentation + rules
```

### tools.py (Lightweight Interface)

```python
from common.isolation import run_skill_command

@skill_command(
    name="crawl_url",
    category="web",
    description="Crawl a URL and extract content",
)
def crawl_webpage(url: str, extract_blocks: bool = True) -> str:
    """Lightweight interface - no heavy imports."""
    return run_skill_command(
        skill_dir=Path(__file__).parent,
        script_name="engine.py",
        args={"url": url, "extract_blocks": extract_blocks},
    )
```

### scripts/engine.py (Heavy Implementation)

```python
# Heavy implementation - can import anything
import json
from crawl4ai import AsyncWebCrawler

async def crawl(url: str, extract_blocks: bool = True):
    """Heavy implementation with full dependencies."""
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            extract_blocks=extract_blocks,
            # ... complex configuration
        )
        return json.dumps({
            "success": result.success,
            "markdown": result.markdown,
            "links": result.links,
        })
```

## common.isolation Module

```python
# common/isolation.py

import subprocess
import json
from pathlib import Path

def run_skill_command(
    skill_dir: Path,
    script_name: str,
    args: dict,
    timeout: int = 60,
) -> str:
    """
    Run a skill script in isolated environment.

    Uses uv run --directory for environment isolation:
    - Reads pyproject.toml from skill directory
    - Creates temporary virtual environment
    - Executes script with proper dependencies
    """
    # Build command
    cmd = [
        "uv",
        "run",
        "--directory", str(skill_dir),
        "python", "scripts/engine.py",
        "--args", json.dumps(args),
    ]

    # Execute
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    return result.stdout or result.stderr
```

## Benefits

| Benefit               | Description                                   |
| --------------------- | --------------------------------------------- |
| **Zero Pollution**    | Main agent doesn't install heavy dependencies |
| **Version Isolation** | Each skill can use different library versions |
| **Hot Swappable**     | Add/remove skills without restarting          |
| **Security**          | Limited blast radius for compromised code     |
| **Performance**       | Parallel skill execution possible             |

## Pure MCP Server

Phase 35.3 introduced a pure MCP Server implementation using the official `mcp.server` package instead of FastMCP.

### Architecture Comparison

| Aspect            | FastMCP (Before)             | Pure MCP (Phase 35.3)  |
| ----------------- | ---------------------------- | ---------------------- |
| **Dependency**    | fastmcp                      | mcp.server (official)  |
| **Control**       | Abstracted                   | Direct protocol access |
| **Overhead**      | Additional abstraction layer | Minimal                |
| **Extensibility** | Limited by FastMCP           | Full protocol control  |
| **Type Safety**   | Partial                      | Full (mcp.types)       |

### Tool Discovery Integration

```python
# Tool discovery is dynamic based on loaded skills
async def handle_list_tools() -> list[Tool]:
    """
    List all available tools from SkillManager.

    This creates a live tool list based on:
    1. Loaded skills
    2. Commands within each skill
    3. Command metadata (description, parameters)
    """
    manager = get_skill_manager()
    tools = []

    for skill_name in manager.list_loaded():
        skill = manager.get_skill(skill_name)
        for cmd_name, cmd in skill.commands.items():
            tools.append(Tool(
                name=f"{skill_name}.{cmd_name}",
                description=cmd.description or "",
                inputSchema={
                    "type": "object",
                    "properties": {
                        param.name: {
                            "type": param.type.__name__,
                            "description": param.description,
                        }
                        for param in get_cmd_params(cmd)
                    },
                    "required": [
                        p.name for p in get_cmd_params(cmd)
                        if not p.optional
                    ],
                },
            ))

    return tools
```

## Related Documentation

- [Trinity Architecture](../explanation/trinity-architecture.md)
- [Skill Standard](../human/architecture/skill-standard.md)
- [MCP Best Practices](./mcp-best-practices.md)
