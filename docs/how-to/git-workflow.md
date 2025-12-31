# Git Workflow Guide

> **TL;DR**: Use `just agent-commit` only when explicitly authorized. Otherwise, always ask the user before committing.

---

## Quick Reference

| Task | Command |
|------|---------|
| Interactive commit | `just commit` |
| Non-interactive commit (agent) | `just agent-commit <type> <scope> "<message>"` |
| Check commit messages | `just log` |
| View status | `just status` |

---

## 1. Commit Message Standard

All commits follow the **Conventional Commits** specification:

```
<type>(<scope>): <description>
```

### Type Meanings

| Type | Description |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Formatting, whitespace, etc. (no code change) |
| `refactor` | Code restructure (no behavior change) |
| `perf` | Performance improvement |
| `test` | Adding or fixing tests |
| `build` | Build system or dependencies |
| `ci` | CI/CD pipeline changes |
| `chore` | Maintenance tasks |

### Suggested Scopes

This project uses **standardized scopes** for better traceability:

| Scope | Covers |
|-------|--------|
| `nix` | `devenv.nix`, `units/`, `*.nix` files |
| `mcp` | `mcp-server/` directory |
| `router` | `tool-router/` directory |
| `docs` | `docs/`, `design/`, `README.md` |
| `cli` | `justfile`, `lefthook.yml` |
| `deps` | `pyproject.toml`, `devenv.lock`, `package.json` |
| `ci` | `.github/`, `.devcontainer/` |

### Good vs Bad Examples

| Bad | Good |
|-----|------|
| `fix: bug` | `fix(mcp): handle connection timeout` |
| `feat: added stuff` | `feat(nix): add redis service` |
| `docs: update` | `docs(readme): add setup instructions` |
| `chore: misc` | `chore(cli): bump just version` |

### Enforcing Standards

This project uses two tools to enforce commit standards:

| Tool | Role | Responsibility |
|------|------|----------------|
| **Conform** | 🛡️ Police (Enforcer) | Validates commit format at `git commit` time. Rejects invalid messages. |
| **Cog** | 📋 Secretary (Helper) | Provides interactive menu for humans, groups changes in CHANGELOG. |

**Conform** checks:
- Format: `<type>(<scope>): <description>`
- Scope must be lowercase
- No illegal characters

**Cog** provides:
- Interactive scope selection menu (for `just commit`)
- CHANGELOG categorization by type and scope

Both tools share the same scope definitions (nix, mcp, router, docs, cli, deps, ci) configured in `lefthook.nix`.

---

## 2. Workflow for Humans

For manual development, use the interactive commit tool:

```bash
just commit
```

This launches an interactive wizard that guides you through:

1. Selecting commit type (feat, fix, docs, etc.)
2. Optional scope (e.g., "mcp", "cli")
3. Commit message
4. Optional body and breaking changes

---

## 3. Workflow for Agents

### Default Rule: "Stop and Ask"

By default, when an Agent finishes a task, it **MUST NOT** commit code automatically.

**Agent Behavior:**

1. Make changes
2. Run tests (`devenv test`)
3. **STOP**
4. Ask the user: *"Changes are ready. Should I commit?"*

**Example:**

```
User: "Fix the bug in router."

Claude: Fixed the code -> Ran tests -> "Tests passed. Ready to commit?
You can review the changes first: git diff"
```

### Override Rule: `just agent-commit`

The Agent is authorized to perform an automated commit **ONLY IF** the user's prompt explicitly contains:

> `"run just agent-commit"`

**Usage:**

```bash
just agent-commit <type> <scope> "<message>"
```

**Example:**

```bash
# User prompt:
> "Fix the typo in README and run just agent-commit."

# Claude executes:
just agent-commit docs docs "fix typo in readme"
```

### Protocol Rules

| Condition | Agent Action |
|-----------|--------------|
| User says: "Fix the bug" | Fix code → Run Tests → **ASK USER** to commit |
| User says: "Fix the bug and **run just agent-commit**" | Fix code → `just agent-commit fix mcp "handle connection timeout"` |
| Tests fail | **STOP** and report error. Do not commit. |
| Pre-commit hooks fail | **STOP** and report error. Do not commit. |

---

## 4. The Agent-Commit Protocol

### Safety First

This protocol enforces **"Human-in-the-loop"** by default:

- ✅ Tests always run before commit
- ✅ Pre-commit hooks always execute
- ✅ Default behavior requires user confirmation
- ✅ Only explicit `"run just agent-commit"` enables auto-commit

---

## 5. Troubleshooting

### "just agent-commit" Fails

| Error | Solution |
|-------|----------|
| Invalid type | Use: feat, fix, docs, style, refactor, perf, test, build, ci, chore |
| Tests failed | Fix failing tests first |
| Hooks failed | Run `just agent-fmt` to auto-fix formatting |

### Reverting a Commit

```bash
# Find the commit hash
just log

# Revert (creates a new commit that undoes the change)
git revert <commit-hash>

# Or reset (dangerous, rewrites history)
git reset --soft HEAD~1
```

---

## Related Documentation

- [Commit Conventions](../../design/writing-style/02_mechanics.md) - Writing clear commit messages
- [CLAUDE.md](../../CLAUDE.md) - Agent instructions

---

*Built on standards. Not reinventing the wheel.*
