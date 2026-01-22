"""
_template/scripts/ - Isolated Implementation Module

Uses importlib.util for dynamic module loading.
No circular imports, hot-reload support.

Architecture:
    scripts/
    ├── __init__.py    # Dynamic module loader
    └── commands.py    # Skill commands (direct definitions)

Usage in skill loader:
    from agent.skills._template.scripts import commands
    commands.example(...)
"""

import importlib.util
from pathlib import Path

_scripts_dir = Path(__file__).parent

# Load commands module dynamically
_commands_path = _scripts_dir / "commands.py"
_spec = importlib.util.spec_from_file_location(
    "agent.skills._template.scripts.commands", str(_commands_path)
)
commands = None
if _spec and _spec.loader:
    commands = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(commands)

# Re-export functions for skill loader
if commands:
    example = commands.example
    example_with_options = commands.example_with_options
    process_data = commands.process_data
