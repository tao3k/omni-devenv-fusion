# Omni-Dev-Fusion Documentation

> AI and LLMs in your software development lifecycle. One entry point, project-aware skills, semantic routing, MCP-native.

**Start here:** [Getting Started](./tutorials/getting-started.md) · **Reference index:** [Reference (by domain)](./reference/README.md) · **Progress:** [Backlog](./backlog.md)

---

## Tutorials

| Document                                          | Description                                                                 |
| ------------------------------------------------- | --------------------------------------------------------------------------- |
| [Getting Started](./tutorials/getting-started.md) | Set up environment (Nix + direnv, uv), generate skill index, run MCP server |

---

## How-to Guides

| Document                                                           | Description                                                          |
| ------------------------------------------------------------------ | -------------------------------------------------------------------- |
| [Git Workflow](./reference/odf-ep-protocol.md#git-workflow)        | Commit conventions and Agent-Commit Protocol (ODF-EP § Git Workflow) |
| [Knowledge MCP query paper](./how-to/knowledge-mcp-query-paper.md) | Query papers via MCP knowledge tools                                 |
| [Run the Rust agent](./how-to/run-rust-agent.md)                   | Verification checklist: gateway, stdio, repl, MCP, memory            |

---

## Reference

Technical specs, contracts, configuration. **Full list by domain:** [reference/README.md](./reference/README.md).

### Essential (mandatory for contributors)

| Document                                                                | Description                                                         |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------- |
| [ODF-EP Protocol](./reference/odf-ep-protocol.md)                       | **MANDATORY for LLMs** — Engineering Protocol (style, testing, git) |
| [Project Execution Standard](./reference/project-execution-standard.md) | **MANDATORY** — Rust/Python workflow, SSOT paths, build/test        |
| [ODF-REP Protocol](./reference/odf-rep-protocol.md)                     | RAG, memory, knowledge indexing                                     |
| [Documentation Standards](./reference/documentation-standards.md)       | Doc guidelines for this project                                     |
| [CLI Reference](./reference/cli.md)                                     | `omni run`, `omni db`, and main commands                            |

### By topic

- **MCP & Skills:** [MCP Orchestrator](./reference/mcp-orchestrator.md), [MCP Tool Schema](./reference/mcp-tool-schema.md), [Skill Data Hierarchy](./reference/skill-data-hierarchy-and-references.md), [Extension System](./reference/extension-system.md), [Skill Generator](./reference/skill-generator.md), [Code Tools](./reference/code-tools.md), [AST-Based Search](./reference/ast-grep.md)
- **Channels:** [Telegram Channel](./reference/telegram-channel.md), [Discord Channel](./reference/discord-channel.md) — provider-specific runtime, allowlists, control-command authorization, and ingress contracts
- **Router & Search:** [Search Systems](./reference/search-systems.md), [Weighted RRF](./reference/weighted-rrf.md), [Vector/Router Schema Contract](./reference/vector-router-schema-contract.md), [Librarian](./reference/librarian.md)
- **Vector & LanceDB:** [LanceDB Query-Release Lifecycle](./reference/lancedb-query-release-lifecycle.md), [LanceDB Version and Roadmap](./reference/lancedb-version-and-roadmap.md), [Vector Store API](./reference/vector-store-api.md)
- **Knowledge & Memory:** [Librarian](./reference/librarian.md), [Memory Module](./reference/memory-module.md), [Omni-Agent Memory Self-Evolution and Self-Repair](./reference/omni-agent-memory-self-evolution-self-repair.md), [LinkGraph to IWE Migration Feasibility and Blueprint](./reference/link-graph-to-iwe-migration-feasibility-and-blueprint.md)
- **Testing & Execution:** [Test Kit](./reference/test-kit.md), [Project Execution Standard](./reference/project-execution-standard.md), [Nickel/Rust Responsibilities](./reference/nickel-rust-responsibilities.md)

---

## Developer

| Document                                                                      | Description                               |
| ----------------------------------------------------------------------------- | ----------------------------------------- |
| [Backlog](./backlog.md)                                                       | Feature status and what to implement next |
| [Testing Guide](./developer/testing.md)                                       | Test system and developer guide           |
| [CLI Guide](./developer/cli.md)                                               | CLI developer documentation               |
| [Skill Discovery](./developer/discover.md)                                    | Skill discovery implementation            |
| [Routing](./developer/routing.md)                                             | Routing architecture                      |
| [MCP Core Architecture](./developer/mcp-core-architecture.md)                 | Shared library and MCP core               |
| [Knowledge Search Improvements](./developer/knowledge-search-improvements.md) | Knowledge search improvements             |

---

## Architecture

### Codebase and systems

| Document                                                              | Description                                                             |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| [Codebase Structure](./architecture/codebase-structure.md)            | Directory tree and file roles                                           |
| [Architecture by Package Storage](./architecture/packages-storage.md) | `packages/` layout, Python/Rust source paths, dependency flow           |
| [Rust Crates](./architecture/rust-crates.md)                          | Rust crates reference (omni-vector, omni-tokenizer, omni-scanner, etc.) |
| [Skills System](./architecture/skills.md)                             | Zero-code skill architecture                                            |
| [Router Architecture](./architecture/router.md)                       | Semantic routing (OmniRouter, hybrid search)                            |
| [MCP-Server Architecture](./architecture/mcp-server.md)               | MCP protocol implementation                                             |
| [Kernel Architecture](./architecture/kernel.md)                       | Microkernel engine and lifecycle                                        |

### Trinity and cognition

Skills, Knowledge, and Memory:

| Component     | Document                                                                                                                                                                                 | Notes                                 |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| **Skills**    | [Skill Standard](./human/architecture/skill-standard.md), [Skills Architecture](./human/architecture/skills-architecture.md), [Skill Lifecycle](./human/architecture/skill-lifecycle.md) | Composable capabilities, hot reload   |
| **Knowledge** | [Knowledge Matrix](./human/architecture/knowledge-matrix.md)                                                                                                                             | Unified index (LinkGraph + Librarian) |
| **Memory**    | [Memory Mesh](./human/architecture/memory-mesh.md), [Skill Memory](./human/architecture/skill-memory.md)                                                                                 | Episodic and project memory           |
| **Runtime**   | [Omni Loop](./human/architecture/omni-loop.md), [Cognitive Scaffolding](./human/architecture/cognitive-scaffolding.md), [Cognitive Pipeline](./explanation/cognitive-pipeline.md)        | CCA runtime, prompt assembly          |

---

## LLM Guides

| Document                                    | Description                              |
| ------------------------------------------- | ---------------------------------------- |
| [Routing Guide](./llm/routing-guide.md)     | How routing works and confidence scoring |
| [Memory Context](./llm/memory-context.md)   | Memory hierarchy and usage               |
| [Skill Discovery](./llm/skill-discovery.md) | Skill discovery for LLMs                 |

---

## Milestones

| Document                                                                                                                | Description                                                                             |
| ----------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| [Unified Search & Contracts (Feb 2026)](./milestones/2026-02-unified-search-and-contracts.md)                           | Router/retrieval contracts, route explain API, keyword backend decision — **completed** |
| [Omni-Vector Optimization & Arrow-Native (Feb 2026)](./milestones/2026-02-omni-vector-optimization-and-arrow-native.md) | Parallel hybrid search, Arrow-native schema — **completed**                             |
| [UltraRAG-Style Ingest — Completed](./milestones/ultrarag-style-ingest-completed.md)                                    | Idempotent ingest, Rust chunking, full_document recall, optional images — **completed** |

---

## Plans and Backlog

| Document                                                                                                                        | Description                                                                                                                                      |
| ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| [Backlog](./backlog.md)                                                                                                         | **Single source** for feature status and priorities                                                                                              |
| [UltraRAG-Style Ingest — Completed](milestones/ultrarag-style-ingest-completed.md)                                              | Ingest pipeline (Rust chunking, idempotent write, full_document recall); see [Backlog](backlog.md#ultrarag-style-ingest-complete-implementation) |
| [Omega + Graph + Loop/ReAct Rust Unification](./plans/omega-graph-react-rust-unification.md)                                    | Unified Rust runtime blueprint and migration rules for removing Python runtime loops safely                                                      |
| [Xiuxian-Qianhuan Injection + Memory Self-Evolution + Reflection](./plans/knowledge-injection-memory-evolution-architecture.md) | Typed injection architecture, policy contracts, and rollout plan for Rust runtime integration                                                    |
| [Xiuxian-Qianhuan Unified Workflow Audit](./plans/xiuxian-qianhuan-unified-workflow-audit.md)                                   | One-page auditable architecture view across Omega, Graph, ReAct, injection, memory, and knowledge boundaries                                     |
| [Xiuxian-Qianhuan Paper Optimization Notes (arXiv 2025-2026)](./plans/xiuxian-qianhuan-paper-optimization-notes.md)             | Two-pass paper review (quick read + deep compare) with code-level gap matrix and pre-implementation optimization backlog                         |
| [Xiuxian-Qianhuan Implementation Rollout Plan](./plans/xiuxian-qianhuan-implementation-rollout.md)                              | A0-A7 execution sequence with data-plane contract, discover confidence contract, and measurable rollout gates                                    |

---

## Testing

| Document                                                                             | Description                                                   |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| [Testing Guide](./developer/testing.md)                                              | Main testing guide                                            |
| [Test Kit](reference/test-kit.md)                                                    | Fixtures and utilities                                        |
| [Keyword Backend Decision](testing/keyword-backend-decision.md)                      | Canonical Tantivy vs Lance FTS decision                       |
| [Omni-Agent Live Multi-Group Runbook](testing/omni-agent-live-multigroup-runbook.md) | Standardized `Test1/Test2/Test3` live black-box evidence flow |
| [Testing folder](testing/README.md)                                                  | What each testing doc is for; reports vs canonical            |

---

## Related

| Document                                                  | Description                                                                        |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| [Skills Directory](../assets/skills/README.md)            | Skill packages and commands                                                        |
| [Why Omni-Dev Fusion](explanation/why-omni-dev-fusion.md) | Scenarios and value proposition                                                    |
| [Why Nix](explanation/why-nix.md)                         | Nix for environment and build; Nickel + Nix for safe, efficient skill environments |
