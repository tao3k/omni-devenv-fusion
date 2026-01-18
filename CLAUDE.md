# Omni-DevEnv Fusion

> One Tool + Trinity Architecture
> Single Entry Point: `@omni("skill.command")`

Quick Reference: `docs/explanation/trinity-architecture.md` | `docs/skills.md`

---

## ODF-EP Protocol (MANDATORY READ)

**All LLMs MUST read and follow `docs/reference/odf-ep-protocol.md`**

This is the complete engineering protocol for this project:

- **SSOT**: Use `SKILLS_DIR()` and `get_setting()` - NEVER `__file__` or hardcoded paths
- **Code Style**: Type hints, async-first, Google docstrings
- **Skill Structure**: SKILL.md + tools.py + scripts/ pattern
- **Naming**: kebab-case (skills), snake_case (commands/functions)

## ⛔ Critical: Git Commit

**Use `/commit` slash command** - Never `git commit` via terminal.

---

## Essential Commands

- `just validate` - fmt, lint, test
- `just build-rust-dev` - Build Rust debug bindings (fast iteration)
- `/mcp enable orchestrator` - Reconnect omni mcp

---

## Rust/Python Cross-Language Development

> **Read First**: [Project Execution Standard](../reference/project-execution-standard.md)

When debugging issues between Rust and Python (e.g., SQL query mismatches), follow the **strict workflow**:

```
Rust Implementation → Add Rust Test → cargo test PASSED
                 ↓
Python Integration → Add Python Test → pytest PASSED
                 ↓
Build & Verify → just build-rust-dev → Full integration test
```

**Key points**:

- Rust tests are ~0.3s, Python `uv run omni ...` is ~30s
- Always add Rust tests before modifying Rust code
- Use `just build-rust-dev` for fast iteration

---

## Path Handling Guidelines

### Preferred Pattern: `$PRJ_ROOT` + Relative Path

Always use **relative paths** from current location combined with `"$PRJ_ROOT"`:

```bash
# GOOD - Always quote $PRJ_ROOT (required for paths with spaces)
"$PRJ_ROOT/packages/python/agent/src/agent/core/skill_manager.py"

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
