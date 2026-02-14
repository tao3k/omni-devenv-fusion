# Route Test Schema and Tool Attributes (for algorithm tuning)

This doc extracts (1) the **omni.router.route_test.v1** schema so we know exactly what data the route test outputs, and (2) the **researcher** tool’s **tool-level** attributes (MCP / index source of truth) vs SKILL.md, so we can tune the algorithm using the same data the router and MCP use.

**Alignment:** The route result item shape is aligned with **omni.vector.tool_search.v1** (skills schema). Each result has the same optional fields as a tool search hit (`name`, `vector_score`, `keyword_score`, `intents`, `category`); route_test adds `id`, `command`, `explain`, and `payload`. Use `routing_keywords` only; `keywords` is forbidden.

---

## 1. Data shape from `omni.router.route_test.v1.schema.json`

**Schema file:** `packages/shared/schemas/omni.router.route_test.v1.schema.json`

**Top-level required fields:**

| Field                | Type           | Description                     |
| -------------------- | -------------- | ------------------------------- |
| `schema`             | string (const) | `"omni.router.route_test.v1"`   |
| `query`              | string         | User query passed to route test |
| `count`              | integer (≥0)   | Number of results returned      |
| `threshold`          | number         | Min score threshold used        |
| `limit`              | integer (≥0)   | Max results requested           |
| `confidence_profile` | object         | Active confidence profile       |
| `stats`              | object         | Search weights / strategy       |
| `results`            | array          | List of route result items      |

**`confidence_profile`:**

| Field    | Type           |
| -------- | -------------- |
| `name`   | string \| null |
| `source` | string         |

**`stats`:**

| Field             | Type           |
| ----------------- | -------------- |
| `semantic_weight` | number \| null |
| `keyword_weight`  | number \| null |
| `rrf_k`           | number \| null |
| `strategy`        | string \| null |

**Each item in `results` (`route_result_item`):**

Aligned with **omni.vector.tool_search.v1**; route_test adds `id`, `command`, `explain`, `payload`.

| Field              | Type            | Description                                                     |
| ------------------ | --------------- | --------------------------------------------------------------- |
| `id`               | string          | Tool id (e.g. full tool name)                                   |
| `name`             | string          | (optional) Display name (tool_search.v1)                        |
| `description`      | string          | **Tool description** (see below)                                |
| `skill_name`       | string          | Skill name                                                      |
| `tool_name`        | string          | Full tool name (e.g. `researcher.git_repo_analyer`)             |
| `command`          | string          | Command part (e.g. `git_repo_analyer`)                          |
| `file_path`        | string          | (optional)                                                      |
| `score`            | number          | Raw RRF score                                                   |
| `vector_score`     | number          | (optional) Component score from vector search (tool_search.v1)  |
| `keyword_score`    | number          | (optional) Component score from keyword search (tool_search.v1) |
| `final_score`      | number          | Calibrated score                                                |
| `confidence`       | string          | `"high"` \| `"medium"` \| `"low"`                               |
| `routing_keywords` | array of string | Keywords used for keyword match                                 |
| `intents`          | array of string | (optional) Intent labels (tool_search.v1)                       |
| `category`         | string          | (optional) Tool category (tool_search.v1)                       |
| `input_schema`     | object          | JSON Schema for tool inputs                                     |
| `explain`          | object          | (optional) Score breakdown when `--explain`                     |
| `payload`          | object          | Nested type + metadata                                          |

**`payload`:**

| Field         | Type                                                                                                |
| ------------- | --------------------------------------------------------------------------------------------------- |
| `type`        | string                                                                                              |
| `description` | string (optional)                                                                                   |
| `metadata`    | object (required: `tool_name`, `routing_keywords`; optional: `input_schema`, `intents`, `category`) |

So the data we get back for ranking and tuning is: **id, description, skill_name, tool_name, command, score, final_score, confidence, routing_keywords, input_schema, payload**. Algorithm tuning should use these fields only (no hardcoding; keywords/description from index).

---

## 2. Researcher tool: tool-level vs SKILL.md

**Important:** The **tool’s** `description` (from the `@skill_command(description="""...""")` in the Python script) is what MCP exposes and what the **router index** uses for embedding and keyword (content). SKILL.md’s frontmatter `description` is skill-level and must not override the tool description. Below we list both so we can align tuning to the **tool-level** attributes.

### 2.1 Tool-level attributes (source of truth for MCP and router index)

**Source:** `assets/skills/researcher/scripts/research_entry.py` — `@skill_command` and function.

| Attribute       | Value (tool level)                                   |
| --------------- | ---------------------------------------------------- |
| **name**        | `git_repo_analyer`                                   |
| **description** | _(This is what gets into the router index and MCP.)_ |
| **category**    | `research`                                           |

**Tool description (full text used for embedding/content):**

```
Execute the Sharded Deep Research Workflow.

This autonomously analyzes large repositories using a Map-Plan-Loop-Synthesize pattern:

1. **Setup**: Clone repository and generate file tree map
2. **Architect (Plan)**: LLM breaks down the repo into 3-5 logical shards (subsystems)
3. **Process Shard (Loop)**: For each shard - compress with repomix + analyze with LLM
4. **Synthesize**: Generate index.md linking all shard analyses

This approach handles large codebases that exceed LLM context limits by analyzing
one subsystem at a time, then combining results.

Args:
    - repo_url: str - Git repository URL to analyze (required)
    - request: str = "Analyze the architecture" - Specific analysis goal
    - visualize: bool = false - If true, return the workflow diagram instead of running

Returns:
    dict with success status, harvest directory path, and shard summaries
```

**Parameters (for input_schema / routing relevance):**

- `repo_url` (str, required) – Git repository URL to analyze
- `request` (str, default `"Analyze the architecture"`) – Analysis goal
- `visualize` (bool, default false) – Return workflow diagram only

So the **action** (analyze/research) and **git repo URL** are already in the **tool description** and params. Ranking should rely on this description + `routing_keywords` / `intents` from the index (which come from SKILL.md for this skill).

### 2.2 SKILL.md (skill-level; used for routing_keywords / intents only)

**Source:** `assets/skills/researcher/SKILL.md` frontmatter.

| Attribute            | Value (SKILL.md)                                                                                                                                                                                                                     |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **description**      | Use when analyzing repositories, conducting deep research on codebases, performing architecture reviews, or exploring large projects. Use when the user wants to research or analyze a git repo, a GitHub link, or a repository URL. |
| **routing_keywords** | research, analyze, analyze_repo, deep_research, code_analysis, repository_map, sharded_analysis, architecture_review, llm_research, explore, investigate, study, git, repo, repository, link, github                                 |
| **intents**          | Research repository; Analyze codebase; Deep research; Architecture review; Analyze git repo or link; Study a repository from a link                                                                                                  |

**Distinction:** The router’s **content** (embedding + keyword description field) is the **tool description** above, not SKILL.md’s description. The **routing_keywords** and **intents** in the index are taken from SKILL.md (scanner merges them per skill). So when we tune the algorithm we should:

- Use **tool description** (and optionally input_schema) for semantic and keyword “description” match.
- Use **routing_keywords** and **intents** from the index (they are the same as SKILL.md for this skill) for keyword/intent match.

---

## 3. How the router index is built (so we know what we’re tuning)

- **Content / description in router:** From Rust scanner → **tool.description** (decorator `description` in `@skill_command`). So the researcher entry’s content is the long “Execute the Sharded Deep Research Workflow…” text.
- **routing_keywords / intents in router:** From SKILL.md (skill scanner merges frontmatter with the tool record).
- **category:** From the tool decorator (e.g. `category="research"`).

So: **Tool description = MCP and router index source of truth for “what this tool does”.** SKILL.md description is not used as the tool’s description in the index; it’s skill-level context. Algorithm improvements should be based on **route_test output fields** and **tool-level attributes** (description, routing_keywords, intents, category) only, so we can iterate step by step.

---

## 4. Keyword search vs vector search: which fields drive which algorithm

Routing uses two kinds of signals. The split below is the design rule for tuning and for adding new index fields.

### 4.1 Keyword search (exact / lexical match)

These fields are **natural fits for keyword search** (e.g. Tantivy BM25 / query terms). Translation of the user query (e.g. “研究 + URL” → “Help me research &lt;url&gt;”) increases precision by aligning query terms with these indexed strings.

| Source | Field                         | Role                                                                       |
| ------ | ----------------------------- | -------------------------------------------------------------------------- |
| Index  | **routing_keywords**          | Primary keyword signal (e.g. research, analyze, repo, link).               |
| Index  | **intents** (intent keywords) | Intent phrases (e.g. “Research repository”, “Analyze git repo or link”).   |
| Index  | **tool_name**                 | Full name (e.g. `researcher.git_repo_analyer`) — contains skill + command. |
| Index  | **skill_name**                | Skill name (e.g. `researcher`).                                            |
| Index  | **command**                   | Command part (e.g. `git_repo_analyer`).                                    |

So: **routing_keywords**, **intent keywords**, **tool name**, **skill name**, and **command** are all keyword-searchable. Translation improves precision by making the query match these strings better.

### 4.2 Vector search (semantic / natural language)

These are **natural language** and are best matched by **vector (embedding) search**, not by keyword alone.

| Source               | Field                       | Role                                                                                                                                  |
| -------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Tool decorator       | **Tool description**        | Main natural-language description; same text MCP sends to the model. **Most important for “can the model call this tool correctly?”** |
| SKILL.md frontmatter | **Skill-level description** | Skill-level natural language (when/why to use the skill).                                                                             |
| SKILL.md body        | **SKILL.md content**        | Full markdown (natural language).                                                                                                     |

So: **Skill-level description** and **tool description** (and any SKILL.md body we index) drive **vector search**. Of these, **tool description** is the critical signal for correct tool selection and usage by the LLM.

### 4.3 Summary

- **Keyword algorithm:** routing_keywords, intent keywords, tool_name, skill_name, command (+ query translation for precision).
- **Vector algorithm:** tool description (primary), skill-level description, SKILL.md content (if indexed).
- **Tool description** is the main lever for LLM tool-calling accuracy: it is what the model reads to decide _whether_ and _how_ to call the tool, so indexing and ranking must treat it as the primary natural-language signal.

### 4.4 Implementation: confidence calibration

Confidence (high/medium/low) and `final_score` are calibrated in the Rust bridge using both paths:

- **Vector path (tool description match):** When `vector_score` ≥ threshold (e.g. 0.55) and fused score ≥ medium_threshold, the result is promoted to **high** confidence. This reflects that semantic match on tool description is the primary signal for “model can call this tool correctly.”
- **Keyword path:** When `keyword_score` is strong (e.g. BM25 ≥ 0.2) or the match is keyword-dominated (keyword > vector and vector &lt; 0.5), and fused score ≥ medium_threshold, the result is also promoted to **high**.
- **Clear winner:** When the top result is far ahead of the second (score gap ≥ 0.15), it is promoted to **high**.

Query translation (non-English → English) is applied before embedding and keyword search so that both the vector and keyword branches see aligned, English query text for indexing (routing_keywords/intents are English).
