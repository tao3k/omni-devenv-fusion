# Tutorial: Getting Started with Omni-Dev-Fusion (v2.0)

> **Duration**: 10 minutes | **Goal**: Run the Omni Agent with Trinity Architecture

This tutorial gets you from zero to a working Omni agent using the new **Rust-First Indexing** architecture.

---

## Goal

In this tutorial, you will:

1. Enter the development environment (Nix + uv).
2. Generate the Skill Index (Rust).
3. Run the Omni MCP server (Python).
4. Experience the "Zero-Scan" startup and Hot Reload.

---

## Prerequisites

| Tool   | Required Version |
| ------ | ---------------- |
| Nix    | 2.18+            |
| direnv | 2.30+            |
| uv     | 0.4+             |

---

## Step 1: Enter the Development Environment

The project uses `direnv` to auto-activate the Nix shell, providing a hermetic environment for both Rust and Python.

```bash
# From the project root
direnv allow

# Expected output:
direnv: loading .envrc
direnv: using nix
...

```

You now have `cargo`, `python`, `uv`, and system dependencies in your PATH.

---

## Step 2: Sync Dependencies

Install both Python and Rust dependencies.

```bash
# Sync Python environment (v2.0 workspace)
uv sync --all-extras

# Expected output:
Resolved X packages in ...ms

```

---

## Step 3: Generate Skill Index (Rust Layer)

In the v2.0 architecture, Python does not scan files. We must generate the **Single Source of Truth** (`skill_index.json`) using Rust.

```bash
# Run skill sync (Python CLI uses Rust omni-scanner under the hood)
omni skill sync

# Expected Output (example):
# ✅ Scanned N skills
# 📜 Updated skill index / LanceDB (skills table)

```

---

## Step 4: Run the Omni Agent (Trinity Architecture)

Now start the Agent. It will act as a "Thin Client," loading business logic from the Kernel via the Index.

**Terminal 1 (Start the MCP Server using CLI):**

```bash
# STDIO mode (for Claude Desktop)
uv run omni mcp --transport stdio

# OR SSE mode (for HTTP clients)
uv run omni mcp --transport sse --port 8080

# OR with verbose mode (shows hot reload logs)
uv run omni mcp --transport sse --port 8080 --verbose
```

**Expected output (STDIO mode):**

```
🚀 Starting Agent MCP Server (STDIO Mode)
🟢 Kernel initializing...
🧠 Building Semantic Cortex...
👃 Initializing Context Sniffer...
📚 Loaded {N} sniffing rules from Skill Index
🚀 Omni MCP Server started (STDIO Mode)
```

> **Note**: The `omni` CLI is the unified entry point. Use `uv run omni --help` to see all available commands.

---

## Step 5: Connect to Claude Desktop (STDIO Mode)

The Omni MCP server supports **two transport modes**:

### Option A: STDIO Mode (Recommended for Claude Desktop)

Configure your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "omni": {
      "command": "uv",
      "args": ["run", "omni", "mcp", "--transport", "stdio"],
      "cwd": "/absolute/path/to/omni-dev-fusion"
    }
  }
}
```

**Expected startup output:**

```
🚀 Starting Agent MCP Server (STDIO Mode)
🟢 Kernel initializing...
🧠 Building Semantic Cortex...
👃 Initializing Context Sniffer...
📚 Loaded {N} sniffing rules from Skill Index
🚀 Omni MCP Server started (STDIO Mode)
```

### Option B: SSE Mode (For Claude Code CLI / HTTP Clients)

Run the server in SSE mode using the CLI:

```bash
uv run omni mcp --transport sse --port 8080
```

Or with verbose mode for hot reload debug logs:

```bash
uv run omni mcp --transport sse --port 8080 --verbose
```

**Endpoints:**

- `POST /message` - Send JSON-RPC requests
- `GET /events` - SSE stream for responses & notifications
- `GET /health` - Health check
- `GET /ready` - Readiness check

---

## Step 6: Execute a Skill Command

Try a command that triggers the **Intent Sniffer**.

In Claude:

```text
> Check the status of this repo

```

**What happens internally:**

1. **Sniffer** (Core Layer) detects `.git` folder via Declarative Rules.
2. **Router** activates `git` skill.
3. **Kernel** executes `git.status`.

**Expected Response:**

```text
On branch main
Your branch is up to date...

```

---

## Step 7: Verify Architecture

Run the test suite to ensure the Trinity Architecture (Rust + Foundation + Core) is intact.

```bash
# Run Rust tests (Scanner & Vector Store)
cargo test

# Run Python tests (Core Kernel & Agent)
just test  # or: uv run pytest

# Expected output:
... passed in ...s

```

---

## Next Steps

| If you want to...        | Go to...                                             |
| ------------------------ | ---------------------------------------------------- |
| Understand v2.0 Layers   | [System Layering](../explanation/system-layering.md) |
| Create a Zero-Code Skill | [Skills Guide](../skills.md)                         |
| Debug Hot Reload         | [Hot Reload Guide](../developer/hot-reload.md)       |

---

_Omni-Dev Fusion v2.0: Rust Foundation. Python Intelligence._
