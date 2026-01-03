# RAG Knowledge Base Usage Guide

> Keywords: rag, knowledge base, consult_knowledge_base, vector store, chromadb

## Overview

The project includes a RAG-powered knowledge base that provides contextual guidance based on project documentation.

## Auto-Activation (Default)

When the orchestrator MCP server starts, it automatically:

1. Ingests all documentation from `agent/knowledge/`, `agent/how-to/`, `docs/explanation/`
2. Bootstraps core knowledge (git workflow, coding standards, architecture)

## Manual Activation

```python
# In Claude, you can trigger knowledge loading:
await bootstrap_knowledge()  # Bootstrap core knowledge
await ingest_all_knowledge()  # Ingest all documentation
```

## Query Knowledge

```python
# Search for best practices
consult_knowledge_base("uv workspace import best practices")

# Search with domain filter
consult_knowledge_base("how to commit code", domain_filter="git")

# List all knowledge domains
list_knowledge_domains()
```

## Knowledge Sources

| Directory                              | Domain       | Content                                   |
| -------------------------------------- | ------------ | ----------------------------------------- |
| `agent/knowledge/`                     | knowledge    | Troubleshooting, patterns, best practices |
| `agent/how-to/`                        | workflow     | How-to guides and workflows               |
| `docs/explanation/`                    | architecture | Architectural decisions                   |
| `agent/knowledge/uv-best-practices.md` | uv           | UV best practices                         |

## Available Tools

| Tool                       | Description                              |
| -------------------------- | ---------------------------------------- |
| `consult_knowledge_base()` | Semantic search across project knowledge |
| `ingest_knowledge()`       | Add new knowledge to the vector store    |
| `bootstrap_knowledge()`    | Initialize core knowledge base           |
| `list_knowledge_domains()` | List all collections and counts          |
| `search_project_rules()`   | Search for project rules and workflows   |
