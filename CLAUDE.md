# CLAUDE.md - Orchestrator Edition

> **Quick Reference Only**. Detailed docs: `mcp-server/README.md`, `agent/how-to/*.md`, `agent/standards/*.md`

## 🤖 Role

Lead Architect & Orchestrator - Manage SDLC by delegating to expert tools.

## ⚡️ Workflow

1. **Awakening**: `@omni-orchestrator manage_context(action="read")`
2. **Legislation**: `draft_feature_spec` → `verify_spec_completeness`
3. **Execution**: `manage_context(update_status, phase="Coding")` → `delegate_to_coder`
4. **Verification**: `smart_test_runner` → `review_staged_changes`
5. **Delivery**: `git add .` → `suggest_commit_message` → `smart_commit`

## 🏗 Commands

- `just validate` - fmt, lint, test
- `just test-mcp` - MCP tools
- `just fmt` - format code

## ⚠️ Rules

| Category | Tools                                                                                     |
| -------- | ----------------------------------------------------------------------------------------- |
| Git      | `smart_commit`, `suggest_commit_message`, `validate_commit_message`, `check_commit_scope` |
| Spec     | `draft_feature_spec`, `verify_spec_completeness`, `archive_spec_to_doc`                   |
| Search   | `search_project_code` (ripgrep), `ast_search`, `ast_rewrite` (ast-grep)                   |
| Test     | `smart_test_runner`, `run_tests`, `get_test_protocol`                                     |
| Review   | `review_staged_changes` (Immune System)                                                   |
| Code     | `ast_search`, `ast_rewrite`, `save_file`, `read_file`                                     |
| Lang     | `consult_language_expert`, `get_language_standards`                                       |

## 🚑 Debugging

1. STOP - Don't retry blindly
2. OBSERVE - `manage_context(action="read")` → Check SCRATCHPAD.md
3. ORIENT - `manage_context(action="add_note", note="Hypothesis...")`
4. ACT - Use `search_files`/`read_file` → Apply fix → Retry

## 🔧 Nix

Edit `.nix` → `consult_language_expert` → Review standards → Apply edits → `nix fmt`

## 📁 Directories

- `agent/` - LLM context (how-to, standards, specs)
- `mcp-server/` - MCP server code & docs
- `tool-router/data/examples/` - Few-shot examples

## 📚 Documentation Classification

Understand audience before reading/writing docs:

| Directory         | Audience         | Purpose                                                   |
| ----------------- | ---------------- | --------------------------------------------------------- |
| `agent/`          | LLM (Claude)     | How-to guides, standards, specs - context for AI behavior |
| `docs/`           | Users            | Human-readable manuals, tutorials, explanations           |
| `mcp-server/*.md` | Developers       | Technical implementation docs, architecture decisions     |
| `agent/specs/`    | LLM + Developers | Feature specifications, implementation contracts          |

### When to Write Documentation

- **New workflow/process** → `agent/how-to/` (for LLM to follow)
- **User-facing guide** → `docs/` (for humans)
- **Implementation details** → `mcp-server/` (for contributors)
- **Feature spec** → `agent/specs/` (contract between需求 and 实现)

## 🔌 MCP Dev

Add `@mcp.tool()` → Add security check → Add test → `just test-mcp`
