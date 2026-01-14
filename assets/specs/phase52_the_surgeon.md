# Phase 52: The Surgeon

> **Status**: Implemented (Partially - AST framework in progress)
> **Date**: 2026-01-13
> **Related**: Phase 50 (The Cartographer), Phase 57 (omni-vector)

## Overview

Phase 52 introduces **The Surgeon** - AST-based structural editing with dry-run support. This enables safe, precise code modifications that understand code structure rather than treating code as text.

## The Problem

**Before Phase 52**: Text-based editing is error-prone

```python
# Problem: String replacement doesn't understand code structure
def replace_in_file(path, old_code, new_code):
    content = read_file(path)
    content = content.replace(old_code, new_code)  # DANGEROUS!
    write_file(path, content)

# Issues:
# 1. Matches partial strings in comments or strings
# 2. Doesn't handle code formatting
# 3. Can't verify changes are syntactically correct
# 4. No preview before applying
```

## The Solution: AST-Based Structural Editing

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Phase 52: The Surgeon - Architecture                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Omni Edit Framework                              │   │
│  │                                                                       │   │
│  │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │   │   AST Parser    │  │   Rule Engine   │  │   Apply Engine  │     │   │
│  │   │  (ast-grep)     │  │  (Patterns)     │  │  (Dry-run/Real) │     │   │
│  │   └────────┬────────┘  └────────┬────────┘  └────────┬────────┘     │   │
│  │            │                    │                    │               │   │
│  │            └────────────────────┼────────────────────┘               │   │
│  │                                 ▼                                     │   │
│  │   ┌─────────────────────────────────────────────────────────────┐   │   │
│  │   │                   omni-edit (Python API)                    │   │   │
│  │   │                                                               │   │   │
│  │   │   edit = OmniEdit("src/")                                    │   │   │
│  │   │   preview = edit.preview("def $NAME($$$): $$$",              │   │   │
│  │   │       replacement="def $NAME($ARGS) -> $RET:")               │   │   │
│  │   │   result = edit.apply(preview)                               │   │   │
│  │   └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Concepts

### 1. Pattern Matching (ast-grep)

Instead of regex, use AST patterns to match code:

```python
# AST Pattern - Matches any function definition
pattern = "def $NAME($$$): $$$"

# Matches:
# def add(a, b):
#     return a + b
#
# def connect(timeout: int = 10):
#     ...

# Does NOT match:
# class MyClass:  # Not a function
# if x > 0:       # Not a function
```

### 2. Variable Capture ($NAME, $ARGS)

Patterns support variable capture for replacement:

```python
# Pattern with captures
pattern = "def $NAME($PARAMS): $BODY"

# Replacement using captures
replacement = "def $NAME($PARAMS) -> Any: $BODY"
```

### 3. Multi-file Operations

```python
# Apply change to all matching functions in project
edit = OmniEdit("src/")
edit.apply_all(
    pattern="print($$$)",
    replacement="logger.info($$$)",
    dry_run=False,  # Preview first!
)
```

## API Reference

### OmniEdit Class

```python
class OmniEdit:
    """
    AST-based code editor with dry-run support.

    Uses ast-grep for pattern matching and safe application.
    """

    def __init__(self, root: str, language: str = "python"):
        """
        Initialize editor with project root.

        Args:
            root: Project root directory
            language: Programming language (python, rust, etc.)
        """
        self.root = Path(root)
        self.language = language

    def preview(
        self,
        pattern: str,
        replacement: str,
        path: Optional[str] = None,
    ) -> EditPreview:
        """
        Preview changes without applying them.

        Returns:
            EditPreview with:
            - matched_files: List of affected files
            - changes: List of per-file changes
            - safety_score: 0.0 (unsafe) to 1.0 (safe)
        """
        # Use ast-grep to find matches
        matches = self._grep(pattern, path)

        # Build preview
        preview = EditPreview(
            pattern=pattern,
            replacement=replacement,
            matched_files=[],
            changes=[],
            safety_score=1.0,
        )

        for match in matches:
            # Calculate affected region
            affected_code = self._extract_region(match)

            # Build replacement
            new_code = self._build_replacement(match, replacement)

            preview.changes.append(FileChange(
                path=match.file,
                line_range=(match.start.line, match.end.line),
                old_code=affected_code,
                new_code=new_code,
            ))
            preview.matched_files.append(match.file)

        return preview

    def apply(self, preview: EditPreview) -> ApplyResult:
        """
        Apply a previewed change.

        Args:
            preview: EditPreview from preview() method

        Returns:
            ApplyResult with success/failure for each file
        """
        results = []

        for change in preview.changes:
            try:
                # Validate syntax before writing
                if not self._validate_syntax(change.new_code):
                    raise SyntaxError(f"Invalid syntax in {change.path}")

                # Atomic write with backup
                backup_path = self._write_backup(change.path)
                self._atomic_write(change.path, change.new_code)

                results.append(FileResult(
                    path=change.path,
                    success=True,
                    backup_path=str(backup_path),
                ))
            except Exception as e:
                results.append(FileResult(
                    path=change.path,
                    success=False,
                    error=str(e),
                ))
                # Restore from backup
                self._restore_backup(change.path, backup_path)

        return ApplyResult(results=results)

    def apply_all(
        self,
        pattern: str,
        replacement: str,
        path: Optional[str] = None,
        dry_run: bool = True,
    ) -> ApplyResult:
        """
        Apply change to all matching locations.

        Args:
            pattern: AST pattern to match
            replacement: Replacement pattern
            path: Optional path filter
            dry_run: If True, only preview (default: True)

        Returns:
            ApplyResult
        """
        preview = self.preview(pattern, replacement, path)

        if dry_run:
            # Just return preview as result
            return ApplyResult(
                results=[
                    FileResult(path=f, success=True, preview=True)
                    for f in preview.matched_files
                ],
                preview=preview,
            )

        return self.apply(preview)
```

### EditPreview Class

```python
@dataclass
class EditPreview:
    """Preview of proposed changes."""
    pattern: str
    replacement: str
    matched_files: List[str]
    changes: List["FileChange"]
    safety_score: float  # 0.0 = unsafe, 1.0 = safe

    def summary(self) -> str:
        """Get human-readable summary."""
        return (
            f"Pattern: {self.pattern}\n"
            f"Replacement: {self.replacement}\n"
            f"Files affected: {len(self.matched_files)}\n"
            f"Changes: {len(self.changes)}\n"
            f"Safety score: {self.safety_score:.2%}"
        )
```

### FileChange Class

```python
@dataclass
class FileChange:
    """A single file change."""
    path: str
    line_range: Tuple[int, int]
    old_code: str
    new_code: str

    def diff(self) -> str:
        """Get unified diff."""
        return difflib.unified_diff(
            self.old_code.splitlines(keepends=True),
            self.new_code.splitlines(keepends=True),
            fromfile=f"a{self.path}",
            tofile=f"b{self.path}",
        )
```

## Usage Examples

### Example 1: Rename Function

```python
from omni_edit import OmniEdit

edit = OmniEdit("src/")

# Preview the change
preview = edit.preview(
    pattern="def old_function_name($ARGS): $BODY",
    replacement="def new_function_name($ARGS): $BODY",
)

print(preview.summary())
# Pattern: def old_function_name($ARGS): $BODY
# Replacement: def new_function_name($ARGS): $BODY
# Files affected: 5
# Changes: 12
# Safety score: 100%

# Apply if safe
if preview.safety_score > 0.9:
    result = edit.apply(preview)
    print(f"Applied to {len(result.successful)} files")
```

### Example 2: Update Type Hints

```python
edit = OmniEdit("src/")

# Update all function returns to include type hints
preview = edit.preview(
    pattern="def $NAME($PARAMS):\n    $BODY",
    replacement="def $NAME($PARAMS) -> Any:\n    $BODY",
)

result = edit.apply(preview)
```

### Example 3: Safe Refactoring Pattern

```python
edit = OmniEdit("src/")

# Dry run first (default)
preview = edit.preview(
    pattern="for $ITEM in $ITER:\n    $BODY",
    replacement="for $ITEM in $ITER:\n    await asyncify($BODY)",
)

# If preview shows expected changes, apply
if not preview.changes:
    print("No matches found - aborting")
else:
    result = edit.apply(preview)
```

## Integration with Trinity

### As a Skill

```python
# assets/skills/structural_editing/tools.py

from omni_edit import OmniEdit

@skill_command(
    name="refactor",
    category="refactor",
    description="Refactor code using AST patterns",
)
async def refactor_code(
    pattern: str,
    replacement: str,
    path: Optional[str] = None,
    dry_run: bool = True,
) -> str:
    """
    Refactor code with AST pattern matching.

    Args:
        pattern: AST pattern to match (e.g., "def $NAME($$$): $$$")
        replacement: Replacement pattern
        path: Optional path filter
        dry_run: Preview only without applying (default: True)

    Returns:
        Preview summary or apply result
    """
    edit = OmniEdit(".")
    preview = edit.preview(pattern, replacement, path)

    if dry_run:
        return preview.summary()
    else:
        result = edit.apply(preview)
        return f"Applied to {len(result.successful)} files"
```

### With Cartographer (Phase 50)

```
Cartographer (Navigation) → Surgeon (Editing) → Holographic Agent (Verification)

1. Cartographer identifies code structure
2. Surgeon applies precise changes
3. Holographic Agent verifies with tests
```

## Safety Features

| Feature               | Description                                                |
| --------------------- | ---------------------------------------------------------- |
| **Dry Run Default**   | Preview before apply (must explicitly set `dry_run=False`) |
| **Backup Creation**   | Atomic writes with automatic backup                        |
| **Syntax Validation** | Verify code is syntactically correct before writing        |
| **Safety Score**      | 0-100% score based on change complexity and risk           |
| **Rollback**          | Automatic restore from backup on failure                   |

## Future Enhancements

- **Multi-language Support**: Rust, TypeScript, Go via tree-sitter
- **LLM Integration**: Use LLM to suggest patterns from natural language
- **Refactoring Recipes**: Pre-built refactoring patterns (Extract Method, etc.)
- **Visual Diff**: GUI for reviewing changes before applying

## Related Files

| File                               | Purpose                            |
| ---------------------------------- | ---------------------------------- |
| `agent/skills/structural_editing/` | Structural editing skill           |
| `packages/rust/crates/omni-tags/`  | AST-based code analysis (Phase 50) |

## Related Specs

- `assets/specs/phase50_cca_navigation.md`
- `assets/specs/phase57_omni_vector.md`
