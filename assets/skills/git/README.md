# Git Skill - Procedural Knowledge

## Overview

This skill provides git operations. It enforces the **Smart Commit Protocol** for clean history.

## Architecture

```
agent/skills/git/
├── manifest.json   # Skill metadata
├── tools.py        # git_commit, git_push (MCP tools)
├── prompts.md      # Router logic + Authorization Protocol (LLM reads this)
└── guide.md        # This file (human procedural reference)
```

## Tools Available

### MCP Tools (Require Confirmation)

| Tool                  | Purpose        | Usage                                              |
| --------------------- | -------------- | -------------------------------------------------- |
| `git_commit(message)` | Execute commit | `skill("git", "git_commit(message='feat: desc')")` |
| `git_push()`          | Push to remote | `skill("git", "git_push()")`                       |

### Claude-native Operations (No Tool Needed)

| Operation | Command           | Notes        |
| --------- | ----------------- | ------------ |
| Status    | `git status`      | Read-only    |
| Diff      | `git diff`        | Read-only    |
| Add       | `git add <files>` | Safe staging |
| Log       | `git log`         | Read-only    |

## Workflow

1. **Read Rules**: LLM reads `prompts.md` → understands authorization protocol
2. **Show Analysis**: Claude shows commit analysis for user confirmation
3. **User Confirms**: User says "yes" or "confirm"
4. **Execute**: Claude calls `git_commit`

## File Locations

| Path                          | Purpose                                       |
| ----------------------------- | --------------------------------------------- |
| `agent/skills/git/tools.py`   | Python execution (blind)                      |
| `agent/skills/git/prompts.md` | Rules + Router Logic + Authorization Protocol |
| `agent/skills/git/guide.md`   | This file (human procedural reference)        |
