# Project Conventions

> Universal project instructions for any LLM CLI (Claude, Gemini, OpenAI, etc.)

## 1. Temporary Files → Follow prj-spec

All auto-generated/temporary files MUST follow [numtide/prj-spec](https://github.com/numtide/prj-spec):

| Directory  | Purpose                                 |
| ---------- | --------------------------------------- |
| `.cache/`  | Caches, build artifacts, temporary data |
| `.config/` | Auto-generated configs (nixago outputs) |
| `.data/`   | Runtime data, databases                 |
| `.run/`    | PID files, runtime state                |
| `.bin/`    | Generated binaries, scripts             |

**Rules:**

- Temporary files go in `.cache/<project-name>/` or subdirectories
- `.gitignore` must exclude prj-spec directories
- **SCRATCHPAD.md** → `.cache/omni-devenv-fusion/.memory/active_context/SCRATCHPAD.md`
- **Session logs** → `.cache/omni-devenv-fusion/.memory/sessions/`

## 2. Environment Isolation

Use devenv/direnv for all development tasks:

| Command         | Purpose                                   |
| --------------- | ----------------------------------------- |
| `direnv reload` | Reload environment after `.envrc` changes |
| `devenv shell`  | Enter isolated development shell          |
| `devenv up`     | Start devenv services                     |

**Workflow:**

1. `cd` into project → direnv auto-loads (`.envrc`)
2. Changes to `.envrc` → run `direnv reload`
3. Need isolated shell → `devenv shell`
4. Dependencies managed by devenv.nix + pyproject.toml (UV)

## 3. Memory Loading vs Document Query

Two patterns for accessing knowledge - use the right tool for the right task:

### Pattern A: Memory Loading (For LLM Actions)

Use when you need to **perform** a task following project conventions.

| Tool                         | When                     | Loads                          | LLM Behavior               |
| ---------------------------- | ------------------------ | ------------------------------ | -------------------------- |
| `load_git_workflow_memory()` | Before git operations    | `agent/how-to/git-workflow.md` | Act according to rules     |
| `load_writing_memory()`      | Before writing/polishing | `agent/writing-style/*.md`     | Write following guidelines |

### Pattern B: Document Query (For User Questions)

Use when user asks **questions** about the project.

| Tool                                  | When                | Reads           | LLM Behavior         |
| ------------------------------------- | ------------------- | --------------- | -------------------- |
| `read_docs(doc="...", action="load")` | User asks questions | `docs/{doc}.md` | Answer based on docs |

**Example Workflows:**

```
User: "What is the git flow?"
→ LLM: call read_docs(doc="how-to/git-workflow", action="load")
→ MCP: returns docs content
→ LLM: answer user question

User: "Help me commit these changes"
→ LLM: call load_git_workflow_memory()
→ MCP: returns git workflow rules
→ LLM: follow rules to execute smart_commit
```

## 4. Feature Development Workflow

Three-phase process for building features with quality and context.

### Phase 1: Startup (Load Process Standards)

Before starting any feature, load the development process standards:

```
User: "Implement a new MCP tool for X"
→ LLM: call get_doc_protocol(doc="how-to/feature-development")
→ LLM: call manage_context(action="update_status", phase="Planning", focus="...")
→ LLM: establish scope and requirements
```

**Load these:**

- `agent/how-to/` - Development process guides
- `agent/standards/feature-lifecycle.md` - Spec-driven development workflow

### Phase 2: Coding (Load Language Standards)

When writing code, load language-specific conventions:

```
User: "Write the Rust implementation"
→ LLM: call get_language_standards(lang="rust")
→ LLM: follow rust conventions while coding
```

**Load these:**

- `agent/standards/lang-nix.md` - Nix conventions
- `agent/standards/lang-python.md` - Python conventions
- `agent/standards/lang-rust.md` - Rust conventions
- `agent/standards/lang-julia.md` - Julia conventions

### Phase 3: Completion (Verify Lifecycle)

Before finishing, verify all lifecycle requirements are met:

```
Feature implementation complete
→ LLM: call get_doc_protocol(doc="standards/feature-lifecycle")
→ LLM: check spec completeness, tests, docs
→ LLM: call manage_context(action="update_status", phase="Done", focus="...")
```

**Verify these:**

- Spec completeness (requirements met)
- Tests written and passing
- Documentation updated
- Code reviewed

## 5. Problem Solving Protocol

When problems occur, follow the **Actions Over Apologies** principle:

```
Identify Problem → Do NOT Apologize → Execute Concrete Actions → Verify Fix → Document Lessons
```

**Core Rules:**

- DO NOT say "sorry" or "I will improve"
- Instead, demonstrate concrete actions that solve the root cause
- Follow the 5-phase checklist:
  1. Verify Docs - Check if rule docs are correct
  2. Check Code - Validate Python implementation
  3. Update Rules - Fix docs or code
  4. Verify - Ensure fix works in new session
  5. Document - Update this file with case study

**Full Guidelines:** See `agent/instructions/problem-solving.md` (auto-loaded)

## 7. Related Documentation

| File                                    | Purpose                                  |
| --------------------------------------- | ---------------------------------------- |
| `agent/how-to/git-workflow.md`          | Git operations and commit protocol       |
| `agent/instructions/problem-solving.md` | Problem-solving guidelines (auto-loaded) |
| `agent/standards/feature-lifecycle.md`  | Spec-driven development workflow         |
| `agent/writing-style/`                  | Writing standards                        |
| `agent/standards/lang-*.md`             | Language-specific conventions            |

## 8. Python Development with UV

**UV is our Python package manager.**

**Workspace:**

- Root: `pyproject.toml` with `[tool.uv.workspace].members = ["mcp-server"]`
- Package: `mcp-server/pyproject.toml` → package name: `omni_orchestrator`

**Commands:**

```bash
uv sync                          # Sync dependencies
uv run python -c "..."          # Run Python (from project root)
uv pip install -e mcp-server/   # Install mcp-server as editable (for imports)
uv add <pkg>                    # Add dependencies
```

**Debug MCP Tools:**

```python
import sys
sys.path.insert(0, 'mcp-server')
from docs import load_doc
from lang_expert import StandardsCache
from git_ops import GitWorkflowCache
```

**Fix Import Error:**

```
ModuleNotFoundError: mcp_server
→ Add: sys.path.insert(0, 'mcp-server')
```
