---
name: "writer"
version: "1.0.0"
description: "Text manipulation and file editing agent. KEYWORDS: replace, update, modify, edit, change, rewrite, insert, append, write, delete, content, text, file, documentation."
routing_keywords:
  [
    "writing",
    "style",
    "grammar",
    "lint",
    "polish",
    "improve",
    "rewrite",
    "text",
    "documentation style",
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
  - "Polish or improve writing"
  - "Check grammar and style"
  - "Rewrite text"
  - "Apply writing standards"
---

# Writer Skill System Prompts

When the Writer skill is loaded, use these guidelines for all writing tasks.

## Writing Principles (Module 01)

1. **Concise over verbose** - Remove unnecessary words
2. **Active voice** - Use "we" and "do", not "it is done"
3. **Parallel structure** - Same grammatical form for related items
4. **Short paragraphs** - Maximum 3-4 sentences per paragraph

## Rosenberg Mechanics (Module 02)

### Clutter Words to Remove

| Instead of            | Use      |
| --------------------- | -------- |
| utilize               | use      |
| facilitate            | help     |
| in order to           | to       |
| at this point in time | now      |
| due to the fact that  | because  |
| in the event that     | if       |
| a large number of     | many     |
| refer back to         | refer to |
| currently             | (remove) |
| basically             | (remove) |
| essentially           | (remove) |
| actually              | (remove) |
| very                  | (remove) |
| really                | (remove) |

### Passive Voice Detection

- Mark sentences using "is/are/was/were/been being" + past participle
- Flag but don't auto-fix - human judgment needed

## Structure Rules (Module 03)

1. **One H1 only** - Document title at top
2. **No skipping levels** - H2 -> H3 -> H4 (never H2 -> H4)
3. **Code blocks labeled** - Use Input/Output comments
4. **Blank lines between sections** - Visual breathing room

## Technical Writing (Module 04)

- Use present tense ("returns" not "will return")
- Second person ("you" for tutorials)
- Specific over generic ("click Save" not "save it")
- Imperative mood for steps ("Run command X")

## Workflow

When writing documentation:

1. Call `load_writing_memory()`
2. Draft content
3. Call `polish_text()` before saving
4. Call `run_vale_check()` for final verification
5. Use `save_file()` with auto_check_writing=True
