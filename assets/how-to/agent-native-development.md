# Agent Native Development Guide

> **Code is Mechanism, Prompt is Policy**
>
> The foundation of Omni-Dev-Fusion architecture.

---

## Core Philosophy

Modern Agent systems should follow a clear separation of concerns:

| Layer          | Purpose               | Technology                        | Rules                   |
| -------------- | --------------------- | --------------------------------- | ----------------------- |
| **Brain**      | Rules, logic, routing | Markdown (`SKILL.md`, `guide.md`) | LLM learns from docs    |
| **Muscle**     | Atomic execution      | Python (`scripts/commands.py`)    | Blind, stateless        |
| **Guardrails** | Hard compliance       | Lefthook, Cog, Pre-commit         | System-level validation |

### Key Principle

> **Python = Execution only**
> **Markdown = Rules**
> **System Tools = Validation**

---

## Why This Architecture?

### 1. Zero Maintenance

**Traditional Approach:**

```python
# Python code holds business rules
if scope not in VALID_SCOPES:
    raise ValueError(f"Invalid scope: {scope}")
```

**Agent Native Approach:**

```markdown
# SKILL.md - Rules in Markdown

Valid scopes: feat, fix, docs, style, refactor, perf, test, build, ci, chore
```

**Result:**

- Change rules without code changes
- No Python hot reload needed
- LLM learns from documentation

### 2. True Agentic Behavior

| Traditional              | Agent Native          |
| ------------------------ | --------------------- |
| Python `if/else` routing | LLM reads `SKILL.md`  |
| Hard-coded validation    | LLM understands rules |
| Code-driven workflow     | Prompt-driven routing |

### 3. Separation of Concerns

```
┌─────────────────────────────────────────────────┐
│  LLM (Brain)                                    │
│  - Reads SKILL.md                               │
│  - Understands rules                            │
│  - Makes decisions                              │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  Python (Muscle)                                │
│  - Receives LLM's intent                        │
│  - Executes atomic operations                   │
│  - No business logic                            │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  System (Guardrails)                            │
│  - Lefthook, Cog, Pre-commit                    │
│  - Hard validation                              │
│  - Rejects invalid operations                   │
└─────────────────────────────────────────────────┘
```

---

## Skill Structure

Every skill follows this structure:

```
assets/skills/{skill_name}/
├── SKILL.md        # Skill metadata + router logic
└── scripts/        # Atomic commands
    └── commands.py # @skill_command decorated functions
```

### scripts/commands.py (Muscle)

```python
"""
{skill_name} Skill - Atomic Operations

This module provides atomic git operations.
Rules are in SKILL.md. Python only executes.
"""
from mcp.server.fastmcp import FastMCP

async def git_commit(message: str) -> str:
    """
    Execute git commit directly.

    Rules (from SKILL.md):
    - Message must follow "type(scope): description"
    - Claude generates message, shows analysis, then calls this tool
    """
    # Pure execution - no validation logic
    # Validation happens at: LLM (reads SKILL.md) + System (lefthook)
    result = subprocess.run(["git", "commit", "-m", message], ...)
    return result.stdout

def register(mcp: FastMCP):
    mcp.tool()(git_commit)
```

## Development Workflow

### Adding a New Rule

**Before (Traditional):**

1. Modify Python validation code
2. Deploy/Reload
3. Test

**After (Agent Native):**

1. Edit `SKILL.md`
2. Done - LLM learns immediately

### Example: Adding New Commit Type

```markdown
# In assets/skills/git/SKILL.md

## Valid Types

Previously: feat, fix, docs, style, refactor, perf, test, build, ci, chore

NEW: `revert` - for revert commits
```

**That's it.** LLM will learn from the updated markdown.

---

## Anti-Patterns

### ❌ Don't: Business Logic in Python

```python
# WRONG - Python making decisions
if message.startswith("feat("):
    do_something()
```

### ✅ Do: Pure Execution

```python
# CORRECT - Blind execution
def git_commit(message: str) -> str:
    subprocess.run(["git", "commit", "-m", message])
    return "Done"
```

### ❌ Don't: Complex Workflows in Code

```python
# WRONG - Workflow in Python
def commit_workflow():
    validate()
    analyze()
    confirm()
    execute()
```

### ✅ Do: Workflow in Prompt

```markdown
# In SKILL.md

## Workflow

1. Observe git_status
2. Generate message
3. Show analysis
4. Wait for "yes"
5. Execute git_commit
```

---

## System Integration

### Guardrails (Validation)

| Tool       | Purpose          |
| ---------- | ---------------- |
| `lefthook` | Pre-commit hooks |
| `cog`      | Code generation  |
| `ruff`     | Python linting   |
| `vale`     | Writing style    |

These are the **final line of defense**. If LLM produces invalid output, these tools reject it.

### Context Injection

Git status is auto-injected into System Prompt:

```python
# In context_loader.py
def get_combined_system_prompt(self):
    git_status = self._get_git_status_summary()
    prompt = core_content.replace("{{git_status}}", git_status)
    return prompt
```

Result: LLM "sees" git status without tool calls.

### Dynamic Skill Loading

Skills are configured in `agent/settings.yaml`:

```yaml
skills:
  # Skills loaded at startup (available immediately)
  preload:
    - knowledge # Project Cortex - Load FIRST
    - git
    - filesystem
    - writer
    - terminal
    - testing_protocol
    - code_insight

  # On-demand: LLM can load via load_skill()
  # (all skills in assets/skills/ are available)
```

**How it works:**

| Mode      | How to Activate                      |
| --------- | ------------------------------------ |
| Preload   | Auto-loaded at server startup        |
| On-Demand | LLM calls `load_skill('skill_name')` |

**Available tools:**

- `list_available_skills()` - Show all skills in `agent/skills/`
- `get_active_skills()` - Show currently loaded skills
- `list_skill_modes()` - Show preload vs available-on-demand status
- `load_skill('name')` - Load a skill on-demand (also triggers hot reload)

### Git Skill (Simplified)

The git skill is now **minimal** - only critical operations go through MCP:

| Operation    | How                | Why                     |
| ------------ | ------------------ | ----------------------- |
| `git_commit` | MCP tool           | Needs user confirmation |
| `git_push`   | MCP tool           | Destructive operation   |
| `git status` | Claude-native bash | Read-only, safe         |
| `git diff`   | Claude-native bash | Read-only, safe         |
| `git log`    | Claude-native bash | Read-only, safe         |
| `git add`    | Claude-native bash | Safe staging            |

**Principle: Read = bash. Write = MCP.**

### Knowledge Skill (Project Cortex)

The `knowledge` skill is the **Project Cortex** - it provides structural knowledge injection:

```python
# Before any work - understand the rules
@omni-orchestrator skill(skill="knowledge", call='get_development_context()')

# When writing docs - load writing memory
@omni-orchestrator skill(skill="knowledge", call='get_writing_memory()')

# When unsure - search docs
@omni-orchestrator skill(skill="knowledge", call='consult_architecture_doc("git workflow")')
```

**Knowledge tools never execute** - they only return structured information.

**Knowledge-First Architecture:**

```
┌─────────────────────────────────────────────────────────┐
│  MCP Server (Omni-Dev-Fusion)                               │
├─────────────────────────────────────────────────────────┤
│  🧠 Knowledge Layer (knowledge skill)                   │
│     - get_development_context()                         │
│     - consult_architecture_doc()                        │
│     - get_writing_memory()                              │
├─────────────────────────────────────────────────────────┤
│  💪 Execution Layer (optional - for Desktop users)      │
│     - git, terminal, filesystem skills                  │
└─────────────────────────────────────────────────────────┘
```

---

## Migration Checklist

When migrating a skill to Agent Native:

- [ ] Move rules to `SKILL.md`
- [ ] Consolidate commands into `scripts/commands.py`
- [ ] Add router logic in SKILL.md
- [ ] Update CLAUDE.md
- [ ] Test with LLM (verify it follows rules)

---

## References

- `assets/skills/knowledge/scripts/commands.py` - Knowledge skill (no execution)
- `assets/skills/knowledge/SKILL.md` - Knowledge router logic
- `assets/skills/git/SKILL.md` - Git router logic example
- `assets/skills/git/scripts/commands.py` - Git atomic execution example
- `assets/settings.yaml` - Skill loading configuration
- `packages/python/agent/src/agent/core/skill_registry.py` - Config-driven skill loading
- `CLAUDE.md` - Quick reference for LLM
- `assets/how-to/gitops.md` - Git workflow documentation

---

## Lessons Learned: From Traditional to Agent Native

This section captures key insights from migrating from **Traditional Engineering** (Python-controlled workflows) to **Agent Native** (LLM-controlled, Prompt-driven architecture).

### The Transformation

We migrated from `commit_flow.py` (old pattern) to `skill_registry.py` + `SKILL.md` (new pattern):

| Aspect             | Old Pattern (`commit_flow.py`) | New Pattern (Skill System)     |
| ------------------ | ------------------------------ | ------------------------------ |
| **Control**        | Python scripts call LLM        | LLM is the runtime master      |
| **Business Logic** | Hardcoded in Python            | Defined in SKILL.md            |
| **Flexibility**    | Restart required for changes   | LLM learns immediately         |
| **Complexity**     | LangGraph state machines       | Atomic tools + dynamic routing |

### Key Lessons

#### 1. Mechanism vs Policy Separation

**The Problem (Old):**

```python
# commit_flow.py - Business logic in Python
def analyze_commit():
    risk_level = calculate_risk()
    suggested_msg = generate_message()
    if risk_level > threshold:
        raise ValueError("High risk commit")
```

**Why It Fails:**

- Every rule change requires code modification
- Python cannot "understand" context like an LLM
- Business logic becomes rigid and brittle

**The Solution (New):**

```markdown
# SKILL.md - Policy in Markdown

## Commit Authorization Protocol

1. Always show analysis first
2. Wait for "yes" or "confirm"
3. Only then call git_commit
```

**Benefits:**

- Rules are instantly updateable
- LLM understands context and intent
- Policy evolves independently of code

#### 2. Avoid Over-Orchestration

**The Anti-Pattern (Old):**

```python
# LangGraph state machine - overkill for simple operations
state_graph = StateGraph(CommitState)
state_graph.add_node("analyze", node_analyze)
state_graph.add_node("confirm", node_confirm)
state_graph.add_node("execute", node_execute)
state_graph.set_entry_point("analyze")
```

**Why It's Overkill:**

- Simple operations don't need complex state machines
- User flexibility is lost to predetermined paths
- Cognitive overhead for maintenance

**The Agent Native Way:**

```markdown
# SKILL.md - LLM makes routing decisions

## Router Logic

User says "commit":

1. Read git_status (bash)
2. Generate message
3. Show analysis
4. Wait for confirmation
5. Call git_commit (MCP)
```

**Benefits:**

- LLM adapts to context
- No rigid workflow enforcement
- Simpler architecture

#### 3. Control Inversion

**Old Pattern:**

```
Python Script → Calls LLM → Returns Output
```

**New Pattern:**

```
LLM (Master) ← Python Runtime (Servant)
               - Presents skills
               - Executes commands
               - Returns results
```

**The `skill_registry.py` Philosophy:**

```python
class SkillRegistry:
    """Not a workflow engine - a capability presenter."""

    def load_skill(self, name: str):
        """Present skills to LLM, don't execute workflows."""
        manifest = self._load_manifest(name)
        tools = self._load_tools(name)
        return SkillPackage(manifest, tools)
```

**Key Insight:** Registry doesn't know what "git" is - it only knows protocols.

#### 4. Dynamic & Hot-Swappable Architecture

**The `importlib` Approach:**

```python
def _load_module_from_path(self, name: str, path: str):
    """Load module from file path - enables hot reload."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # No sys.modules pollution (controlled)
    spec.loader.exec_module(module)
    return module
```

**Benefits:**

- **Hot Reload:** Update skills without restarting Agent
- **Isolation:** No global namespace pollution
- **Extensibility:** Add Rust/Node skills via same protocol

### Architecture Comparison

| Dimension            | Traditional                 | Agent Native                       |
| -------------------- | --------------------------- | ---------------------------------- |
| **Code Size**        | Large (all logic in Python) | Small (atomic execution only)      |
| **Prompt Size**      | Minimal                     | Large (rules, examples, workflows) |
| **Change Frequency** | High (code changes)         | Low (only prompt updates)          |
| **LLM Role**         | Tool for scripts            | Runtime master                     |
| **Flexibility**      | Rigid                       | Dynamic                            |

### The Result: Lightweight Core + Heavy Skills

```
packages/python/agent/src/agent/core/
├── skill_registry.py   # 50 lines - pure loading logic
├── settings.py         # Configuration driven
└── mcp_core/           # I/O mechanisms only

assets/skills/{skill}/
├── SKILL.md            # Protocol definition
├── scripts/            # Atomic execution
│   └── commands.py     # @skill_command decorated functions
└── ...                 # Other skill files
```

### What to Delete, Not Keep

**Delete immediately:**

- Workflow files with hardcoded business logic
- State machines for simple operations
- Python files that "guide" the LLM

**Keep and nurture:**

- `SKILL.md` with clear router logic
- `scripts/commands.py` with atomic operations
- `skill_registry.py` for dynamic loading

### Anti-Patterns to Avoid

| Anti-Pattern                  | Why It's Wrong         | Correct Approach              |
| ----------------------------- | ---------------------- | ----------------------------- |
| `if/else` routing in Python   | LLM should decide      | Route in SKILL.md             |
| Complex state graphs          | Over-engineering       | Atomic tools + LLM            |
| Business logic in commands.py | Couples code to policy | Move rules to SKILL.md        |
| Hardcoded validation          | LLM can't adapt        | Trust LLM + system guardrails |

### References

- `packages/python/agent/src/agent/core/skill_registry.py` - Dynamic loading implementation
- `assets/skills/git/SKILL.md` - Router logic example
- `assets/skills/git/scripts/commands.py` - Atomic execution example
- `assets/how-to/gitops.md` - Git workflow documentation

---

> **Remember: Python is the muscle, Prompt is the brain.**
