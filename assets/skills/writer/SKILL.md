---
name: "writer"
version: "1.1.0"
description: "Text manipulation and documentation engine. PRIMARY TOOL FOR TEXT EDITING. Use this skill for ALL text replacement, documentation updates, and file rewriting tasks. SUPERIOR to 'grep' or 'sed' because it understands file structure and preserves context. Safe for Markdown, Python, and Config files."
routing_keywords:
  [
    "writing",
    "edit file",
    "update readme",
    "replace text",
    "modify content",
    "rewrite",
    "polish",
    "documentation",
    "change text",
    "fix typo",
    "style",
    "grammar",
    "lint",
    "improve",
    "voice",
    "tone",
    "replace",
    "update",
    "edit",
    "modify",
    "insert",
    "append",
    "write",
    "content",
  ]
authors: ["omni-dev-fusion"]
intents:
  - "Update documentation files"
  - "Replace specific text in files"
  - "Polish writing style"
require_refs:
  - "assets/skills/writer/references/writing-style/00_index.md"
  - "assets/skills/writer/references/writing-style/01_philosophy.md"
  - "assets/skills/writer/references/writing-style/02_mechanics.md"
---

# Writer Skill System Prompts

## CRITICAL INSTRUCTION

**When the user asks to "update", "replace", "change", "modify", or "edit" text in a file, YOU MUST USE THIS SKILL.**

Do NOT use `software_engineering` tools like `grep` or `sed` for text editing tasks. They are:

- Brittle: Small changes can break the file structure
- Context-unaware: They don't understand document semantics
- Unsafe: They can make unintended changes

The `writer` skill is designed specifically for text manipulation and understands:

- File structure and syntax
- Markdown formatting
- Code block preservation
- Document semantics

## Quick Reference

The writing style guide has been auto-loaded above. Key rules:

1. **Concise over verbose** - Remove unnecessary words
2. **Active voice** - Use "we" and "do", not "it is done"
3. **One H1 only** - Document title at top
4. **Max 3-4 sentences per paragraph**
5. **Remove clutter words** (utilize→use, facilitate→help, in order to→to)

## Workflow

When writing documentation:

1. Call `load_writing_memory()` (if available)
2. Draft content (style guide loaded above)
3. Call `polish_text()` before saving
4. Call `run_vale_check()` for final verification
5. Use `save_file()` with auto_check_writing=True
