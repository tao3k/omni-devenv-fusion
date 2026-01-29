# Modular Skill Loading (Zero-Boilerplate)

## Overview

In `omni-dev-fusion`, skills are designed to be highly modular and extensible. To support complex logic while keeping the codebase clean, the `ScriptLoader` implements a recursive, physical-first loading strategy.

## Key Features

- **Recursive Discovery**: The system automatically scans all subdirectories under a skill's `scripts/` folder for `.py` files.
- **Zero Boilerplate**: No `__init__.py` files are required. The loader uses PEP 420-like logic to dynamically construct the package hierarchy in memory.
- **Relative Import Support**: You can use standard relative imports (e.g., `from .engine import ...`) within subdirectories. The loader automatically configures `__package__` and `sys.path` during the loading process.
- **Namespace Isolation**: Each script is executed in a unique, dynamically generated module name to prevent collisions between skills or submodules with the same name (e.g., two different skills having an `engine.py`).

## How It Works

1. **Rust Discovery**: The Rust `ToolsScanner` performs a recursive scan of the `scripts/` directory to index all functions decorated with `@skill_command`.
2. **Package Construction**: When loading a script at `scripts/subdir/module.py`, the Python `ScriptLoader`:
   - Ensures parent modules (e.g., `skill.scripts.subdir`) exist in `sys.modules`.
   - Temporarily injects the physical directory into `sys.path`.
   - Sets the `__package__` attribute of the module to allow relative imports.
3. **Execution & Harvesting**: The script is executed, and all decorated functions are harvested and registered as top-level skill commands.

## Best Practices

- **Logical Grouping**: Group complex tool implementations into subdirectories (e.g., `scripts/my_feature/`).
- **Relative Imports**: Use `from .helper import ...` within subdirectories to maintain modularity.
- **Avoid Collisions**: While the system isolates namespaces, try to use descriptive file names for clarity.
