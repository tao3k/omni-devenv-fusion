# Phase 27: JIT Skill Acquisition Protocol

> **Status**: IMPLEMENTED
> **Date**: 2026-01-06
> **Owner**: System Architecture

## Overview

Phase 27 introduces **Just-in-Time (JIT) Skill Acquisition** - Omni can now discover, install, and load skills from a known index automatically when needed.

This transforms Omni from a fixed-capability system to a truly extensible Agentic OS.

## Problem Statement

### Before Phase 27

```
User: "Analyze this pcap file"

Omni: "❌ I don't have pcap analysis skills.
       Please ask me something else."

# Omni's capabilities were fixed at build time
# Users couldn't extend it without modifying code
```

### After Phase 27

```
User: "Analyze this pcap file"

Omni: "🔍 I don't have pcap skills.
       Searching for relevant skills...

       💡 Found: network-analysis (keywords: pcap, network, wireshark)

       Installing network-analysis skill...
       ✅ Installed and loaded!

       Ready to analyze your pcap file."
```

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Phase 27: JIT Acquisition                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐   ┌─────────────────────────────────────┐  │
│  │ User Request    │   │ Known Skills Index                  │  │
│  │                 │   │                                     │  │
│  │ "analyze pcap"  │   │ skills/                             │  │
│  └────────┬────────┘   │   ├── pandas-expert/                │  │
│           │            │   ├── docker-ops/                    │  │
│           ▼            │   ├── network-analysis/ ← NEW!       │  │
│  ┌─────────────────┐   │   └── ...                            │  │
│  │ Suggest Tool    │   └─────────────────────────────────────┘  │
│  │                 │                                            │
│  │ suggest_        │            ┌─────────────────────────┐    │
│  │ skills_for_     │            │ Skill Registry          │    │
│  │ task()          │            │                         │    │
│  └────────┬────────┘            │ • load_skill()          │    │
│           │                     │ • install_remote_skill()│    │
│           ▼                     └───────────┬─────────────┘    │
│  ┌─────────────────┐                       │                   │
│  │ Discovery       │                       ▼                   │
│  │                 │           ┌─────────────────────────┐    │
│  │ discover_       │           │ Skill Installer         │    │
│  │ skills()        │           │                         │    │
│  └────────┬────────┘           │ • Git clone             │    │
│           │                    │ • Git update            │    │
│           ▼                    │ • Sparse checkout       │    │
│  ┌─────────────────┐           └─────────────────────────┘    │
│  │ JIT Install     │                                              │
│  │                 │           ┌─────────────────────────┐    │
│  │ jit_install_    │           │ Skills Directory        │    │
│  │ skill()         │           │                         │    │
│  └─────────────────┘           │ assets/skills/          │    │
│                                │   ├── network-analysis/ │    │
│                                │   └── .omni-lock.json   │    │
│                                └─────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Known Skills Index

**File**: `agent/core/data/known_skills.json`

```json
{
  "version": "1.0.0",
  "description": "Official Omni Skill Index",
  "skills": [
    {
      "id": "pandas-expert",
      "name": "Pandas Expert",
      "url": "https://github.com/omni-dev/skill-pandas",
      "description": "Advanced pandas data manipulation",
      "keywords": ["pandas", "dataframe", "data-analysis"],
      "version": "1.0.0"
    },
    {
      "id": "network-analysis",
      "name": "Network Analysis",
      "url": "https://github.com/omni-dev/skill-network",
      "description": "PCAP analysis and network troubleshooting",
      "keywords": ["pcap", "network", "wireshark"],
      "version": "1.0.0"
    }
  ]
}
```

### 2. SkillDiscovery Class

**File**: `agent/core/skill_discovery.py`

| Method                       | Description                         |
| ---------------------------- | ----------------------------------- |
| `search_local(query, limit)` | Fuzzy search index by name/keywords |
| `find_by_id(skill_id)`       | Get skill by exact ID               |
| `find_by_keyword(keyword)`   | Find skills with specific keyword   |
| `suggest_for_query(query)`   | Get suggestions for a task          |
| `list_all()`                 | List all known skills               |

### 3. JIT Functions

**File**: `agent/core/skill_registry.py`

```python
# Discover skills from index
def discover_skills(query: str = "", limit: int = 5) -> dict:
    """
    Search the known skills index.

    Returns:
        {
            "query": "docker",
            "count": 2,
            "skills": [...],
            "ready_to_install": ["docker-ops", ...]
        }
    """

# Suggest skills for a task
def suggest_skills_for_task(task: str) -> dict:
    """
    Analyze task and suggest relevant skills.

    Returns:
        {
            "query": "analyze pcap file",
            "count": 1,
            "suggestions": [...],
            "ready_to_install": ["network-analysis"]
        }
    """

# Install and load a skill
def jit_install_skill(skill_id: str, auto_load: bool = True) -> dict:
    """
    Install a skill from known index and optionally load it.

    Returns:
        {
            "success": True,
            "skill_name": "network-analysis",
            "url": "https://github.com/...",
            "loaded": True,
            "ready_to_use": True
        }
    """
```

### 4. MCP Tools

**File**: `agent/mcp_server.py`

| Tool   | Description                         |
| ------ | ----------------------------------- |
| `omni` | Single entry point for all commands |

**Note**: Phase 27 follows One Tool design. All skill discovery commands are accessed via `@omni("skill.command")`.

### 4. Skill Commands (via omni)

**File**: `agent/skills/skill/tools.py`

| Command             | Description                |
| ------------------- | -------------------------- |
| `skill.discover`    | Search the skills index    |
| `skill.suggest`     | Get task-based suggestions |
| `skill.jit_install` | Install and load a skill   |
| `skill.list_index`  | List all known skills      |

## Usage Examples

### Via MCP (Claude) - One Tool Syntax

```python
# Discover skills
@omni("skill.discover", {"query": "data analysis"})

# Get suggestions
@omni("skill.suggest", {"task": "work with docker containers"})

# Install and load a skill
@omni("skill.jit_install", {"skill_id": "docker-ops"})

# List all known skills
@omni("skill.list_index")
```

### Via CLI

```bash
# Discover skills matching "docker"
omni skill discover docker

# Discover with limit
omni skill discover "pcap" --limit 3
```

## Search Algorithm

The skill discovery uses a **weighted scoring system**:

1. **Keyword match** (score +10) - Query term found in skill keywords
2. **ID match** (score +8) - Query term found in skill ID
3. **Name match** (score +5) - Query term found in skill name
4. **Description match** (score +2) - Query term found in description
5. **Partial name match** (score +3) - Query contains skill name

Example:

```
Query: "pcap network"
Skill: {id: "network-analysis", keywords: ["pcap", "network", ...]}

Score calculation:
  "pcap" in keywords → +10
  "network" in keywords → +10
Total: 20 (top result)
```

## Extensibility

### Adding New Skills

1. **Manual**: Edit `known_skills.json` directly

2. **Via Pull Request**: Submit to omni-dev repository

3. **Dynamic**: Future versions will support GitHub API search

### Skill Manifest Requirements

Skills in the index must have:

- Valid `manifest.json` (v2.0.0 format)
- `@skill_command` decorated functions
- Proper `guide.md` documentation

## Error Handling

| Scenario                | Behavior                             |
| ----------------------- | ------------------------------------ |
| Skill not in index      | Return error with search suggestions |
| Skill already installed | Return info with update option       |
| Git clone fails         | Provide actionable error hint        |
| Skill load fails        | Report specific load error           |

## Future Enhancements

1. **GitHub API Search** - Search public repos for skills
2. **Auto-Install on Missing** - Automatically install when router fails
3. **Skill Ratings** - Community ratings for quality signals
4. **Dependency Resolution** - Auto-install skill dependencies

## Test Coverage

| Test File                         | Tests                              |
| --------------------------------- | ---------------------------------- |
| `test_phase27_jit_acquisition.py` | Discovery, suggestion, JIT install |

## Changelog

| Version | Date       | Changes                |
| ------- | ---------- | ---------------------- |
| 1.0.0   | 2026-01-06 | Initial implementation |
