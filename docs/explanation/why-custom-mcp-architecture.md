# Philosophy: Why Build a Custom MCP Architecture?

> **Summary**: General-purpose AI models are talented "Contractors," but they lack the "Institutional Knowledge" of our environment. Our custom MCP architecture acts as the **Bridge** that translates generic intelligence into project-compliant execution.

---

## 1. The Context (The "Why")

### The Pain Point

When we started using standard MCP, we hit a wall. Standard MCP tools are isolated—like a series of one-on-one phone calls where each participant only hears their own ring.

```bash
# You ask the AI
> Create a Python service with Docker

# Standard MCP creates this (wrong stack!)
> pip install -r requirements.txt
> docker build -t myapp .
> Dockerfile
# But we use: uv + pyproject.toml + devenv.nix!
```

The "Git" tool didn't know about our "Nix" standards. The "Python" tool didn't understand our dependency management. They are siloed.

### The Goal

We needed a way to glue them together. We needed an AI that understood:

| Domain | Our Standard |
|--------|--------------|
| Dependencies | `uv` + `pyproject.toml` |
| Containerization | `devenv.nix` |
| Code quality | `ast-grep`, `ruff`, `nixfmt` |
| Commits | Conventional Commits |

---

## 2. The Mental Model (The "What")

### The Analogy

Think of our custom architecture as a **General Contractor** on a construction site.

| Role | Description |
|------|-------------|
| **Specialized Subcontractors** | Individual MCP servers (Git, Docker, Python) - each has one specialty |
| **General Contractor** | The Orchestrator - coordinates all subcontractors, translates between them |
| **Blueprint** | CLAUDE.md - the institutional knowledge that guides every decision |

Instead of a series of one-on-one phone calls, imagine a **conference call**. When the Git tool speaks, the Nix tool hears it. The Orchestrator ensures every tool speaks "our language."

### The Diagram

```
User Request
      ↓
┌─────────────────┐
│   Orchestrator  │  ← The General Contractor
│   (The Bridge)  │
└────────┬────────┘
         │
    ┌────┴────┬─────────────┐
    ↓         ↓             ↓
┌───────┐ ┌───────┐    ┌──────────┐
│ Git   │ │ Nix   │    │ Python   │
│ Tool  │ │ Tool  │    │ Tool     │
└───────┘ └───────┘    └──────────┘
```

---

## 3. How It Works (The Mechanics)

### Contextual Adaptation (Solving "N+1" Latency)

Standard MCP implementations suffer from the "N+1" problem:

| Step | Standard MCP | Our Bridge |
|------|--------------|------------|
| 1 | List directory | Fetch entire module structure via Repomix |
| 2 | Read file A | Skip - already have context |
| 3 | Read file B | Skip - already have context |
| ... | N+1 calls | 1 call |

**Our Innovation**: Integrated **Repomix** directly into `get_codebase_context`. The Orchestrator fetches a "Dense XML Map" of the entire module structure in a single turn.

### Policy Enforcement (The SOP Guardrails)

We don't just want code; we want **compliant** code.

| Capability | Implementation |
|------------|----------------|
| **Personas as Guardrails** | Specialized personas (`Architect`, `SRE`, `Platform Expert`) force the model to "put on a specific hat" before answering |
| **Workflow Enforcement** | The Orchestrator follows `Plan -> Consult -> Execute`. It rejects "cowboy coding" by requiring architectural consultation first |

### Tool Aggregation (Unified Interface)

Instead of exposing raw CLI commands, we expose **Semantic Actions**:

| Raw Command | Semantic Action |
|-------------|-----------------|
| `git commit -m "fix"` | `just agent-commit fix "" "correct import"` |
| `ast-grep -p pattern` | `ast_rewrite` tool with AST validation |
| `find . -name "*.py"` | `search_files` with project-aware filtering |

---

## 4. Design Decisions & Trade-offs

| Decision | Why We Chose It (Pros) | What We Sacrificed (Cons) |
|----------|------------------------|---------------------------|
| **Dual-MCP Architecture** | Separation of concerns (Orchestrator plans, Coder executes) | More complex setup for new contributors |
| **Nix-based devenv** | Reproducible, declarative environments | Steeper learning curve for non-Nix users |
| **ast-grep for refactoring** | Structural changes, no regex nightmares | Requires learning AST patterns |
| **Persona delegation** | Domain expertise per query | Slight latency from persona routing |

---

## 5. The Dual-Architecture Strategy

Why separate the system into **Orchestrator** and **Coder**?

| Feature | Server A: Orchestrator | Server B: Coder |
|---------|------------------------|-----------------|
| **Analogy** | The Tech Lead / PM | The Senior Engineer |
| **Focus** | Process, Architecture, Reliability | Syntax, AST, Performance |
| **Context** | Macro (File Tree, Docs) | Micro (Function Body, AST) |
| **Tools** | Repomix, backlog-md, just | ast-grep, ruff, tree-sitter |
| **Value** | Ensures we build the **Right Thing**. | Ensures we build the Thing **Right**. |

---

## 6. Future Vision: From Tool to Digital Organism

We are evolving this system into a self-correcting, adaptive **Digital Organism**.

### Organizational Memory (The Learning Loop)

```bash
# When just validate fails
> Orchestrator records: {"error": "nixfmt failed", "solution": "run nix fmt first"}

# Future warning
> Architect Persona: "Before committing, run nix fmt to avoid validation failures."
```

### Adversarial Quality Assurance (Red Teaming)

A new **`Critic` Persona** finds flaws in the Architect's plan before they become bugs.

### Cost-Aware Routing

| Query Type | Model/Tool |
|------------|------------|
| Formatting changes | local model (Mistral) |
| Linting | ruff, nixfmt |
| Architectural decisions | Claude 3.5 Sonnet |

---

## Related Documentation

* [Tutorial: Getting Started with Omni-DevEnv](../docs/tutorials/getting-started.md)
* [Explanation: Why Omni-DevEnv?](../docs/explanation/why-omni-devenv.md)
* [MCP Architecture Roadmap](./mcp-architecture-roadmap.md)

---

*Built on standards. Not reinventing the wheel.*
