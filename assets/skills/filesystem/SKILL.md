---
name: "filesystem"
version: "1.0.0"
description: "Safe file operations (read, write, list, search) with codebase awareness."
routing_keywords:
  [
    "file",
    "read",
    "write",
    "list",
    "directory",
    "folder",
    "path",
    "search",
    "find",
    "glob",
    "exists",
    "create",
    "delete",
    "edit",
  ]
authors: ["omni-dev-fusion"]
---

You have loaded the **Filesystem Skill**.

- You can now manipulate files in the codebase.
- **CRITICAL**: When creating new files, always ensure the parent directory exists.
- **CRITICAL**: When editing code, always strictly follow the project's coding standards.
- **CRITICAL**: If you encounter a 'FileNotFoundError', check the path using `list_directory`.
