"""
terminal/scripts/ - Isolated implementation module

This package contains atomic script implementations for the terminal skill.
Uses relative imports to avoid circular dependencies.
"""

# Import submodules using relative imports
from . import engine
from . import commands

# Re-export functions for skill loader
run_task = commands.run_task
analyze_last_error = commands.analyze_last_error
inspect_environment = commands.inspect_environment
run_command = commands.run_command
