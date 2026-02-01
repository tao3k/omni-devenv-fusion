# OmniCell System Operations (sys_ops) Reference

This document details the underlying protocol for the `omni_cell` tool.

## Philosophy

OmniCell treats the OS as a database.

- **Files** are records.
- **Directories** are tables.
- **Commands** are queries.

## Advanced Usage Examples

### 1. File Inspection (Structured)

Instead of `cat`, use `open` to get structured data.

```nu
# Input
open package.json

# Output (received by Agent)
{
  "name": "omni-dev-fusion",
  "version": "2.0.0",
  "dependencies": { ... }
}
```

### 2. Complex Filtering (Server-Side Filter)

Filter data in the kernel (Rust/Nu) to save context tokens.

```nu
# Find all Python files modified in the last 24 hours
ls **/*.py | where modified > ((date now) - 1day)
```

### 3. System Health

```nu
# Check memory usage
sys | get host.memory
```

## Security Protocol

- **Observe Mode**: Sandboxed, read-only.
- **Mutate Mode**: Requires explicit intent. High-risk commands (e.g., `rm -rf /`, `mkfs`) are blocked by the Rust AST Validator.
