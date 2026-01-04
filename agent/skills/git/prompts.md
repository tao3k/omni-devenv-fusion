# Git Skill Policy

> **Code is Mechanism, Prompt is Policy**

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
| Add             | `git add <files>`   | Safe staging    |

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
| Use MCP for `git add`                      | Use Claude-native bash              |
| Call `git_commit` without showing analysis | Always show analysis first          |
| Use `smart_commit` (doesn't exist)         | Use `git_commit` after confirmation |

---

## Key Principle

> **Read operations = Claude-native bash. Write operations = MCP tools.**
