# Omni-DevEnv Fusion

> **Phase 25.3: One Tool + Trinity Architecture**
> Single Entry Point: `@omni("skill.command")`

Quick Reference: `docs/explanation/trinity-architecture.md` | `docs/skills.md`

---

## ⛔ Critical: Git Commit

**Use `/commit` slash command** - Never `git commit` via terminal.

---

## Essential Commands

- `just validate` - fmt, lint, test
- `/mcp enable orchestrator` - Reconnect omni mcp

---

## Path Handling Guidelines

### Preferred Pattern: `$PRJ_ROOT` + Relative Path

Always use **relative paths** from current location combined with `$PRJ_ROOT`:

```bash
# GOOD - Relative to current location
$PRJ_ROOT/packages/python/agent/src/agent/core/skill_manager.py

# GOOD - Using environment variable
echo $PRJ_ROOT/.data/benchmark_report.txt

# BAD - Hardcoded absolute path
/Users/guangtao/ghq/github.com/tao3k/omni-devenv-fusion/packages/python/agent/src/agent/core/skill_manager.py
```

### Root Path: Git Toplevel

Use `$(git rev-parse --show-toplevel)` or `$PRJ_ROOT` as the project root. All paths should be relative to this.

### Security: Unsafe Absolute Paths

**Absolute paths are considered UNSAFE** unless they match:

- `/nix/store/*` - Nix store paths (read-only, trusted)

```python
# SAFE - Nix store path
/nix/store/abc123-python-3.13.9/lib/python3.13/site-packages/pydantic/

# UNSAFE - Any other absolute path
/etc/config.yaml           # ❌
/usr/local/bin/python      # ❌
/tmp/secrets.txt           # ❌
/home/user/.ssh/id_rsa     # ❌
```

### File Operations

```bash
# Use relative paths with PRJ_ROOT
$PRJ_ROOT/assets/skills/git/tools.py
$PRJ_ROOT/docs/developer/testing.md

# NEVER use absolute paths for project files
# /Users/guangtao/...  ❌
# /home/...            ❌
```

---

## Directory Structure

```
.claude/commands/     # Slash command templates
agent/skills/*/       # Skill implementations (tools.py + prompts.md)
docs/                 # Documentation (see docs/skills.md for index)
.cache/               # Repomix skill contexts (auto-generated)
```
