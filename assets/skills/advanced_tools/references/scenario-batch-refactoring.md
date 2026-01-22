# Scenario: Batch Refactoring (Search-and-Destroy)

**Danger Level**: High - Modifies multiple files in one operation

**Safety Feature**: Dry-run mode with unified diff preview

## Overview

The `batch_replace` command enables large-scale refactoring across multiple files while maintaining safety through preview functionality.

## Workflow

```
1. Discovery    → Use `rg -l` to find files containing pattern
2. Preview      → Run with dry_run=True to see unified diffs
3. Validation   → Review changes, verify no unintended modifications
4. Apply        → Run with dry_run=False to commit changes
```

## Command Reference

### batch_replace

```python
@skill_command(
    name="batch_replace",
    description="Replace regex pattern across multiple files. Default is dry-run (preview).",
    autowire=True,
)
def batch_replace(
    pattern: str,              # Regex pattern to search
    replacement: str,          # Replacement string
    file_glob: str = "**/*",   # File filter (e.g., "**/*.py")
    dry_run: bool = True,      # Preview mode (default: True)
    max_files: int = 50,       # Safety limit
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
```

### Parameters

| Parameter     | Type   | Default  | Description                     |
| ------------- | ------ | -------- | ------------------------------- |
| `pattern`     | `str`  | -        | Regex pattern to search for     |
| `replacement` | `str`  | -        | Replacement string              |
| `file_glob`   | `str`  | `"**/*"` | Glob pattern to filter files    |
| `dry_run`     | `bool` | `True`   | Generate diff without modifying |
| `max_files`   | `int`  | `50`     | Maximum files to process        |

## Return Structure

```python
{
    "success": bool,
    "mode": "Dry-Run" | "Live",
    "files_matched": int,
    "files_changed": int,
    "total_replacements": int,
    "changes": [
        {
            "file": "path/to/file.py",
            "replacements": 3,
            "status": "Dry-Run" | "Modified",
            "diff": "--- a/path/to/file.py\n+++ b/path/to/file.py\n@@ -1,3 +1,3 @@\n- old content\n+ new content"
        }
    ]
}
```

## Safety Mechanisms

1. **Dry-Run by Default**: `dry_run=True` prevents accidental modifications
2. **File Limit**: `max_files=50` prevents mass changes
3. **Diff Preview**: Unified diff shows exact changes before applying
4. **Project Sandbox**: All operations constrained to project root

## Usage Examples

### Example 1: Preview Refactoring

```python
# Find and preview renaming "old_function" to "new_function"
result = batch_replace(
    pattern="old_function",
    replacement="new_function",
    file_glob="**/*.py",
    dry_run=True,
)

# Review changes
for change in result["changes"]:
    print(f"File: {change['file']}")
    print(f"Replacements: {change['replacements']}")
    print(change["diff"])
```

### Example 2: Apply Refactoring

```python
# If preview looks correct, apply changes
result = batch_replace(
    pattern="old_function",
    replacement="new_function",
    file_glob="**/*.py",
    dry_run=False,  # Live mode
)

print(f"Modified {result['files_changed']} files")
print(f"Total replacements: {result['total_replacements']}")
```

### Example 3: Batch TODO Cleanup

```python
# Replace all TODO comments with FIXME
result = batch_replace(
    pattern=r"TODO:?\s*",
    replacement="FIXME: ",
    file_glob="**/*.{py,js,ts}",
    dry_run=True,
)

# If满意, apply
if result["success"] and result["files_changed"] > 0:
    apply = batch_replace(
        pattern=r"TODO:?\s*",
        replacement="FIXME: ",
        file_glob="**/*.{py,js,ts}",
        dry_run=False,
    )
```

### Example 4: API Version Migration

```python
# Migrate from v1 API to v2
result = batch_replace(
    pattern=r"api\.v1\.(\w+)",
    replacement=r"api.v2.\1",
    file_glob="**/*.{py,js}",
    dry_run=True,
)

print(f"Found {result['files_matched']} files")
print(f"Would modify {result['files_changed']} files")
```

## Best Practices

1. **Always Preview First**: Never run with `dry_run=False` without reviewing diffs
2. **Use Specific Patterns**: Narrow patterns reduce risk of unintended changes
3. **Limit File Scope**: Use `file_glob` to restrict to relevant files
4. **Check File Count**: If `files_matched` is unexpectedly high, refine pattern
5. **Version Control**: Commit before running live mode

## Common Patterns

| Task               | Pattern        | Replacement |
| ------------------ | -------------- | ----------- |
| Rename function    | `old_name`     | `new_name`  |
| Update API version | `v1\.(\w+)`    | `v2.\1`     |
| Change import      | `from \.old`   | `from .new` |
| Add prefix         | `(\w+)_suffix` | `prefix_\1` |
| Remove suffix      | `(\w+)_old`    | `\1`        |

## Error Handling

```python
result = batch_replace(pattern="...", replacement="...")

if not result["success"]:
    if "Too many files" in result.get("error", ""):
        # Refine pattern or increase max_files
        pass
    elif "ripgrep not found" in result.get("error", ""):
        # Install ripgrep
        pass
```

## Related Commands

- `regex_replace`: Single file regex replacement
- `smart_search`: Text search with ripgrep
- `smart_find`: File finding with fd
