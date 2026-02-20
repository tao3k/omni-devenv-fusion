# Rust as Skill Executor (Replace Python Subprocess)

> **Idea**: Skill _implementation_ (registry, discovery, schema, what to run) lives mainly in Rust. The _runnable_ is still Python, bash, or other (scripts/commands). The **only** change we add: **Rust is the executor** that runs that tool (spawn process, capture output) instead of Python subprocess. We keep flexibility (any interpreter/script); we gain performance and a single place for timeouts/sandboxing.

---

## 1. Current vs Proposed

| Aspect                         | Today                                                                                                    | Proposed                                                                                                                                                                                                                                                                     |
| ------------------------------ | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Skill registry / discovery** | Python (kernel, tools_loader, discovery).                                                                | **Rust** (or shared): which tools exist, name, description, input schema, **how to run** (command line + env).                                                                                                                                                               |
| **Who runs the tool**          | Python: `kernel.execute_tool` → handler (in-process) or Python `subprocess` for script-like invocations. | **Rust executor**: given (tool name, args), resolve to command (e.g. `python scripts/recall.py`, `bash scripts/foo.sh`), then **Rust** spawns the process (e.g. `tokio::process::Command`), captures stdout/stderr, returns result. No Python in the hot path for execution. |
| **What gets run**              | Python callables or scripts (Python/bash).                                                               | **Unchanged**: still Python scripts, bash, or other; we only change **who** spawns the process (Rust instead of Python).                                                                                                                                                     |

So: we are **not** rewriting each skill in Rust. We are replacing **Python subprocess** (or Python in-process dispatch) with a **Rust executor** that runs the same scripts/commands. Skills stay flexible (Python/bash/other); execution becomes Rust-owned.

---

## 2. Why Rust as Executor

- **Performance**: No Python interpreter in the hot path for “run this tool.” Rust does fork/exec (or spawn), which is typically cheaper and more controllable than Python subprocess (and avoids GIL if we ever parallelise tool calls).
- **Single place for policy**: Timeouts, memory limits, sandboxing, cwd, env can all live in the Rust executor. Easier to harden and reason about than scattered Python subprocess calls.
- **Aligns with “skills implementation mainly in Rust”**: Registry + “how to run” in Rust; the runnable payload stays Python/bash/other. So we improve execution without giving up script flexibility.

---

## 3. What the Rust Executor Needs

- **Input**: (tool name, arguments dict).
- **Resolution**: Map tool name → command line + env (e.g. from Rust-held registry or manifest). Example: `knowledge.recall` → `python -m omni.skills.run knowledge recall --args '{"query":"..."}'` or `path/to/scripts/recall.py` with args.
- **Execution**: Rust spawns process (e.g. `tokio::process::Command`), sets timeout, captures stdout/stderr, optionally applies resource limits.
- **Output**: Parse or pass through stdout (and stderr) as the tool result; return to MCP client / agent loop.

So the executor is a small Rust layer: resolve (tool, args) → command + env → spawn → capture → return. No Python in this path.

---

## 4. Skill Metadata and “How to Run”

Today many skills are “Python module + decorated handler” (in-process). To use a Rust executor we need a **run spec** per command, e.g.:

- **Script-based**: `command: "python", args: ["scripts/recall.py"], env: {...}` or `command: "bash", args: ["scripts/foo.sh"]`. Rust executor runs that.
- **Module-based (current Python entry)**: Could be exposed as a single script entry point so Rust can still run it, e.g. `python -m omni.skills.run <skill> <command> --args '...'`. Then the “implementation” of the skill is still Python (scripts/modules); only the **invoker** is Rust.

So we don’t remove Python scripts; we define a contract: “every tool is runnable as one process invocation” (script or thin CLI). Rust holds the registry and the run spec; Rust executor runs that process.

---

## 5. MCP and the Executor

- **Option A (Rust MCP server)**: MCP server lives in Rust. It implements `tools/list` (from Rust registry) and `tools/call` (Rust executor runs the tool, returns result). No Python process for MCP; Codex/Gemini and our Rust agent both talk to this Rust MCP server.
- **Option B (hybrid)**: Keep Python MCP server for now; add a **Rust executor service** (e.g. HTTP or FFI). Python MCP receives `tools/call`, calls Rust executor (HTTP or PyO3), Rust spawns the process and returns output; Python returns that to the client. So we still replace “Python subprocess” with “Rust executor,” but MCP stays in Python until we’re ready to move it.

Both options “use Rust as the executor instead of subprocess”; the only difference is whether MCP is in Rust (A) or Python (B). Option B is a smaller step; Option A gives a single Rust binary (agent + MCP server + executor).

---

## 6. Tradeoffs: Is It Actually Worth It?

The benefit of "Rust executor instead of Python subprocess" is **debatable**. Here is an honest assessment.

### 6.1 Performance

- **Spawn overhead**: The difference between "Python subprocess" and "Rust spawn" is the **caller** side: a few ms (Python interpreter + subprocess module vs Rust syscall). The **child** process (e.g. starting the Python interpreter to run a skill script) is usually **tens to hundreds of ms**. So the **saving per tool call is small** (on the order of a few ms), and often **&lt;5%** of the total tool time.
- **When it could matter**: Only if we have **many very short** tool calls (e.g. &lt;20 ms each), where spawn overhead is a large fraction. For typical skills (run a script that does I/O or computation), the script's own runtime dominates; switching the spawn from Python to Rust does not change that.
- **If we also move MCP to Rust**: Then we remove the **MCP round-trip** (Rust agent → Python MCP server → execute_tool). That saves a few ms per call (no HTTP/localhost hop). So the **combined** win (Rust MCP + Rust executor) is "no Python in the tools path" — a few to ~10 ms per call. Still modest compared to LLM or heavy tool logic.

So **performance alone** is not a strong reason to do Rust executor; it's a **marginal** gain unless we're already moving MCP to Rust and want a single Rust process.

### 6.2 Other considerations

- **Timeouts / sandboxing**: Python can do this too (`subprocess.run(..., timeout=..., ...)`, resource limits on Unix). So "single place for policy" is not unique to Rust; it's a design choice, not a capability only Rust can provide.
- **Complexity**: We'd need run-specs (how to invoke each skill from Rust), and possibly a thin CLI for current in-process Python skills. That's extra surface to maintain. If the gain is small, the complexity may not pay off.
- **When it _is_ useful**: (1) We're **already** building a Rust MCP server (e.g. for single-binary or Codex/Gemini); then having the executor in the same process is natural and avoids a Python dependency for the tools path. (2) We want **one** implementation of "how we run a tool" (Rust) so all clients (Rust agent, future CLI) share it. (3) We plan to add **heavy** sandboxing or resource limits and prefer to implement that once in Rust.

### 6.3 Recommendation

- **Do not** treat "Rust executor" as a must-have for performance; the gain is **small and context-dependent**.
- **Consider it optional or deferred**: Keep Python as the executor (kernel + subprocess) until we have a clear reason to move (e.g. we're doing Rust MCP and want no Python in the tools path, or we're adding Rust-first sandboxing).
- If we do it, do it **together with** (or after) Rust MCP server; doing "Rust executor called by Python MCP" (Option B) adds a hop and may not reduce latency at all.

So: the idea is **technically sound** but the **advantage is debatable**. Proceed only when it clearly supports a larger goal (e.g. single Rust binary, or unified execution policy in Rust).

---

## 7. Summary

| Point                | Detail                                                                                                                                                                                                                  |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Skills “in Rust”** | Registry, discovery, schema, and **how to run** (command line + env) can live in Rust. The runnable itself stays Python/bash/other.                                                                                     |
| **Rust as executor** | Replace **Python subprocess** with **Rust executor**: Rust spawns the process for the tool (script or thin CLI), captures output, applies timeouts/limits. Same scripts; **performance gain is marginal** (see §6).     |
| **Flexibility**      | We do **not** rewrite each skill in Rust; we only change **who** runs the tool (Rust instead of Python). So we keep Python/bash/other flexibility.                                                                      |
| **When to do it**    | **Optional / deferred.** Worth it mainly if we're already moving MCP to Rust and want no Python in the tools path, or we need a single Rust implementation for execution policy. Not a must-have for performance alone. |

So: "Rust as the executor" is **technically sound** but the “” **advantage is debatable**; treat it as an option, not a requirement.
