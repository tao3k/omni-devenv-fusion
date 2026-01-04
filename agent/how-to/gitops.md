# Git Workflow Guide

> **TL;DR**: Use `git_commit` tool directly. Git status is auto-injected via Context Injection.

---

## Quick Reference

| Task        | Tool / Command                                  |
| ----------- | ----------------------------------------------- |
| View status | Auto-injected in System Prompt ({{git_status}}) |
| Stage files | `git_add(files=[...])`                          |
| Commit      | `git_commit(message="type(scope): desc")`       |

---

## ⚠️ CRITICAL: Never Use Bash for Git Operations

**This is the #1 rule violation that keeps happening:**

| What I Did Wrong    | Why It's Wrong                        |
| ------------------- | ------------------------------------- |
| `git status` (Bash) | Status is auto-injected, no tool call |
| `git commit` (Bash) | Bypasses authorization protocol       |
| `git diff` (Bash)   | Should use `git_diff_staged()`        |

### The Correct Workflow (Executor Mode)

```
User: commit

Claude: (analyzes changes)

    Commit Analysis:

    Type: feat
    Scope: git
    Message: simplify to executor mode

    Please say: "yes" or "confirm", or "skip"

User: yes

Claude: git_commit(message="feat(git): simplify to executor mode")

User: [Claude Desktop approves]

Claude: ✅ Commit Successful
```

**Steps:**

1. User says "commit"
2. Claude reads `{{git_status}}` from context
3. Claude generates message and shows analysis
4. User confirms with "yes" or "confirm"
5. Claude calls `git_commit`
6. User approves via Claude Desktop popup

### Bash Git Commands are Blocked

Use MCP tools instead:

| Instead of   | Use This Tool               |
| ------------ | --------------------------- |
| `git commit` | `git_commit(message="...")` |
| `git add .`  | `git_add(files=["."])`      |
| `git status` | Auto-injected (no tool)     |
| `git diff`   | `git_diff_staged()`         |

---

## 1. Commit Message Standard

All commits follow **Conventional Commits**:

```
<type>(<scope>): <description>
```

### Types

| Type       | Description                  |
| ---------- | ---------------------------- |
| `feat`     | New feature                  |
| `fix`      | Bug fix                      |
| `docs`     | Documentation changes        |
| `style`    | Formatting (no code change)  |
| `refactor` | Code restructure             |
| `perf`     | Performance improvement      |
| `test`     | Adding or fixing tests       |
| `build`    | Build system or dependencies |
| `ci`       | CI/CD pipeline changes       |
| `chore`    | Maintenance tasks            |

---

## 2. Agent Workflow

### When user says "commit":

1. **Observe**: Look at `{{git_status}}` in your context
2. **Think**: Generate a conventional commit message
3. **Act**: Call `git_commit(message="...")` directly
4. **User Approves**: Via Claude Desktop popup

### Example

```
User: commit

Claude: I see the changes. Let me commit them.
[Tool Request] git_commit(message="feat(git): simplify to executor mode")

Claude Desktop: Allow git_commit?
message: "feat(git): simplify to executor mode"

User: [Click Allow]

Claude: ✅ Commit Successful
```

---

## 3. Protocol Rules

| Condition               | Agent Action               |
| ----------------------- | -------------------------- |
| User says "commit"      | Call `git_commit` directly |
| Tests fail              | STOP, don't commit         |
| User asks to force push | REFUSE, explain risks      |
| Pre-commit hooks fail   | STOP, fix issues first     |

---

## 4. Git Safety Rules

- **NEVER** use `git push --force`
- **NEVER** use `git reset --hard`
- **NEVER** use `git commit --amend` on pushed commits
- For history correction: Use `git revert`

---

## 5. Phase 13.10: Executor Mode (Current)

### Core Philosophy: Less Code, More Intelligence

| Old (Over-Engineered)           | New (Executor Mode)                      |
| ------------------------------- | ---------------------------------------- |
| `smart_commit` (session dance)  | `git_commit` (direct execution)          |
| `spec_aware_commit` (AI middle) | Claude generates message, calls directly |
| `commit_flow.py` (LangGraph)    | Prompt handles workflow, not Python      |

### The Result

```
User: commit
Claude: (sees {{git_status}})
       → generates message
       → calls git_commit
User: [Allow]
Done. One click, no session dance.
```

### Key Insight

> **Skill = Tool (Hand) + Prompt (Brain)**
>
> Python does execution. Markdown tells LLM when to execute.

---

## Related Documentation

- [Commit Conventions](../../agent/writing-style/02_mechanics.md)
- [Feature Lifecycle](../../agent/standards/feature-lifecycle.md)
- [Agent Native Development](../../agent/how-to/agent-native-development.md) - Core philosophy
- [CLAUDE.md](../../CLAUDE.md)

---

_Built on standards. Not reinventing the wheel._
