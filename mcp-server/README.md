# Orchestrator MCP Server

This server follows the Claude cookbooks pattern for an orchestrator MCP tool: it exposes a `consult_specialist` tool that forwards a question to a selected persona, and a `list_personas` tool that advertises the available roles with recommended use cases.

## Configuration

Environment variables control the client and runtime behavior. Defaults are aligned with the cookbook examples.

| Variable | Default | Description |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | _required_ | API key used by the orchestrator to call the model. |
| `ANTHROPIC_BASE_URL` | `https://api.minimax.io/anthropic` | Base URL for the Anthropic-compatible endpoint. |
| `ORCHESTRATOR_MODEL` | `MiniMax-M2.1` (fallback to `ANTHROPIC_MODEL` when set) | Model name passed to the client. |
| `ORCHESTRATOR_TIMEOUT` | `30` | Timeout (seconds) applied to each request. |
| `ORCHESTRATOR_MAX_TOKENS` | `4096` | Max tokens for responses. |
| `ORCHESTRATOR_ENABLE_STREAMING` | `false` | When `true`, forces streaming responses. |
| `ORCHESTRATOR_LOG_LEVEL` | `INFO` | Logging level for structured JSON logs. |
| `ORCHESTRATOR_ENV_FILE` | `.mcp.json` in repo root | Optional JSON file to preload env values (supports flat object or `mcpServers.orchestrator.env`). |

## Running the server

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Export your API key (and any optional overrides) **or** supply them via a JSON file (default `.mcp.json` in the repo root) using the schema in the table above:

   ```bash
   export ANTHROPIC_API_KEY=sk-...
   export ORCHESTRATOR_MODEL=claude-3-opus-20240229   # example override
   ```

3. Start the MCP server (use `python -u` for unbuffered logs; environment variables can also be sourced from your client config such as `.mcp.json` or `settings.json`):

   ```bash
   python -u mcp-server/orchestrator.py
   ```

You should see a startup message like:

```
🚀 Orchestrator Server (Async) starting...
```

## Registering with an MCP client

Configure your MCP-aware client (e.g., VS Code MCP extension, Claude Desktop) to register this server with the `orchestrator-tools` name and a command that launches the script above. Refer to the [Claude cookbooks orchestrator workflow](https://github.com/anthropics/claude-cookbook/tree/main/mcp#orchestrator-pattern) for client-specific wiring.

## Example calls

1. List available personas (mirrors the persona-selection step from the cookbooks):

   ```json
   {
     "tool": "list_personas",
     "arguments": {}
   }
   ```

2. Consult a specialist (matches the consult-specialist pattern):

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

The response will include persona context hints and can stream tokens when `stream` is `true` (or when `ORCHESTRATOR_ENABLE_STREAMING` is enabled).
