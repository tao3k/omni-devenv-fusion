# Skill Tool → Reference Schema (Audit)

This document lists the **exact schema** for the "tool → reference document" link. Use it to audit types, field names, and persistence before locking the format.

**Source of truth**: Skill, skill tools, and references metadata (including which refs a tool refers to) are defined **only by parsing markdown front matter** under the skill directory (SKILL.md and `references/*.md`). The Python `@skill_command` decorator does **not** supply `references` or `skill_tools_refers`.

---

## 1. Source: Markdown front matter (references/\*.md)

**Location**: `assets/skills/<skill>/references/*.md`

**Format**: YAML front matter with a single top-level **`metadata`** block (same pattern as SKILL.md). All reference fields go under `metadata`.

| Key                         | Type            | Required | Meaning                                                                   |
| --------------------------- | --------------- | -------- | ------------------------------------------------------------------------- |
| `metadata.for_tools`        | string or array | No       | Full tool name(s). Single string or list; skill(s) are derived from this. |
| `metadata.title`            | string          | No       | Title; fallback = filename stem.                                          |
| `metadata.description`      | string          | No       | Short description.                                                        |
| `metadata.routing_keywords` | array           | No       | Keywords for discovery (merged into reference keywords).                  |
| `metadata.intents`          | array           | No       | Intents (merged into reference keywords).                                 |

When `metadata.for_tools` is set, the indexer associates that reference doc with those tools. When absent, the skill comes from the file path.

---

## 2. Rust: DecoratorArgs (omni-scanner) — no references

**Crate**: `omni-scanner`  
**File**: `packages/rust/crates/omni-scanner/src/skills/metadata.rs`

DecoratorArgs does **not** have a `references` or `skill_tools_refers` field. Tool → reference link is **not** parsed from the Python decorator.

---

## 3. Rust: ToolRecord (omni-scanner)

**Crate**: `omni-scanner`  
**File**: `packages/rust/crates/omni-scanner/src/skills/metadata.rs`

Relevant fields (tool identity + reference link):

| Field                    | Type              | Required              | Meaning                                                                                                               |
| ------------------------ | ----------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `tool_name`              | `String`          | Yes                   | Full tool id (e.g. `researcher.run_research_graph`).                                                                  |
| `skill_name`             | `String`          | Yes                   | Skill name.                                                                                                           |
| `description`            | `String`          | Yes                   | Tool description.                                                                                                     |
| `file_path`              | `String`          | Yes                   | Script path.                                                                                                          |
| `function_name`          | `String`          | Yes                   | Python function name.                                                                                                 |
| …                        | (others)          | -                     | execution_mode, keywords, intents, file_hash, input_schema, docstring, category, annotations, parameters.             |
| **`skill_tools_refers`** | **`Vec<String>`** | **No (default `[]`)** | **Reference doc names (ref_name); populated from reference markdown front matter (`for_tools`), not from decorator.** |

When building the index, the scanner fills `skill_tools_refers` by scanning `references/*.md` and matching `for_tools` to the tool's full name; the list holds `ref_name` (filename stem) for each matching reference doc.

---

## 4. Rust: ReferenceRecord (omni-scanner)

**Crate**: `omni-scanner`  
**File**: `packages/rust/crates/omni-scanner/src/skills/metadata.rs`

**Role**: "Document → tool" link (reference doc declares which tool it describes).

| Field        | Type                  | Required           | Meaning                                                                                                                        |
| ------------ | --------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `ref_name`   | `String`              | Yes                | Filename stem (e.g. `run_research_graph`).                                                                                     |
| `title`      | `String`              | Yes                | Title (frontmatter or first heading).                                                                                          |
| `skill_name` | `String`              | Yes                | Primary skill (first of `for_skills` or parent path).                                                                          |
| `file_path`  | `String`              | Yes                | Path to the reference file.                                                                                                    |
| `for_skills` | `Vec<String>`         | Yes (default `[]`) | **Derived** from `for_tools` (skill part of each `skill.tool`), or from path when `for_tools` is absent. Not parsed from YAML. |
| `for_tools`  | `Option<Vec<String>>` | No                 | **Only field** in front matter for "what this ref applies to". List of full tool names; YAML accepts single string or array.   |

**Tool → doc**: For each tool, `skill_tools_refers` lists `ref_name` of reference docs where `for_tools` contains the tool. **Doc → tool**: Only `for_tools` is in YAML; `for_skills` and `skill_name` are derived (no redundant `for_skill`).

---

## 5. Lance DB: skills table — tool row metadata (JSON)

**Written by**: `omni-vector` in `packages/rust/crates/omni-vector/src/ops/writer_impl.rs` when indexing tools.

**Table**: `skills` (single table for routing + discovery).

**Per-row metadata** (JSON string column): all keys below. `skill_tools_refers` is always present; empty array when none.

| Key                      | Type                | Required                     | Meaning                                                                                        |
| ------------------------ | ------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------- |
| `type`                   | string              | Yes                          | `"command"`.                                                                                   |
| `skill_name`             | string              | Yes                          | Skill name.                                                                                    |
| `tool_name`              | string              | Yes                          | Full tool name (e.g. `researcher.run_research_graph`).                                         |
| `command`                | string              | Yes                          | Command part (e.g. `run_research_graph`).                                                      |
| `file_path`              | string              | Yes                          | Script path.                                                                                   |
| `function_name`          | string              | Yes                          | Python function name.                                                                          |
| `intents`                | array               | -                            | Intent strings.                                                                                |
| `routing_keywords`       | array               | -                            | Keywords for routing.                                                                          |
| `file_hash`              | string              | -                            | Source file hash.                                                                              |
| `input_schema`           | string              | -                            | JSON schema string.                                                                            |
| `docstring`              | string              | -                            | Function docstring.                                                                            |
| `category`               | string              | -                            | Category.                                                                                      |
| `annotations`            | object              | -                            | MCP safety annotations.                                                                        |
| `parameters`             | array               | -                            | Parameter names.                                                                               |
| **`skill_tools_refers`** | **array of string** | **Yes (key always present)** | **Reference doc names (ref_name); `[]` when empty. Source = reference markdown front matter.** |

Storage rule: `skill_tools_refers = ToolRecord.skill_tools_refers` → JSON array of strings; empty list when none.

---

## 6. Summary matrix

| Layer          | Entity / Store    | Field / Key         | Type                   | When empty  |
| -------------- | ----------------- | ------------------- | ---------------------- | ----------- |
| Markdown       | references/\*.md  | for_tools           | string (YAML)          | not present |
| Rust (scanner) | ReferenceRecord   | ref_name, for_tools | String, Option<String> | -           |
| Rust (scanner) | ToolRecord        | skill_tools_refers  | Vec<String>            | `[]`        |
| Lance (skills) | row metadata JSON | skill_tools_refers  | array of string        | `[]`        |

---

## 7. Validation / audit checklist

- [ ] **No decorator**: `@skill_command` does not take `references` or `skill_tools_refers`; tool→ref link is not parsed from Python.
- [ ] **ToolRecord**: `skill_tools_refers` is filled by indexer from `references/*.md` front matter (`for_tools` → ref_name list).
- [ ] **Lance**: `skill_tools_refers` key always present in metadata JSON; value is array of ref_name strings; empty array when none.
- [ ] **Convention**: Each list item is the reference doc name (ref_name / filename stem). Reference doc sets `for_skill` / `for_tools` in front matter (string or list; graph docs use lists).
- [ ] **Rust only parses**: No Rust logic interprets reference file content beyond front matter; ref_name is stored and written to the index.

This schema reflects the front-matter-only source for skill, tool, and reference metadata.
