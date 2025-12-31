# Orchestrator MCP Server

Exposes a `consult_specialist` tool that forwards questions to personas, and a `list_personas` tool that advertises available roles with use cases.

## Configuration

Environment variables control client and runtime behavior. Defaults follow the cookbook examples.

| Variable | Default | Description |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | _required_ | API key for the orchestrator. |
| `ANTHROPIC_BASE_URL` | `https://api.minimax.io/anthropic` | Anthropic-compatible endpoint. |
| `ORCHESTRATOR_MODEL` | `MiniMax-M2.1` | Model name. Falls back to `ANTHROPIC_MODEL`. |
| `ORCHESTRATOR_TIMEOUT` | `30` | Request timeout in seconds. |
| `ORCHESTRATOR_MAX_TOKENS` | `4096` | Max response tokens. |
| `ORCHESTRATOR_ENABLE_STREAMING` | `false` | Set to `true` for streaming responses. |
| `ORCHESTRATOR_LOG_LEVEL` | `INFO` | Logging level for JSON output. |
| `ORCHESTRATOR_ENV_FILE` | `.mcp.json` | Preload env from JSON (flat or `mcpServers.orchestrator.env`). |

## Run the Server

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Export your API key or load from JSON:

   ```bash
   export ANTHROPIC_API_KEY=sk-...
   export ORCHESTRATOR_MODEL=claude-3-opus-20240229   # optional override
   ```

3. Start the server (use `python -u` for unbuffered logs):

   ```bash
   python -u mcp-server/orchestrator.py
   ```

Expected output:

```
🚀 Orchestrator Server (Async) starting...
```

## Register with MCP Client

Configure your MCP client (VS Code, Claude Desktop) to use `orchestrator-tools`. Reference the [Claude cookbooks orchestrator workflow](https://github.com/anthropics/claude-cookbook/tree/main/mcp#orchestrator-pattern).

## Example Calls

**List personas:**

```json
{
  "tool": "list_personas",
  "arguments": {}
}
```

**Consult specialist:**

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

Response includes persona context hints. Streams tokens when `stream: true`.
