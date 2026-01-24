"""
agent/cli - Atomic CLI Module for Omni DevEnv

Modular CLI structure:
- app.py: Typer application and configuration
- console.py: Console and output formatting
- runner.py: Skill execution logic
- omni_loop.py: CCA Runtime Integration
- commands/: Command submodules

Usage:
    python -m agent.cli                    # Run CLI
    python -m agent.cli skill list         # List skills
    omni mcp                               # Start MCP server
"""

from __future__ import annotations

from .app import app, main
from .console import err_console
from .runner import run_skills

__all__ = ["app", "err_console", "main", "run_skills"]
