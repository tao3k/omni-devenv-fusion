# What is omni-devenv-fusion?

> Exploring the potential of AI and LLMs in software development

---

## The Problem: Generic Genius Fallacy

LLMs like Claude are incredibly smart, but they're **contextually blind** to project-specific constraints.

| Generic Agent | Our Reality |
|---------------|-------------|
| "I'll create a `requirements.txt`" | We use `pyproject.toml` with `uv` |
| "Here's the fix" | Fix is valid only if it passes `just validate` |
| "Configure Docker" | We use `devenv.nix` |

Without a custom layer, we spend 50% of our time "fighting" the AI to follow our rules.

---

## The Solution: The "Bridge" Pattern

We built a **Policy Engine** and **Context Adapter** that translates generic LLM capabilities into project-compliant execution.

```
User Request
    ↓
Orchestrator (The "Brain")
    ├─ get_codebase_context → Holistic project view
    ├─ consult_specialist → Route to personas
    └─ delegate_to_coder → Bridge to Coder
    ↓
Expert Personas
    ├─ architect → Design decisions
    ├─ platform_expert → Nix/infrastructure
    ├─ devops_mlops → CI/CD
    ├─ sre → Security/Reliability
    └─ tech_writer → Documentation standards
    ↓
Coder (The "Hands")
    ├─ ast_search → Structural code search
    ├─ ast_rewrite → AST-based refactoring
    └─ save_file → Safe file operations
    ↓
Validate & Commit
```

---

## Why omni-devenv-fusion?

### 1. Institutional Knowledge
The Bridge understands our stack, standards, and history—so every interaction is **project-aware**.

### 2. Quality Assurance
Personas act as guardrails. An `architect` review prevents bad infrastructure decisions. An `sre` review catches security issues.

### 3. Automation without Sacrifice
We automate workflows (`just agent-commit`, `run_task`) without losing engineering rigor.

### 4. Living Documentation
Writing standards are enforced via `tech_writer` persona and `polish_text` tool—documentation stays clean automatically.

### 5. Safe Experimentation
`safe_sandbox` and `run_task` allow exploration without risking the repository.

---

## Core Capabilities

| Capability | Tool | Purpose |
|------------|------|---------|
| **Context Aggregation** | `get_codebase_context` | Holistic view without N+1 latency |
| **Expert Consultation** | `consult_specialist` | Route to specialized personas |
| **Documentation** | `polish_text` | Enforce writing standards |
| **Code Quality** | `ast_search/rewrite` | Surgical, structural changes |
| **Safe Execution** | `run_task` | Sandboxed `just` commands |
| **Memory** | `memory_garden` | Long-term project memory |

---

## Who is this for?

Developers who want to:
- **Explore** what LLMs can do in software engineering
- **Maintain** engineering standards while leveraging AI
- **Build** custom AI workflows without losing control
- **Learn** by experimenting with MCP-based automation

---

## Key Principles

1. **The Bridge First**: Every LLM interaction goes through the Bridge (Orchestrator)
2. **Personas as Guardrails**: Different hats for different tasks
3. **Test Everything**: `just test-mcp` before every commit
4. **Write Clearly**: Follow `design/writing_style.md`
5. **Experiment Safely**: Use `safe_sandbox` for exploration

---

## Project Philosophy

> "Writing is thinking on paper." — William Zinsser

This project is not just about automation. It's about **pushing the boundaries** of what's possible when we combine:
- LLMs (intelligence)
- Nix (reproducibility)
- MCP (extensibility)
- Engineering rigor (quality)

---

## Next Steps

- Read `design/mcp-architecture-roadmap.md` for technical details
- Read `design/writing_style.md` for documentation standards
- Read `CLAUDE.md` for agent instructions
- Run `just validate` to verify your environment

---

*Built with devenv, Nix, and Claude Code*
