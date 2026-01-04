# Git Skill Policy

> **Code is Mechanism, Prompt is Policy**

## Philosophy: MCP as Guard, Claude-native as Explorer

| Layer                             | Purpose                            | Operations                                     |
| --------------------------------- | ---------------------------------- | ---------------------------------------------- |
| **MCP (Guard)**                   | Dangerous ops needing confirmation | `git_commit`, `git_push`                       |
| **Claude-native bash (Explorer)** | Safe read operations               | `git status`, `git diff`, `git log`, `git add` |

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
| Add             | `git add <files>`   | Safe staging    |

---

## Workflow: Commit

```
User: commit

Claude:
  1. (Claude-native) git status → See what changed
  2. (Claude-native) git diff --cached → Review staged
  3. Generate commit message following format
  4. Show analysis to user
  5. User says "yes"
  6. (MCP) git_commit(message="...") → Execute commit
```

### Example

```
Claude: (analyzing...)

    Commit Analysis:

    Type: feat
    Scope: git
    Message: simplify to executor mode

    Please say: "yes" or "confirm", or "skip"

User: yes

Claude: git_commit(message="feat(git): simplify to executor mode")
```

### Authorization Protocol

1. **Always show analysis first** - User must see what will be committed
2. **Wait for "yes" or "confirm"** - User's response is the authorization
3. **Only then call git_commit** - Execute after confirmation
4. **If "skip"** - Do nothing, wait for corrected instructions

---

## Workflow: Push

```
User: push

Claude:
  1. (Claude-native) git status → Verify commit succeeded
  2. (MCP) git_push() → Push to remote
```

---

## Anti-Patterns

| Wrong                                      | Correct                             |
| ------------------------------------------ | ----------------------------------- |
| Use MCP for `git status`, `git diff`       | Use Claude-native bash              |
| Use MCP for `git add`                      | Use Claude-native bash              |
| Call `git_commit` without showing analysis | Always show analysis first          |
| Use `smart_commit` (doesn't exist)         | Use `git_commit` after confirmation |

---

## Commit Message Format

```
<type>(<scope>): <subject>

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
Scope: Component or area (e.g., git, mcp, cli, docs)

Example: feat(git): simplify to executor mode
```

---

## Key Principle

> **Read operations = Claude-native bash. Write operations = MCP tools.**
