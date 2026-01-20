# Omni-Dev Fusion

> One Tool + Trinity Architecture
> Single Entry Point: `@omni("skill.command")`

Quick Reference: `docs/explanation/trinity-architecture.md` | `docs/skills.md`

---

## MANDATORY READING

**All LLMs MUST read these documents BEFORE making any changes:**

### 1. Engineering Protocol (Python/Rust)

**File: `docs/reference/odf-ep-protocol.md`**

Universal engineering standards:

- Code Style: Type hints, async-first, Google docstrings
- Naming Conventions: snake_case, PascalCase, UPPER_SNAKE_CASE
- Module Design: Single responsibility, import rules, dependency flow
- Error Handling: Fail fast, rich context
- Testing Standards: Unit tests required, parametrized tests
- Git Workflow: Commit format, branch naming

### 2. Project Execution Standard

**File: `docs/reference/project-execution-standard.md`**

Project-specific implementations:

- Rust/Python cross-language workflow
- Project namespace conventions and examples
- SSOT utilities: `SKILLS_DIR()`, `PRJ_DATA()`, `get_setting()`
- Build and test commands

### 3. RAG/Representation Protocol

**File: `docs/reference/odf-rep-protocol.md`**

Memory system, knowledge indexing, context optimization

---

## Critical Rules

### Git Commit

**Use `/commit` slash command** - Never `git commit` via terminal.

### Rust/Python Cross-Language Development

> **Read First**: `docs/reference/project-execution-standard.md`

Follow the **strict workflow**:

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

## Essential Commands

- `just validate` - fmt, lint, test
- `just build-rust-dev` - Build Rust debug bindings (fast iteration)
- `/mcp enable orchestrator` - Reconnect omni mcp

---

## Directory Structure

```
.claude/commands/     # Slash command templates
agent/skills/*/       # Skill implementations (tools.py + prompts.md)
docs/                 # Documentation (see docs/skills.md for index)
.cache/               # Repomix skill contexts (auto-generated)
```
