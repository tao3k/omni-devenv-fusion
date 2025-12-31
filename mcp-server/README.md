# Orchestrator MCP Server

> Route complex queries to expert personas. Get architectural, platform, DevOps, or SRE guidance without leaving your IDE.

This server exposes two tools:

| Tool | Purpose |
|------|---------|
| `list_personas` | Advertises available roles with use cases |
| `consult_specialist` | Routes questions to specialized personas |

## The Problem It Solves

Generic AI doesn't understand your project's institutional knowledge—your conventions, your stack, your standards.

```bash
# You ask the AI
> How should I design a multitenant control plane?

# Generic AI creates this (wrong context!)
> class ControlPlane(models.Model):
>     # Uses SQLite!
```

The Orchestrator solves this by routing your query to a persona that understands your project's context.

---

## Quick Start

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Export your API key or load from `.mcp.json`:

   ```bash
   export ANTHROPIC_API_KEY=sk-...
   export ORCHESTRATOR_MODEL=claude-3-opus-20240229   # optional
   ```

3. Start the server:

   ```bash
   python -u mcp-server/orchestrator.py
   ```

Expected output:

```
🚀 Orchestrator Server (Async) starting...
```

---

## Configuration

Control client and runtime behavior via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | _required_ | API key for the orchestrator. |
| `ANTHROPIC_BASE_URL` | `https://api.minimax.io/anthropic` | Anthropic-compatible endpoint. |
| `ORCHESTRATOR_MODEL` | `MiniMax-M2.1` | Model name. Falls back to `ANTHROPIC_MODEL`. |
| `ORCHESTRATOR_TIMEOUT` | `30` | Request timeout in seconds. |
| `ORCHESTRATOR_MAX_TOKENS` | `4096` | Max response tokens. |
| `ORCHESTRATOR_ENABLE_STREAMING` | `false` | Set to `true` for streaming responses. |
| `ORCHESTRATOR_LOG_LEVEL` | `INFO` | Logging level for JSON output. |
| `ORCHESTRATOR_ENV_FILE` | `.mcp.json` | Preload env from JSON (flat or `mcpServers.orchestrator.env`). |

---

## Available Personas

| Persona | Role | When to Use |
|---------|------|-------------|
| `architect` | High-level design | Splitting modules, defining boundaries, refactoring strategies |
| `platform_expert` | Nix/OS infrastructure | devenv configs, containers, environment variables |
| `devops_mlops` | CI/CD and pipelines | Build workflows, reproducibility, model training |
| `sre` | Reliability and security | Error handling, performance, vulnerability checks |

---

## Example Calls

### List Available Personas

**Input:**

```json
{
  "tool": "list_personas",
  "arguments": {}
}
```

**Output:**

```json
{
  "content": [{
    "type": "text",
    "text": "Available personas:\n- architect: High-level design decisions\n- platform_expert: Nix and infrastructure\n- devops_mlops: CI/CD and pipelines\n- sre: Security and reliability"
  }]
}
```

### Consult a Specialist

**Input:**

```json
{
  "tool": "consult_specialist",
  "arguments": {
    "role": "architect",
    "query": "Help design a multitenant control plane for internal platform APIs.",
    "stream": true
  }
}
```

**Output:**

```json
{
  "content": [{
    "type": "text",
    "text": "For a multitenant control plane, consider..."
  }]
}
```

The response includes persona context hints. Set `stream: true` for streaming token delivery.

---

## Register with MCP Client

Configure your MCP client (VS Code, Claude Desktop) to use `orchestrator-tools`. Reference the [Claude cookbooks orchestrator workflow](https://github.com/anthropics/claude-cookbook/tree/main/mcp#orchestrator-pattern).

---

## Writing Standards

This project follows the Omni-DevEnv Technical Writing Standard. See [`design/writing-style/`](../../design/writing-style/) for rules on:

- Clarity and mental models (Feynman)
- Eliminating clutter (Zinsser)
- Engineering precision (Rosenberg)
- LLM-optimized structure (Claude)
