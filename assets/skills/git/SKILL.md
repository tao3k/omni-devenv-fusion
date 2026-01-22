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
    # High-frequency phrases
    "commit code",
    "save changes",
    "commit changes",
    "push code",
    "save work",
    "check in",
    "submit code",
    "version control",
    "branch",
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
permissions:
  - "filesystem:*"
  - "terminal:run_command"
  - "knowledge:ingest"
---

# Git Skill

> **Code is Mechanism, Prompt is Policy**

## Architecture

This skill uses `@skill_command` decorator in `scripts/*.py` files.
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

## Staged Files Feature

### Stage and Scan Workflow

The `stage_and_scan` function provides automatic staging with security validation:

```
Stage All Files → Security Scan → Lefthook Pre-commit → Finalize
```

#### Key Features

1. **Automatic Staging**

   ```python
   stage_and_scan(project_root=".")
   # Returns: {staged_files, diff, security_issues, lefthook_error}
   ```

2. **Security Scanning**
   - Detects sensitive files (`.env*`, `*.pem`, `*.key`, `*.secret`, etc.)
   - Automatically un-stages detected files
   - Returns list of security issues

3. **Lefthook Integration**
   - Runs pre-commit hooks after staging
   - Re-stages files modified by lefthook formatters
   - Returns lefthook output for review

### Staged Files Commands

| Command           | Description                               |
| ----------------- | ----------------------------------------- |
| `git.stage_all()` | Stage all changes with security scan      |
| `git.status()`    | Show staged files and working tree status |
| `git.diff()`      | Show staged diff                          |

### Security Patterns Detected

```
.env*, *.env*, *.pem, *.key, *.secret, *.credentials*
id_rsa*, id_ed25519*, *.priv
secrets.yml, secrets.yaml, credentials.yml
```

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
