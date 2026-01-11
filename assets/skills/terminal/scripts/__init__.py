"""
terminal/scripts/ - Isolated implementation module

This package contains atomic script implementations for the terminal skill.
Each script is isolated via absolute imports.

Architecture:
    tools.py  -> Router (just dispatches)
    scripts/  -> Controllers (actual implementation)

Usage in tools.py:
    from agent.skills.terminal.scripts import engine
    result = engine.run_command("ls", ["-la"])
"""
