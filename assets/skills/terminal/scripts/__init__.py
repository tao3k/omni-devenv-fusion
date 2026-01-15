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

from agent.skills.terminal.scripts import engine
from agent.skills.terminal.scripts import commands

# Re-export functions for skill loader
run_task = commands.run_task
analyze_last_error = commands.analyze_last_error
inspect_environment = commands.inspect_environment
run_command = engine.run_command
