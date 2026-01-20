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

| Document                                                          | Description                                   |
| ----------------------------------------------------------------- | --------------------------------------------- |
| [Version Control](./reference/versioning.md)                      | Monorepo versioning with hatch-vcs + Justfile |
| [MCP Orchestrator](./reference/mcp-orchestrator.md)               | Omni MCP tool configuration and usage         |
| [MCP Best Practices](./reference/mcp-best-practices.md)           | MCP server design patterns and anti-patterns  |
| [Documentation Standards](./reference/documentation-standards.md) | Doc guidelines for this project               |
| [ODF-EP Protocol](./reference/odf-ep-protocol.md)                 | MANDATORY for LLMs - Engineering Protocol     |
| [Skill Discovery](./developer/discover.md)                        | Vector-Enhanced Discovery & Hot Reload        |
| [CLI Reference](./reference/cli.md)                               | Omni run, omni run exec commands              |

---

## Developer

Internal documentation for Omni-Dev Fusion developers.

| Document                                                      | Description                                       |
| ------------------------------------------------------------- | ------------------------------------------------- |
| [Skill Discovery](./developer/discover.md)                    | Vector-Enhanced Discovery & Hot Reload            |
| [Testing Guide](./developer/testing.md)                       | Test system architecture and developer guide      |
| [CLI Guide](./developer/cli.md)                               | CLI developer documentation                       |
| [MCP Core Architecture](./developer/mcp-core-architecture.md) | Shared library architecture guide                 |
| [LangGraph Builder](./developer/langgraph-builder.md)         | DynamicGraphBuilder API for workflow construction |

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
| **Omni Loop** | CCA Runtime                    | [Omni Loop](./human/architecture/omni-loop.md)                         | Active |

---

## LangGraph Workflows

Building complex workflows with DynamicGraphBuilder:

| Document                                                  | Description                               |
| --------------------------------------------------------- | ----------------------------------------- |
| [LangGraph Builder API](./developer/langgraph-builder.md) | DynamicGraphBuilder API reference         |
| [Workflow Guide](./llm/langgraph-workflow-guide.md)       | LLM guide for writing LangGraph workflows |

---

## LLM Guides

Guides specifically for LLMs interacting with the system:

| Document                                    | Description                               |
| ------------------------------------------- | ----------------------------------------- |
| [Skill Discovery](./llm/skill-discovery.md) | How LLMs discover and use skills          |
| [Routing Guide](./llm/routing-guide.md)     | How routing works with confidence scoring |
| [Memory Context](./llm/memory-context.md)   | Memory hierarchy and usage patterns       |

---

## Related

| Document                                       | Description                           |
| ---------------------------------------------- | ------------------------------------- |
| [Skills Directory](../assets/skills/README.md) | Skill packages and commands reference |
