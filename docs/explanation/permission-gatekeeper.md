# Permission Gatekeeper

> Trinity Architecture - Zero Trust Security Layer

## Overview

The Permission Gatekeeper implements **Zero Trust** security for skill tool execution. Every tool call is validated against the skill's declared permissions before execution.

## Zero Trust Principles

| Principle           | Implementation                                      |
| ------------------- | --------------------------------------------------- |
| **Default Deny**    | No permissions = no access to any capabilities      |
| **Explicit Allow**  | Skills must explicitly declare required permissions |
| **Least Privilege** | Minimal permission scope required                   |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Python Layer (omni.core.security)                           │
│                                                              │
│  ┌─────────────────────┐    ┌───────────────────────────┐  │
│  │ SecurityValidator   │───►│ SecurityError             │  │
│  │                     │    │ (Clear error messages)    │  │
│  │ - validate()        │    └───────────────────────────┘  │
│  │ - validate_or_raise()                                    │
│  └─────────┬───────────┘                                    │
└────────────┼────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Rust Core (omni_core_rs)                                    │
│                                                              │
│  ┌─────────────────────┐    ┌───────────────────────────┐  │
│  │ check_permission()  │───►│ PermissionGatekeeper      │  │
│  │ (PyO3 binding)      │    │                           │  │
│  │                     │    │ - O(n) pattern matching   │  │
│  │                     │    │ - Wildcard support        │  │
│  └─────────────────────┘    └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ omni-security Crate                                        │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ PermissionGatekeeper                                   │  │
│  │                                                        │  │
│  │  Supports:                                              │  │
│  │  - Exact: "filesystem:read"                           │  │
│  │  - Wildcard: "filesystem:*"                           │  │
│  │  - Admin: "*"                                         │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Permission Format

### Basic Syntax

```
category:action
```

Examples:

- `filesystem:read_file` - Allow reading files
- `network:http_post` - Allow HTTP POST requests
- `git:status` - Allow checking git status

### Wildcard Patterns

| Pattern      | Description                   | Example                                                     |
| ------------ | ----------------------------- | ----------------------------------------------------------- |
| `category:*` | Allow all actions in category | `filesystem:*` allows `filesystem:read`, `filesystem:write` |
| `*`          | Allow all tools (Admin)       | Dangerous - use sparingly                                   |

### Tool Name to Permission Mapping

Tool names use dots, permissions use colons:

| Tool Name               | Permission Format      |
| ----------------------- | ---------------------- |
| `filesystem.read_files` | `filesystem:read_file` |
| `git.status`            | `git:status`           |
| `network.http_post`     | `network:http_post`    |

## Usage

### 1. Declare Permissions in SKILL.md

```yaml
---
name: my_skill
version: 1.0.0
description: My skill with file access
permissions:
  - "filesystem:read_file"
  - "filesystem:write_file"
  - "network:*"
---
```

### 2. Validate Before Execution (Python)

```python
from omni.core.security import SecurityValidator, SecurityError

validator = SecurityValidator()

# Check permission
if not validator.validate(
    skill_name="my_skill",
    tool_name="filesystem.read_files",
    skill_permissions=["filesystem:read_file", "filesystem:write_file"],
):
    raise SecurityError(
        skill_name="my_skill",
        tool_name="filesystem.read_files",
        required_permission="filesystem:read_file",
    )
```

### 3. Raise Directly on Failure

```python
validator.validate_or_raise(
    skill_name="my_skill",
    tool_name="filesystem.read_files",
    skill_permissions=["filesystem:read_file"],
)
# Raises SecurityError if not authorized
```

### 4. Using Rust Directly

```python
from omni_core_rs import check_permission

# Direct Rust call (faster for high-frequency checks)
allowed = check_permission("filesystem.read_files", ["filesystem:*"])
```

## Error Handling

### SecurityError

```python
from omni.core.security import SecurityError

try:
    validator.validate_or_raise(
        skill_name="calculator",
        tool_name="filesystem.read_files",
        skill_permissions=[],  # Zero Trust: no permissions!
    )
except SecurityError as e:
    print(e.skill_name)      # "calculator"
    print(e.tool_name)       # "filesystem.read_files"
    print(e.required_permission)  # "filesystem:read_file"
```

Error message format:

```
SecurityError: Skill 'calculator' is not authorized to use 'filesystem.read_files'.
Required permission: 'filesystem:read_file'.
Add this permission to SKILL.md frontmatter to enable.
```

## Examples

### Calculator Skill (No File Access)

```yaml
# assets/skills/calculator/SKILL.md
---
name: calculator
version: 1.0.0
description: Mathematical calculator skill
permissions: [] # No filesystem or network access
---
```

Attempted filesystem access will be blocked:

```python
# This will raise SecurityError
validator.validate_or_raise(
    skill_name="calculator",
    tool_name="filesystem.read_files",
    skill_permissions=[],
)
```

### Git Skill (Limited Access)

```yaml
# assets/skills/git/SKILL.md
---
name: git
version: 1.0.0
description: Git operations skill
permissions:
  - "git:status"
  - "git:commit"
  - "git:push"
---
```

### Admin Skill (Full Access)

```yaml
# assets/skills/admin/SKILL.md
---
name: admin
version: 1.0.0
description: Administrative operations (use with caution)
permissions:
  - "*" # Allow everything - for trusted admins only!
---
```

## Performance

| Operation        | Python | Rust |
| ---------------- | ------ | ---- |
| Permission check | ~50μs  | ~1μs |

Rust's `PermissionGatekeeper` provides ~50x speedup for permission validation, which is important since checks occur on every tool call.

## Testing

### Rust Tests

```bash
cargo test -p omni-security permission_tests
```

### Python Tests

```bash
python -m pytest packages/python/core/tests/units/test_security/ -v
```

## Related Files

**Rust:**

- `packages/rust/crates/omni-security/src/lib.rs` - PermissionGatekeeper implementation
- `packages/rust/bindings/python/src/security.rs` - PyO3 bindings

**Python:**

- `packages/python/core/src/omni/core/security/__init__.py` - SecurityValidator wrapper
- `packages/python/core/tests/units/test_security/test_validator.py` - Tests

**Schema:**

- `packages/shared/schemas/skill_metadata.schema.json` - Generated from Rust
- `packages/shared/schemas/generate_types.py` - Type generation script
- `assets/skills/_template/SKILL.md` - Template with permissions field
