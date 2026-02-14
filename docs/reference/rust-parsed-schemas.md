# Rust Parsed Schemas Reference

This document lists all **Rust-side** data structures (schemas) produced after parsing SKILL.md, scripts, references, knowledge, etc. Use it to cross-check source code with downstream index and Lance writes.

---

## 0. Canonical per-skill payload shape (agreed parsing model)

A **reasonable and consistent** way to parse everything under a skill directory is to produce one payload per skill with this shape:

```
{
  "skill_name": "<string>",              // e.g. "researcher"
  "SKILL.md": "<path>",                  // path to SKILL.md
  "metadata": {                          // from SKILL.md YAML front matter (SkillMetadata)
    // description, routing_keywords, intents, require_refs, permissions, ...
  },
  "skill_tools": {
    "<tool_full_name>": {                // e.g. "researcher.run_research_graph"
      // DecoratorParamsValue: name, description, category, input_schema, parameters, ...
      "skill_tool_references": {         // ref_key -> path (this tool’s reference docs, from references/*.md for_tools)
        "<skill_name>.references.<ref_stem>": "<path>",
        // e.g. "researcher.references.run_research_graph": "assets/skills/researcher/references/run_research_graph.md"
      }
    },
    // "researcher.tool2": { ... },
  },
  "references": {                        // ref_id (e.g. filename stem) -> { frontmatter, path }
    "markdown1": { "frontmatter": { ... }, "path": "<path>" },
    "markdown2": { "frontmatter": { ... }, "path": "<path>" }
  }
}
```

- **skill_name**: Skill id (e.g. `"researcher"`). From directory name or SKILL.md front matter.
- **SKILL.md**: Path to the skill’s `SKILL.md` file.
- **metadata**: Parsed SKILL.md YAML front matter only (`SkillMetadata`). Empty `{}` if missing or no front matter.
- **skill_tools**: Map from full tool name (`skill_name.tool_name`) to:
  - Decorator-derived and enriched fields (name, description, category, input_schema, parameters, file_hash, …),
  - **skill_tool_references**: Map from a ref key (e.g. `"<skill_name>.references.<ref_stem>"`) to the **path** of that reference markdown. So each tool carries “which reference docs describe me” with resolvable paths; source of this link is **only** `references/*.md` front matter (`for_tools`).
- **references**: Map from reference id (e.g. filename stem `"markdown1"`, `"markdown2"`) to an object with **frontmatter** (title, for_skill, for_tools, …) and **path**. One entry per file. Entries may come from **this skill’s** `references/*.md` or, when resolving cross-skill refs, from **other skills’** reference markdown.

**Cross-skill and multiple refs**: A tool’s reference docs are not limited to the same skill. We may resolve references from **other skills’** `references/*.md` (e.g. `"git.references.smart_commit"` → path under `assets/skills/git/references/`). A single tool can point to **multiple** markdown files; `skill_tool_references` is a map (ref_key → path) with one entry per reference doc, possibly from different skills.

This keeps: (1) skill-level metadata from SKILL.md only, (2) each tool’s decorator params plus a clear tool→ref mapping with paths (same-skill or cross-skill, multiple refs), (3) a references catalog that can include refs from this skill and others. The current Rust types (`SkillIndexEntry`, `ToolRecord.skill_tools_refers`, `Vec<ReferenceRecord>`) can be viewed as an implementation of this shape; `skill_tool_references` as ref_key→path supports multiple refs and future cross-skill resolution.

### Step 1: Rust types (for verification)

**File**: `packages/rust/crates/omni-scanner/src/skills/canonical.rs`

| Type                      | Field                   | Rust type                             | JSON / description                                                                                                           |
| ------------------------- | ----------------------- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **CanonicalSkillPayload** | `skill_name`            | `String`                              | Skill id (e.g. `"researcher"`).                                                                                              |
|                           | `skill_md_path`         | `String`                              | Path to this skill's SKILL.md.                                                                                               |
|                           | `metadata`              | `SkillMetadata`                       | Parsed SKILL.md front matter only.                                                                                           |
|                           | `skill_tools`           | `HashMap<String, CanonicalToolEntry>` | Key = full tool name (`skill_name.tool_name`).                                                                               |
|                           | `references`            | `HashMap<String, ReferenceRecord>`    | Key = ref_id (e.g. filename stem). Value = frontmatter + path (see ReferenceRecord).                                         |
| **CanonicalToolEntry**    | `tool`                  | `ToolRecord`                          | Full tool record (decorator + enrichment).                                                                                   |
|                           | `skill_tool_references` | `HashMap<String, String>`             | Key = ref_key (e.g. `"researcher.references.run_research_graph"`). Value = resolved path. Multiple refs; may be cross-skill. |

**ReferenceRecord** (value of `references` map): already defined in `metadata.rs` — `ref_name`, `title`, `skill_name`, `file_path`, `for_tools`, `doc_type`, `content_preview`, `keywords`, `sections`, `file_hash`. So `references[ref_id]` gives frontmatter-like fields + `file_path`.

**Serialization**: Both structs use `#[serde(rename_all = "snake_case")]`. So JSON keys are `skill_name`, `skill_md_path`, `metadata`, `skill_tools`, `references`, `tool`, `skill_tool_references`.

Verify: (1) One payload type per skill. (2) `skill_tools` is a map; each value has `tool` + `skill_tool_references` (ref_key → path). (3) `references` is a map ref_id → record (frontmatter + path). **Wired:** `SkillScanner::build_canonical_payload(metadata, tools, skill_path)` in `omni-scanner` fills the canonical payload from the filesystem (SKILL.md metadata, scripts-derived tools, `references/*.md` with `for_tools` → ref_key `"<skill>.references.<ref_stem>"` → path per tool).

**Snapshot JSON**: A full example payload is in **`docs/reference/canonical-skill-payload-snapshot.json`**. Use it to see the exact structure. Under **`references`**, each value is one **fully parsed front matter**: we parse each reference markdown’s YAML front matter into a `ReferenceRecord` (ref_name, title, skill_name, file_path, for_tools, doc_type, content_preview, keywords, sections, file_hash). Reference .md files use a single **`metadata`** block in front matter (same pattern as SKILL.md): `metadata.for_tools`, `metadata.title`, `metadata.description`, `metadata.routing_keywords`, `metadata.intents`. Each `references[ref_id]` is the full parsed metadata plus path.

---

## 1. omni-scanner: Skill-related

**Crate**: `omni-scanner`  
**Path**: `packages/rust/crates/omni-scanner/src/skills/`

### 1.1 SkillMetadata

**File**: `metadata.rs`  
**Source**: SKILL.md YAML front matter (parsed by `SkillScanner`)

| Field              | Type                 | Default | Description                          |
| ------------------ | -------------------- | ------- | ------------------------------------ |
| `skill_name`       | `String`             | `""`    | Unique skill name                    |
| `version`          | `String`             | `""`    | Semantic version                     |
| `description`      | `String`             | `""`    | Skill description                    |
| `routing_keywords` | `Vec<String>`        | `[]`    | Keywords for routing/semantic search |
| `authors`          | `Vec<String>`        | `[]`    | Authors                              |
| `intents`          | `Vec<String>`        | `[]`    | Intents (intent-based routing)       |
| `require_refs`     | `Vec<ReferencePath>` | `[]`    | Required reference paths             |
| `repository`       | `String`             | `""`    | Repository URL                       |
| `permissions`      | `Vec<String>`        | `[]`    | Required permissions (Zero Trust)    |

### 1.2 DecoratorArgs

**File**: `metadata.rs`  
**Source**: `@skill_command` decorator kwargs (**does not include** references / skill_tools_refers)

| Field         | Type             | Description                                  |
| ------------- | ---------------- | -------------------------------------------- |
| `name`        | `Option<String>` | Explicit tool name (overrides function name) |
| `description` | `Option<String>` | Tool description                             |
| `category`    | `Option<String>` | Category                                     |
| `destructive` | `Option<bool>`   | Whether the tool modifies external state     |
| `read_only`   | `Option<bool>`   | Whether the tool is read-only                |

### 1.3 ToolRecord

**File**: `metadata.rs`  
**Source**: Scripts scan + decorator/signature/docstring parsing; `skill_tools_refers` is filled **only** from references/\*.md front matter

| Field                | Type              | Default | Description                                                                 |
| -------------------- | ----------------- | ------- | --------------------------------------------------------------------------- |
| `tool_name`          | `String`          | -       | Full name `skill.tool` (e.g. `git.smart_commit`)                            |
| `description`        | `String`          | -       | Description                                                                 |
| `skill_name`         | `String`          | -       | Owning skill                                                                |
| `file_path`          | `String`          | -       | Definition file path                                                        |
| `function_name`      | `String`          | -       | Implementing function name                                                  |
| `execution_mode`     | `String`          | -       | e.g. sync/async/script                                                      |
| `keywords`           | `Vec<String>`     | -       | Keywords for discovery/routing                                              |
| `intents`            | `Vec<String>`     | `[]`    | Intents (inherited from skill)                                              |
| `file_hash`          | `String`          | -       | Source file hash                                                            |
| `input_schema`       | `String`          | `""`    | Input JSON Schema                                                           |
| `docstring`          | `String`          | `""`    | Function docstring                                                          |
| `category`           | `String`          | `""`    | Category                                                                    |
| `annotations`        | `ToolAnnotations` | default | MCP safety annotations                                                      |
| `parameters`         | `Vec<String>`     | `[]`    | Parameter names                                                             |
| `skill_tools_refers` | `Vec<String>`     | `[]`    | Reference doc names (ref_name); **only from references/\*.md front matter** |

### 1.4 ToolAnnotations

**File**: `metadata.rs`  
**Source**: Decorator or heuristic inference

| Field         | Type   | Description                          |
| ------------- | ------ | ------------------------------------ |
| `read_only`   | `bool` | Read-only                            |
| `destructive` | `bool` | Modifies or deletes data             |
| `idempotent`  | `bool` | Safe to repeat without side effects  |
| `open_world`  | `bool` | Interacts with external/open systems |

### 1.5 ReferenceRecord

**File**: `metadata.rs`  
**Source**: `references/*.md` scan (front matter + optional content preview)

| Field             | Type                  | Default       | Description                                                                                                |
| ----------------- | --------------------- | ------------- | ---------------------------------------------------------------------------------------------------------- |
| `ref_name`        | `String`              | -             | Reference name (usually filename stem)                                                                     |
| `title`           | `String`              | -             | Title (front matter or first heading)                                                                      |
| `skill_name`      | `String`              | -             | Primary skill (first of `for_skills` or path)                                                              |
| `file_path`       | `String`              | -             | File path                                                                                                  |
| `for_skills`      | `Vec<String>`         | `[]`          | **Derived** from `for_tools` (skill part of each `skill.tool`); or from path when `for_tools` is absent.   |
| `for_tools`       | `Option<Vec<String>>` | `None`        | From front matter only. List of full tool names (e.g. graph docs); single source of truth, no `for_skill`. |
| `doc_type`        | `String`              | `"reference"` | Document type                                                                                              |
| `content_preview` | `String`              | `""`          | Content preview                                                                                            |
| `keywords`        | `Vec<String>`         | `[]`          | Keywords                                                                                                   |
| `sections`        | `Vec<String>`         | `[]`          | Section headings                                                                                           |
| `file_hash`       | `String`              | `""`          | File hash                                                                                                  |

### 1.6 SkillIndexEntry

**File**: `metadata.rs`  
**Source**: Single-skill index entry (for skills index / skills.json, etc.)

| Field                | Type                   | Default | Description                             |
| -------------------- | ---------------------- | ------- | --------------------------------------- |
| `name`               | `String`               | -       | Skill name                              |
| `description`        | `String`               | -       | Description                             |
| `version`            | `String`               | -       | Version                                 |
| `path`               | `String`               | -       | Relative path                           |
| `tools`              | `Vec<IndexToolEntry>`  | -       | Tool list                               |
| `routing_keywords`   | `Vec<String>`          | -       | Routing keywords                        |
| `intents`            | `Vec<String>`          | -       | Intents                                 |
| `authors`            | `Vec<String>`          | -       | Authors                                 |
| `docs_available`     | `DocsAvailable`        | default | Documentation availability              |
| `oss_compliant`      | `Vec<String>`          | `[]`    | OSS compliance                          |
| `compliance_details` | `Vec<String>`          | `[]`    | Compliance details                      |
| `require_refs`       | `Vec<ReferencePath>`   | `[]`    | Required reference paths                |
| `sniffing_rules`     | `Vec<SnifferRule>`     | `[]`    | Sniffer rules                           |
| `permissions`        | `Vec<String>`          | `[]`    | Permissions                             |
| `references`         | `Vec<ReferenceRecord>` | `[]`    | Reference records from references/\*.md |

### 1.7 IndexToolEntry

**File**: `metadata.rs`  
**Use**: Tool entry when writing the skill index (e.g. JSON); not a Lance row

| Field          | Type     | Default | Description           |
| -------------- | -------- | ------- | --------------------- |
| `name`         | `String` | -       | Tool name (full name) |
| `description`  | `String` | -       | Description           |
| `category`     | `String` | `""`    | Category              |
| `input_schema` | `String` | `""`    | Input JSON Schema     |
| `file_hash`    | `String` | `""`    | File hash             |

### 1.8 Other skill-related types (metadata.rs)

| Type             | Description                                                                  |
| ---------------- | ---------------------------------------------------------------------------- |
| `ReferencePath`  | Validated relative reference path (md/pdf/txt/html/json/yaml/yml)            |
| `SnifferRule`    | `type` + `pattern`; from extensions/sniffer/rules.toml                       |
| `DocsAvailable`  | `skill_md`, `readme`, `tests` booleans                                       |
| `SkillStructure` | `required` / `default` / `optional` list of `StructureItem`                  |
| `StructureItem`  | `path`, `description`, `item_type`                                           |
| `SyncReport`     | `added` / `updated` / `deleted` / `unchanged_count` (scan vs existing index) |

### 1.9 ParsedParameter (parser)

**File**: `skills/skill_command/parser.rs`  
**Source**: Function signature parsing; used to build input_schema and ToolRecord.parameters

| Field             | Type             | Description                               |
| ----------------- | ---------------- | ----------------------------------------- |
| `name`            | `String`         | Parameter name                            |
| `type_annotation` | `Option<String>` | Python type annotation                    |
| `has_default`     | `bool`           | Whether the parameter has a default value |
| `default_value`   | `Option<String>` | Default value as string                   |

---

## 2. omni-scanner: Knowledge-related

**Path**: `packages/rust/crates/omni-scanner/src/knowledge/`

### 2.1 KnowledgeCategory

**File**: `types.rs`  
**Description**: Knowledge document category enum

`architecture` | `debugging` | `error` | `note` | `pattern` | `reference` | `technique` | `workflow` | `solution` | `unknown`

### 2.2 KnowledgeMetadata

**File**: `types.rs`  
**Source**: Knowledge document YAML front matter

| Field         | Type                        | Description |
| ------------- | --------------------------- | ----------- |
| `title`       | `Option<String>`            | Title       |
| `description` | `Option<String>`            | Description |
| `category`    | `Option<KnowledgeCategory>` | Category    |
| `tags`        | `Vec<String>`               | Tags        |
| `authors`     | `Vec<String>`               | Authors     |
| `source`      | `Option<String>`            | Source      |
| `version`     | `Option<String>`            | Version     |

### 2.3 KnowledgeEntry

**File**: `types.rs`  
**Source**: Knowledge document scan result (front matter + file info)

| Field             | Type                | Description     |
| ----------------- | ------------------- | --------------- |
| `id`              | `String`            | Unique id       |
| `file_path`       | `String`            | Relative path   |
| `title`           | `String`            | Title           |
| `description`     | `String`            | Description     |
| `category`        | `KnowledgeCategory` | Category        |
| `tags`            | `Vec<String>`       | Tags            |
| `authors`         | `Vec<String>`       | Authors         |
| `source`          | `Option<String>`    | Source          |
| `version`         | `String`            | Version         |
| `file_hash`       | `String`            | File hash       |
| `content_preview` | `String`            | Content preview |

---

## 3. omni-scanner: Generic front matter

**File**: `frontmatter.rs`

### 3.1 GenericFrontmatter

| Field         | Type                        | Description           |
| ------------- | --------------------------- | --------------------- |
| `title`       | `Option<String>`            | Title                 |
| `description` | `Option<String>`            | Description           |
| `category`    | `Option<String>`            | Category              |
| `tags`        | `Option<Vec<String>>`       | Tags                  |
| `metadata`    | `Option<serde_yaml::Value>` | Other key-value pairs |

---

## 4. omni-vector: Skill index and search

**Path**: `packages/rust/crates/omni-vector/src/skill/`

### 4.1 SkillManifest (inside omni-vector)

**File**: `scanner.rs`  
**Source**: Lightweight parse of SKILL.md front matter (for omni-vector internal use)

| Field              | Type          | Description      |
| ------------------ | ------------- | ---------------- |
| `skill_name`       | `String`      | Skill name       |
| `version`          | `String`      | Version          |
| `description`      | `String`      | Description      |
| `routing_keywords` | `Vec<String>` | Routing keywords |
| `authors`          | `Vec<String>` | Authors          |
| `intents`          | `Vec<String>` | Intents          |

### 4.2 ToolSearchResult

**File**: `mod.rs`  
**Use**: Single tool result returned from search

| Field        | Type | Description                        |
| ------------ | ---- | ---------------------------------- |
| (see source) | -    | id, score, content, metadata, etc. |

### 4.3 ToolSearchOptions

**File**: `mod.rs`  
**Use**: Tool search options (filter, limit, etc.)

---

## 5. Lance table (skills): tool row metadata JSON shape

**Written by**: `omni-vector` in `writer_impl.rs`  
**Description**: Each row corresponds to one `ToolRecord`; metadata is a JSON string whose keys align with `ToolRecord` (including `skill_tools_refers`).

| Key                  | Type            | Description                                                                 |
| -------------------- | --------------- | --------------------------------------------------------------------------- |
| `type`               | string          | `"command"`                                                                 |
| `skill_name`         | string          | Skill name                                                                  |
| `tool_name`          | string          | Full name `skill.tool`                                                      |
| `command`            | string          | Command part (tool name)                                                    |
| `file_path`          | string          | Script path                                                                 |
| `function_name`      | string          | Function name                                                               |
| `intents`            | array           | Intents                                                                     |
| `routing_keywords`   | array           | Routing keywords                                                            |
| `file_hash`          | string          | File hash                                                                   |
| `input_schema`       | string          | JSON Schema string                                                          |
| `docstring`          | string          | Docstring                                                                   |
| `category`           | string          | Category                                                                    |
| `annotations`        | object          | MCP annotations                                                             |
| `parameters`         | array           | Parameter names                                                             |
| `skill_tools_refers` | array of string | Reference doc names (ref_name); **only from references/\*.md front matter** |

---

## 6. Data flow summary

```
SKILL.md (YAML front matter)        → SkillMetadata, SkillIndexEntry.name/description/...
scripts/*.py (@skill_command)       → DecoratorArgs → ToolRecord (name/description/category/...)
references/*.md (YAML front matter) → ReferenceRecord; for_tools match → ToolRecord.skill_tools_refers
SkillScanner.build_index_entry()    → SkillIndexEntry (tools + references)
omni-vector scan_unique_skill_tools → ToolRecord list → writer_impl → Lance skills table (each row metadata includes skill_tools_refers)
```

The contract with frontends and indexes is defined in `skill-data-hierarchy-and-references.md` and `skill-tool-reference-schema-audit.md`.
