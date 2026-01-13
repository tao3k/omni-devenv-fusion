---
name: "git"
version: "2.0.0"
description: "Git integration with LangGraph workflow support, Smart Commit V2, and Spec-Awareness"
routing_keywords:
  [
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

# Git Skill Policy

> **Code is Mechanism, Prompt is Policy**

## Trinity Architecture Context

This skill is part of Phase 25.3 Trinity Architecture:

- **Code**: Tools auto hot-reload when `tools.py` is modified
- **Context**: Use `@omni("git.help")` to get full skill context (XML via Repomix)
- **State**: `Skill` registry tracks mtime, commands, and context cache

For implementation details, see `tools.py` or run `@omni("git.help")`.

## Skill Structure (Role Clarity)

| File         | Role                     | When to Read                   |
| ------------ | ------------------------ | ------------------------------ |
| `prompts.md` | **Rules & Router Logic** | When skill loads (LLM context) |
| `guide.md`   | Procedural Knowledge     | Implementation reference       |
| `tools.py`   | Atomic Execution         | Blind operation                |

---

## Router Logic

### Critical Operations (Use MCP Tools)

| Operation | Tool                  | When                       |
| --------- | --------------------- | -------------------------- |
| Commit    | `git_commit(message)` | User says "commit", "save" |
| Push      | `git_push()`          | After successful commit    |

### Safe Operations (Use Claude-native bash)

| Operation       | Command             | Why             |
| --------------- | ------------------- | --------------- |
| Status          | `git status`        | Read-only, safe |
| Diff (staged)   | `git diff --cached` | Read-only, safe |
| Diff (unstaged) | `git diff`          | Read-only, safe |
| Log             | `git log`           | Read-only, safe |

### Staging (Use MCP Tool)

| Operation | Tool              | Why                                       |
| --------- | ----------------- | ----------------------------------------- |
| Stage all | `git_stage_all()` | **LLM security scan** for sensitive files |

**When user says "commit": System automatically runs:**

1. `git add -A` → call `git_stage_all()` (NOT bash)
2. LLM scans for sensitive files (.env, credentials, secrets, tokens)
3. If sensitive files detected → ⚠️ Alert user:
   - [c] Continue staging anyway
   - [s] Skip sensitive files
   - [a] Abort
4. If safe → auto-stage files
5. Then show commit analysis for confirmation
6. Then execute `git_commit(message="...")`

---

## Authorization Protocol

When user says "commit":

1. **Show Commit Analysis** (required):
   ```
   Type: feat/fix/docs/style/refactor/test/chore
   Scope: component area
   Message: brief description
   ```
2. **Wait for "yes" or "confirm"**
3. **Then call `git_commit(message="...")`**

### Authorization Template

```
📋 Commit Analysis:

   Type: feat
   Scope: git
   Message: simplify to executor mode

🔒 *Authorization Required*
   Please say: "yes" ✅ or "confirm" ✅, or "skip" ⏭️
```

---

## Commit Message Format

```
<type>(<scope>): <subject>
```

**Types:** feat, fix, docs, style, refactor, perf, test, build, ci, chore

---

## Anti-Patterns

| Wrong                                      | Correct                             |
| ------------------------------------------ | ----------------------------------- |
| Use MCP for `git status`, `git diff`       | Use Claude-native bash              |
| Use bash for `git add -A`                  | Use `git_stage_all()` for security  |
| Call `git_commit` without showing analysis | Always show analysis first          |
| Use `smart_commit` (doesn't exist)         | Use `git_commit` after confirmation |

---

## Key Principle

> **Read operations = Claude-native bash. Write operations = MCP tools.**
