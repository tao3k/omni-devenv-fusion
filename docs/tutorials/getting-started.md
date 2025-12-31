# Tutorial: Getting Started with Omni-DevEnv

> **Duration**: 15 minutes | **Goal**: Run your first MCP server

This tutorial gets you from zero to a working MCP environment. We assume you know basic terminal commands.

---

## Goal

In this tutorial, you will:

1. Enter the development environment
2. Verify the MCP servers work
3. Run your first consultaion with a persona

---

## Prerequisites

| Tool | Required Version |
|------|------------------|
| Nix | 2.4+ |
| direnv | 2.21+ |
| uv | 0.4+ |

---

## Step 1: Enter the Development Environment

The project uses `direnv` to auto-activate the Nix shell.

```bash
# From the project root, allow direnv
direnv allow

# Expected output:
direnv: loading .envrc
direnv: using nix
...
direnv: export +ARTEFACT_ROOT ~PATH
```

You now have all tools (Python, uv, ast-grep, vale) in your PATH.

---

## Step 2: Sync Python Dependencies

```bash
uv sync

# Expected output:
Using Python 3.12
Resolved 15 packages in 23ms
```

---

## Step 3: Verify MCP Servers Start

Open two terminal windows.

**Terminal 1 (Orchestrator):**

```bash
python -u mcp-server/orchestrator.py

# Expected output:
🚀 Orchestrator Server (Async) starting...
```

**Terminal 2 (Coder):**

```bash
python -u mcp-server/coder.py

# Expected output:
🦈 Coder Server (Async) starting...
```

Both servers print their startup messages. They are ready to accept connections.

---

## Step 4: Test with Claude Code

The MCP servers register with Claude Code automatically via `~/.config/claude/claude_desktop_config.json`.

1. Restart Claude Code
2. Run `/mcp` to verify both servers appear:

```
Available MCP Servers:
- omni-orchestrator (connected)
- omni-coder (connected)
```

---

## Step 5: Consult a Specialist

Try your first persona consultation:

```
> Ask the architect: Should I split mcp-server/orchestrator.py into multiple files?
```

**Expected Response:**

The Architect persona considers your module boundaries and suggests a split strategy based on the project's ADR records.

---

## Step 6: Verify Your Environment

Run the validation suite to confirm everything works:

```bash
just test-mcp

# Expected output:
test_orchestrator_tools ... ok
test_coder_tools ... ok
test_all_tools ... ok

Ran 3 tests in 5.234s
OK
```

---

## Next Steps

| If you want to... | Go to... |
|-------------------|----------|
| Learn why we built this | [Explanation: Why Omni-DevEnv?](../explanation/why-omni-devenv.md) |
| Solve a specific problem | [How-to Guides](../how-to/) |
| Browse API commands | [Reference](../reference/) |

---

*Built on standards. Not reinventing the wheel.*
