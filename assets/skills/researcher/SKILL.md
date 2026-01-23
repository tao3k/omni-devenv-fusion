---
name: "researcher"
version: "1.1.0"
description: "Deep research capabilities for analyzing, mapping, and digesting external code repositories using Repomix and LangGraph-powered cognitive workflows."
routing_keywords:
  [
    "analyze_repo",
    "git_clone",
    "research_github",
    "repomix",
    "code_analysis",
    "repository_map",
    "compress_code",
    "read_codebase",
    "compare_architecture",
    "deep_research",
    "llm_analysis",
  ]
authors: ["omni-dev-fusion"]
intents:
  [
    "research_repository",
    "analyze_codebase",
    "compare_architecture",
    "deep_research",
  ]
permissions: []
---

# Researcher Tools

Deep research capabilities for analyzing external code repositories. Designed for the Map -> Zoom -> Compare -> Harvest workflow.

## Tools

### run_research_graph

[CORE] Execute the Deep Research LangGraph workflow. Uses LLM reasoning to dynamically decide what to look at, what to read, and how to analyze.

**Workflow:**

1. Clone repository to sandbox
2. Map file structure (god view)
3. Scout: LLM decides what to read based on architecture analysis
4. Digest: Compress selected code into LLM-friendly format
5. Synthesize: Generate deep analysis report comparing with Omni-Dev patterns
6. Save report to harvested knowledge base

**Parameters:**

- `repo_url` (string, required): Git repository URL to analyze
- `request` (string, optional): Specific analysis goal (default: "Analyze the architecture")

**Returns:** Research report with analysis and report path

### clone_repo

Clone a remote git repository to a temporary research workspace for analysis.

**Parameters:**

- `url` (string, required): The Git URL of the repository
- `branch` (string, optional): Specific branch to clone

**Returns:** Local path to the cloned repository

### repomix_map

Generate a lightweight file tree structure of the repository. Use this FIRST to understand the project layout.

**Parameters:**

- `path` (string, required): Local path to the repository
- `max_depth` (integer, optional): Depth of the tree (default: 5)

**Returns:** ASCII file tree representation

### repomix_compress

Compress selected files into a single context-friendly XML block.

**Noise Reduction:** Supports removing comments and empty lines for cleaner output.

**Parameters:**

- `path` (string, required): Local path to the repository
- `targets` (array, required): List of patterns to include
- `ignore` (array, optional): List of patterns to ignore
- `remove_comments` (boolean, optional): Remove code comments (default: false)
- `remove_empty_lines` (boolean, optional): Remove blank lines (default: true)

**Returns:** dict with `xml_content`, `char_count`, and config used

### save_report

Save the final research findings to the harvested knowledge directory.

**Parameters:**

- `repo_name` (string, required): Name of the repository analyzed
- `content` (string, required): The markdown content of the analysis
- `category` (string, optional): Category of research (default: architecture)

**Returns:** Path to saved report
