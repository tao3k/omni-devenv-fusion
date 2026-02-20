# Reference Documentation

Technical specs, contracts, and configuration. Grouped by domain.

**Start with:** [Protocols](#protocols-mandatory-for-contributors) and [Project Execution Standard](project-execution-standard.md) if you are contributing. Use the sections below to find specs by topic.

---

## Protocols (mandatory for contributors)

| Document                                              | Description                                                         |
| ----------------------------------------------------- | ------------------------------------------------------------------- |
| [ODF-EP Protocol](odf-ep-protocol.md)                 | **MANDATORY for LLMs** — Engineering Protocol (style, testing, git) |
| [ODF-REP Protocol](odf-rep-protocol.md)               | RAG, memory, knowledge indexing, context optimization               |
| [Documentation Standards](documentation-standards.md) | Doc guidelines for this project                                     |

---

## MCP

| Document                                                | Description                                 |
| ------------------------------------------------------- | ------------------------------------------- |
| [MCP Orchestrator](mcp-orchestrator.md)                 | Omni MCP tool configuration and usage       |
| [MCP Best Practices](mcp-best-practices.md)             | Server design patterns and anti-patterns    |
| [MCP Transport](mcp-transport.md)                       | Transport layer (stdio, SSE)                |
| [MCP Tool Schema](mcp-tool-schema.md)                   | `tools/call` result contract, shared schema |
| [MCP Sidecar Architecture](mcp-sidecar-architecture.md) | Sidecar and embedding HTTP server           |

---

## CLI & Skills

| Document                                                                      | Description                               |
| ----------------------------------------------------------------------------- | ----------------------------------------- |
| [CLI Reference](cli.md)                                                       | `omni run`, `omni db`, and main commands  |
| [Skill Generator](skill-generator.md)                                         | Hybrid skill generator (Jinja2 + LLM)     |
| [Code Tools Skill](code-tools.md)                                             | AST-based code navigation and refactoring |
| [AST-Based Search](ast-grep.md)                                               | ast-grep patterns, Cartographer/Hunter    |
| [Skill Data Hierarchy and References](skill-data-hierarchy-and-references.md) | Skill data layout and references          |
| [Skill Tool Reference Schema Audit](skill-tool-reference-schema-audit.md)     | Tool schema audit                         |
| [Tools vs Resources](tools-vs-resources.md)                                   | MCP tools vs resources distinction        |
| [Extension System](extension-system.md)                                       | Skill extensions                          |
| [Extension System LLM](extension-system-llm.md)                               | LLM-related extension behavior            |

---

## Channels

| Document                                | Description                                                    |
| --------------------------------------- | -------------------------------------------------------------- |
| [Telegram Channel](telegram-channel.md) | Telegram webhook/polling runtime, allowlists, control commands |
| [Discord Channel](discord-channel.md)   | Discord ingress runtime, allowlists, session partition         |

---

## Router & Search

| Document                                                                          | Description                                     |
| --------------------------------------------------------------------------------- | ----------------------------------------------- |
| [Search Systems](search-systems.md)                                               | When to use vector vs hybrid vs agentic search  |
| [Retrieval Namespace](retrieval-namespace.md)                                     | Unified retrieval API, backends, factory        |
| [Weighted RRF](weighted-rrf.md)                                                   | Weighted reciprocal rank fusion                 |
| [Route Test Result Shape](route-test-result-shape.md)                             | Algorithm contract: Rust → route result         |
| [Route Test Schema and Tool Attributes](route-test-schema-and-tool-attributes.md) | Route test schema and tool attributes           |
| [Route Test Benchmark](route-test-benchmark.md)                                   | Route test performance benchmark                |
| [Vector/Router Schema Contract](vector-router-schema-contract.md)                 | Tool search / vector / hybrid field definitions |
| [Routing Search Schema](routing-search-schema.md)                                 | Routing search configuration schema             |
| [Routing Search Value Flow](routing-search-value-flow.md)                         | Value flow in routing search                    |
| [Skill Routing Value Standard](skill-routing-value-standard.md)                   | Routing value standards for skills              |
| [Skills and Router Databases](skills-and-router-databases.md)                     | Two DBs: skills (full data) vs router (scores)  |

---

## Vector Store & LanceDB

| Document                                                                | Description                                                                                 |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| [LanceDB Query-Release Lifecycle](lancedb-query-release-lifecycle.md)   | **Current approach** — evict after each tool so MCP does not retain vector memory           |
| [LanceDB Version and Roadmap](lancedb-version-and-roadmap.md)           | Rust lance 2.x; phases 1–5 (scalar, maintenance, vector index, partitioning, observability) |
| [Vector Store API](vector-store-api.md)                                 | RustVectorStore, payload schemas, Arrow IPC                                                 |
| [Omni-Vector Status](omni-vector-status.md)                             | Feature matrix, Python API gaps                                                             |
| [Omni-Vector Audit and Next Steps](omni-vector-audit-and-next-steps.md) | Audit and P0–P3 priorities                                                                  |
| [Omni-Vector Phase 2 Architecture](omni-vector-phase2-architecture.md)  | Connection pool, async index build, compression                                             |

---

## Arrow & Performance

| Document                                                          | Description                                                             |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------- |
| [Arrow Integration](arrow-integration.md)                         | Zero-copy and batch paths (Rust ↔ Python); **primary Arrow reference** |
| [Python Arrow Integration Plan](python-arrow-integration-plan.md) | Roadmap to reduce JSON and adopt Arrow                                  |
| [Router & RAG Arrow Roadmap](router-rag-arrow-roadmap.md)         | Arrow status for router and RAG                                         |
| [Arrow Ecosystem Optimization](arrow-ecosystem-optimization.md)   | Arrow ecosystem optimizations                                           |
| [JSON vs Arrow Performance](json-vs-arrow-performance.md)         | Benchmark JSON path vs Arrow IPC                                        |

---

## Schemas & Contracts

| Document                                                            | Description                        |
| ------------------------------------------------------------------- | ---------------------------------- |
| [Search Result Batch Contract](search-result-batch-contract.md)     | Batch result contract              |
| [Vector Search Options Contract](vector-search-options-contract.md) | Vector search options              |
| [Schema Singularity](schema-singularity.md)                         | Single source of truth for schemas |
| [Schema Migration](schema-migration.md)                             | Schema migration approach          |
| [Rust Parsed Schemas](rust-parsed-schemas.md)                       | Rust-side schema parsing           |

---

## Knowledge & RAG

| Document                                                                                                         | Description                                                                           |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| [Librarian](librarian.md)                                                                                        | Unified knowledge (RAG) service                                                       |
| [RAG Search](rag-search.md)                                                                                      | RAG search behavior and API                                                           |
| [LinkGraph to IWE Migration Feasibility and Blueprint](link-graph-to-iwe-migration-feasibility-and-blueprint.md) | Source-audited migration plan from graph path to IWE-backed common engine             |
| [Xiuxian-Wendao Common Engine Route](xiuxian-wendao-common-engine-route.md)                                      | Modular implementation route from LinkGraph ecosystem audit (Rucola + IWE references) |
| [UltraRAG Integration Summary](ultrarag-integration-summary.md)                                                  | UltraRAG-style integration summary                                                    |

---

## Memory & Project Memory

| Document                                                                                            | Description                                                                 |
| --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| [Memory Module](memory-module.md)                                                                   | Project memory (ADR-style decisions/tasks), LanceDB-backed                  |
| [Omni-Agent Memory/Window Strategy Audit](omni-agent-memory-window-strategy-audit.md)               | Audit and next steps for memory + session window + strategy engine coupling |
| [Omni-Agent Memory Self-Evolution and Self-Repair](omni-agent-memory-self-evolution-self-repair.md) | Current architecture, event workflow, and runtime verification path         |

---

## Testing & Tracing

| Document                       | Description                      |
| ------------------------------ | -------------------------------- |
| [Execution Tracing](tracer.md) | UltraRAG-style execution tracing |
| [Test Kit](test-kit.md)        | Test fixtures and utilities      |

---

## Execution & Architecture

| Document                                                              | Description                                                  |
| --------------------------------------------------------------------- | ------------------------------------------------------------ |
| [Project Execution Standard](project-execution-standard.md)           | **MANDATORY** — Rust/Python workflow, SSOT paths, build/test |
| [Unified Execution Engine Design](unified-execution-engine-design.md) | Execution engine design                                      |
| [Cognitive Architecture](cognitive-architecture.md)                   | Cognitive layer overview                                     |
| [LangGraph UltraRAG Demo](langgraph-ultrarag-demo.md)                 | XML contracts, quality gates                                 |
| [MatureReact](maturereact.md)                                         | MatureReact pattern                                          |
| [Nickel/Rust Responsibilities](nickel-rust-responsibilities.md)       | Nix vs Rust boundaries                                       |
| [Sniffer](sniffer.md)                                                 | Intent sniffer and rules                                     |
