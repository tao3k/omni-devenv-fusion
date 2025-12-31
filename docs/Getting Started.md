# Getting Started with omni-devenv-fusion

> Exploring the potential of AI and LLMs in software development

---

## What is omni-devenv-fusion?

A sandbox for exploring what LLMs can do in software development. We transform Claude Code from a "smart chatbot" into an **exploratory partner** that:
- Understands our stack (Nix, devenv, Python)
- Follows our standards (Conventional Commits, Writing Standards)
- Adapts to our architecture (Modular, Orchestrated)
- Learns from our history (Lessons, ADRs)

This is not just about automation—it's about **pushing the boundaries** of AI-assisted engineering.

## The "Bridge" Pattern

```
User Request
    ↓
Orchestrator (Plan & Delegate)
    ↓
Expert Personas (Consult)
    ├─ architect → Design decisions
    ├─ platform_expert → Nix/infrastructure
    ├─ devops_mlops → CI/CD
    ├─ sre → Security/Reliability
    └─ tech_writer → Documentation
    ↓
Coder (Implement with AST)
    ↓
Validate & Commit
```

## Prerequisites

- **Nix** with flakes enabled
- **direnv** (for auto-loading the environment)
- **just** (command runner)
- **uv** (Python package manager)

## Initial Setup

```bash
# 1. Clone and enter
git clone https://github.com/tao3k/omni-devenv-fusion.git
cd omni-devenv-fusion

# 2. Allow direnv to load the environment
direnv allow .

# 3. Verify setup
just info
```

## Core Concepts

### Dual-MCP Architecture

This project uses two MCP servers:

| Server | File | Purpose |
|--------|------|---------|
| **Orchestrator** | `mcp-server/orchestrator.py` | Macro planning, persona delegation |
| **Coder** | `mcp-server/coder.py` | Surgical code operations |

**Workflow:**
```
User -> Orchestrator (plan) -> Coder (implement) -> Validate -> User
```

### Personas

Specialized AI experts accessible via `consult_specialist`:

| Persona | When to Use |
|---------|-------------|
| `architect` | Design decisions, refactoring strategies |
| `platform_expert` | Nix, devenv, infrastructure |
| `devops_mlops` | CI/CD, pipelines, ML workflows |
| `sre` | Security, reliability, performance |
| `tech_writer` | Documentation polishing |

### Writing Standards

All documentation follows `design/writing_style.md`:

- **BLUF**: Lead with the most important information
- **Strip Clutter**: Cut unnecessary words
- **Active Voice**: Use active verbs
- **Be Specific**: Avoid vague words

## Daily Workflow

### 1. Start Your Session

```bash
# Check environment health
just health

# View available commands
just
```

### 2. Make Changes

```bash
# Validate before committing
just validate

# Non-interactive commit (for AI agents)
just agent-commit "feat" "" "add new feature"
```

### 3. Run Tests

```bash
# MCP server tests
just test-mcp

# Orchestrator tests
uv run python mcp-server/tests/test_basic.py

# Coder tests
uv run python mcp-server/tests/test_basic.py --coder
```

### 4. Document Changes

Use the `polish_text` tool to polish documentation:

```python
# Via MCP
polish_text(text="rough draft...", context="readme")
```

Or consult the Tech Writer persona:

```python
consult_specialist(role="tech_writer", query="Polish this text...")
```

## Project Structure

```
omni-devenv-fusion/
├── mcp-server/
│   ├── orchestrator.py    # Orchestrator MCP server
│   ├── coder.py           # Coder MCP server
│   ├── mcp_core/          # Shared MCP core library
│   └── tests/             # Test suites
├── design/                # Design documents
├── docs/                  # Documentation
├── units/modules/         # Nix modules
├── CLAUDE.md              # Agent instructions
├── devenv.nix             # Devenv config
└── justfile               # Task runner
```

## Key Commands

| Command | Purpose |
|---------|---------|
| `just validate` | Run all checks (fmt, lint, test) |
| `just agent-commit` | Non-interactive commit |
| `just test-mcp` | Test MCP servers |
| `just health` | Environment health check |
| `just bump-minor` | Bump minor version |

## Troubleshooting

### direnv not loading

```bash
direnv allow .
```

### MCP server fails to start

```bash
just test-mcp
```

Check `.mcp.json` configuration.

### Tests failing

```bash
uv run python -m compileall mcp-server/
```

Verify syntax.

## Next Steps

- Read `design/mcp-architecture-roadmap.md` for architecture details
- Read `design/writing_style.md` for documentation standards
- Explore `CLAUDE.md` for agent instructions

---

*Built with devenv, Nix, and Claude Code*
