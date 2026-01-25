# LLM Routing Guide

> **Status**: Active | **Version**: v1.0 | **Date**: 2026-01-16

## Overview

This guide explains how the routing system works and how LLMs can work effectively with it.

## How Routing Works

### 1. Semantic Router

The system uses semantic search to route requests to appropriate skills:

```
User Query → Semantic Router → Best Matching Skill
```

### 2. Confidence Scoring

Each routing decision has a confidence score:

| Score Range   | Meaning           | Action                |
| ------------- | ----------------- | --------------------- |
| **>= 0.8**    | High confidence   | Direct tool dispatch  |
| **0.5 - 0.8** | Medium confidence | Proceed with caution  |
| **< 0.5**     | Low confidence    | Ask for clarification |

### 3. Routing Factors

The router considers:

- **Vector similarity** - Semantic match to skill descriptions
- **Keyword boost** - Direct keyword matches get priority
- **Verb priority** - Action verbs (read, write, run) boost relevant skills
- **Feedback history** - Past successful routes boost future matches

## Writing Effective Queries

### 1. Be Specific

```python
# GOOD - Specific action
@omni("filesystem.read_files", {"path": "src/main.py"})

# GOOD - Specific intent
@omni("git.commit", {"message": "feat: add new feature"})
```

### 2. Use Action Verbs

| Action                      | Recommended Skill                    |
| --------------------------- | ------------------------------------ |
| `read`, `view`, `open`      | `filesystem.read_files`              |
| `write`, `create`, `edit`   | `filesystem.write_file`              |
| `run`, `execute`, `command` | `terminal.run_task`                  |
| `search`, `find`, `grep`    | `advanced_tools.search_project_code` |
| `commit`, `push`, `branch`  | `git.*`                              |
| `test`, `validate`          | `testing.run_tests`                  |

### 3. Include Context

```python
# GOOD - Includes context
@omni("filesystem.read_files", {"path": "src/main.py"})
# Later: @omni("filesystem.search_files", {"pattern": "def main"})
```

## Trinity Role Routing

The system routes to one of three Trinity roles:

### Orchestrator (Planning & Strategy)

For complex tasks requiring planning:

```python
# Orchestrator handles:
# - Multi-step workflows
# - Task decomposition
# - Context assembly
@omni("knowledge.get_development_context")
@omni("skill.suggest", {"task": "refactor authentication module"})
```

### Coder (Reading & Writing)

For code manipulation:

```python
# Coder handles:
# - File operations
# - Code analysis
# - AST operations
@omni("filesystem.read_files", {"path": "src/main.py"})
@omni("code_tools.refactor_repository", {
    "search_pattern": "print($MSG)",
    "rewrite_pattern": "logger.info($MSG)"
})
```

### Executor (Operations)

For running commands:

```python
# Executor handles:
# - Shell commands
# - Git operations
# - Test execution
@omni("terminal.run_task", {"command": "just", "args": ["test"]})
@omni("git.status")
```

## Hybrid Routing

### Confidence Threshold

When confidence is below threshold, the system may invoke the Planner:

```
User Query → Router → [Confidence < 0.8?]
                           ↓ Yes
                    Planner (Decompose → Task List)
                           ↓
                    Executor (Loop: Execute Task → Review → Next)
```

## Routing Best Practices

### 1. Trust the Router

The router is designed to make optimal decisions. If you're unsure which skill to use, describe your intent:

```python
# Instead of guessing, ask for suggestion
@omni("skill.suggest", {"task": "I need to search for all test files"})
```

### 2. Use Skill Suggestions

When uncertain:

```python
@omni("skill.suggest", {"task": "find and read configuration"})
# Returns: Suggested skill with confidence score
```

### 3. Check Available Tools

List available tools for current context:

```python
@omni("skill.list_tools")
```

### 4. Use Ghost Tools for Discovery

Ghost tools provide hints about available capabilities:

```
[GHOST] advanced_tools.search_project_code
[GHOST] code_tools.count_lines
```

## Common Routing Patterns

### Pattern 1: Simple File Operation

```
User: "Read README.md"
→ Router: filesystem.read_files (confidence: 0.95)
→ Action: @omni("filesystem.read_files", {"path": "README.md"})
```

### Pattern 2: Multi-step Task

```
User: "Run tests and show results"
→ Router: terminal.run_task (confidence: 0.85)
→ Action: @omni("terminal.run_task", {"command": "pytest", "args": ["-v"]})
```

### Pattern 3: Complex Task (Planner)

```
User: "Refactor the entire authentication module"
→ Router: confidence: 0.65 (below threshold)
→ Action: Invoke Planner → Decompose → Execute per task
```

### Pattern 4: Git Workflow

```
User: "Commit my changes with a message"
→ Router: git.commit (confidence: 0.92)
→ Action: @omni("git.commit", {"message": "feat: add auth"})
```

## Troubleshooting

### Low Confidence Routes

If routing confidence is low:

1. **Be more specific** in your query
2. **Use skill suggestions** to find the right tool
3. **Break into smaller steps** if the task is complex

### Unexpected Routing

If routed to wrong skill:

1. **Provide more context** in your query
2. **Use explicit skill.command** format
3. **Report feedback** to improve routing

## Related Documentation

- [Skill Discovery](./skill-discovery.md)
- [Memory Context](./memory-context.md)
- [Cognitive Scaffolding](../human/architecture/cognitive-scaffolding.md)
- [Trinity Architecture](./trinity-architecture.md)
