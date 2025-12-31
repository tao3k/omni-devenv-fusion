# Design & Roadmap: Dual-MCP Server Architecture

> **Philosophy**: Separation of Concerns. "Macro" orchestration vs. "Micro" surgical coding.

This document outlines the architectural vision for the `omni-devenv-fusion` project, moving from a single monolithic MCP server to a specialized dual-server setup. This design acts as a **Bridge** between generic LLM capabilities and the specific, strict requirements of our Nix-based project environment.

---

## 1. Architectural Overview

The system is divided into two distinct Model Context Protocol (MCP) servers, each serving a specific abstraction level.

### Server A: The Orchestrator (The "Brain")
* **Focus**: SDLC, DevOps, MLOps, SRE, Architecture, Policy Enforcement.
* **Role**: High-level decision making, project management, and context gathering.
* **Key Characteristic**: "Macro" view. Uses `Repomix` to see the forest, not the trees.

### Server B: The Coding Expert (The "Hands")
* **Focus**: High-quality code implementation, AST-based refactoring, Performance, Security.
* **Role**: Precise execution of coding tasks defined by the Orchestrator.
* **Key Characteristic**: "Micro" view. Uses `ast-grep`/`tree-sitter` for surgical precision.

---

## 2. Server A: The Orchestrator MCP

**Current Status**: Partially implemented in `mcp-server/orchestrator.py`.

### Core Responsibilities
1.  **SDLC Guardrails**: Ensuring software development follows the "Plan -> Consult -> Implement -> Validate" loop.
2.  **Context Aggregation**: Using `get_codebase_context` (Repomix) to fetch holistic project views without "N+1" tool call latency.
3.  **Specialist Delegation**: Routing queries to `Architect`, `Platform Expert`, `DevOps`, or `SRE` personas.
4.  **Execution Management**: (Future) Safely triggering `just` commands (e.g., `just agent-validate`) to verify changes.

### The "Bridge" Role
* **Contextual Adaptation**: Translates generic user requests (e.g., "Deploy to K8s") into project-specific actions (e.g., "Configure `devenv.nix` and `helm` modules").
* **Policy Enforcement**: Rejects commits that violate architectural rules defined in `CLAUDE.md`.

### Toolset Roadmap
* `consult_specialist`: (Existing) Multi-persona routing.
* `read_backlog`: (New) Integration with task tracking (e.g., `backlog-md`) to maintain project state.
* `run_task`: (New) Safe execution of `just` commands within a sandboxed environment (integration with `claudebox`).

---

## 3. Server B: The Expert Coding MCP

**Current Status**: Conceptual / To Be Implemented.

### Core Responsibilities
1.  **Surgical Refactoring**: structural code changes rather than line-based text replacement.
2.  **Quality Assurance**: Applying linters (`ruff`, `nixfmt`) and static analysis before passing code back to the Orchestrator.
3.  **Security Scanning**: Detecting hardcoded secrets or unsafe patterns before they enter the repo.

### The "Bridge" Role
* **Syntax Adaptation**: Ensures generated code matches the specific versions and style guides defined in `treefmt.toml` or `.editorconfig`.
* **Performance Optimization**: Uses specialized knowledge to optimize specific patterns (e.g., Python `uv` dependency management).

### Toolset Roadmap
* `ast_search`: Query code structure using `ast-grep` patterns (e.g., "Find all functions calling API X without error handling").
* `ast_rewrite`: Apply structural patches based on AST patterns.
* `validate_syntax`: Pre-commit syntax checks.

---

## 4. Interaction Workflow

```mermaid
sequenceDiagram
    participant User
    participant Orch as Orchestrator MCP
    participant Coder as Coding Expert MCP
    participant Repo as Codebase

    User->>Orch: "Refactor the API error handling module."
    Orch->>Orch: (Architect Persona) Analyze design patterns.
    Orch->>Orch: (Repo Context) Fetch holistic view via Repomix.
    Orch->>Coder: Delegate: "Rewrite try/except blocks in module X using pattern Y."
    Coder->>Repo: (AST-Grep) Locate and Rewrite code structurally.
    Coder-->>Orch: Return diff/result.
    Orch->>Orch: (SRE Persona) Run `just agent-validate`.
    Orch->>Repo: Commit if valid.
    Orch-->>User: "Refactoring complete and verified."
