# Skills Documentation

## Overview

Omni-DevEnv Fusion uses a skill-based architecture where each skill is a self-contained module with:

- **tools.py** - Atomic execution functions
- **prompts.md** - Rules and routing logic
- **commit-workflow.md** - Workflow documentation (if applicable)

## Available Skills

| Skill                | Path                                 | Description                      |
| -------------------- | ------------------------------------ | -------------------------------- |
| Git                  | `agent/skills/git/`                  | Version control, commit workflow |
| Terminal             | `agent/skills/terminal/`             | Shell command execution          |
| Filesystem           | `agent/skills/filesystem/`           | File I/O operations              |
| Testing Protocol     | `agent/skills/testing_protocol/`     | Test runner                      |
| File Ops             | `agent/skills/file_ops/`             | Batch file operations            |
| Knowledge            | `agent/skills/knowledge/`            | Project context                  |
| Writer               | `agent/skills/writer/`               | Writing quality                  |
| Memory               | `agent/skills/memory/`               | Vector memory                    |
| Documentation        | `agent/skills/documentation/`        | Doc management                   |
| Code Insight         | `agent/skills/code_insight/`         | Code analysis                    |
| Software Engineering | `agent/skills/software_engineering/` | Architecture                     |
| Advanced Search      | `agent/skills/advanced_search/`      | Semantic search                  |

## Quick Links

- [Git Commit Workflow](../agent/skills/git/commit-workflow.md)
