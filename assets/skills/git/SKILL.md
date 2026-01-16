---
name: "git"
version: "2.0.0"
description: "Git integration with LangGraph workflow support, Smart Commit V2, and Spec-Awareness"
routing_keywords: [
    # Core verbs (high priority)
    "git",
    "commit",
    "push",
    "pull",
    "merge",
    "rebase",
    "checkout",
    "stash",
    "tag",
    # High-frequency phrases (Phase 38 optimization)
    "commit code",
    "save changes",
    "commit changes",
    "push code",
    "save work",
    "check in",
    "submit code",
    # Context keywords
    "branch",
    "version control",
    "repo",
    "repository",
    "history",
    "diff",
    "status",
    "log",
    "hotfix",
    "pr",
    "pull request",
    "code review",
  ]
intents:
  [
    "hotfix",
    "pr",
    "branch",
    "commit",
    "stash",
    "merge",
    "revert",
    "tag",
    "status",
  ]
authors: ["omni-dev-fusion"]
---

# Git Skill

> **Code is Mechanism, Prompt is Policy**

## Architecture

This skill uses `@skill_script` decorator in `scripts/*.py` files.
Commands are automatically exposed via MCP as `git.command_name`.

## Available Commands

| Command            | Description                                             |
| ------------------ | ------------------------------------------------------- |
| `git.status`       | Show working tree status                                |
| `git.stage_all`    | Stage all changes (with security scan)                  |
| `git.commit`       | Commit staged changes                                   |
| `git.smart_commit` | Smart Commit workflow (stage → scan → approve → commit) |
| `git.push`         | Push to remote                                          |
| `git.log`          | Show commit logs                                        |

## Smart Commit Workflow

Use `git.smart_commit` for secure, human-in-the-loop commits:

```python
# Step 1: Start workflow
git.smart_commit(action="start")
# Returns workflow_id and diff preview

# Step 2: After LLM analysis and user approval
git.smart_commit(action="approve", workflow_id="xxx", message="feat: description")
```

**Flow:** `stage_and_scan` → `route_prepare` → `format_review` → `re_stage` → `interrupt` → `commit`

## Usage Guidelines

### Read Operations (Safe - Use Claude-native bash)

```bash
git status
git diff --cached
git diff
git log --oneline
```

### Write Operations (Use MCP Tools)

| Operation    | Tool                                  |
| ------------ | ------------------------------------- |
| Stage all    | `git.stage_all()` (scans for secrets) |
| Commit       | `git.commit(message="...")`           |
| Push         | `git.push()`                          |
| Smart Commit | `git.smart_commit(action="start")`    |

## Key Principle

> **Read = Claude-native bash. Write = MCP tools.**
