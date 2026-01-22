# Extension System - LLM Reference

> LLM-optimized documentation for Omni's extension architecture

## Overview

The extension system provides **plugin capabilities** for skills. Extensions are automatically discovered and loaded from each skill's `extensions/` directory.

## Extension Types

### Built-in Extensions (Framework-Provided)

| Extension     | Purpose                        | Auto-Injected      |
| ------------- | ------------------------------ | ------------------ |
| `rust_bridge` | High-performance Rust bindings | As `rust` variable |

### User Extensions (Skill-Specific)

Extensions placed in `assets/skills/<skill>/extensions/` are skill-specific and loaded at skill initialization.

## Extension Discovery

Extensions are discovered automatically:

```
assets/skills/<skill>/
├── extensions/
│   ├── __init__.py          # Package marker
│   ├── rust_bridge/         # Package extension
│   │   └── __init__.py
│   └── hooks.py             # Single-file extension
└── scripts/
    └── *.py                 # Scripts receive injected extensions
```

## Built-in Extension: rust_bridge

### Available Methods

```python
rust.status() -> Dict[str, Any]
    Returns: {"active": bool, "features": List[str]}

rust.is_active() -> bool
    Returns: True if Rust bindings are available
```

### In Scripts

Scripts automatically receive `rust` as a global variable:

```python
# assets/skills/git/scripts/status.py
@skill_command(name="git_status")
def status() -> str:
    # Automatically available - no import needed
    if rust.is_active():
        return rust.status()
    return "Using Python fallback"
```

## Creating User Extensions

### Single-File Extension

```python
# assets/skills/<skill>/extensions/hooks.py
"""Custom hooks for skill."""

def on_pre_execute(context: Dict[str, Any]) -> None:
    """Called before each command execution."""
    pass

def on_post_execute(context: Dict[str, Any], result: Any) -> Any:
    """Called after each command execution."""
    return result
```

### Package Extension

```python
# assets/skills/<skill>/extensions/my_extension/__init__.py
"""My custom extension."""

from typing import Any, Dict

class MyExtension:
    """Custom extension implementation."""

    def __init__(self, context: Dict[str, Any]):
        self.context = context

    def process(self, data: Any) -> Any:
        """Main extension logic."""
        return data

def create(context: Dict[str, Any]) -> MyExtension:
    """Factory function required for package extensions."""
    return MyExtension(context)
```

## Accessing Extensions in Scripts

### Method 1: Automatic Injection (Recommended)

```python
# rust is automatically available
def my_command():
    if rust.is_active():
        return rust.status()
```

### Method 2: Via Skill Context

```python
# In skill script
skill = get_current_skill()
ext = skill.get_extension("rust_bridge")
if ext:
    ext.initialize(context)
```

## Extension Loading Order

1. Built-in extensions (rust_bridge)
2. User package extensions (alphabetically)
3. User single-file extensions (alphabetically)

## Error Handling

If an extension fails to load:

- Error is logged but doesn't block skill loading
- Scripts continue to work without the extension
- Check logs for extension loading errors
