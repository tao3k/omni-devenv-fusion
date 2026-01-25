# Omni-Dev-Fusion Documentation

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

| Document                                                          | Description                                  |
| ----------------------------------------------------------------- | -------------------------------------------- |
| [MCP Orchestrator](./reference/mcp-orchestrator.md)               | Omni MCP tool configuration and usage        |
| [MCP Best Practices](./reference/mcp-best-practices.md)           | MCP server design patterns and anti-patterns |
| [Documentation Standards](./reference/documentation-standards.md) | Doc guidelines for this project              |
| [ODF-EP Protocol](./reference/odf-ep-protocol.md)                 | MANDATORY for LLMs - Engineering Protocol    |
| [CLI Reference](./reference/cli.md)                               | Omni run, omni run exec commands             |
| [Code Tools Skill](./reference/code-tools.md)                     | AST-based code navigation and refactoring    |
| [AST-Based Search](./reference/ast-grep.md)                       | ast-grep patterns and Cartographer/Hunter    |
| [Skill Generator](./reference/skill-generator.md)                 | Hybrid skill generator (Jinja2 + LLM)        |

---

## Developer

Internal documentation for Omni-Dev Fusion developers.

| Document                                                      | Description                                  |
| ------------------------------------------------------------- | -------------------------------------------- |
| [Skill Discovery](./developer/discover.md)                    | Skill discovery (MIGRATION GUIDE)            |
| [Testing Guide](./developer/testing.md)                       | Test system architecture and developer guide |
| [CLI Guide](./developer/cli.md)                               | CLI developer documentation (OUTDATED)       |
| [MCP Core Architecture](./developer/mcp-core-architecture.md) | Shared library architecture guide            |
| [Routing Guide](./developer/routing.md)                       | Routing architecture (MIGRATION GUIDE)       |

---

## Trinity Architecture

Skill-centric agent architecture with hot reload and DynamicGraphBuilder.

| Document                                                           | Description                                           |
| ------------------------------------------------------------------ | ----------------------------------------------------- |
| [Trinity Core](./human/architecture/trinity-core.md)               | Core architecture - Orchestrator/Coder/Executor roles |
| [Skills Architecture](./human/architecture/skills-architecture.md) | Complete skills guide - start here                    |
| [Skill Standard](./human/architecture/skill-standard.md)           | Living Skill Architecture and standards               |
| [Skill Lifecycle](./human/architecture/skill-lifecycle.md)         | LangGraph workflow support and patterns               |

---

## Cognitive Trinity

Skills, Knowledge, and Memory integration:

| Component     | Capability                     | Document                                                               | Status |
| ------------- | ------------------------------ | ---------------------------------------------------------------------- | ------ |
| **Skills**    | Composable capability packages | [Skill Standard](./human/architecture/skill-standard.md)               | Active |
| **Knowledge** | Unified Knowledge Index        | [Knowledge Matrix](./human/architecture/knowledge-matrix.md)           | Active |
| **Memory**    | Episodic Memory                | [Memory Mesh](./human/architecture/memory-mesh.md)                     | Active |
| **Cognition** | CCA Runtime                    | [Cognitive Scaffolding](./human/architecture/cognitive-scaffolding.md) | Active |
| **Omni Loop** | CCA Runtime                    | [Omni Loop](./human/architecture/omni-loop.md)                         | ACTIVE |
| **Pipeline**  | System Prompt Assembly         | [Cognitive Pipeline](./explanation/cognitive-pipeline.md)              | NEW    |

---

## LLM Guides

Guides specifically for LLMs interacting with the system:

| Document                                  | Description                               |
| ----------------------------------------- | ----------------------------------------- |
| [Routing Guide](./llm/routing-guide.md)   | How routing works with confidence scoring |
| [Memory Context](./llm/memory-context.md) | Memory hierarchy and usage patterns       |

---

## Architecture

Detailed codebase structure and architecture documentation.

| Document                                                   | Description                                        |
| ---------------------------------------------------------- | -------------------------------------------------- |
| [Codebase Structure](./architecture/codebase-structure.md) | Complete directory tree and file descriptions      |
| [Rust Crates](./architecture/rust-crates.md)               | Rust crates reference with modules and performance |
| [Skills System](./architecture/skills.md)                  | Zero-Code skill architecture and development guide |
| [Kernel Architecture](./architecture/kernel.md)            | Microkernel engine, lifecycle management           |
| [Router Architecture](./architecture/router.md)            | Semantic routing system (OmniRouter, HiveRouter)   |
| [MCP-Server Architecture](./architecture/mcp-server.md)    | MCP protocol implementation                        |

---

## Related

| Document                                       | Description                           |
| ---------------------------------------------- | ------------------------------------- |
| [Skills Directory](../assets/skills/README.md) | Skill packages and commands reference |
