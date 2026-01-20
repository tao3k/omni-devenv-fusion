# LLM Skill Discovery Guide

> **Status**: Active | **Version**: v1.0 | **Date**: 2026-01-16

## Overview

This guide explains how LLMs discover and use skills in the Omni-Dev-Fusion Fusion system.

## The Trinity Entry Point

All skill commands use the single `@omni("skill.command")` entry point:

```python
# Single entry point for all operations
@omni("filesystem.read_file", {"path": "README.md"})
@omni("terminal.run_task", {"command": "ls", "args": ["-la"]})
@omni("git.status")
```

## Skill Discovery Mechanisms

### 1. Loaded Skills (Direct Discovery)

Loaded skills are immediately available with full tool schemas:

```python
# Available immediately when skill is loaded
@omni("filesystem.read_file", {"path": "src/main.py"})
```

**Pinned Skills** (always loaded):

- `filesystem` - File operations
- `terminal` - Command execution
- `writer` - Writing assistance
- `git` - Version control
- `note_taker` - Session notes

### 2. Ghost Tools (Lazy Discovery)

Unloaded skills appear as "Ghost Tools" with `[GHOST]` prefix:

```
[GHOST] advanced_tools.search_project_code
Description: Searches for a regex pattern in code files...

[GHOST] code_tools.count_lines
Description: Counts lines of code in a file...
```

When you use a ghost tool, it **auto-loads on first use**.

### 3. Semantic Search

Search for skills using natural language:

```python
@omni("skill.search_tools", {"query": "git commit workflow"})
```

Returns matching tools with similarity scores.

### 4. Skill Discovery Command

List all available skills:

```python
@omni("skill.list_skills")
```

Output:

```
Available Skills:
├── filesystem (pinned)
├── terminal (pinned)
├── writer (pinned)
├── git (pinned)
├── note_taker (pinned)
├── advanced_tools
├── code_tools
├── documentation
├── knowledge
├── memory
├── skill
├── software_engineering
├── testing
└── testing_protocol
```

## How to Discover Skills

### Step 1: Describe Your Task

Tell the system what you want to do:

```python
@omni("skill.suggest", {"task": "find all python files containing 'test'"})
```

### Step 2: Use Ghost Tools

If a ghost tool matches your need, use it directly:

```python
@omni("advanced_tools.search_project_code", {
    "pattern": "def test_",
    "file_type": "py"
})
```

### Step 3: Check Skill Help

Get detailed information about a skill:

```python
@omni("git.help")
```

## Skill Naming Convention

All skills follow the pattern `skill_name.command_name`:

| Category     | Skill            | Example Command                                      |
| ------------ | ---------------- | ---------------------------------------------------- |
| **Core**     | `filesystem`     | `read_file`, `write_file`, `search_files`            |
| **Core**     | `terminal`       | `run_task`, `run_command`                            |
| **Core**     | `git`            | `status`, `commit`, `push`                           |
| **Core**     | `writer`         | `polish_text`, `lint_writing_style`                  |
| **Analysis** | `advanced_tools` | `search_project_code`                                |
| **Analysis** | `code_tools`     | `search_code`, `structural_replace`, `find_tools`    |
| **Meta**     | `skill`          | `list_tools`, `search_tools`, `reload`               |
| **Meta**     | `knowledge`      | `get_development_context`, `consult_language_expert` |

## Best Practices

### 1. Start with Core Skills

Use pinned skills for common operations:

```python
# GOOD - Uses pinned filesystem skill
@omni("filesystem.read_file", {"path": "README.md"})

# GOOD - Uses pinned terminal skill
@omni("terminal.run_task", {"command": "just", "args": ["test"]})
```

### 2. Use Ghost Tools for Specialized Tasks

When you need specialized functionality:

```python
# GOOD - Uses ghost tool for code analysis
@omni("code_tools.count_lines", {"file_path": "src/main.py"})
```

### 3. Use Semantic Search for Discovery

When unsure which skill to use:

```python
# Search for relevant tools
@omni("skill.search_tools", {"query": "search text in files"})
```

### 4. Check Skill Help First

Before using an unfamiliar skill:

```python
@omni("advanced_tools.help")
```

## Related Documentation

- [Skill Standard](../human/architecture/skill-standard.md)
- [Skill Lifecycle](../human/architecture/skill-lifecycle.md)
- [Routing Guide](./routing-guide.md)
- [Trinity Architecture](./trinity-architecture.md)
