# Omni Run Rewrite Plan

> **Problem**: Current `omni run` is not acceptable as a user-facing interface. Performance, speed, and behaviour are poor; it does not qualify as normal use. This plan outlines a full rewrite so that `omni run` is usable out-of-the-box and can later align with the gateway + Rust window + omni-memory design.
>
> **Principle**: All work on `omni run` is guided by the **long-term target** (gateway-first, one loop, session, MCP as tool surface). See [omni-run-roadmap-nanobot-zeroclaw.md](./omni-run-roadmap-nanobot-zeroclaw.md) for the full roadmap; do not preserve or extend the old “wrong” design.

---

## 1. Current State (Why It Feels Broken)

### 1.1 Default Single-Task Path Is Wrong

| What users expect                                                              | What actually happens                                                                                                                                  |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `omni run "list files"` runs the agent (kernel + skills + LLM) in this process | **Default path** calls `run_simple_task()`: an HTTP client that talks to `localhost:3002` for `tools/list` and `tools/call`. **No kernel is started.** |
| One command, one process                                                       | User must **run `omni mcp` in another terminal first**. If MCP is not running: connection refused, or confusing errors.                                |
| Full agent (router, Cortex, skills, memory)                                    | Only LLM + raw MCP tool calls; no router, no Cortex, no in-process skills.                                                                             |

**Root cause**: `execute_task_via_kernel()` (the real path: kernel init → router → OmniLoop) is **never called** from the CLI for a single task. It exists in `run_entry.py` but the run command only uses `run_simple_task()`.

### 1.2 Other Issues

- **--fast**: Documented as "skip kernel, use MCP directly". For single task the code prints "Fast mode not implemented for single task. Using full mode." but then **still** runs `run_simple_task()` (MCP client). So "full mode" is a lie; there is no in-process kernel path for single task.
- **REPL**: Also uses MCP over HTTP (same dependency on a second process).
- **run.py size**: ~770 lines. The **entire LangGraph Robust Workflow** (discovery, clarify, plan, execute, validate, reflect, review, summary) is **inlined** inside the `run()` command (~400 lines). Unmaintainable.
- **Performance**: Even if we wired `execute_task_via_kernel`, every run does full `kernel.initialize()` + `kernel.start()` (load all skills, build Cortex in background). Cold start is heavy; no reuse across invocations.
- **UX**: No streaming, no clear progress, session report only at the end. Not suitable as a primary user interface.

---

## 2. Goals for the Rewrite

1. **Single command works**: `omni run "task"` must run the **in-process** agent (kernel + router + OmniLoop) by default. No requirement to start `omni mcp` in another terminal.
2. **Clear, thin CLI**: `run.py` should only parse args and delegate. All workflow logic lives in `run_entry` or dedicated modules (e.g. graph workflow in its own runner).
3. **Performance**:
   - **Time to first step**: Target a reasonable cold start (e.g. kernel init + router ready in &lt; 10s on a typical machine, with async Cortex so tools are available as soon as skills load).
   - Optional **daemon mode** later: `omni mcp` (or `omni run --gateway`) keeps kernel alive so repeated `omni run` or a client can reuse it (future work).
4. **User interface**: At least: clear banner, progress or streaming so the user sees that something is happening, and a readable final outcome. No silent hangs.
5. **Preserve contracts**: `execute_task_via_kernel` return shape and run_entry API stay stable so tests and future gateway can reuse them.

---

## 3. Proposed Changes

### 3.1 Default Path: Use Kernel (In-Process)

- **Change**: For `omni run "task"` (no `--repl`, no `--graph`, no `--omega`), call **`execute_task_via_kernel(task, max_steps=steps, verbose=verbose)`** instead of `run_simple_task()`.
- **Effect**: One process, one command. Kernel loads, router runs, OmniLoop runs. No dependency on another MCP server process.
- **Optional**: Keep `run_simple_task` as an **explicit** mode (e.g. `omni run --mcp-client "task"`) for users who already have `omni mcp` running and want a lightweight client; document that it requires MCP to be up.

### 3.2 Fix --fast or Remove It

- **Option A**: Implement real fast path: if `--fast` and no MCP server detected, **fall back to execute_task_via_kernel** (and say "MCP not detected, using in-process agent").
- **Option B**: Remove `--fast` until we have a defined fast path (e.g. kernel already running in daemon). Avoid misleading "not implemented" message.

### 3.3 Extract Graph Workflow from run.py

- **Move** the LangGraph Robust Workflow (build_graph, streaming loop, review interrupt, session report) into a dedicated module, e.g. `omni.agent.workflows.robust_task.runner` or `run_graph.py`.
- **run.py** only: `if graph: run_async_blocking(run_graph(task)); return`.
- **Benefit**: run.py shrinks to a thin CLI; graph workflow is testable and reusable.

### 3.4 Thin run.py Layout

Target structure:

```text
run.py
├── register_run_command(app)
│   └── run(task, steps, json_output, repl, graph, omega, fast, tui_socket, verbose)
│       ├── if no task or repl → run_repl_mode()
│       ├── if omega → run_omega_mission()
│       ├── if graph → run_graph_workflow(task)  # from workflows.robust_task.runner
│       └── else → run_async_blocking(execute_task_via_kernel(task, ...))  # DEFAULT
├── run_repl_mode() (can stay or later use kernel in-process)
├── run_simple_task() (optional, --mcp-client only)
└── helpers: print_banner, print_session_report, etc.
```

No 400-line inline graph in the CLI.

### 3.5 Performance and UX (Incremental)

- **Kernel**: Already uses async Cortex build so tools are available before Cortex finishes. Ensure router init does not block on full Cortex if we can serve fast path (e.g. keyword-only) first.
- **Output**: Keep or add simple progress (e.g. "Starting…", "Routing…", "Running step 1…") so the user is not left with a blank screen during init and first LLM call.
- **Streaming**: Optional follow-up; not required for first rewrite.

---

## 4. Implementation Order

| Step | Action                                                                                                                                                                                                                                     |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1    | **Wire default path**: In `run()`, replace the final `run_simple_task` branch with `execute_task_via_kernel`. Add a single test that `omni run "hello"` (or equivalent) triggers `execute_task_via_kernel` and returns the expected shape. |
| 2    | **Fix or remove --fast**: Either implement fallback to kernel when MCP is not available, or remove the flag and the "not implemented" message.                                                                                             |
| 3    | **Extract graph**: Move the graph workflow block from run.py into `run_entry` or a new `workflows/robust_task/runner.py`; call it from run.py in one line.                                                                                 |
| 4    | **Clean run.py**: Remove dead code, reduce duplication, document the two modes (in-process vs MCP-client if kept).                                                                                                                         |
| 5    | **Optional**: Add `--mcp-client` to explicitly use run_simple_task when user has MCP running; document in CLI help.                                                                                                                        |

---

## 5. What Stays the Same

- **run_entry.execute_task_via_kernel**: Signature and return shape unchanged; it remains the single entry point for "run one task with kernel + OmniLoop".
- **run_entry.print_session_report, print_banner**: Reused.
- **OmniLoop, router, kernel**: No change to core logic; only the CLI is fixed to call them.
- **Contract tests**: `test_data_interface_services.test_execute_task_via_kernel_returns_session_output_steps` and similar remain valid.

---

## 6. Summary

The current `omni run` is bad because the **default path never runs the real agent**; it only runs an MCP HTTP client that requires a separate process. The rewrite is: **make the default path call `execute_task_via_kernel`** (in-process kernel + router + OmniLoop), **extract the graph workflow** out of run.py, and **fix or remove --fast**. That gives a single-command, usable experience. Performance and UX can then be improved incrementally (e.g. daemon mode, streaming, Rust window) on top of this corrected base.
