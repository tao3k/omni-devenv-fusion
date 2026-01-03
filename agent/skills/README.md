# Skills Directory

> Phase 13: The Skill-First Reformation

This directory contains **Skills** - composable, self-contained packages that provide specific capabilities.

## Architecture Overview

```
agent/
├── skills/              # Skill-centric knowledge (THIS DIRECTORY)
│   ├── {skill_name}/
│   │   ├── manifest.json    # Skill metadata
│   │   ├── guide.md         # Procedural knowledge
│   │   ├── tools.py         # MCP tool definitions
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

## Related Documentation

- [Phase 13 Spec](../specs/phase13_skill_architecture.md) - Original specification
- [Git Operations Skill](./git_operations/guide.md) - Example skill implementation
- [Project Conventions](../instructions/project-conventions.md) - LLM behavior standards
