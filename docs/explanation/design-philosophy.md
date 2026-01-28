# Design Philosophy

> **Status**: Historical document - Core principles still valid, but superseded by current Trinity Architecture
> **See Also**: `trinity-architecture.md` for current architecture

---

## Core Design Principles

### 1. Code is Mechanism, Prompt is Policy

The fundamental separation in Fusion:

| Layer          | Purpose        | Files                                   |
| -------------- | -------------- | --------------------------------------- |
| **Brain**      | Rules, routing | `SKILL.md` (LLM reads when skill loads) |
| **Muscle**     | Execution      | `scripts/commands.py` (@skill_command)  |
| **Guardrails** | Validation     | Lefthook, Cog, Pre-commit               |

**Key insight:** Code is mechanism (how), prompts are policy (what/when).

### 2. User Interface Design First

**Think about the user interface before implementing any feature.**

Every feature should be designed from the user's perspective:

- What does the user need to see?
- What actions can the user take?
- How does the user understand what's happening?
- What's the simplest way to achieve their goal?

> "A beautiful interface to a bad workflow is still bad. But a good interface to a good workflow is magic."

**Design before you code:**

1. Sketch the user flow
2. Define the API/interface
3. Consider edge cases
4. Then implement

### 3. Don't Reinvent the Wheel (CCC Principle)

**Use existing tools when they fit. Build only when necessary.**

The "Clean Code Concepts" (CCC) philosophy teaches us:

| Instead of...                 | Consider...                        |
| ----------------------------- | ---------------------------------- |
| Writing custom file parsers   | Using `repomix`                    |
| Building your own linter      | Using `ruff`, `prettier`, `vale`   |
| Creating custom config format | Using YAML/JSON/TOML               |
| Implementing own caching      | Using built-in LRU/frequency-based |
| Manual directory traversal    | Using `pathlib` or `repomix`       |

**The Trade-off:**

- **Use existing tools**: Faster development, standard format, community support
- **Build custom**: Full control, exact fit, no dependencies

**Our decision framework:**

1. Does an existing tool solve >80% of the problem?
2. Is it actively maintained?
3. Does it integrate with our stack (Nix, Python, etc.)?
4. If yes → Use it. If no → Build.

**Examples in this project:**

- `repomix` → Standardized knowledge XML packing
- `ruff` → Python formatting and linting
- `prettier` → Markdown/JSON formatting
- `vale` → Documentation linting

---

## Three Interaction Patterns

This project defines three clear patterns for how AI agents interact with project knowledge:

| Pattern            | When LLM reads... | Purpose                             |
| ------------------ | ----------------- | ----------------------------------- |
| **Skill Loading**  | `assets/skills/`  | Load capability packages to **act** |
| **Memory Loading** | `agent/`          | Follow rules to **act**             |
| **Document Query** | `docs/`           | Find info to **answer** questions   |

### Pattern 1: Skill Loading

When LLM needs to **perform** a task, it loads a Skill from `assets/skills/`:

```
User: "Help me commit these changes"
→ LLM loads: assets/skills/git/
→ LLM acts: follows SKILL.md + uses @skill_command commands
```

A Skill contains:

- `SKILL.md` - Rules and routing (LLM reads when skill loads)
- `scripts/commands.py` - @skill_command decorated commands
- `references/` - Workflow documentation (optional)

### Pattern 2: Memory Loading

When LLM needs to **perform** a task and no Skill is available:

```
User: "Help me write documentation"
→ LLM loads: agent/writing-style/*.md
→ LLM acts: follows writing standards
```

### Pattern 3: Document Query

When user asks **questions**, LLM queries `docs/`:

```
User: "What is the git flow?"
→ LLM queries: docs/explanation/*.md
→ LLM answers: explains the workflow
```

## The Evolution: From Agent-Centric to Skill-Centric to One Tool

### Agent-Centric (Previous Pattern)

```
Orchestrator (The Brain) ← All tools loaded always
     ↓
Hardcoded tool sets (Git + Python + Docker + K8s + ...)
     ↓
Problem: Context bloat as tools increase
```

### Skill-Centric

```
Runtime (No fixed personality)
     ↓
Dynamic Skill Loading (load only what's needed)
     ↓
Skills: git, terminal, filesystem, testing_protocol...
     ↓
Solution: Constant context cost regardless of skill count
```

### One Tool Architecture

```
Single MCP Entry Point: @omni
     ↓
Claude sees ONE tool, not 100+ functions
     ↓
Command: @omni("skill.command")
     ↓
Dispatches to: skill.command() function
```

**The Shift:**

| Dimension     | Agent-Centric     | Skill-Centric         | One Tool              |
| ------------- | ----------------- | --------------------- | --------------------- |
| **Core Unit** | Tools (functions) | Skills (packages)     | Commands              |
| **Interface** | 100+ MCP tools    | 100+ MCP tools        | 1 MCP tool            |
| **Syntax**    | `git_status()`    | `@omni("git.status")` | `@omni("git.status")` |
| **Extension** | Add tools         | Add skill directory   | Add @skill_command    |

## Why This Separation?

| Directory         | Audience     | Content                                       |
| ----------------- | ------------ | --------------------------------------------- |
| `assets/skills/`  | LLM (Claude) | Composable capability packages                |
| `agent/` (legacy) | LLM (Claude) | Rules, protocols, standards - for AI behavior |
| `docs/`           | Users        | Manuals, tutorials, explanations - for humans |

### Design Rationale

LLMs often "hallucinate" by skipping project-specific rules when answering questions.
By separating documentation into three audiences:

- **`assets/skills/`**: Self-contained packages - "load this to do X"
- **`agent/`**: Explicitly tells LLM "this is for you, read before acting"
- **`docs/`**: Clearly marked as "for users", LLM can reference it when answering

This forces the LLM to:

1. Use skill commands when **acting** with a composable capability
2. Use memory loading tools when **acting** with legacy rules
3. Use read docs tool when **answering** (finds information)

## Key Tools

| Tool                     | Pattern       | Purpose                           |
| ------------------------ | ------------- | --------------------------------- |
| `@omni("skill.command")` | One Tool      | Single entry point for all skills |
| `load_skill()`           | Skill Loading | Load skill into semantic memory   |
| `list_skills()`          | Discovery     | List available skills             |
| `@omni("help")`          | Help          | Show all available commands       |

All tools are accessed through the single `@omni` MCP tool with the format:

- `@omni("skill.command")` - Execute a skill command
- `@omni("skill")` - Show skill help

## The Skill Anatomy

Every skill follows a standardized structure:

```
assets/skills/{skill_name}/
├── SKILL.md              # Rules & routing (LLM reads when skill loads)
├── scripts/commands.py   # @skill_command decorated commands
└── references/           # Workflow documentation (optional)
```

### One Tool Architecture

All skills are accessed through a single MCP entry point:

```python
@omni("git.status")           # Dispatches to git.status command
@omni("git.commit")           # Dispatches to git.commit command
@omni("filesystem.read")      # Dispatches to filesystem.read command
```

**No more tool bloat:** Claude sees one tool, not 100+ functions.

### Slash Commands

Claude Code slash commands provide templates for workflows:

```
.claude/commands/
├── commit.md     # Smart commit workflow template
├── hotfix.md     # Hotfix workflow template
├── load-skill.md # Skill loading template
└── skills.md     # List available skills
```

Run `/commit` to trigger the smart commit workflow with lefthook and cog integration.

## Documentation Sources

| Source                        | Purpose                 | Audience    |
| ----------------------------- | ----------------------- | ----------- |
| `assets/skills/*/SKILL.md`    | Skill rules & routing   | LLM         |
| `assets/skills/*/scripts/`    | Atomic execution        | LLM         |
| `assets/skills/*/references/` | Workflow documentation  | LLM         |
| `.claude/commands/*.md`       | Slash command templates | Claude Code |
| `agent/how-to/`               | Process guides (legacy) | LLM         |
