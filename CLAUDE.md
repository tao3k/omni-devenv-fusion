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

### Cognitive Alignment & Protocols

- **Protocol Adherence**: Strictly follow the instructions in each skill's `SKILL.md`.
- **Re-anchoring**: If you drift from the protocol or attempt unauthorized tool calls, the Gatekeeper will inject the correct `SKILL.md` rules into your context to force re-alignment.
- **Overload Management**: Avoid activating more than 5 skills simultaneously. If you see a `COGNITIVE LOAD WARNING`, disable unused skills to maintain precision.
- **Tool Selection**: Prioritize skill-specific MCP tools over generic shell commands for all write operations.

### Language

**All project content in English**: All documentation, commit messages, and committed content in this repository must be written in English (`docs/`, skill docs, code comments, commit messages). This is a persistent rule; do not add or commit non-English docs or messages.

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
Build & Verify → Full integration test
```

**Key points**:

- Rust tests are ~0.3s, Python `uv run omni ...` is ~30s
- Always add Rust tests before modifying Rust code
- **For pure Rust packages**: `cargo build` in the crate directory is sufficient
- **For Rust + Python bindings**: Use `uv sync --reinstall-package omni-core-rs`
- Pure Python changes: No rebuild needed, just run pytest

---

## Essential Commands

- `just validate` - fmt, lint, test
- `uv run pytest` - Run Python tests
- `/mcp enable orchestrator` - Reconnect omni mcp

---

## Directory Structure

```
.claude/commands/     # Slash command templates
assets/skills/*/       # Skill implementations (scanned recursively in scripts/)
docs/                 # Documentation (see docs/skills.md for index)
.cache/               # Repomix skill contexts (auto-generated)
```
