# LLM Memory Context Guide

> **Status**: Active | **Version**: v1.0 | **Date**: 2026-01-16

## Overview

This guide explains how memory systems work in Omni-DevEnv Fusion and how LLMs can leverage episodic memory.

## Memory Architecture

The system implements a three-level memory hierarchy:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Memory Hierarchy                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Level 1: Scratchpad (Short-term)                       │   │
│  │  - Current task's detailed tool outputs                 │   │
│  │  - FIFO, 4k-8k tokens max                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Level 2: Episodic Summary (Medium-term)                │   │
│  │  - Generated when Task completes                        │   │
│  │  - Stored in SQLite/JSONL                              │   │
│  │  - Injected into future System Prompts                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Level 3: Knowledge Graph (Long-term)                   │   │
│  │  - Vectorized Episode Summaries                         │   │
│  │  - Retrieved by Wisdom Injection                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Cognitive Trinity

Memory completes the Cognitive Trinity:

| Component     | Capability                     | Data Source                    |
| ------------- | ------------------------------ | ------------------------------ |
| **Skills**    | "I know how to do"             | `assets/skills/*/scripts/*.py` |
| **Knowledge** | "I know what that is"          | `docs/`, `assets/specs/`       |
| **Memory**    | "I remember doing that before" | VectorDB (LanceDB)             |

## Using Memory

### 1. Adding Experiences

Record successful patterns:

```python
@omni("memory.add_experience", {
    "user_query": "git commit fails with lock",
    "tool_calls": ["git.commit"],
    "outcome": "failure",
    "error_msg": "index.lock exists",
    "reflection": "Solution: rm .git/index.lock"
})
```

### 2. Recalling Memories

Retrieve relevant past experiences:

```python
@omni("memory.recall", {
    "query": "git commit lock"
})
```

Output:

```
[failure] Solution: rm .git/index.lock
[success] Used git_stage_all for bulk staging
```

### 3. Consulting Knowledge Base

Query harvested wisdom:

```python
@omni("knowledge.consult_knowledge_base", {
    "topic": "writing style"
})
```

## Memory in System Prompts

Memories are automatically injected into your context:

```markdown
## Relevant Past Experiences

- **git**: Don't run git commit without staging files first - always check git status
- **filesystem**: Always use absolute paths, never relative
```

## Memory Types

### Session Memory

Short-term memory for current session:

```python
@omni("note_taker.update_knowledge_base", {
    "category": "notes",
    "title": "Session Summary",
    "content": "Completed feature X, found Y issue"
})
```

### Episodic Memory

Long-term memory for learning:

```python
@omni("memory.add_experience", {
    "user_query": "Refactored authentication module",
    "tool_calls": ["filesystem.*", "code_tools.*"],
    "outcome": "success",
    "reflection": "Used AST-based refactoring for safe changes"
})
```

### Knowledge Memory

Harvested wisdom from sessions:

```python
@omni("note_taker.update_knowledge_base", {
    "category": "patterns",
    "title": "Safe Refactoring Pattern",
    "content": "Always use code_tools for code changes",
    "tags": ["refactoring", "safety", "pattern"]
})
```

## Memory Best Practices

### 1. Record Failures

Learning from mistakes is valuable:

```python
# GOOD - Records what went wrong
@omni("memory.add_experience", {
    "user_query": "Tried to edit file with sed",
    "outcome": "failure",
    "reflection": "Syntax error in replacement pattern - use code_tools instead"
})
```

### 2. Capture Solutions

Record successful approaches:

```python
# GOOD - Records the solution
@omni("memory.add_experience", {
    "user_query": "Fixed auth bug",
    "outcome": "success",
    "reflection": "Used code_tools.structural_replace() for nested conditions"
})
```

### 3. Harvest Knowledge

Share lessons with future sessions:

```python
# GOOD - Harvests knowledge
@omni("note_taker.update_knowledge_base", {
    "category": "techniques",
    "title": "Git Workflow Best Practice",
    "content": "Always run git_status first to see what's staged",
    "tags": ["git", "workflow", "best-practice"]
})
```

## Memory Integration Points

### With Routing

Memory influences routing decisions:

```
Query: "commit my changes"
    ↓
Router consults memory
    ↓
[Found: git commit fails with lock → Use git_stage_all first]
    ↓
Mission Brief includes: "Use git_stage_all for bulk staging"
```

### With Execution

Memory injects lessons into execution:

```markdown
## Known Pitfalls & Past Lessons

- **filesystem**: Always use absolute paths
- **git**: Check status before commit
```

### With Review

Memory helps review past actions:

```python
@omni("memory.recall", {
    "query": "How did we fix the threading issue?"
})
```

## Related Documentation

- [Memory Mesh](../human/architecture/memory-mesh.md)
- [Cognitive Architecture](../reference/cognitive-architecture.md)
- [Cognitive Scaffolding](../human/architecture/cognitive-scaffolding.md)
- [Knowledge Matrix](../human/architecture/knowledge-matrix.md)
