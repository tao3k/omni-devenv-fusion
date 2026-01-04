# Git Skill - Procedural Knowledge

## Overview

This skill provides git operations. It enforces the **Smart Commit Protocol** for clean history.

## Architecture

```
agent/skills/git/
├── manifest.json   # Skill metadata
├── tools.py        # git_commit, git_push (MCP tools)
├── prompts.md      # Router logic + Authorization Protocol (READ THIS)
└── guide.md        # This file (procedural reference)
```

## Tools Available

### MCP Tools (Require Confirmation)

| Tool | Purpose | Usage |
|------|---------|-------|
| `git_commit(message)` | Execute commit | `skill("git", "git_commit(message='feat: desc')")` |
| `git_push()` | Push to remote | `skill("git", "git_push()")` |

### Claude-native Operations (No Tool Needed)

| Operation | Command | Notes |
|-----------|---------|-------|
| Status | `git status` | Read-only |
| Diff | `git diff` | Read-only |
| Add | `git add <files>` | Safe staging |
| Log | `git log` | Read-only |

## Commit Authorization Protocol

See **`prompts.md`** for full details. The authorization template:

```
📋 Commit Analysis:

   Type: feat
   Scope: git
   Message: describe your change

🔒 *Authorization Required*
   Please say: "yes" ✅ or "confirm" ✅, or "skip" ⏭️
```

**Flow:**
1. Claude reads `prompts.md` → understands rules
2. Claude shows authorization template
3. User confirms
4. Claude calls `git_commit`

## Commit Message Format

```
<type>(<scope>): <subject>

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
```

## File Locations

| Path | Purpose |
|------|---------|
| `agent/skills/git/tools.py` | Python execution (blind) |
| `agent/skills/git/prompts.md` | Rules + Router Logic + Authorization Protocol |
| `agent/skills/git/guide.md` | This file (procedural reference) |
