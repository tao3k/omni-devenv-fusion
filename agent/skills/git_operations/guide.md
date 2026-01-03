# Git Operations Skill Guide

> **TL;DR**: In LLM context, `git commit` means `smart_commit` workflow. Never use raw `git commit`.

This skill provides version control operations using Git with an emphasis on safe, compliant commits through the smart_commit workflow.

## When to Use This Skill

Use this skill when the user wants to:

- Commit changes to the repository
- Review changes (diff, status, log)
- Analyze commit history
- Manage branches
- Prepare commits for review

---

## 🚨 CRITICAL: Never Use Bash for Git Operations

**This is the #1 rule violation that keeps happening:**

| What I Did Wrong                  | Why It's Wrong                         |
| --------------------------------- | -------------------------------------- |
| `git status` (Bash)               | Bypasses MCP `run_task` security       |
| `git add -A && git commit` (Bash) | Bypasses authorization protocol        |
| `git diff` (Bash)                 | Should use `run_task("git", ["diff"])` |

**Bash Git Commands are Blocked:**

| Blocked Command | Replacement                     |
| --------------- | ------------------------------- |
| `git commit`    | `smart_commit()` via MCP        |
| `git add`       | `run_task("git", ["add", ...])` |
| `git status`    | `git_status()` via MCP          |
| `git diff`      | `git_diff()` via MCP            |

**If you catch yourself typing `git ...` in Bash → STOP and use MCP tools instead.**

---

## Quick Reference

| Task                      | MCP Tool / Command                              |
| ------------------------- | ----------------------------------------------- |
| View status               | `git_status()`                                  |
| View unstaged changes     | `git_diff()`                                    |
| View staged changes       | `git_diff_staged()`                             |
| View commit history       | `git_log(n=10)`                                 |
| Generate commit message   | `suggest_commit_message(spec_path=...)`         |
| Validate commit message   | `validate_commit_message(type, scope, message)` |
| Execute commit            | `smart_commit(type, scope, message)`            |
| Execute authorized commit | `execute_authorized_commit(auth_token="...")`   |
| Spec-aware commit         | `spec_aware_commit(spec_path=...)`              |

---

## Smart Commit Workflow

The **smart_commit workflow** is the standard way to commit changes in this project.

### Step 1: Analyze Changes

```
git_status()          → Show working tree status
git_diff()            → Show unstaged changes
git_diff_staged()     → Show staged changes
git_log(n=10)         → Show recent commit history
```

### Step 2: Generate Commit Message

Use `suggest_commit_message` to generate a compliant commit message based on staged changes. The tool reads `cog.toml` to understand valid scopes.

### Step 3: Validate Message

Use `validate_commit_message` to verify a commit message follows all rules before committing.

### Step 4: Execute Commit

After user authorization, use `smart_commit` or `execute_authorized_commit` to perform the commit.

---

## Conventional Commits Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Valid Types

| Type       | Description                                   |
| ---------- | --------------------------------------------- |
| `feat`     | New feature or capability                     |
| `fix`      | Bug fix                                       |
| `docs`     | Documentation changes                         |
| `style`    | Formatting, whitespace, etc. (no code change) |
| `refactor` | Code restructure (no behavior change)         |
| `perf`     | Performance improvement                       |
| `test`     | Adding or fixing tests                        |
| `build`    | Build system or dependencies                  |
| `ci`       | CI/CD pipeline changes                        |
| `chore`    | Maintenance tasks                             |

### Valid Scopes

This project uses **standardized scopes**:

| Scope    | Covers                                                   |
| -------- | -------------------------------------------------------- |
| `nix`    | `devenv.nix`, `units/`, `*.nix` files                    |
| `mcp`    | `mcp-server/` directory                                  |
| `router` | `tool-router/` directory                                 |
| `docs`   | `docs/` (user docs), `agent/` (LLM context), `README.md` |
| `cli`    | `justfile`, `lefthook.yml`                               |
| `deps`   | `pyproject.toml`, `devenv.lock`, `package.json`          |
| `ci`     | `.github/`, `.devcontainer/`                             |

### Good vs Bad Examples

| Bad                 | Good                                   |
| ------------------- | -------------------------------------- |
| `fix: bug`          | `fix(mcp): handle connection timeout`  |
| `feat: added stuff` | `feat(nix): add redis service`         |
| `docs: update`      | `docs(readme): add setup instructions` |
| `chore: misc`       | `chore(cli): bump just version`        |

---

## Authorization Protocol (Human-in-the-Loop)

### Default Rule: "Stop and Ask" - ALWAYS

**By default, when an Agent (LLM) finishes a task, it MUST NOT commit code automatically.**

### Authorization Flow

```
1. Agent calls: smart_commit(type, scope, message)
2. System returns: {authorization_required: true, auth_token: "xxx"}
3. Agent asks user: "Please say: run just agent-commit"
4. User authorizes with exact phrase
5. Agent calls: execute_authorized_commit(auth_token="xxx")
6. Token validated AND consumed (one-time use only)
```

### Authorization Token System (Code-Enforced)

**Why this prevents bypass:**

- Token expires after 5 minutes
- Token can only be used ONCE
- Direct `git commit` is blocked by `run_task` guard
- Only `execute_authorized_commit` can execute commits after authorization

### Authorization is EXPLICIT Only

**Only these phrases grant authorization:**

| Phrase                                     | Effect                                    |
| ------------------------------------------ | ----------------------------------------- |
| `"run just agent-commit"`                  | ✅ Authorized - execute with staged files |
| `"just agent-commit <type> <scope> <msg>"` | ✅ Full authorization                     |

**These do NOT grant authorization:**

- `"ok"` / `"yes"` / `"hao"` / `"go ahead"`
- `"please commit"`
- `"that looks good"`
- Any variation not matching exactly

### Protocol Rules

| Condition                                             | Agent/LLM Action                                               |
| ----------------------------------------------------- | -------------------------------------------------------------- |
| User says: "Fix the bug"                              | Fix code → Run Tests → **ASK USER** for permission             |
| User says: "submit/commit"                            | **ASK USER** for permission first - do NOT assume!             |
| User grants permission                                | Execute commit                                                 |
| `smart_commit` returns `authorization_required: true` | **IMMEDIATELY STOP** → Ask user to say "run just agent-commit" |
| Tests fail                                            | **STOP** and report error. Do not commit.                      |

---

## Git Status Interpretation

- `A` (Added): New files staged for commit
- `M` (Modified): Existing files staged for commit
- `D` (Deleted): Files staged for deletion
- `??` (Untracked): New files not staged
- ` M`: Modified but not staged

---

## Commit Message Best Practices

1. Use imperative mood ("add feature" not "added feature")
2. Keep subject line under 50 characters
3. Separate subject from body with a blank line
4. Wrap body at 72 characters
5. Explain what and why, not how

---

## Smart Error Recovery

When `just agent-commit` fails due to pre-commit hooks, the system provides intelligent diagnosis:

| Error Type          | Analysis                    | Suggested Fix                        |
| ------------------- | --------------------------- | ------------------------------------ |
| `nixfmt` / `fmt`    | Formatting checks failed    | `just agent-fmt`                     |
| `vale`              | Writing style checks failed | Use `writer.polish_text` to fix      |
| `ruff` / `pyflakes` | Python linting failed       | Fix python errors shown in logs      |
| `secrets`           | Secret detection failed     | Remove secrets from code immediately |
| `typos`             | Spelling check failed       | Fix typos shown in output            |

---

## Safety Rules

1. **NEVER commit without running validation first**
2. **NEVER use `git commit -m` directly** - always use smart_commit
3. **ALWAYS check git status before committing**
4. **ALWAYS review diff before staging**
5. **NEVER commit secrets or credentials**
6. **ALWAYS run tests before committing** (when applicable)

---

## Git Safety Rules

- **NEVER** use `git push --force` or `git push --force-with-lease`
- **NEVER** use `git reset --hard` that discards uncommitted changes
- **NEVER** use `git commit --amend` on pushed commits
- For history correction: Use `git revert` or create a new commit
- If force is required: **ASK USER** for explicit confirmation first

---

## Related Documentation

- [Writing Style - Mechanics](../../agent/writing-style/02_mechanics.md) - Writing clear commit messages
- [Feature Lifecycle](../../agent/standards/feature-lifecycle.md) - Spec-Driven Development, testing requirements
- [Project Conventions](../../agent/instructions/project-conventions.md) - Agent instructions

---

_Built on standards. Not reinventing the wheel._
