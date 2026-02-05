---
name: writer
description: Use when editing files, updating documentation, replacing text, polishing writing style, or performing text manipulation tasks.
metadata:
  author: omni-dev-fusion
  version: "1.1.0"
  source: "https://github.com/tao3k/omni-dev-fusion/tree/main/assets/skills/writer"
  routing_keywords:
    - "writing"
    - "edit file"
    - "update readme"
    - "replace text"
    - "modify content"
    - "rewrite"
    - "polish"
    - "documentation"
    - "change text"
    - "fix typo"
    - "style"
    - "grammar"
    - "lint"
    - "improve"
    - "voice"
    - "tone"
    - "replace"
    - "update"
    - "edit"
    - "modify"
    - "insert"
    - "append"
    - "write"
    - "content"
  intents:
    - "Update documentation files"
    - "Replace specific text in files"
    - "Polish writing style"
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

### Editing Files (Primary Use Case)

When editing files (MOST COMMON):

1. **ONE-TIME READ**: Read the file ONCE using `filesystem.read_files`. DO NOT call `cat`, `head`, or `read_file` again. The content stays in your context.
2. **ANALYSIS**: Plan your edits based on the content in context.
3. **EXECUTION**: Use `writer.replace` or `writer.rewrite` with the exact strings from step 1.
4. **VERIFY**: Done. No need to re-read.

**FORBIDDEN**: Repeated reads of the same file waste tokens and slow down the agent.

### Writing Documentation

When writing documentation:

1. **Trust the Context**: The writing style guide has been auto-loaded above. Rely on it.
2. **Draft Content**: Write following the style rules in your context.
3. **Polish**: Use `writer.polish_text()` before saving if needed.
4. **Save**: Use `filesystem.write_file()` or `writer.rewrite()`.

**DO NOT** run external validation tools like `vale` unless explicitly requested. The style guide in context is sufficient.
