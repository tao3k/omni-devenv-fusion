# Documentation Standards

> Where to write what, and who should read it.

---

## Documentation Role Matrix

| Location                    | Reader                 | Purpose                        | Update Frequency |
| --------------------------- | ---------------------- | ------------------------------ | ---------------- |
| `CLAUDE.md`                 | Claude (auto)          | Quick reference, key rules     | Low              |
| `docs/index.md`             | Human developers       | Navigation portal              | Low              |
| `docs/tutorials/*.md`       | New developers         | Learning paths                 | Medium           |
| `docs/how-to/*.md`          | Developers             | Task solutions                 | High             |
| `docs/reference/*.md`       | Developers             | API/config reference           | Medium           |
| `docs/explanation/*.md`     | Architects             | Design decisions               | Low              |
| `assets/skills/*/SKILL.md`  | Claude (on skill load) | Skill metadata + rules         | High             |
| `assets/skills/*/README.md` | Human developers       | Skill implementation reference | Medium           |

---

## CLAUDE.md (Claude Context)

**Reader**: Claude (auto-loaded on every conversation)

**Contents**:

- One-line project description
- Key rules (1-3 items, prohibitions)
- Common commands (3-5 items)
- Directory structure overview
- References to detailed docs

**Excludes**:

- Detailed architecture explanations
- Complete workflow descriptions
- Lengthy background explanations

**Example**:

```markdown
# Project Name

One-line description.

**Rules**:

- Never use X (use Y instead)
- Always do Z before committing

**Commands**:

- `just test` - Run tests
- `just lint` - Run linter

**Docs**: See `docs/explanation/architecture.md` for details.
```

---

## docs/ Directory Structure

### docs/index.md (Documentation Portal)

**Reader**: All developers

**Contents**:

- Documentation category index
- Brief description of each category
- Quick navigation links

**Excludes**: Detailed content (link to other files instead)

### docs/tutorials/ (Tutorials)

**Reader**: New developers

**Contents**:

- Step-by-step learning paths
- Complete examples from 0 to 1
- Assumes zero prior knowledge

**Style**: Learning-oriented, educational

**Example**:

- `getting-started.md` - Environment setup tutorial

### docs/how-to/ (How-to Guides)

**Reader**: Developers solving problems

**Contents**:

- Step-by-step instructions for specific tasks
- Problem→Solution mapping
- Best practices

**Style**: Problem-solving oriented, practical

**Example**:

- [ODF-EP Protocol](odf-ep-protocol.md#git-workflow) — Commit conventions and protocols

### docs/reference/ (Reference Docs)

**Reader**: Developers looking up details

**Contents**:

- API parameter descriptions
- Configuration options
- CLI interfaces
- Data structures

**Style**: Information-oriented, precise, complete

**Example**:

- `mcp-orchestrator.md` - MCP tool reference

### docs/explanation/ (Explanatory Docs)

**Reader**: Architects, developers wanting to understand "why"

**Contents**:

- Design decision background
- Architecture principles
- Historical evolution
- Trade-off analysis

**Style**: Understanding-oriented, in-depth analysis

**Example**:

- `system-layering.md` - Detailed architecture design

---

## assets/skills/ Directory Structure

### assets/skills/\*/SKILL.md (Skill Definition)

**Reader**: Claude (when skill is loaded into context) + Developers

**Contents**:

- YAML frontmatter (name, version, description, routing_keywords)
- System Prompt Additions (LLM rules)
- Router Logic (when to use which tool)
- Authorization Protocol
- Anti-Patterns

**Style**: Rule-oriented, YAML frontmatter + Markdown body

**Example**:

```markdown
---
name: "git"
version: "2.0.0"
description: "Git operations with Smart Commit"
routing_keywords: ["git", "commit", "push", "branch"]
---

# Git Skill

## System Prompt Additions

When this skill is active, add these guidelines:

- Use `git.status` for read-only operations
- Use `git.commit` with explicit confirmation

## Router Logic

| Operation | Tool           | When               |
| --------- | -------------- | ------------------ |
| Commit    | `git_commit()` | User says "commit" |
```

### assets/skills/\*/README.md (Skill Documentation)

**Reader**: Human developers (understanding implementation details)

**Contents**:

- How the skill works
- Command reference with examples
- Usage patterns
- Implementation notes

**Style**: Reference-oriented, detailed but readable

### assets/specs/ (Architecture Specs)

**Reader**: Architects, core contributors

**Contents**:

- Major design decisions
- Evolution plans
- Architecture review results

**Style**: Formal, authoritative

---

## Documentation Writing Principles

### 1. English Only

All documentation and all committed content in this repository must be written in **English**. This includes everything under `docs/`, `AGENTS.md`, `CLAUDE.md`, skill `SKILL.md` and `README.md`, and code comments that are part of the codebase. Commit messages must be in English. User-facing or external deliverables may use other languages only when explicitly required; the canonical project surface is English.

### 2. Single Responsibility

Each document has exactly one primary purpose. Don't explain architecture in how-to, don't explain history in reference.

### 3. DRY Principle

Avoid duplication. If the same information is needed in multiple places, extract it into a standalone document and reference it.

### 4. Reader-Oriented

Before writing, ask:

- Who will read this document?
- What do they already know?
- What do they want from this document?

### 5. Match Update Frequency

Keep frequently updated documents (like SKILL.md) concise. Less frequently updated documents (like explanation) can be more detailed.

---

## Documentation Checklist

Before creating a new document:

- [ ] Identify the target reader
- [ ] Confirm document type (tutorial/how-to/reference/explanation)
- [ ] Check if similar documents exist (avoid duplication)
- [ ] Choose appropriate location

Before updating a document:

- [ ] Does the update change the document type?
- [ ] Should stakeholders be notified?
- [ ] Does the index need updating?

---

## Quick Reference

| Need                             | Choose                      |
| -------------------------------- | --------------------------- |
| Quick reference for Claude       | `CLAUDE.md`                 |
| Learning to use                  | `docs/tutorials/`           |
| Solving a specific problem       | `docs/how-to/`              |
| Looking up API parameters        | `docs/reference/`           |
| Understanding architecture       | `docs/explanation/`         |
| Defining skill rules             | `agent/skills/*/prompts.md` |
| Recording architecture decisions | `assets/specs/`             |

---

## Claude Code Best Practices

Based on [Anthropic's Engineering Guidelines](https://www.anthropic.com/engineering/claude-code-best-practices).

### Core Philosophy

Claude Code is a **flexible, low-level, unopinionated power tool**. It provides raw model access with safety guardrails—not a forced workflow. This flexibility enables customization but requires intentional context management.

**Key Principle**: Nothing is set in stone. Treat these as starting points and adapt to your needs.

---

### CLAUDE.md Best Practices

#### Strategic Placement

| Location              | Use Case                                        |
| --------------------- | ----------------------------------------------- |
| Repository root       | Most common, shareable via git                  |
| Parent directories    | Monorepo organization                           |
| Child directories     | Pulled on demand when working in subdirectories |
| `~/.claude/CLAUDE.md` | Session-wide defaults                           |

#### Content Recommendations

CLAUDE.md should include:

- **Common bash commands** and build scripts
- **Core files, utility functions**, and architecture patterns
- **Code style guidelines** (ES modules vs CommonJS, import preferences)
- **Testing instructions** and commands
- **Repository etiquette** (branch naming, merge vs rebase)
- **Developer environment setup** (pyenv, compilers, tool versions)
- **Project-specific behaviors**, warnings, or gotchas

#### Refinement

CLAUDE.md files become part of Claude's prompts—**treat them like prompts worth tuning**:

- Use the **`#` key** during coding for inline instructions
- Consider running through a prompt improver
- Use emphasis (`IMPORTANT`, `YOU MUST`) for critical rules

---

### Communication Patterns

#### Be Specific

Claude infers intent but can't read minds. Specificity dramatically improves first-attempt success:

| Poor                                               | Better                                                                                   |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| "add tests for foo.py"                             | "write a test case for foo.py covering edge cases where user is logged out. avoid mocks" |
| "why does ExecutionFactory have such a weird api?" | "look through ExecutionFactory's git history and summarize how its api came to be"       |

#### Extended Thinking

Use trigger phrases to allocate more thinking budget:

- "think" → "think hard" → "think harder" → "ultrathink"

#### Visual Verification

- **Paste screenshots** directly (cmd+ctrl+shift+4 on macOS)
- **Drag and drop** images into prompts
- **Provide file paths** for images Claude should analyze
- Use MCP tools like Puppeteer for automated screenshots

#### Give Claude URLs

Paste specific URLs alongside prompts. Use `/permissions` to allowlist domains.

---

### Recommended Workflow Patterns

#### Pattern 1: Explore → Plan → Code → Commit

```
1. Ask Claude to read relevant files first (no coding yet)
2. Ask for a plan using "think" for extended thinking
3. Implement the solution
4. Commit and create PR
```

#### Pattern 2: TDD Workflow

```
1. Write tests based on expected input/output pairs
2. Confirm tests fail
3. Commit the tests
4. Write code until tests pass (iterate)
5. Commit the implementation
```

#### Pattern 3: Visual Iteration

```
1. Give Claude screenshot capability
2. Provide a visual mock
3. Implement, screenshot, iterate until match
4. Commit when satisfied
```

---

### Technical Recommendations

#### Subagents for Complex Problems

For complex problems, have Claude use subagents to investigate details early—this preserves context without efficiency loss.

#### Verification Methods

Give Claude ways to verify its work:

- **Screenshots** with Puppeteer MCP or iOS simulator MCP
- **Test cases** to iterate against
- **Checklists** stored in Markdown files for multi-step tasks

#### Context Management

- Use `/clear` frequently between tasks to reset context
- Use checklists or GitHub issues as scratchpads for large migrations
- Interrupt with Escape to redirect, or double-tap Escape to edit previous prompts

#### Multi-Claude Patterns

- **One writes, one reviews** — separate Claude instances
- **Multiple checkouts** — 3-4 terminal tabs with different tasks
- **Git worktrees** — lightweight alternative with isolated working directories

#### Headless Mode for Automation

Use `claude -p "prompt"` with `--output-format stream-json` for:

- Issue triage and labeling
- Subjective code reviews
- Fanning out large migrations
- CI/CD pipeline integration

---

### Configuration Files

| File                    | Purpose                                              |
| ----------------------- | ---------------------------------------------------- |
| `.mcp.json`             | MCP server configurations (check in for team access) |
| `.claude/commands/`     | Reusable slash command templates                     |
| `.claude/settings.json` | Tool allowlist settings to share with team           |
| `.claude/CLAUDE.md`     | Session-wide defaults                                |

---

### Key Takeaways

Claude Code works best when you:

1. **Provide clear context** via CLAUDE.md files
2. **Give specific instructions** (avoid ambiguity)
3. **Use visual verification** for UI work
4. **Iterate with checkpoints** (tests, screenshots, checklists)
5. **Leverage multiple instances** for complex tasks
6. **Manage context actively** (`/clear`, checklists)
