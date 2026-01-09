"""
_template/scripts/ - Isolated Implementation Module

This package contains atomic script implementations for this skill.
Each script is isolated via absolute imports, preventing namespace conflicts.

Architecture (Phase 35.2):
    tools.py    -> Router (just dispatches, validates params)
    scripts/    -> Controllers (actual implementation)

Usage in tools.py:
    from agent.skills._template.scripts import example

Each script module is directly importable as:
    agent.skills._template.scripts.<module_name>
"""
