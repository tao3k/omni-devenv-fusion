# Skill Data Hierarchy and References

This document defines the **data hierarchy** for skills and the **reference document** convention. It is the source of truth for how we parse and store skill-level vs tool-level vs reference-level data.

---

## 1. Data hierarchy

A skill directory has three levels of content. Parsing and storage must respect this hierarchy:

| Level                        | Location          | Role                                                                                      | Parser / source                       |
| ---------------------------- | ----------------- | ----------------------------------------------------------------------------------------- | ------------------------------------- |
| **Skill (top)**              | `SKILL.md`        | **Comprehensive** document: overall skill role, capabilities, when to use. One per skill. | `SkillScanner` → `SkillMetadata`      |
| **Tools (under skill)**      | `scripts/*.py`    | Commands/tools from `@skill_command`. Each tool has name, description, params.            | `ToolsScanner` → `ToolRecord`         |
| **References (under skill)** | `references/*.md` | **Per-tool or per-topic** detailed docs. Usage, workflows, examples.                      | Reference scanner → `ReferenceRecord` |

- **SKILL.md** is the **top-level** asset: it describes the skill as a whole. It is **not** the source of tool descriptions; tool descriptions come from **scripts** (decorator `description`).
- **scripts/** are the **only** source of tools (command name, description, input_schema). No row in the index should treat SKILL.md as a “tool.”
- **references/** hold **detailed** documentation. Each reference markdown can be tied to the whole skill or to a specific tool via frontmatter. Specific usage and workflows live here; SKILL.md points to them for “see also.”

---

## 2. SKILL.md = comprehensive

- **Single file per skill**: `assets/skills/<skill_name>/SKILL.md`.
- **Content**: High-level description, routing_keywords, intents, required_refs, permissions. Body = overview and pointers to references.
- **Stored as**: Skill-level metadata only (name, description, routing_keywords, intents, etc.). Not stored as a “tool” row.
- **Usage**: Routing uses skill metadata (keywords/intents) and **tool** rows from scripts for vector/keyword search. LLM “overview” of the skill can be loaded from SKILL.md; **specific usage** is in `references/*.md`.

---

## 3. references/\*.md = reference docs with metadata

**Create one markdown file per reference** under the skill’s `references/` folder (e.g. `assets/skills/researcher/references/run_research_graph.md`). Put all reference fields in a single **`metadata`** block in the front matter (same pattern as SKILL.md). The canonical payload’s `references` map is built from these files; each value is the full parsed metadata plus path. **Front matter** uses a single **`metadata`** block (same pattern as SKILL.md). Put all reference fields under `metadata` so the structure is consistent.

Each markdown under `references/` should have **YAML frontmatter** with one top-level key **`metadata`**:

- **`metadata.for_tools`** (optional): Full tool name(s) (e.g. `git.smart_commit`). Single string or list of strings. If present, skill(s) are derived from the tool list. If absent, the doc is skill-level only and the skill comes from the file path.
- **`metadata.title`** (optional): Document title; fallback = filename stem.
- **`metadata.description`** (optional): Short description.
- **`metadata.routing_keywords`** / **`metadata.intents`** (optional): Same style as SKILL.md; merged into the reference’s keywords for discovery.

Example for a **tool-specific** reference (minimal):

```yaml
---
metadata:
  for_tools: git.smart_commit
  title: Smart Commit Workflow
---
```

Example with **description and keywords** (reuse SKILL.md-style fields):

```yaml
---
metadata:
  for_tools: researcher.run_research_graph
  title: Run Research Graph Workflow
  description: How to use the Sharded Deep Research Workflow (run_research_graph).
  routing_keywords:
    - "research"
    - "graph"
    - "workflow"
  intents:
    - "Deep research"
    - "Repository analysis"
---
```

Example for a **graph doc** (multiple tools); skills are derived from the tool list:

```yaml
---
metadata:
  for_tools: [researcher.run_research_graph, git.smart_commit]
  title: Graph spanning multiple skills/tools
---
```

Example for a **skill-level** reference (no specific tool); skill comes from path:

```yaml
---
metadata:
  title: Git workflow overview
---
```

- **Stored as**: `ReferenceRecord` with `for_tools` (list), derived `for_skills` / `skill_name`, `file_path`, `title`, and optionally content preview / sections.
- **Usage**: When the router or LLM needs “how do I use tool X?”, resolve `for_tools` → open the corresponding reference doc. SKILL.md can link to these files (e.g. “See [references/smart-commit-workflow.md](references/smart-commit-workflow.md) for usage.”).

---

## 3b. Tool → reference link (from markdown front matter only)

**Skill, skill tools, and references metadata all come from parsing markdown front matter** under the skill folder (SKILL.md and all .md under subdirs such as `references/`). They are **not** taken from Python decorators.

To know **which reference doc describes which tool**:

- In **references/\*.md**, set **YAML front matter** `metadata.for_tools: <skill_name>.<tool_name>` (e.g. `for_tools: researcher.run_research_graph`). That doc is then the reference for that tool.
- The indexer scans `references/` and, for each tool, sets `skill_tools_refers` to the list of reference doc names (ref_name) where `for_tools` contains the tool's full name.
- **Stored as**: `ToolRecord.skill_tools_refers` (list of ref_name), written into the skills vector table as `skill_tools_refers`. Source of truth is **only** the reference markdown front matter.

---

## 4. Stored data format (index / schema)

- **Skill index entry** (`SkillIndexEntry`):
  - **Skill-level fields**: From SKILL.md only (name, description, version, path, routing_keywords, intents, require_refs, etc.).
  - **tools**: From **scripts** only (`IndexToolEntry` per tool). No row derived from SKILL.md as a tool.
  - **references**: List of `ReferenceRecord` from scanning `references/*.md`, each with optional `for_tools` and derived `for_skills`.

- **Router vector index**: One row per **tool** (from scripts). Content = tool description. Metadata can include skill_name, routing_keywords, intents. No separate “skill document” row unless we explicitly add a “comprehensive” document type later (then it would be one row per skill from SKILL.md body, distinct from tools).

- **Metadata source**: Skill, skill tools, and references metadata (including which refs a tool refers to, `skill_tools_refers`) are defined **only by parsing markdown front matter** under the skill directory (SKILL.md and `references/*.md`). The Python decorator does **not** supply references or `skill_tools_refers`.

- **Clarification**: “Dataset” = skill directory. **Top-level** data = SKILL.md (comprehensive). **Subordinate** data = scripts (tools) + references (reference docs).

---

## 5. Summary

| Asset             | Type          | Stored as                                         | Purpose                                                                 |
| ----------------- | ------------- | ------------------------------------------------- | ----------------------------------------------------------------------- |
| `SKILL.md`        | Comprehensive | Skill metadata only                               | Skill overview, routing keywords, intents; “see references for details” |
| `scripts/*.py`    | Tools         | `ToolRecord` / `IndexToolEntry`                   | Tool name, description, params; source of truth for MCP and router      |
| `references/*.md` | Reference     | `ReferenceRecord` (for_tools, derived for_skills) | Detailed usage for a tool or the skill                                  |

This hierarchy and the reference frontmatter convention (`metadata.for_tools`) are the contract for parsing and for any UI or RAG that shows “overview in SKILL.md, details in references/…”.
