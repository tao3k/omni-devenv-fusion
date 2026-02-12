# Router File Discovery Intent Report

## Scope

This report documents the production routing behavior for file-discovery intents (for example, "find files", "find \*.py", "list directories") and where each ranking signal comes from.

## Data Sources Used By Hybrid Search

The router does not rank from a single field. It uses a fused score built from:

1. Vector similarity from Lance table rows
2. Keyword stream (Tantivy BM25 or Lance FTS depending on backend)
3. Metadata rerank signals from tool records

### Metadata Field Mapping

These fields are indexed and used in ranking:

- `tool_name`: exact tool identity (e.g. `advanced_tools.smart_find`)
- `description`: tool-level text from `@skill_command(description=...)` or docstring fallback
- `category`: tool category from `@skill_command(category=...)` (or inferred fallback)
- `keywords`: merged scanner keywords (skill + tool)
- `intents`: skill intents and intent-like phrases
- `file_path`: only for payload/context, not core score term

Primary code path:

- Rust search path: `packages/rust/crates/omni-vector/src/skill/ops_impl.rs`
- Fusion: `packages/rust/crates/omni-vector/src/keyword/fusion.rs`
- Scanner source for decorator metadata: `packages/rust/crates/omni-scanner/src/skills/tools.rs`

## Ranking Pipeline (Current)

1. Vector candidates are retrieved from Lance.
2. Vector candidates are sorted by vector score before RRF fusion.
3. Keyword hits are fused if available.
4. If keyword backend is unavailable/fails, fusion still runs with empty keyword hits.
5. Metadata rerank runs for all query_text searches.
6. For file-discovery intent, `advanced_tools.smart_find` receives strong intent bonus.

## File Discovery Intent Detection

Query is classified as file-discovery intent when normalized terms include one or more of:

- `find`
- `list`
- `file` / `files`
- `directory` / `folder`
- `path`
- `glob`
- extension wildcard tokens like `*.py`, `*.rs`

## Scenario Boundaries

Use `advanced_tools.smart_find` as preferred candidate when:

- user intent is locating files/directories
- query includes file patterns, extensions, path constraints
- task is discovery, not content grep

Use `advanced_tools.smart_search` as preferred candidate when:

- user intent is finding text/patterns inside files
- regex/content matching is explicit
- context lines or content-level matching is requested

Use `code.code_search` when:

- user intent is semantic/AST code understanding, symbol lookup, architecture-level code navigation

## Regression Guard Added

A deterministic Rust test now enforces this behavior:

- `test_search_tools_file_discovery_intent_boost_without_keyword_backend`
- file: `packages/rust/crates/omni-vector/tests/test_rust_cortex.rs`

This protects the critical case where keyword backend is unavailable and file-discovery intent must still prioritize `smart_find`.

## Validation Snapshot

Executed validations after this change:

- `cargo test -p omni-vector --test test_rust_cortex test_search_tools_file_discovery_intent_boost_without_keyword_backend -- --nocapture`
- `cargo test -p omni-vector --test test_fusion --test test_search -- --nocapture`
- route scenario re-run with rebuilt/reinstalled `omni-core-rs`
