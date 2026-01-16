---
name: "filesystem"
version: "1.0.0"
description: "File I/O operations (read, write, list) for the codebase."
routing_keywords:
  [
    "file",
    "read",
    "write",
    "list",
    "directory",
    "folder",
    "path",
    "glob",
    "exists",
    "create",
    "delete",
    "edit",
  ]
authors: ["omni-dev-fusion"]
intents:
  - "Read a file"
  - "Write or create a file"
  - "List directory contents"
  - "Check if file exists"
  - "Get file metadata"
  - "Batch write multiple files"
---

You have loaded the **Filesystem Skill**.

## Scope: FILE I/O ONLY

This skill handles **file reading and writing operations** ONLY.

## What to Use Instead

| Task                  | Use Skill              | Tool                                     |
| --------------------- | ---------------------- | ---------------------------------------- |
| Text search in files  | **advanced_search**    | `search_project_code` (ripgrep)          |
| Find files by pattern | **filesystem**         | `list_directory` + path patterns         |
| AST pattern search    | **code_navigation**    | `search_code`, `search_directory`        |
| Code refactoring      | **structural_editing** | `structural_replace`, `structural_apply` |

## Available Tools

- `read_file`: Read file content with line numbers
- `save_file`: Write file with backup and validation
- `write_file`: Simple file write (no backup)
- `apply_file_changes`: Batch write multiple files
- `list_directory`: List directory contents
- `get_file_info`: Get file metadata

## Important

- **CRITICAL**: When creating new files, always ensure the parent directory exists.
- **CRITICAL**: When editing code, always strictly follow the project's coding standards.
- **CRITICAL**: If you encounter a 'FileNotFoundError', check the path using `list_directory`.
