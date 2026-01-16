# Git Skill - Procedural Knowledge

## Overview

This skill provides git operations with **Smart Commit Protocol** for clean, safe commits.

## Architecture (Phase 63+)

```
assets/skills/git/
├── SKILL.md              # Skill manifest + LLM context
├── README.md             # This file
├── scripts/              # @skill_script decorated commands
│   ├── __init__.py
│   ├── commit.py         # commit operations
│   ├── graph_workflow.py # Smart Commit workflow (LangGraph)
│   └── ...
├── templates/            # Cascading templates
│   ├── commit_message.j2
│   ├── workflow_result.j2
│   └── error_message.j2
└── tests/                # Zero-config pytest
    └── test_git_commands.py
```

---

## Smart Commit Workflow

Use `/commit` slash command for the complete workflow:

### Step 1: Preparation & Checks

```bash
@omni("git.prepare_commit")
```

This:

- Stages all changes
- Runs lefthook pre-commit checks
- Scans for sensitive files

### Step 2: Analysis & Report

Generates commit analysis based on staged diff:

- Determines commit type (feat, fix, refactor, docs, etc.)
- Identifies scope
- Lists changed files

### Step 3: Scope Validation

```bash
@omni("git.prepare_commit", {"message": "type(scope): description"})
```

This validates:

- **Scope Check**: Verifies scope against `cog.toml`
- **Auto-fix**: Auto-corrects close-matching scopes
- **Security Scan**: Detects sensitive files (`.env`, `.pem`, `.key`, etc.)

### Step 4: Commit

```bash
@omni("git.commit", {"message": "type(scope): description"})
```

Executes the commit with template rendering.

---

## Security Guard Detection

The commit workflow includes **automated security scanning**:

### Sensitive File Patterns

Detects and warns about:

```
*.env*       .env files (may contain secrets)
*.pem        Private keys
*.key        API keys
*.secret     Secret files
*.credentials*  Credential files
*.priv       Private keys
id_rsa*      SSH keys
id_ed25519*  SSH keys
```

### LLM Advisory

When sensitive files are detected, the LLM receives this guidance:

```
⚠️ Security Check

Detected X potentially sensitive file(s):
  ⚠️ .env.production

LLM Advisory: Please verify these files are safe to commit.
- Are they intentional additions (not accidentally staged)?
- Do they contain secrets, keys, or credentials?
- Should they be in .gitignore?

If unsure, press No and run git reset <file> to unstage.
```

---

## Scope Validation

Uses `cog.toml` for Conventional Commit scope validation:

```toml
scopes = [
    "git",
    "docs",
    "agent",
    "core",
    "git-ops",
    ...
]
```

### Validation Rules

| Scenario          | Behavior                                |
| ----------------- | --------------------------------------- |
| Valid scope       | ✅ Proceeds                             |
| Invalid scope     | ⚠️ Warning + auto-fix to closest match  |
| No scope provided | ℹ️ Uses first valid scope from cog.toml |
| No cog.toml       | ✅ Passes (validation skipped)          |

---

## Available Commands

### MCP Tools

| Command              | Category | Description                   |
| -------------------- | -------- | ----------------------------- |
| `git.prepare_commit` | workflow | Stage + lefthook + validation |
| `git.commit`         | write    | Execute commit with template  |
| `git.stage_all`      | write    | Stage all changes             |
| `git.status`         | read     | Get git status                |
| `git.branch`         | read     | List branches                 |
| `git.log`            | read     | Show recent commits           |
| `git.diff`           | read     | Show changes                  |
| `git.add`            | write    | Stage specific files          |

---

## Tools Available (No Tool Needed)

| Operation | Command      | Notes     |
| --------- | ------------ | --------- |
| Status    | `git status` | Read-only |
| Diff      | `git diff`   | Read-only |
| Branch    | `git branch` | Read-only |
| Log       | `git log`    | Read-only |

---

## File Locations

| Path                                          | Purpose                 |
| --------------------------------------------- | ----------------------- |
| `assets/skills/git/scripts/commit.py`         | Commit commands         |
| `assets/skills/git/scripts/graph_workflow.py` | Smart Commit workflow   |
| `assets/skills/git/templates/`                | Default templates       |
| `assets/templates/git/`                       | User override templates |
| `cog.toml`                                    | Scope configuration     |

---

## Related

- [Skills Documentation](../../docs/skills.md)
- [Trinity Architecture](../../docs/explanation/trinity-architecture.md)
- [ODF-EP Protocol](../../docs/reference/odf-ep-protocol.md)
