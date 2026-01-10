#!/usr/bin/env python3
"""
agent/cli.py - Phase 25 One Tool CLI with Typer + Rich

UNIX Philosophy:
- stdout: Only skill results (pure data for pipes)
- stderr: Logs and progress (visible to user, invisible to pipes)

Usage:
    omni mcp                      # Start MCP server (for Claude Desktop)
    omni skill run <cmd>          # Execute skill command
    omni skill install <url>      # Install a skill from URL
    omni skill list               # List installed skills
    omni skill info <name>        # Show skill information
    omni skill discover <query>   # Discover skills from index
    omni skill update <name>      # Update an installed skill
    omni --help                   # Show this help

Note: This module is now a thin wrapper. See agent/cli/ for modular implementation.
"""

from __future__ import annotations

# Re-export main components for backward compatibility
from .app import app, main
from .console import err_console

__all__ = ["app", "main", "err_console"]
