---
name: "advanced_tools"
version: "1.2.0"
description: "High-performance [FIND] and [SEARCH] engine for the project. Uses Rust-native tools (fd, ripgrep) to locate files and search code content with extreme speed. Includes safe batch refactoring."
routing_keywords:
  [
    "find",
    "search",
    "locate",
    "grep",
    "ripgrep",
    "rg",
    "fd",
    "discovery",
    "explore",
    "pattern",
    "regex",
    "match",
    "content",
    "text",
    "files",
    "codebase",
    "batch",
    "refactor",
    "replace",
    "directory",
    "tree",
  ]
authors: ["omni-dev-fusion"]
intents:
  - "Find files by name, extension, or glob pattern"
  - "Search for text or regex patterns in code content"
  - "Locate specific files across the entire project"
  - "Fast codebase exploration and discovery"
  - "Batch find and replace across multiple files"
  - "High-performance grep replacement"
  - "Scan directory for files matching a pattern"
---

You have loaded the **Advanced Tools (Find & Search) Skill**.

## 🚀 The Search Engine of Agentic OS

This skill is the **PRIMARY** gateway for locating anything in the project. It wraps high-performance Rust tools.

| Category     | Tool            | Implementation  | Best For                      |
| ------------ | --------------- | --------------- | ----------------------------- |
| **Locator**  | `smart_find`    | **fd-find**     | Finding FILES by name/path    |
| **Searcher** | `smart_search`  | **ripgrep**     | Finding TEXT inside files     |
| **Refactor** | `batch_replace` | **Rust/Python** | Multi-file search and replace |

## Available Tools

### 🔍 smart_find: Fast File Location

**ALWAYS use this to find files.** Superior to `ls` or `list_directory` for discovery.

```python
def smart_find(
    pattern: str = ".",      # Regex or glob for filename
    extension: str = None,   # Filter: 'py', 'rs', 'md'
    exclude: str = None,     # Patterns to ignore
    search_mode: str = "filename" # "filename" (fd) or "content" (rg -l)
) -> dict
```

### 🧠 smart_search: Fast Code Search

**ALWAYS use this to find code content.** The gold standard for `grep`.

```python
def smart_search(
    pattern: str,            # Text or regex to find (REQUIRED)
    file_globs: str = None,  # Filter: "*.py *.ts"
    case_sensitive: bool = True,
    context_lines: int = 0
) -> dict
```

### 🛠️ batch_replace: Safe Refactoring

**RECOMMENDED for mass changes.** Always includes a dry-run preview.

```python
def batch_replace(
    pattern: str,            # Find this
    replacement: str,        # Replace with this
    file_glob: str = "**/*",
    dry_run: bool = True     # Default is PREVIEW for safety
) -> dict
```

## Use Cases & Intention

- **"Find all python files"** -> `smart_find(extension="py")`
- **"Where is the Kernel defined?"** -> `smart_search(pattern="class Kernel")`
- **"Find files containing API_KEY"** -> `smart_find(pattern="API_KEY", search_mode="content")`
- **"Rename variable 'old_name' to 'new_name'"** -> `batch_replace(...)`

## Important Rules

1. **Discovery First**: If you don't know where a file is, use `smart_find`.
2. **Context Matters**: Use `smart_search` with `context_lines` to understand match surroundings.
3. **Respect Ignored**: All tools automatically respect `.gitignore`.
4. **Prefer Patterns**: Use specific regex patterns to reduce noise.
