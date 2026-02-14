---
metadata:
  for_tools: researcher.run_research_graph
  title: Run Research Graph Workflow
  description: How to use the Sharded Deep Research Workflow (run_research_graph).
  routing_keywords:
    - "research"
    - "graph"
    - "workflow"
    - "url"
    - "github url"
    - "repository url"
    - "research url"
    - "repo url"
  intents:
    - "Deep research"
    - "Repository analysis"
    - "Run the sharded deep research workflow on a repo URL"
    - "Help me analyze or research a GitHub repository with a structured workflow"
    - "I want to research this repository and get an index of analyses"
---

# Run Research Graph Workflow

This document describes how to use the `run_research_graph` command.

## Overview

Execute the Sharded Deep Research Workflow. Uses a Map-Plan-Loop-Synthesize pattern to analyze large repositories that exceed LLM context limits.

## Args

- **repo_url** (required): Git repository URL to analyze.
- **request** (optional): Specific analysis goal (default: "Analyze the architecture").
- **visualize** (optional): If true, return the workflow diagram instead of running.

## Example

```python
@omni("researcher.run_research_graph", {"repo_url": "https://github.com/owner/repo", "request": "Analyze the architecture"})
```

## See also

- [SKILL.md](../SKILL.md) for the researcher skill overview.
