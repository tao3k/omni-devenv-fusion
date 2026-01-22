# Extension System - Developer Guide

> Comprehensive documentation for Omni's extension architecture

## Introduction

The Extension System is a **plugin architecture** that allows skills to have optional capabilities loaded dynamically. Extensions live in each skill's `extensions/` directory and are automatically discovered and loaded when the skill initializes.

### Key Principles

1. **Discovery over Configuration**: No registration files needed - just place extensions in the right directory
2. **Lazy Loading**: Extensions are loaded only when needed
3. **Transparent Injection**: Extensions (like `rust_bridge`) are automatically available in scripts
4. **Graceful Degradation**: Missing extensions don't crash the skill

## Architecture

```
UniversalScriptSkill
        │
        ├── extensions/
        │   ├── __init__.py          # Package marker
        │   ├── rust_bridge/         # Built-in: Rust accelerator
        │   │   ├── __init__.py
        │   │   ├── bindings.py      # Rust binding isolation
        │   │   └── accelerator.py   # Performance-critical logic
        │   └── custom_extension/    # User extension
        │       └── __init__.py
        │
        └── scripts/
            └── *.py                 # Scripts use injected extensions
```

## Extension Types

### 1. Built-in Extensions

These are provided by the framework and automatically available:

| Extension     | Path                                      | Purpose                        |
| ------------- | ----------------------------------------- | ------------------------------ |
| `rust_bridge` | `omni.core.skills.extensions.rust_bridge` | High-performance Rust bindings |

**Usage in Scripts:**

```python
# assets/skills/git/scripts/commit.py

@skill_command(name="git_commit")
def commit(message: str) -> str:
    # rust is automatically injected - no import needed!
    if rust.is_active():
        return rust_accelerated_commit(message)
    return python_fallback_commit(message)
```

### 2. User Extensions (Skill-Specific)

Extensions specific to a skill are placed in that skill's directory:

```
assets/skills/git/
├── extensions/
│   ├── __init__.py
│   ├── rust_bridge/        # Override framework extension
│   └── analytics/          # Git-specific analytics
│       ├── __init__.py
│       └── metrics.py
└── scripts/
    └── commit.py
```

## Creating Extensions

### Single-File Extension

Best for simple extensions (hooks, utilities):

```python
# assets/skills/git/extensions/hooks.py
"""Git hooks extension."""

from typing import Any, Dict


def on_pre_commit(message: str) -> bool:
    """Validate commit message before committing."""
    if len(message) < 5:
        raise ValueError("Commit message too short")
    return True


def on_post_commit(commit_hash: str) -> None:
    """Perform actions after commit."""
    print(f"Committed: {commit_hash}")
```

### Package Extension

Best for complex extensions with multiple files:

```python
# assets/skills/git/extensions/analytics/__init__.py
"""Git analytics extension - tracks commit patterns."""

from typing import Any, Dict


class GitAnalytics:
    """Analytics tracker for git operations."""

    def __init__(self, context: Dict[str, Any]):
        self.repo_path = context.get("cwd", ".")
        self._commits: List[str] = []

    def track_commit(self, commit_hash: str) -> None:
        """Track a commit."""
        self._commits.append(commit_hash)

    def get_stats(self) -> Dict[str, Any]:
        """Get analytics summary."""
        return {
            "total_commits": len(self._commits),
            "repo": self.repo_path
        }


def create(context: Dict[str, Any]) -> GitAnalytics:
    """Factory function - required for package extensions."""
    return GitAnalytics(context)
```

### Extension with Dependencies

If your extension needs external packages, declare them in `SKILL.md`:

```markdown
# SKILL.md

name: git
version: 1.0.0

requirements:

- pandas # For analytics extension
```

## Accessing Extensions in Scripts

### Automatic Injection (Built-in Extensions)

The `rust` variable is automatically available in all scripts:

```python
# assets/skills/git/scripts/status.py

@skill_command(name="git_status")
def status() -> str:
    # No import needed - rust is injected
    if rust.is_active():
        return rust.status()
    return "Using Python fallback"
```

### Manual Access (User Extensions)

For user extensions, access via the skill context:

```python
# In script context
from omni.core.skills.extensions import SkillExtensionLoader

# Get extension from skill
extension_loader = skill.extension_loader  # Available on UniversalScriptSkill
analytics = extension_loader.get("analytics")

if analytics:
    stats = analytics.get_stats()
```

## Built-in Extension: rust_bridge

The `rust_bridge` extension provides high-performance implementations using Rust bindings.

### API Reference

```python
class RustBridge:
    """Rust accelerator for performance-critical operations."""

    @property
    def is_active(self) -> bool:
        """Check if Rust bindings are available."""
        return self._bindings is not None

    def status(self) -> Dict[str, Any]:
        """Get Rust bindings status."""
        return {
            "active": self.is_active,
            "version": self._bindings.version() if self.is_active else None
        }

    def git_status(self, path: str) -> Dict[str, Any]:
        """High-performance git status (Rust implementation)."""
        return self._bindings.git_status(path)

    def git_diff(self, path: str) -> str:
        """High-performance git diff (Rust implementation)."""
        return self._bindings.git_diff(path)
```

### Usage Example

```python
# assets/skills/git/scripts/status.py

@skill_command(name="git_status")
def git_status(project_root: Path) -> str:
    # Automatically uses Rust if available
    if rust.is_active():
        result = rust.git_status(str(project_root))
    else:
        result = python_git_status(project_root)

    return format_status(result)
```

## Extension Loading Sequence

1. Framework scans `omni.core.skills.extensions.rust_bridge`
2. Framework scans `assets/skills/<skill>/extensions/`
3. Package extensions are loaded (directories with `__init__.py`)
4. Single-file extensions are loaded (`.py` files)
5. Extensions are injected into script context

### Loading Order

Extensions are loaded alphabetically within each category:

```
rust_bridge/           (built-in, always first)
analytics/             (package, loaded second)
hooks.py               (single-file, loaded third)
```

## Error Handling

Extensions are loaded with error isolation:

```python
# If an extension fails to load, it's logged but doesn't block the skill
try:
    loader.load_all()
except Exception as e:
    logger.error(f"Extension failed: {e}")
    # Skill continues without the extension
```

### Best Practices

1. **Graceful Degradation**: Always check if extension is available:

   ```python
   if rust.is_active():
       # Use Rust path
   else:
       # Use Python fallback
   ```

2. **Log Errors**: Use the logger for extension errors:

   ```python
   import logging
   logger = logging.getLogger("omni.skills.my_extension")
   ```

3. **Factory Pattern**: Use `create()` function for package extensions:

   ```python
   # my_extension/__init__.py
   def create(context):
       return MyExtension(context)
   ```

## Debugging Extensions

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Loaded Extensions

```python
from omni.core.skills.extensions import SkillExtensionLoader

loader = SkillExtensionLoader("/path/to/extensions")
loader.load_all()

print(f"Loaded: {loader.list_all()}")
print(f"Order: {loader.load_order}")
```

## Migration Guide

### From Old System

If you're migrating from a monolithic skill system:

**Before:**

```python
# Old: Hard-coded dependencies
from agent.core.git import RustGitBridge
```

**After:**

```python
# New: Extension-based
# rust is automatically available
if rust.is_active():
    rust.git_status(cwd)
```

## Summary

| Concept               | Description                        |
| --------------------- | ---------------------------------- |
| Built-in Extension    | Framework-provided (rust_bridge)   |
| User Extension        | Skill-specific code in extensions/ |
| Package Extension     | Directory with `__init__.py`       |
| Single-File Extension | Standalone `.py` file              |
| Automatic Injection   | `rust` variable in scripts         |
