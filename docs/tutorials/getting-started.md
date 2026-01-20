# Tutorial: Getting Started with Omni-Dev-Fusion

> **Duration**: 15 minutes | **Goal**: Run the Omni Agent

This tutorial gets you from zero to a working Omni agent. We assume you know basic terminal commands.

---

## Goal

In this tutorial, you will:

1. Enter the development environment
2. Run the Omni MCP server
3. Execute your first skill command

---

## Prerequisites

| Tool   | Required Version |
| ------ | ---------------- |
| Nix    | 2.4+             |
| direnv | 2.21+            |
| uv     | 0.4+             |

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
Using Python 3.13
Resolved 15 packages in 23ms
```

---

## Step 3: Run the Omni Agent (Trinity Architecture)

Omni uses a single `omni` tool that dispatches to skills via the Skill Registry.

**Terminal 1 (Start the Omni MCP Server):**

```bash
cd packages/python/agent
python -m agent.mcp_server

# Expected output:
🚀 Omni MCP Server started
📦 Skill Registry initialized with {N} skills
🎯 Ready to accept commands via omni("skill.command")
```

---

## Step 4: Execute Your First Skill

With Claude Desktop connected to Omni, try:

```
> @omni("git.status")
```

This dispatches to the git skill's `git_status` command.

---

## Step 4: Test with Claude Desktop

The Omni MCP server registers with Claude Desktop automatically.

1. Restart Claude Desktop
2. Run `/mcp` to verify the server appears:

```
Available MCP Servers:
- omni (connected)
```

---

## Step 5: Execute a Skill Command

Try your first skill command:

```
> @omni("git.status")
```

**Expected Response:**

```
On branch main
Changes to be committed:
  M   docs/README.md
```

---

## Step 6: Verify Your Environment

Run the validation suite to confirm everything works:

```bash
just test

# Expected output:
577 passed, 1 skipped in 25.82s
```

---

## Next Steps

| If you want to...      | Go to...                                                       |
| ---------------------- | -------------------------------------------------------------- |
| Learn the architecture | [Trinity Architecture](../explanation/trinity-architecture.md) |
| Create a new skill     | [Skills Guide](../skills.md)                                   |
| Browse API commands    | [Reference](../reference/)                                     |

---

_Built on standards. Not reinventing the wheel._
