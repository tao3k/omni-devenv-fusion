# CLAUDE.md - Omni-DevEnv Fusion

> **Quick Reference Only**. Detailed docs: `agent/instructions/*.md`, `docs/reference/mcp-orchestrator.md`, `agent/how-to/*.md`, `agent/standards/*.md`

## 🚨🚨🚨 GIT COMMIT IS NOT "git commit" - CRITICAL 🚨🚨🚨

**This is the #1 rule violation that keeps happening:**

| What I Did Wrong                 | Why It's Wrong                               |
| -------------------------------- | -------------------------------------------- |
| `git commit -m "..."` (Bash)     | ❌ BYPASSES authorization protocol           |
| `git add -A && git commit` (Bash) | ❌ BYPASSES pre-commit hooks + authorization |

**The ONLY correct way to commit:**

```
1. @omni-orchestrator skill(skill="git", call='smart_commit(message="feat(scope): description")')
   → Returns: {analysis, session_id: "xxx..."}

2. User confirms by saying: "run just agent-commit"

3. @omni-orchestrator skill(skill="git", call='smart_commit(message="...", auth_token="xxx")')
   → Executes the commit
```

**If you catch yourself typing `git ...` in Bash → STOP and use skill() tool instead.**

---

## 📝 WRITING WORKFLOW - MANDATORY 🚨

**This is the #2 rule violation that keeps happening:**

| What I Did Wrong                         | Why It's Wrong                     |
| ---------------------------------------- | ---------------------------------- |
| Writing docs without load_writing_memory | BYPASSES project writing standards |
| Skipping run_vale_check before commit    | BYPASSES writing quality gate      |

**The ONLY correct way to write/edit docs:**

```
1. @omni-orchestrator skill(skill="writer", call='load_writing_memory()')  # ALWAYS first step
   → Loads: agent/writing-style/*.md into context

2. Write/Edit the document

3. @omni-orchestrator skill(skill="writer", call='run_vale_check(file_path="path/to/doc.md")')
   → Fix any violations

4. @omni-orchestrator skill(skill="writer", call='polish_text(text="...")')  # Optional

5. Then commit with smart_commit workflow
```

**If you catch yourself writing docs → STOP → load_writing_memory → continue.**

---

## 🏗️ Bi-MCP Architecture Protocol (CRITICAL)

The system is strictly divided into two specialized MCP servers. You MUST route your requests to the correct server based on the task type.

| Role             | Server         | Responsibilities                   | Key Tools                                                              |
| :--------------- | :------------- | :--------------------------------- | :--------------------------------------------------------------------- |
| **🧠 The Brain** | `orchestrator` | Planning, Routing, Context, Policy | `consult_router`, `start_spec`, `manage_context`, `skill()`           |
| **📝 The Pen**   | `coder`        | File I/O, Code Search              | `read_file`, `save_file`, `search_files`, `ast_search`                 |

**Routing Rules:**

1. **Never** ask `orchestrator` to read/write files directly. Use `coder` tools.
2. **Always** consult `orchestrator` first for new features or complex tasks (`start_spec`).
3. **Use** `skill()` to access git, terminal, testing, and other operations via `orchestrator`.
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
4. **Verification**: `skill("testing_protocol", "smart_test_runner()")` → `review_staged_changes`
5. **Delivery**: `skill("git", "git_add(files=['.'])")` → `skill("git", "smart_commit(message='...')")`

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
| Git      | `skill("git", "git_status()")`, `skill("git", "smart_commit(message='...')")`                     |
| Spec     | `start_spec` (gatekeeper), `draft_feature_spec`, `verify_spec_completeness`, `archive_spec_to_doc` |
| Search   | `search_project_code` (ripgrep), `ast_search`, `ast_rewrite` (ast-grep)                            |
| Test     | `skill("testing_protocol", "smart_test_runner()")`                                                 |
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

| Operation           | Tool to Use                                                         | Why                    |
| ------------------- | ------------------------------------------------------------------- | ---------------------- |
| Commit (analysis)   | `skill("git", "smart_commit(message='feat(scope): description')")`  | Creates session, shows diff |
| Commit (execute)    | `skill("git", "smart_commit(message='...', auth_token='xxx')")`     | Authorization protocol |
| Git status/diff/log | `skill("git", "git_status()")`, `skill("git", "git_log()")`        | Safe MCP execution     |
| Git add             | `skill("git", "git_add(files=[...])")`                              | Safe staging           |

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
- `agent/skills/` - Skill modules (filesystem, git, terminal, testing, etc.)
- `docs/` - User documentation (explanation, reference, tutorials)
- `tool-router/data/examples/` - Few-shot examples

## 📚 Documentation Classification

Understand audience before reading/writing docs:

| Directory       | Audience         | Purpose                                                   |
| --------------- | ---------------- | --------------------------------------------------------- |
| `agent/`        | LLM (Claude)     | How-to guides, standards, specs - context for AI behavior |
| `docs/`         | Users            | Human-readable manuals, tutorials, explanations           |
| `agent/skills/` | LLM + Developers | Skill modules with tools, guides, and manifests           |
| `agent/specs/`  | LLM + Developers | Feature specifications, implementation contracts          |

### When to Write Documentation

- **New workflow/process** → `agent/how-to/` (for LLM to follow)
- **User-facing guide** → `docs/` (for humans)
- **New skill module** → `agent/skills/{skill_name}/` (guide.md + tools.py)
- **Feature spec** → `agent/specs/` (contract between requirements and implementation)

## 🔌 MCP Dev

Add `@mcp.tool()` → Add security check → Add test → `just test-mcp`

## 🧠 Bi-MCP Architecture

```
Claude Desktop
       │
       ├── 🧠 orchestrator (The Brain)
       │      └── router, reviewer, skill management, git operations...
       │
       └── 📝 coder (File Operations)
              └── save_file, read_file, search_files, ast_search, ast_rewrite

Tool Routing Rules:
1. **Planning/Routing/Review** → orchestrator (router, start_spec, review_staged_changes)
2. **Skills (Git, Terminal, Testing, etc.)** → orchestrator (skill() tool)
3. **File Operations** → coder (save_file, read_file, search_files)
```

## 🎯 Skill System (Phase 13)

Skills are dynamically-loaded modules in `agent/skills/` that provide specialized capabilities.

### Available Skills

| Skill              | Purpose             | Tools (accessed via skill() tool)                     |
| ------------------ | ------------------- | ------------------------------------------------------ |
| `git`              | Git operations      | git_status, git_log, git_add, smart_commit             |
| `terminal`         | Command execution   | execute_command, inspect_environment                   |
| `testing_protocol` | Smart test runner   | smart_test_runner, run_test_command, get_test_protocol |
| `writer`           | Writing quality     | lint_writing_style, polish_text, load_writing_memory   |
| `filesystem`       | File I/O operations | list_directory, read_file, write_file, search_files    |
| `advanced_search`  | ripgrep search      | search_project_code                                    |

### Using Skills

```python
# List available skills
@omni-orchestrator list_available_skills()

# Execute skill operation (auto-loads if needed)
@omni-orchestrator skill(skill="git", call='git_status()')

# Check active skills
@omni-orchestrator get_active_skills()
```

### Creating New Skills

1. Create directory: `agent/skills/{skill_name}/`
2. Add files:
   - `manifest.json` - Skill metadata
   - `tools.py` - Tool implementations with `register(mcp)` function
   - `guide.md` - Procedural knowledge for LLM
   - `prompts.md` - System prompts
3. Skills auto-discover on server restart
