# Omni-DevEnv Fusion

> **Phase 25: One Tool Architecture** - Single Entry Point: `@omni("skill.command")`

---

## Quick Reference

| Resource                    | Purpose                                     |
| --------------------------- | ------------------------------------------- |
| `.claude/commands/*`        | Slash commands (e.g., `/commit`, `/hotfix`) |
| `agent/skills/*/prompts.md` | Skill rules & routing                       |
| `docs/skills.md`            | Skills documentation index                  |

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
agent/skills/*/       # Skill implementations
docs/                 # User documentation
```
