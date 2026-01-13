---
name: "structural_editing"
version: "1.0.0"
description: "Surgical code refactoring using AST patterns. Modify code with precision, not regex. Dry-run supported."
routing_keywords:
  [
    "refactor",
    "rename",
    "replace",
    "modify",
    "edit",
    "transform",
    "migrate",
    "upgrade",
    "surgeon",
    "surgical",
    "structural",
    "ast",
    "rewrite",
    "diff",
    "pattern",
    "sed",
    "find-and-replace",
  ]
authors: ["omni-dev-fusion"]
execution_mode: "library"
---

You have loaded the **Structural Editing Skill** (Phase 52: The Surgeon).

## Philosophy: Surgical Precision

Unlike naive find-and-replace, this skill uses AST-based pattern matching:

- **Semantic Awareness**: Understands code structure, not just text
- **Variable Capture**: `$$$` captures actual arguments, not string literals
- **Preview First**: Always preview changes before applying (dry-run)
- **Diff Generation**: See exactly what will change
- **Multi-Language**: Python, Rust, JavaScript, TypeScript support

## Architecture

```
+-------------------------------------------------------------+
|            Phase 52: The Surgeon - Structural Editing      |
+-------------------------------------------------------------+
|  ┌─────────────────────────────────────────────────────┐   |
|  |           omni-edit (Rust Core)                      |   |
|  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   |   |
|  │  │error.rs │ │types.rs │ │diff.rs  │ │capture │   |   |
|  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘   |   |
|  │                                                     |   |
|  │  ┌─────────────────────────────────────────────┐   |   |
|  │  │              editor.rs                       │   |   |
|  │  │    StructuralEditor::replace()               │   |   |
|  │  │    StructuralEditor::preview()  [DRY RUN]    │   |   |
|  │  │    StructuralEditor::apply()    [MODIFY]     │   |   |
|  │  └─────────────────────────────────────────────┘   |   |
|  └─────────────────────────────────────────────────────┘   |
|                          ↑                                 |
|              Python Bindings (PyO3)                        |
|                          ↓                                 |
|  ┌─────────────────────────────────────────────────────┐   |
|  |        structural_editing.py (Skill Layer)          |   |
|  │  structural_replace()  |  structural_preview()      |   |
|  │  structural_apply()    |  get_edit_info()           |   |
|  └─────────────────────────────────────────────────────┘   |
+-------------------------------------------------------------+
```

## Available Commands

| Command              | Description                                 | Dry Run |
| -------------------- | ------------------------------------------- | ------- |
| `structural_replace` | Replace patterns in content strings         | N/A     |
| `structural_preview` | Preview changes on a file (no modification) | ✅ Yes  |
| `structural_apply`   | Apply changes to a file (modifies file)     | ❌ No   |
| `get_edit_info`      | Get skill capability information            | N/A     |

## Pattern Syntax

| Pattern            | Meaning                       | Example Match              |
| ------------------ | ----------------------------- | -------------------------- |
| `$NAME`            | Any single identifier         | `foo`, `MyClass`           |
| `$$$`              | Variadic match (any args)     | `(a, b, c)`                |
| `$$$ARGS`          | Named variadic match          | `(x, y, z)`                |
| `$A, $B`           | Two explicit captures         | `host, port`               |
| `connect($$$)`     | Function call with any args   | `connect("host", 8080)`    |
| `class $NAME`      | Class definition              | `class Agent:`             |
| `def $NAME`        | Function definition           | `def process(data):`       |
| `old_api($$$ARGS)` | Function call with named args | `old_api(result, options)` |

**Note**: For function arguments, use `$$$` (variadic) not `$ARGS`.

## Usage Examples

### Rename Function Calls (Dry Run First)

```python
# Preview what will change (safe - no modification)
structural_preview("src/client.py", "old_connect($$$)", "new_connect($$$)")

# Output shows diff:
# // EDIT: src/client.py
# // Replacements: 3
# // Changes:
# L10: "old_connect(host, port)" -> "new_connect(host, port)"
# L15: "old_connect(a, b)" -> "new_connect(a, b)"
# L20: "old_connect(x, y)" -> "new_connect(x, y)"
#
# // Diff:
# -old_connect(host, port)
# +new_connect(host, port)
```

### Upgrade API Patterns (Content-Based)

```python
# Migrate to async API
structural_replace(
    content="result = fetch(url)",
    pattern="fetch($$$ARGS)",
    replacement="await async_fetch($$$ARGS)",
    language="python"
)
# Returns: Formatted diff showing the change
```

### Apply Changes (After Preview)

```python
# Apply only after confirming preview looks correct
structural_apply("src/client.py", "old_connect($$$)", "new_connect($$$)")
# Output: "[FILE MODIFIED]" confirmation
```

### Multi-Language Support

```python
# Rust: Rename struct
structural_preview("src/lib.rs", "pub struct OldName", "pub struct NewName")

# JavaScript: Rename function
structural_apply("src/utils.js", "oldFunc($$$)", "newFunc($$$)")

# TypeScript: Rename interface
structural_preview("src/types.ts", "interface OldName", "interface NewName")
```

## Workflow

```
1. PREVIEW (Dry Run)
   structural_preview(path, pattern, replacement)
   ↓
2. REVIEW
   - Check the generated diff
   - Verify matches are correct
   - Confirm no false positives
   ↓
3. APPLY (Only if preview looks good!)
   structural_apply(path, pattern, replacement)
   ↓
4. VERIFY
   - Run tests: `pytest`
   - Review changes: `git diff`
```

## Best Practices

1. **Always Preview First**: Use `structural_preview` before `structural_apply`
2. **Use Specific Patterns**: `old_api($$$)` is better than `old_api`
3. **Test Small Changes First**: Try on a single file before批量应用
4. **Run Tests After**: Verify changes don't break functionality

## Test Coverage

This skill has comprehensive test coverage (26 tests):

```bash
# Run structural editing tests
pytest packages/python/agent/src/agent/tests/test_structural_editing.py -v

# Test categories:
# - TestStructuralReplace (9 tests): Unit tests for content operations
# - TestStructuralPreview (4 tests): Integration tests for dry-run
# - TestStructuralApply (2 tests): File modification tests
# - TestDryRunWorkflow (1 test): Full preview → apply workflow
# - TestPatternSyntax (3 tests): Pattern variation tests
# - TestErrorHandling (4 tests): Edge cases and errors
# - TestSkillAvailability (2 tests): Skill loading verification
```

## Rust Core (omni-edit)

The underlying Rust implementation provides:

- **Atomic Module Structure**: ODF-REP compliant (lib.rs, error.rs, types.rs, diff.rs, capture.rs, editor.rs)
- **ast-grep 0.40.5**: AST-based pattern matching
- **similar 2.7**: Human-readable unified diffs
- **omni-io**: Safe file I/O with binary detection

## Key Insights

- "The Surgeon operates with precision, not force."
- "Preview twice, apply once."
- "AST patterns find code, not strings."
- "Dry-run is not a limitation - it's a feature for trust."
