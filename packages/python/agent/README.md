# omni-dev-fusion-agent

Tri-MCP Agent Orchestrator - The Brain of omni-dev-fusion.

## Overview

This package provides the orchestrator MCP server that handles skill routing, LLM session management, and the `@omni("skill.command")` single entry point.

## Architecture

- `src/agent/core/` - Core system components (orchestrator, router, skill manager)
- `src/agent/mcp_server.py` - MCP server implementation
- `src/agent/cli.py` - CLI entry points

## Dependencies

- `omni-dev-fusion-common` - Shared kernel and utilities
- MCP, LangGraph, Pydantic-AI for agent orchestration
