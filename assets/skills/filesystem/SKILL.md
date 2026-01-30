---
name: "filesystem"
version: "1.1.0"
description: "Core [FILE I/O] engine. Handles reading, writing, and direct directory listing. Does NOT perform fuzzy search or pattern discovery."
routing_keywords:
  [
    "file",
    "read",
    "write",
    "save",
    "create",
    "delete",
    "mkdir",
    "io",
    "content",
    "filesystem",
    "binary",
    "text",
    "metadata",
  ]
authors: ["omni-dev-fusion"]
intents:
  - "Read a specific file by path"
  - "Write, save, or overwrite a file"
  - "Create a new directory"
  - "Check file existence or size"
  - "Batch update multiple known files"
---

You have loaded the **Filesystem (File I/O) Skill**.

## 🛑 Scope Limitation

This skill is for **DIRECT File I/O operations** where you already know the path.

| Task               | Use Skill          | Tool                      |
| ------------------ | ------------------ | ------------------------- |
| **Find files**     | **advanced_tools** | `smart_find` (fd-powered) |
| **Search text**    | **advanced_tools** | `smart_search` (ripgrep)  |
| **AST Search**     | **code_tools**     | `smart_ast_search`        |
| **List directory** | **filesystem**     | `list_directory`          |

## Available Tools

### 📥 Reading

- `read_files`: Read multiple files with line numbers.
- `get_file_info`: Get metadata (size, type) about a file.

### 📤 Writing

- `save_file`: Safe write with **backup** and syntax validation.
- `write_file`: Raw write (no backup).
- `apply_file_changes`: **Batch** update multiple files.

### 📂 Navigation

- `list_directory`: Direct enumeration of a specific path (ls).

## Critical Best Practices

1. **Known Paths Only**: Use this skill only when you have a specific relative path.
2. **Safety First**: Prefer `save_file` over `write_file` for critical source code.
3. **Verify Listings**: If a file is missing, use `list_directory` on the parent to verify state.
4. **No Discovery**: Do not attempt to "find" things here; use `advanced_tools` for discovery.
