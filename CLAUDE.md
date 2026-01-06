# Omni-DevEnv Fusion

> **Phase 25.3: One Tool + Trinity Architecture**
> Single Entry Point: `@omni("skill.command")`

Quick Reference: `docs/explanation/trinity-architecture.md` | `docs/skills.md`

---

## ⛔ Critical: Git Commit

**Use `/commit` slash command** - Never `git commit` via terminal.

---

## Essential Commands

- `just validate` - fmt, lint, test
- `/mcp enable orchestrator` - Reconnect omni mcp

---

## Directory Structure

```
.claude/commands/     # Slash command templates
agent/skills/*/       # Skill implementations (tools.py + prompts.md)
docs/                 # Documentation (see docs/skills.md for index)
.cache/               # Repomix skill contexts (auto-generated)
```
