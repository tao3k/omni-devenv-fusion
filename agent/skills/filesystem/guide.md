# FileSystem Skill Guide

This skill provides file operations including reading, writing, searching, and glob patterns.

## When to Use This Skill

Use this skill when:

- Reading existing files
- Creating or modifying files
- Searching for patterns in code
- Finding files by name patterns

## Best Practices

1. **Always read before editing** - Use `read_file` to get current content
2. **Use glob patterns** for finding files by name
3. **Use search_files** for finding patterns in code
4. **Backup before overwrite** - Create backups when saving files

## File Operations

- `read_file`: Read file contents with optional line range
- `save_file`: Write content with automatic backup
- `search_files`: Search for text patterns in files
- `glob_files`: Find files matching patterns
