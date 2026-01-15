# Omni-DevEnv Documentation

> Explore the potential of AI and LLMs in your software development lifecycle.

We organized our docs into four categories. Find what you need:

---

## Tutorials

Learning-oriented. Step-by-step lessons to get you running.

| Document                                          | Description                                           |
| ------------------------------------------------- | ----------------------------------------------------- |
| [Getting Started](./tutorials/getting-started.md) | Set up your environment and run your first MCP server |

---

## How-to Guides

Problem-oriented. Recipes for solving specific tasks.

| Document                                 | Description                                  |
| ---------------------------------------- | -------------------------------------------- |
| [Git Workflow](./how-to/git-workflow.md) | Commit conventions and Agent-Commit Protocol |

---

## Reference

Information-oriented. Technical details, API specs, and configuration options.

| Document                                                                | Description                                                       |
| ----------------------------------------------------------------------- | ----------------------------------------------------------------- |
| [Version Control](./reference/versioning.md)                            | Monorepo versioning with hatch-vcs + Justfile                     |
| [MCP Orchestrator](./reference/mcp-orchestrator.md)                     | Omni MCP tool configuration and usage                             |
| [MCP Best Practices](./reference/mcp-best-practices.md)                 | MCP server design patterns and anti-patterns                      |
| [Documentation Standards](./reference/documentation-standards.md)       | Doc guidelines for this project                                   |
| [ODF-EP Protocol](./reference/odf-ep-protocol.md)                       | MANDATORY for LLMs - Engineering Protocol                         |
| [Skills](./skills.md)                                                   | Skill architecture and development guide                          |
| [Skill Discovery](./developer/discover.md)                              | Phase 36.2 Vector-Enhanced Discovery & Phase 36.5/36.6 Hot Reload |
| [CLI Reference](./reference/cli.md)                                     | Omni run, omni run exec commands                                  |
| [The Knowledge Matrix](../assets/specs/phase70_the_knowledge_matrix.md) | Phase 70: Unified Knowledge Index                                 |
| [The Memory Mesh](../assets/specs/phase71_the_memory_mesh.md)           | Phase 71: Episodic Memory for Self-Learning                       |

---

## Developer

Internal documentation for Omni-Dev Fusion developers.

| Document                                                      | Description                                                       |
| ------------------------------------------------------------- | ----------------------------------------------------------------- |
| [Skill Discovery](./developer/discover.md)                    | Phase 36.2 Vector-Enhanced Discovery & Phase 36.5/36.6 Hot Reload |
| [Testing Guide](./developer/testing.md)                       | Test system architecture and developer guide                      |
| [CLI Guide](./developer/cli.md)                               | CLI developer documentation                                       |
| [MCP Core Architecture](./developer/mcp-core-architecture.md) | Shared library architecture guide                                 |

---

## Trinity Architecture

Phase 25-36, 52: Skill-centric agent architecture with hot reload and Swarm Engine.

| Document                                                                               | Description                                                  |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| [Phase 25: Trinity Architecture v1.0](../assets/specs/phase25_trinity_architecture.md) | Original Trinity concept - Orchestrator/Coder/Executor roles |
| [Phase 29: Trinity + Protocols](../assets/specs/phase29_trinity_protocols.md)          | Modular registry with protocol-based design                  |
| [Phase 35: Sidecar Pattern + Pure MCP](../assets/specs/phase35_sidecar_mcp.md)         | Heavy dependency isolation + native MCP server               |
| [Phase 36: Trinity v2.0 + Swarm Engine](../assets/specs/phase36_trinity_v2.md)         | Hot reload, Observer pattern, Production stability           |
| [Phase 52: The Surgeon](../assets/specs/phase52_the_surgeon.md)                        | AST-based structural editing with dry-run support            |

---

## Cognitive Trinity - Phase 69-71

Phase 69-71 completes the Cognitive Trinity with Skills, Knowledge, and Memory:

| Component     | Capability                     | Phase | Status |
| ------------- | ------------------------------ | ----- | ------ |
| **Skills**    | "I know how to do"             | 69    | ✅     |
| **Knowledge** | "I know what that is"          | 70    | ✅     |
| **Memory**    | "I remember doing that before" | 71    | ✅     |

### Core Components

| Document                                                                               | Description                             |
| -------------------------------------------------------------------------------------- | --------------------------------------- |
| [Phase 67: Adaptive Loader](./skills.md#phase-67-the-adaptive-loader-infinite-toolbox) | JIT Loading, Ghost Tools, LRU Unloading |
| [Phase 69: The Skill Mesh](./skills.md)                                                | Dynamic tool loading with Hybrid Search |
| [Phase 70: The Knowledge Matrix](../assets/specs/phase70_the_knowledge_matrix.md)      | Unified Knowledge Index                 |
| [Phase 71: The Memory Mesh](../assets/specs/phase71_the_memory_mesh.md)                | Episodic Memory for Self-Learning       |
| [CLI Reference](./reference/cli.md)                                                    | Omni run, omni run exec commands        |

---

## Rust Core Architecture

Phase 45-47, 50: High-performance Rust core with Python bindings.

| Document                                                                              | Description                                                |
| ------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [Phase 45: Rust Core Integration](../assets/specs/phase45_rust_core_integration.md)   | Monorepo structure, workspace configuration, PyO3 bindings |
| [Phase 46: The Neural Bridge](../assets/specs/phase46_the_neural_bridge.md)           | Type unification between Rust and Python                   |
| [Phase 47: The Iron Lung](../assets/specs/phase47_the_iron_lung.md)                   | Safe I/O, tokenization, GIL release patterns               |
| [Phase 50: The Cartographer (CCA-Aligned)](../assets/specs/phase50_cca_navigation.md) | AST-based code navigation with symbol extraction           |

---

## Self-Evolving Systems

Phase 39-44, 59: Autonomous agent with memory, learning, and self-improvement.

| Document                                                                                          | Description                                            |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| [Phase 39: Self-Evolving Feedback Loop](../assets/specs/phase39_self_evolving_feedback_loop.md)   | Context building with dynamic skill discovery          |
| [Phase 40: Automated Reinforcement Loop](../assets/specs/phase40_automated_reinforcement_loop.md) | Automated code improvement and reinforcement           |
| [Phase 41: Wisdom-Aware Routing](../assets/specs/phase41_wisdom_aware_routing.md)                 | Skill routing based on experience quality              |
| [Phase 42: State-Aware Routing](../assets/specs/phase42_state_aware_routing.md)                   | Dynamic routing based on agent state                   |
| [Phase 43: Holographic Agent](../assets/specs/phase43_holographic_agent.md)                       | Continuous state injection for persistent context      |
| [Phase 44: Experiential Agent](../assets/specs/phase44_experiential_agent.md)                     | Skill-level episodic memory for learning from mistakes |
| [Phase 59: The Meta-Agent](../assets/specs/phase59_the_meta_agent.md)                             | Autonomous Build-Test-Improve loop (Self-Healing)      |

---

## Explanation

Understanding-oriented. Deep dives into architecture and design philosophy.

| Document                                                                      | Description                                                                              |
| ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| [Design Philosophy](./design-philosophy.md)                                   | Two interaction patterns (Memory Loading vs Query)                                       |
| [Why Fusion Exists](./explanation/why-fusion-exists.md)                       | The Silo Problem - why standard tools aren't enough                                      |
| [Why Nix Is the Agent Runtime](./explanation/why-nix-is-the-agent-runtime.md) | The three paths to Agentic Infrastructure                                                |
| [Why Nix for AI?](./explanation/why-nix-for-ai.md)                            | The Technical Bet - reproducibility as foundation                                        |
| [Vision: Agentic OS](./explanation/vision-agentic-os.md)                      | The Endgame - from IDE to Agentic OS                                                     |
| [Why Omni-DevEnv?](./explanation/why-omni-devenv.md)                          | Core value proposition and solutions                                                     |
| [Trinity Architecture](./explanation/trinity-architecture.md)                 | Phase 36 v2.0 - Orchestrator/Coder/Executor Pattern + Phase 39/40 Self-Evolving Feedback |
| [MCP Architecture Roadmap](../design/mcp-architecture-roadmap.md)             | Technical architecture and future vision                                                 |

---

## Writing Standards

We maintain world-class documentation quality:

| Resource                                                                   | Description                           |
| -------------------------------------------------------------------------- | ------------------------------------- |
| [Writing Style Index](../design/writing-style/00_index.md)                 | Entry point for our writing standards |
| [Module 01: Philosophy](./design/writing-style/01_philosophy.md)           | Feynman (clarity), Zinsser (humanity) |
| [Module 02: Mechanics](./design/writing-style/02_mechanics.md)             | Rosenberg (precision, active voice)   |
| [Module 03: Structure & AI](./design/writing-style/03_structure_and_ai.md) | Claude (Markdown hierarchy, Few-Shot) |

---

## Quick Navigation

```
📖 Docs           → docs/index.md (you are here)
🎓 Tutorials      → docs/tutorials/
🧠 Explanation    → docs/explanation/
🏗 Architecture   → docs/explanation/mcp-architecture-roadmap.md
```

**For AI Agents**: See [agent/](../agent/) directory for LLM context (specs, how-to, standards).

```

---

*Built on standards. Not reinventing the wheel.*
```
