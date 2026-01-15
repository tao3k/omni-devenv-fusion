"""
terminal/scripts/ - Isolated implementation module

This package contains atomic script implementations for the terminal skill.
Each script is isolated via absolute imports.

Architecture:
    scripts/  -> Controllers (actual implementation)

Usage in commands.py:
    from agent.skills.terminal.scripts import engine
    result = engine.run_command("ls", ["-la"])
"""

# Import submodules directly without circular imports
import importlib.util
from pathlib import Path

_scripts_dir = Path(__file__).parent

# Load engine module
_engine_path = _scripts_dir / "engine.py"
_spec = importlib.util.spec_from_file_location(
    "agent.skills.terminal.scripts.engine", str(_engine_path)
)
if _spec and _spec.loader:
    engine = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(engine)

# Load commands module
_commands_path = _scripts_dir / "commands.py"
_spec = importlib.util.spec_from_file_location(
    "agent.skills.terminal.scripts.commands", str(_commands_path)
)
if _spec and _spec.loader:
    commands = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(commands)

# Re-export functions for skill loader
run_task = commands.run_task
analyze_last_error = commands.analyze_last_error
inspect_environment = commands.inspect_environment
run_command = commands.run_command
