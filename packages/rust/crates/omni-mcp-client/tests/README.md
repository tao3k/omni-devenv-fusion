# omni-mcp-client tests

## Unit tests (always run)

- **config**: `McpServerTransportConfig` (de)serialization for StreamableHttp and Stdio.
- **client**: `from_config` builds a client; `list_tools` and `call_tool` return an error when not connected.

Run: `cargo test -p omni-mcp-client`

## Integration test (requires MCP server on 3002)

- **streamable_http_integration**: Connects to a real MCP server via Streamable HTTP, lists tools, and calls one.

To run:

1. Start the MCP server in another terminal: `omni mcp --transport sse --port 3002`
2. From repo root: `just test-mcp-integration`  
   or: `OMNI_MCP_URL=http://127.0.0.1:3002/sse cargo test -p omni-mcp-client --test streamable_http_integration -- --ignored`
