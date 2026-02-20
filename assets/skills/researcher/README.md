# Researcher Skill

Deep research capabilities for analyzing external code repositories using LangGraph-powered cognitive workflows.

## Overview

The Researcher skill implements a **Deep Research Workflow** that uses LLM reasoning to dynamically decide:

- **What to look at** (file tree mapping)
- **What to read** (module selection with smart filtering)
- **How to analyze** (context compression and synthesis)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Research Workflow                   │
├─────────────────────────────────────────────────────────────────┤
│  clone ──► survey ──► scout ──► digest ──► synthesize ──► save │
│     │        │        │        │           │           │        │
│     ▼        ▼        ▼        ▼           ▼           ▼        │
│  Clone    Map file  Design    Compress    Generate    Save to   │
│  repo     tree     Repomix    context     report      harvested │
│                    config                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Workflow Nodes

### 1. `node_clone`

Clones the target repository to `.cache/research/{repo_name}/`.

### 2. `node_survey`

Generates a lightweight ASCII file tree (god view) of the repository.

### 3. `node_scout` (Smart Scouting)

LLM analyzes the file tree and designs a precise Repomix configuration:

```json
{
  "targets": [
    "crates/agentgateway/src/lib.rs",
    "crates/agentgateway/src/config.rs"
  ],
  "ignore": ["**/__init__.py", "**/*_test.py", "**/migrations/**"],
  "remove_comments": true,
  "reasoning": "Focusing on core abstract classes..."
}
```

### 4. `node_digest`

Compresses selected code using Repomix with smart filtering:

- Applies `targets` (what to include)
- Applies `ignore` patterns (what to exclude)
- Optionally removes comments for cleaner output

### 5. `node_synthesize`

LLM generates a comprehensive Markdown analysis report.

### 6. `node_save`

Saves the report to `.data/harvested/{timestamp}-deep-research-{repo}.md`.

## Usage

### Quick Start (Recommended)

```bash
# Run the full LangGraph workflow
omni run "research https://github.com/agentgateway/agentgateway"
```

### Programmatic Usage

```python
from researcher.scripts.research_graph import run_research_workflow

result = await run_research_workflow(
    repo_url="https://github.com/agentgateway/agentgateway",
    request="Analyze the core architecture and agent orchestration patterns",
)

# Returns:
# {
#     "final_report": "# Agent Gateway Comprehensive Analysis...",
#     "report_path": ".data/harvested/20260123-deep-research-agentgateway.md",
#     "selected_targets": [...],
#     "steps": 6,
# }
```

### Individual Tools

#### `clone_repo`

Clone a remote Git repository to the research workspace.

```python
from researcher.scripts.research import clone_repo

result = clone_repo(url="https://github.com/agentgateway/agentgateway")
# Returns: {"path": ".cache/research/agentgateway"}
```

#### `repomix_map`

Generate a lightweight ASCII file tree.

```python
from researcher.scripts.research import repomix_map

result = repomix_map(path=".cache/research/agentgateway", max_depth=5)
# Returns: {"tree": "Repository: agentgateway\n├── src/\n│   └── ..."}
```

#### `repomix_compress`

Compress selected files with noise reduction.

```python
from researcher.scripts.research import repomix_compress

result = repomix_compress(
    path=".cache/research/agentgateway",
    targets=["crates/agentgateway/src"],
    ignore=["**/*_test.py"],
    remove_comments=True,  # For architecture analysis
)
# Returns: {"xml_content": "<file>...</file>", "char_count": 12345}
```

#### `save_report`

Save research findings to the harvested knowledge base.

```python
from researcher.scripts.research import save_report

result = save_report(
    repo_name="agentgateway",
    content="# Analysis Report\n...",
    category="deep-research",
)
# Returns: {"report_path": ".data/harvested/20260123-deep-research-agentgateway.md"}
```

## Smart Context Engineering

The Researcher skill implements **Context Engineering** principles:

### 1. Precision Targeting

Instead of copying entire directories, LLM designs precise Glob patterns:

- `crates/agentgateway/src/lib.rs` (specific file)
- `crates/agentgateway/src/**/mod.rs` (module files)

### 2. Noise Reduction (repomix)

- **Comments removal**: For architecture analysis (saves ~30-50% tokens)
- **Empty line removal**: For compact output
- **Pattern exclusion**: Tests, configs, generated files

**Do we need repomix?** Yes for typical repos. repomix reduces tokens (removeComments, removeEmptyLines) and structures output (XML). Alternative: raw file concatenation—simpler, no subprocess (~1–3s saved per shard), but more tokens and less structure. For small repos or speed-critical runs, a future `skip_repomix` option could use raw concatenation.

### 3. Iterative Scouting

Two-pass analysis:

1. **Survey**: Get the big picture (file tree)
2. **Scout**: Design targeted extraction strategy

## Configuration

### Repomix Options

The `repomix_compress` tool supports:

| Parameter            | Type      | Default          | Description              |
| -------------------- | --------- | ---------------- | ------------------------ |
| `path`               | string    | -                | Repository root path     |
| `targets`            | list[str] | -                | Glob patterns to include |
| `ignore`             | list[str] | default patterns | Patterns to exclude      |
| `remove_comments`    | bool      | false            | Remove code comments     |
| `remove_empty_lines` | bool      | true             | Remove blank lines       |

### Default Ignore Patterns

```python
[
    "**/*.lock",
    "**/*.png",
    "**/*.svg",
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/.git/**",
]
```

## Output

### Report Structure

Generated reports include:

```
# {Repo} Comprehensive Architecture Analysis

## 1. Executive Summary
- High-level overview
- Primary purpose and use cases

## 2. Architecture Deep Dive
- Architectural patterns
- Component hierarchy
- Data flow

## 3. Core Components Analysis
- Module purposes
- Key data structures
- Important functions/classes

## 4. Interface & Contract Definitions
- Public APIs
- Data models
- Configuration interfaces

## 5. Technology Stack
- Languages, frameworks, libraries
- Rationale for choices

...

## 10. Comparison with Industry Standards
- Best practices followed
- Deviations from norms
```

## Files

```
researcher/
├── SKILL.md          # Skill manifest (MCP tool definitions)
├── README.md         # This file
├── scripts/
│   ├── __init__.py
│   ├── research.py           # Atomic tools (clone, map, compress, save)
│   ├── research_graph.py     # LangGraph workflow nodes
│   └── research_entry.py     # MCP command entry point
└── tests/
    └── ...
```

## Best Practices

1. **Use `run_research_graph`** for complete analysis workflows
2. **Be specific in requests**: "Analyze the agent orchestration patterns" instead of "analyze architecture"
3. **Use appropriate noise reduction**:
   - `remove_comments=True` for architecture/overview
   - `remove_comments=False` for code audits/implementation details
4. **Reports are saved** to `.data/harvested/` for future reference

## Troubleshooting

### LLM returns malformed JSON

The system includes fallback logic that uses heuristic defaults.

### No files found in Repomix

Ensure paths are relative to repository root (e.g., `crates/agentgateway/src/lib.rs`).

### Empty report

Check that the repository was successfully cloned and targets are valid patterns.
