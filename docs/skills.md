# Skills Documentation

## Overview

Omni-DevEnv Fusion uses a skill-based architecture where each skill is a self-contained module in the `assets/skills/` directory.

## Trinity Architecture

Skills are managed by the **Trinity Architecture** (Phase 25.3):

- **Code**: Hot-reloaded via mtime detection (`SkillManager`)
- **Context**: XML-packed via Repomix (`RepomixCache`)
- **State**: Persistent registry (`SkillRegistry`)

See [Trinity Architecture](./explanation/trinity-architecture.md) for details.

## Skill Structure

```
assets/skills/<skill_name>/
├── tools.py           # @skill_command decorated functions
├── prompts.md         # Skill rules (LLM context)
├── guide.md           # Developer documentation
├── manifest.json      # Skill metadata
└── repomix.json       # Atomic context config (optional)
```

## Available Skills

| Skill                | Path                                  | Description                      |
| -------------------- | ------------------------------------- | -------------------------------- |
| Git                  | `assets/skills/git/`                  | Version control, commit workflow |
| Terminal             | `assets/skills/terminal/`             | Shell command execution          |
| Filesystem           | `assets/skills/filesystem/`           | File I/O operations              |
| Testing Protocol     | `assets/skills/testing_protocol/`     | Test runner                      |
| File Ops             | `assets/skills/file_ops/`             | Batch file operations            |
| Knowledge            | `assets/skills/knowledge/`            | Project context, RAG             |
| Writer               | `assets/skills/writer/`               | Writing quality                  |
| Memory               | `assets/skills/memory/`               | Vector memory                    |
| Documentation        | `assets/skills/documentation/`        | Doc management                   |
| Code Insight         | `assets/skills/code_insight/`         | Code analysis                    |
| Software Engineering | `assets/skills/software_engineering/` | Architecture                     |
| Advanced Search      | `assets/skills/advanced_search/`      | Semantic search                  |
| Python Engineering   | `assets/skills/python_engineering/`   | Python best practices            |

## Usage

Call skills via the `@omni` MCP tool:

```python
# In Claude or any MCP client
@omni("git.status")           # Run git status
@omni("filesystem.read", {"path": "README.md"})  # Read file
@omni("git.help")             # Get full skill context
```

## Creating a New Skill

1. Copy `assets/skills/_template/` to new skill name
2. Update `manifest.json` with skill metadata
3. Add `@skill_command` decorated functions in `tools.py`
4. (Optional) Add `repomix.json` for atomic context

## Related Documentation

- [Version Control](./reference/versioning.md) - Monorepo versioning strategy
- [Git Commit Workflow](../assets/skills/git/commit-workflow.md) - Git skill usage
- [Trinity Architecture](./explanation/trinity-architecture.md) - Technical deep dive
