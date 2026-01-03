# CLAUDE.md - Omni-DevEnv Fusion

> **Quick Reference Only**. Detailed docs: `agent/instructions/*.md`, `docs/reference/mcp-orchestrator.md`, `agent/how-to/*.md`, `agent/standards/*.md`

## 🚨🚨🚨 GIT COMMIT IS NOT "git commit" - CRITICAL 🚨🚨🚨

**This is the #1 rule violation that keeps happening:**

| What I Did Wrong                 | Why It's Wrong                               |
| -------------------------------- | -------------------------------------------- |
| `git commit -m "..."` (Bash)     | ❌ BYPASSES authorization protocol           |
| `git add -A && gitcommit` (Bash) | ❌ BYPASSES pre-commit hooks + authorization |
| `just agent-commit` (Bash)       | ❌ MUST use smart_commit() workflow first    |

**The ONLY correct way to commit:**

```
1. @omni-orchestrator smart_commit(type="chore", scope="git-ops", message="...")
   → Returns: {authorization_required: true, auth_token: "xxx..."}

2. Display to user: "Authorization Required. Please say: run just agent-commit"

3. Wait for user to say exactly: "run just agent-commit"

4. @omni-orchestrator execute_authorized_commit(auth_token="xxx")
```

**If you catch yourself typing `git ...` in Bash → STOP and use MCP tools instead.**

---

## 📝 WRITING WORKFLOW - MANDATORY 🚨

**This is the #2 rule violation that keeps happening:**

| What I Did Wrong                         | Why It's Wrong                     |
| ---------------------------------------- | ---------------------------------- |
| Writing docs without load_writing_memory | BYPASSES project writing standards |
| Skipping run_vale_check before commit    | BYPASSES writing quality gate      |

**The ONLY correct way to write/edit docs:**

```
1. @omni-executor load_writing_memory()  # ALWAYS first step for ANY writing task
   → Loads: agent/writing-style/*.md into context

2. Write/Edit the document

3. @omni-executor run_vale_check(file_path="path/to/doc.md")
   → Fix any violations

4. @omni-executor polish_text(text="...")  # Optional: auto-fix style issues

5. Then commit with smart_commit workflow
```

**If you catch yourself writing docs → STOP → load_writing_memory → continue.**

---

## 🏗️ Tri-MCP Architecture Protocol (CRITICAL)

The system is strictly divided into three specialized MCP servers. You MUST route your requests to the correct server based on the task type.

| Role             | Server         | Responsibilities                   | Key Tools                                                              |
| :--------------- | :------------- | :--------------------------------- | :--------------------------------------------------------------------- |
| **🧠 The Brain** | `orchestrator` | Planning, Routing, Context, Policy | `consult_router`, `start_spec`, `manage_context`, `consult_specialist` |
| **📝 The Pen**   | `coder`        | File I/O, Code Search              | `read_file`, `save_file`, `search_files`, `ast_search`                 |
| **🛠️ The Hands** | `executor`     | Git, Testing, Shell, Docs          | `git_status`, `smart_commit`, `run_tests`, `run_task`                  |

**Routing Rules:**

1. **Never** ask `orchestrator` to read/write files or run git commands. It has no access.
2. **Always** consult `orchestrator` first for new features or complex tasks (`start_spec`).
3. **Use** `executor` for all terminal-like operations (tests, git).
4. **Use** `coder` for all file editing operations.

## Core Principle: Actions Over Apologies

When problems occur:

```
Identify Problem → Do NOT Apologize → Execute Concrete Actions → Verify Fix → Document Lessons
```

**Rules:**

- DO NOT say "sorry" or "I will improve"
- Instead, demonstrate concrete actions that solve the root cause
- Follow the 5-phase checklist:
  1. Verify Docs - Check if rule docs are correct
  2. Check Code - Validate Python implementation
  3. Update Rules - Fix docs or code
  4. Verify - Ensure fix works in new session
  5. Document - Update problem-solving.md with case study

## 🤖 Role

Lead Architect & Orchestrator - Manage SDLC by delegating to expert tools.

## ⚡️ Workflow

1. **Awakening**: `@omni-orchestrator manage_context(action="read")`
2. **Legislation**: `start_spec("Feature Name")` → `draft_feature_spec` → `verify_spec_completeness`
3. **Execution**: `manage_context(update_status, phase="Coding")` → `delegate_to_coder`
4. **Verification**: `smart_test_runner` → `review_staged_changes`
5. **Delivery**: `git add .` → `suggest_commit_message` → `smart_commit`

### Legislation Phase (CRITICAL)

When you judge the user is requesting NEW work, call `start_spec` FIRST:

| Your Judgment                          | Your Action                            |
| -------------------------------------- | -------------------------------------- |
| User requesting new feature/capability | Call `start_spec(name="Feature Name")` |
| User asking to build/implement/create  | Then proceed with Legislation workflow |
| Question about existing code           | No need to call `start_spec`           |

**NEVER proceed to code without calling `start_spec` first when work is NEW.**

## 🏗 Commands

- `just validate` - fmt, lint, test
- `just test-mcp` - MCP tools
- `just fmt` - format code

## ⚠️ Rules

| Category | Tools                                                                                              |
| -------- | -------------------------------------------------------------------------------------------------- |
| Git      | `smart_commit`, `suggest_commit_message`, `validate_commit_message`, `check_commit_scope`          |
| Spec     | `start_spec` (gatekeeper), `draft_feature_spec`, `verify_spec_completeness`, `archive_spec_to_doc` |
| Search   | `search_project_code` (ripgrep), `ast_search`, `ast_rewrite` (ast-grep)                            |
| Test     | `smart_test_runner`, `run_tests`, `get_test_protocol`                                              |
| Review   | `review_staged_changes` (Immune System)                                                            |
| Code     | `ast_search`, `ast_rewrite`, `save_file`, `read_file`                                              |
| Lang     | `consult_language_expert`, `get_language_standards`                                                |

## 🚑 Debugging

1. STOP - Don't retry blindly
2. OBSERVE - `manage_context(action="read")` → Check SCRATCHPAD.md
3. ORIENT - `manage_context(action="add_note", note="Hypothesis...")`
4. ACT - Use `search_files`/`read_file` → Apply fix → Retry

## 🔒 Git Operations Security

**CRITICAL: See `agent/how-to/git-workflow.md` for complete rules.**

| Operation           | Tool to Use                     | Why                    |
| ------------------- | ------------------------------- | ---------------------- |
| Commit              | `smart_commit()`                | Authorization protocol |
| Git status/diff/log | `run_task("git", [...])`        | Safe MCP execution     |
| Git add             | `run_task("git", ["add", ...])` | Safe staging           |

**NEVER use Bash for git operations.**

## 📚 Documentation Classification

| Directory           | Audience | Purpose                                       |
| ------------------- | -------- | --------------------------------------------- |
| `docs/explanation/` | Users    | Why we chose X (design decisions, philosophy) |
| `docs/reference/`   | Users    | API docs, configuration reference             |
| `docs/tutorials/`   | Users    | Step-by-step guides                           |
| `agent/`            | LLM      | How-to guides, standards, specs               |

## 🔧 Nix

Edit `.nix` → `consult_language_expert` → Review standards → Apply edits → `nix fmt`

## 📁 Directories

- `agent/` - LLM context (how-to, standards, specs)
- `src/mcp_server/` - MCP server code
- `docs/` - User documentation (explanation, reference, tutorials)
- `tool-router/data/examples/` - Few-shot examples

## 📚 Documentation Classification

Understand audience before reading/writing docs:

| Directory         | Audience         | Purpose                                                   |
| ----------------- | ---------------- | --------------------------------------------------------- |
| `agent/`          | LLM (Claude)     | How-to guides, standards, specs - context for AI behavior |
| `docs/`           | Users            | Human-readable manuals, tutorials, explanations           |
| `src/mcp_server/` | Developers       | MCP server code (Python)                                  |
| `agent/specs/`    | LLM + Developers | Feature specifications, implementation contracts          |

### When to Write Documentation

- **New workflow/process** → `agent/how-to/` (for LLM to follow)
- **User-facing guide** → `docs/` (for humans)
- **Implementation details** → `src/mcp_server/` (for contributors)
- **Feature spec** → `agent/specs/` (contract between需求 and 实现)

## 🔌 MCP Dev

Add `@mcp.tool()` → Add security check → Add test → `just test-mcp`

## 🧠 Tri-MCP Architecture

```
Claude Desktop
       │
       ├── 🧠 orchestrator (The Brain)
       │      └── router, reviewer, product_owner, lang_expert, memory...
       │
       ├── 🛠️ executor (The Hands)
       │      └── git_ops, tester, docs, advanced_search, writer...
       │
       └── 📝 coder (File Operations)
              └── save_file, read_file, search_files, ast_search, ast_rewrite

Tool Routing Rules:
1. **Planning/Routing/Review** → orchestrator (router, start_spec, review_staged_changes)
2. **Execution/Testing/Docs** → executor (git_ops, smart_test_runner, lint_writing_style)
3. **File Operations** → coder (save_file, read_file, search_files)
```
