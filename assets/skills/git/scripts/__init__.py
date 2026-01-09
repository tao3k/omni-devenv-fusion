"""
git/scripts/ - Isolated implementation module

This package contains atomic script implementations for the git skill.
Each script is isolated via absolute imports, preventing namespace conflicts
with other skills (e.g., docker/scripts/status.py).

Architecture:
    tools.py  -> Router (just dispatches)
    scripts/  -> Controllers (actual implementation)

Usage in tools.py:
    from agent.skills.git.scripts import status
    from agent.skills.git.scripts import branch
    from agent.skills.git.scripts import log

Each script module is directly importable as agent.skills.git.scripts.<module_name>
"""

# Re-export commonly used functions for convenience
# Note: Individual modules can also be imported directly
