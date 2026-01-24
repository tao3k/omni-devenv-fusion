---
name: "researcher"
version: "2.0.0"
description: "Sharded Deep Research V2.0 - Turbo-charged for speed. Smart clone, native repomix, native tree generation."
routing_keywords:
  [
    "analyze_repo",
    "deep_research",
    "code_analysis",
    "repository_map",
    "sharded_analysis",
    "architecture_review",
    "llm_research",
  ]
authors: ["omni-dev-fusion"]
intents:
  [
    "research_repository",
    "analyze_codebase",
    "deep_research",
    "architecture_review",
  ]
permissions: []
---

# Researcher Skill

Sharded Deep Research for analyzing large codebases. Uses LangGraph with Map-Plan-Loop-Synthesize architecture to handle repositories that exceed LLM context limits.

## Architecture

```
┌─────────┐     ┌──────────────┐     ┌────────────────┐     ┌──────────────┐
│  Setup  │ --> │  Architect   │ --> │ Process Shard  │ --> │ Synthesize  │
│  Clone  │     │   (Plan)     │     │    (Loop)      │     │   Index.md   │
└─────────┘     └──────────────┘     └────────────────┘     └──────────────┘
     │                  │                    │
     │              3-5 shards          compress
     │              defined by           + analyze
     │              LLM                  each shard
```

## Commands

### run_research_graph

**[CORE]** Execute the Sharded Deep Research Workflow.

This autonomously:
1. **Clones** the repository to a temporary workspace
2. **Maps** the file structure (god view)
3. **Plans** 3-5 logical analysis shards (subsystems) via LLM
4. **Iterates** through each shard:
   - Compress with repomix (shard-specific config)
   - Analyze with LLM
   - Save shard analysis to `shards/<id>_<name>.md`
5. **Synthesizes** `index.md` linking all shard analyses

**Parameters:**

- `repo_url` (string, required): Git repository URL to analyze
- `request` (string, optional): Research goal/focus (default: "Analyze the architecture")

**Returns:**

```json
{
  "success": true,
  "harvest_dir": "/path/to/.data/harvested/20250123-repo/",
  "shards_analyzed": 4,
  "shard_summaries": [
    "- **[Core Kernel](./shards/01_core_kernel.md)**: Main business logic",
    "- **[API Layer](./shards/02_api_layer.md)**: HTTP handlers"
  ],
  "summary": "Research Complete!..."
}
```

**Output Location:**

```
.data/harvested/<date>-<repo_name>/
├── index.md                    # Master index with all shard links
└── shards/
    ├── 01_core_kernel.md       # Shard 1 analysis
    ├── 02_api_layer.md         # Shard 2 analysis
    └── ...
```

## Usage Example

```python
# Analyze a repository's security patterns
await researcher.run_research_graph(
    repo_url="https://github.com/example/large-repo",
    request="Analyze security patterns and vulnerability surfaces"
)

# Result: Multiple shard analyses saved to .data/harvested/
```

## Technical Details

- **Repomix**: Used directly (not via npx) for code compression
- **Sharding**: LLM dynamically determines shard boundaries based on repo structure
- **Loop**: Conditional edges in LangGraph process shards until queue empty
- **Checkpoint**: MemorySaver enables resumption of interrupted workflows
