---
name: researcher
description: Use when analyzing repositories, conducting deep research on codebases, performing architecture reviews, or exploring large projects. Use when the user wants to research or analyze a git repo, a GitHub link, or a repository URL.
metadata:
  author: omni-dev-fusion
  version: "2.0.0"
  source: "https://github.com/tao3k/omni-dev-fusion/tree/main/assets/skills/researcher"
  routing_keywords:
    - "research"
    - "analyze"
    - "analyze_repo"
    - "deep_research"
    - "code_analysis"
    - "repository_map"
    - "sharded_analysis"
    - "architecture_review"
    - "llm_research"
    - "explore"
    - "investigate"
    - "study"
    - "git"
    - "repo"
    - "repository"
    - "link"
    - "url"
    - "github"
    - "github url"
    - "repository url"
    - "research url"
  intents:
    - "Research repository"
    - "Analyze codebase"
    - "Deep research"
    - "Architecture review"
    - "Analyze git repo or link"
    - "Study a repository from a link"
    - "Help me research or analyze a repository from a GitHub URL or link"
    - "I want to analyze or research a codebase from a URL"
    - "Do deep research on a repo I'll give you a link to"
    - "Review the architecture of a project from its GitHub URL"
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
- `visualize` (bool, optional): If true, return workflow diagram only
- `chunked` (bool, optional): If true, use step-by-step actions (like knowledge recall)
- `action` (string, optional): When chunked: `"start"` | `"shard"` | `"synthesize"`
- `session_id` (string, optional): When chunked: required for `shard` and `synthesize` (returned from `start`)
- `chunk_id` (string, optional): When chunked + `action="shard"`, run one specific chunk (e.g. `c1`)
- `chunk_ids` (list[string], optional): When chunked + `action="shard"`, run multiple chunks in parallel in one call
- `max_concurrent` (int, optional): Max concurrent shard LLM calls; null = unbounded. Set to 6–8 if API rate limits (429). Falls back to `researcher.max_concurrent` in settings.

**Chunked mode (step-by-step):**

- 1. Call with `chunked=true`, `action="start"` → returns `session_id`, `chunk_plan` (`c1`, `c2`, ...), `next_action`.
- 2. Call with `chunked=true`, `action="shard"`, `session_id=<from start>`, and either:
     `chunk_id=<cx>` for one chunk, or `chunk_ids=[...]` for parallel chunk execution.
     If omitted, all pending chunks are executed in parallel in that call.
- 3. Call with `chunked=true`, `action="synthesize"`, `session_id=<same>` after all chunks complete.

State is persisted in the checkpoint store under workflow type `research_chunked`.

**Returns:**

```json
{
  "success": true,
  "harvest_dir": "/path/to/.data/harvested/<owner>/<repo_name>/",
  "shards_analyzed": 4,
  "revision": "abc1234",
  "shard_summaries": [
    "- **[Core Kernel](./shards/01_core_kernel.md)**: Main business logic",
    "- **[API Layer](./shards/02_api_layer.md)**: HTTP handlers"
  ],
  "summary": "Research Complete!..."
}
```

**Output Location:**

```
.data/harvested/<owner>/<repo_name>/
├── index.md                    # Master index with YAML frontmatter (includes revision)
└── shards/
    ├── 01_core_kernel.md       # Shard 1 analysis
    ├── 02_api_layer.md         # Shard 2 analysis
    └── ...
```

**index.md Frontmatter:**

```yaml
---
title: Research Analysis: <repo_name>
source: <repo_url>
revision: <git_hash>
revision_date: <YYYY-MM-DD HH:MM:SS TZ>
generated: <YYYY-MM-DD>
shards: <count>
---
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
- **Sharding**: LLM (architect) proposes subsystems; **normalization** enforces efficient bounds
- **Loop**: Conditional edges in LangGraph process shards until queue empty
- **Checkpoint**: MemorySaver enables resumption of interrupted workflows
- **Chunked API**: Same workflow type as knowledge recall; one step per MCP call via `action` and `session_id`

## Efficient sharding design

To avoid timeouts and unbalanced work, sharding is **constrained and normalized**:

1. **Architect prompt limits**
   - At most 5 files per shard, total files ≤ 25 across all shards.
   - 4–6 subsystems; explicit “stay under limits” so the LLM does not propose oversized shards.

2. **Post-architect normalization** (`_normalize_shards`)
   - **Split**: Any shard with &gt; 5 files is split into multiple shards (e.g. “Core (1)”, “Core (2)”).
   - **Cap**: Total files across all shards are capped at 30; excess is trimmed from the end.
   - **Merge**: Consecutive shards with ≤ 2 files each are merged into one shard (up to 5 files) to reduce round-trips and balance size.

3. **Per-shard processing limits**
   - Repomix output per shard capped at 32k chars; subprocess timeout 120s; run in executor so heartbeat can run.
   - LLM input 28k chars, output 4096 tokens.

Result: each `action=shard` runs on a bounded amount of code and stays within MCP idle/total timeout when heartbeat is used.

## Performance & timeouts

Shard processing is tuned and uses **progress-aware timeout**:

- **Idle timeout** (`mcp.idle_timeout`, default 120s): Cancel only when there is **no progress** for this long. The researcher calls `heartbeat()` every 10s during repomix and LLM, so the runner does not kill the tool while it is still working.
- **Total timeout** (`mcp.timeout`, default 180s): Hard cap (wall-clock); 0 = disable.
- **Repomix**: Output capped at 32k chars per shard; subprocess timeout 120s; run in executor so heartbeat can run.
- **LLM**: Input 28k chars, output 4096 tokens; architect prefers 4–6 shards with 3–6 files each.

To allow longer runs without changing behaviour, increase timeouts in settings:

```yaml
mcp:
  timeout: 300 # Hard cap (seconds); 0 = disable
  idle_timeout: 120 # Cancel only after no heartbeat for this long; 0 = use only timeout
```
