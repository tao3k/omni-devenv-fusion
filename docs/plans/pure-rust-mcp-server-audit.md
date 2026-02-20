# Audit: Pure Rust MCP Server — Impact, Python’s Role, and Architecture

> **Scope**: If we implement a **pure Rust MCP server**, what changes for the current architecture? What is **Python’s role** after the migration? How should we **design and evolve** the architecture?

---

## 1. Current Architecture (Snapshot)

| Component                | Today                                                                                                  | Owner                                     |
| ------------------------ | ------------------------------------------------------------------------------------------------------ | ----------------------------------------- |
| **MCP transport**        | stdio, SSE                                                                                             | Python (MCP SDK, `omni.agent.mcp_server`) |
| **MCP protocol**         | initialize, tools/list, tools/call, resources, prompts                                                 | Python (`AgentMCPServer`)                 |
| **tools/list**           | From kernel `skill_context` or HolographicRegistry; alias/filter logic in Python                       | Python + (optionally) Rust registry       |
| **tools/call**           | `kernel.execute_tool(real_command, arguments)`; validation (Rust scanner), timeout/heartbeat in Python | Python (kernel, skills)                   |
| **resources/list, read** | Sniffer (context), Checkpoint (memory)                                                                 | Python / Foundation                       |
| **prompts/list, get**    | Filesystem + template args                                                                             | Python                                    |
| **Kernel**               | Skills load, Cortex (semantic index), router, skill_context                                            | Python (`omni.core.kernel`)               |
| **Skill execution**      | In-process Python (handlers) or subprocess                                                             | Python                                    |

So today: **one Python process** = MCP server + kernel + skills. Clients (Rust agent, Codex, Gemini CLI) connect to this process via stdio or SSE.

---

## 2. What “Pure Rust MCP Server” Implies

- **MCP protocol and transport** implemented in **Rust** (e.g. rmcp server: StreamableHttpService, stdio).
- **tools/list**: Rust must produce the list. So the **source of truth** for “which tools exist” must be readable by Rust (e.g. skill index in omni-vector, or a manifest generated at sync/build time).
- **tools/call**: Rust must **run** the tool. The actual execution today is Python (kernel + skills). So we must choose: run via **Rust executor** (spawn Python/script) or **call Python** (HTTP or embedded).
- **resources** and **prompts**: Either reimplemented in Rust (if we have or add Rust Sniffer/Checkpoint, and file-based prompts) or **delegated to Python** (Rust MCP calls a Python service).

So “pure Rust MCP server” = Rust owns protocol + transport + tool list source; **tool execution** (and optionally resources/prompts) either moves to Rust (executor) or stays in Python as a **backend service**.

---

## 3. Impact by Component

| Component                    | Current                                             | With Rust MCP server                                                                                                                                                                                                         | Migration effort                                                                                               |
| ---------------------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Transport (SSE, stdio)**   | Python                                              | **Rust** (rmcp)                                                                                                                                                                                                              | Medium: implement server in Rust; reuse rmcp.                                                                  |
| **tools/list**               | Python (kernel.skill_context / HolographicRegistry) | **Rust** must read tool list from somewhere: (a) Rust registry (e.g. from omni-vector skill table or sync-generated manifest), or (b) Rust calls Python “list tools” API at startup/refresh.                                 | Medium: need single source of truth for tools that Rust can read, or keep a small Python API for “list tools.” |
| **tools/call**               | Python `kernel.execute_tool`                        | **Rust** must invoke execution: (A) **Rust executor** (spawn script / `python -m omni.skills.run …`), or (B) **Rust → Python** (HTTP or IPC: “run this tool”), or (C) **Rust embeds Python** (PyO3, call kernel in-process). | High: defines Python’s role (see §4).                                                                          |
| **Validation**               | Python (validate_tool_args, Rust scanner)           | Can stay in Rust (Rust validation) or be done in Python if tools/call is delegated to Python.                                                                                                                                | Low if Rust executor; medium if we keep validation in Python and call it from Rust.                            |
| **Timeout / heartbeat**      | Python (`run_with_idle_timeout`, `heartbeat`)       | In Rust: timeout in executor or MCP handler. If execution is in Python, we need a way for Python to report heartbeat to Rust (e.g. streaming or polling).                                                                    | Medium.                                                                                                        |
| **resources/list, read**     | Python (Sniffer, Checkpoint)                        | Option 1: **Rust** reimplements (if Rust has Sniffer/Checkpoint). Option 2: **Rust calls Python** “resources” API. Option 3: Rust MCP returns minimal or no resources in v1.                                                 | Low–medium depending on option.                                                                                |
| **prompts/list, get**        | Python (filesystem + template)                      | Option 1: **Rust** reads files, simple template. Option 2: **Rust calls Python** prompts API.                                                                                                                                | Low.                                                                                                           |
| **Kernel / Cortex / router** | Python                                              | No longer in the MCP process. Either (a) **not used** by Rust MCP (Rust executor runs scripts only), or (b) used by a **Python “tool runner”** service that Rust MCP calls.                                                  | Defines Python’s role.                                                                                         |

---

## 4. Python’s Role: Three Options

### Option A — Python as “Tool Runner” backend (minimal disruption)

- **Rust MCP server**: Handles transport, handshake, tools/list (from Rust registry or from Python “list” API), tools/call (forwards to Python), optionally resources/prompts (forward to Python).
- **Python**: Long-running **tool runner** service (e.g. HTTP API: `POST /run_tool` with `name`, `arguments`; returns result). This service holds **kernel**, **skills**, **execute_tool**, validation, timeout/heartbeat. So Python stays “the execution backend”; Rust MCP is the **front** that speaks MCP and delegates every tools/call to Python.
- **Pros**: Smallest change: kernel, skills, Cortex, router unchanged. One new Python endpoint; Rust MCP is additive. Easy rollback.
- **Cons**: Still a Python process; Rust MCP still does one HTTP (or IPC) hop per tools/call.

### Option B — Python as “script payload” only (Rust executor)

- **Rust MCP server**: Handles transport, tools/list (from Rust registry/manifest), **tools/call** via **Rust executor** (spawn `python -m omni.skills.run <skill> <cmd> --args '...'` or per-skill script). No long-running Python process for MCP.
- **Python**: Only the **scripts and their runtime** (e.g. `omni.skills.run` entry point). No kernel/Cortex in the MCP path; tools are “run spec” + Rust spawn. Optional: keep a separate Python process for **standalone** `omni run` / gateway if we still want in-process kernel there.
- **Pros**: Single Rust process for MCP; no Python in the hot path. Aligns with “Rust executor” design.
- **Cons**: Need run-spec per tool; timeout/heartbeat and validation must be in Rust or in the spawned script; in-process-only skills must be exposed as script entry points.

### Option C — Python embedded in Rust (PyO3)

- **Rust MCP server**: Embeds Python (PyO3), loads kernel once at startup, calls `kernel.execute_tool` from Rust on each tools/call. Single process (Rust + embedded Python).
- **Python**: **Library** inside the Rust binary. Same kernel/skills code, but no separate Python process.
- **Pros**: One binary; no network hop for tools/call.
- **Cons**: Build and packaging complexity; binary size; GIL and Python startup cost; harder to upgrade Python/kernel independently.

---

## 5. Recommended Direction and Design

- **Short term (minimal risk)**: **Option A** — Pure Rust MCP server as **front**: protocol + transport in Rust, **tools/list** from Rust (read from existing skill index or a generated manifest) or from a one-off/cached call to Python. **tools/call** forwarded to a **Python “tool runner”** HTTP (or IPC) service. resources/prompts can be forwarded to Python or stubbed in Rust. Python’s role: **backend for execution and (optionally) resources/prompts**. No big rewrite of kernel/skills; we only add a small Python API and a Rust MCP server that calls it.

- **Later (if we want to remove Python from the MCP path)**: Move to **Option B** — Introduce **Rust executor** (run-spec per tool, spawn script), and make Rust MCP server call the executor instead of Python. Python then becomes “script payload” only for MCP; we can keep Python gateway/standalone run unchanged.

- **Option C** is possible but only if we explicitly want a single binary with embedded Python; it is more invasive and not necessary for “pure Rust MCP server” in the sense of “Rust speaks MCP and controls the process.”

### Architecture diagram (Option A)

```
  MCP clients (Rust agent, Codex, Gemini)
           │
           ▼
  ┌─────────────────────────────┐
  │   Rust MCP server           │
  │   (transport, tools/list,   │
  │    tools/call → forward)     │
  └─────────────┬───────────────┘
                │ HTTP / IPC
                ▼
  ┌─────────────────────────────┐
  │   Python “tool runner”      │
  │   kernel, execute_tool,     │
  │   resources, prompts        │
  └─────────────────────────────┘
```

### Architecture diagram (Option B)

```
  MCP clients
       │
       ▼
  ┌─────────────────────────────┐
  │   Rust MCP server            │
  │   + Rust executor            │
  │   tools/list (Rust registry) │
  │   tools/call → spawn script  │
  └─────────────┬───────────────┘
                 │ spawn
                 ▼
  ┌─────────────────────────────┐
  │   Python (script only)       │
  │   e.g. python -m omni.skills.run
  └─────────────────────────────┘
```

---

## 6. Migration and Design Changes (Summary)

| Area                    | Change                                                                                                                                                         |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **MCP process**         | From “one Python process” to “Rust MCP (+ optional Python backend).”                                                                                           |
| **Tool list**           | Single source of truth that **Rust** can read (skill index, manifest) or Rust calls Python once/cached for list.                                               |
| **Tool execution**      | Either (A) Rust → Python service, or (B) Rust executor spawns script. Validation/timeout in Rust or in the backend.                                            |
| **Python’s role**       | (A) **Backend**: tool runner (+ optional resources/prompts). (B) **Payload only**: scripts run by Rust executor. (C) **Embedded**: library inside Rust binary. |
| **Resources / prompts** | Implement in Rust (if we have data and logic) or delegate to Python; or ship Rust MCP v1 with tools only and add resources/prompts later.                      |
| **CLI / gateway**       | Can stay Python (`omni run`, `omni gateway`) or later move to Rust; independent of “Rust MCP server” if we choose Option A (Python backend).                   |

This audit gives a clear impact view and three concrete roles for Python (backend, payload-only, embedded), with a recommended path: **Option A first**, then **Option B** if we want to remove Python from the MCP path.
