# File Operations Skill

File I/O, search, and AST-based refactoring tools.

## Core Philosophy

**"Surgical precision"** - Read, write, and refactor code with safety checks and validation.

## Tools

### read_file

Read a single file with:

- Line numbering
- Size limit (100KB max)
- Security validation

### search_files

Pattern search in files:

- Like grep but with safety checks
- Max 100 matches
- Case insensitive by default

### save_file

Write files with safety:

- Auto backup (.bak)
- Syntax validation (Python, Nix)
- Auto writing-check for markdown
- Security path validation

### ast_search

Query code structure using ast-grep:

- Structural search (not text)
- Language-aware
- Examples: "def $NAME", "import $MODULE"

### ast_rewrite

Apply structural patches:

- AST-based replacement
- CAUTION: Modifies files
- Use with backups

## Usage

```python
# Read file
await read_file(path="src/main.py")

# Search files
await search_files(pattern="TODO", path="src/")

# Write file with backup
await save_file(path="new_file.py", content="# New file")

# AST search
await ast_search(pattern="def $NAME", lang="py")

# AST rewrite
await ast_rewrite(
    pattern="print($MSG)",
    replacement="logger.info($MSG)",
    lang="py"
)
```

## Safety Features

1. **Path safety** - All operations validate paths
2. **Size limits** - Prevents reading huge files
3. **Syntax validation** - Python/Nix syntax checked on write
4. **Backups** - .bak files created before overwrite
5. **Writing checks** - Markdown style validated on write
