# eBPF Monitoring of Sandboxed Skill Execution

> **Context**: Execute flow is (1) NCL generates a **sandbox profile** (JSON) that defines the sandbox environment for a skill tool; (2) **Rust executor** (omni-sandbox) reads that config and runs the tool via **nsjail** (Linux) or **sandbox-exec/Seatbelt** (macOS). **Question**: Can we use **eBPF** to monitor the sandbox when it runs the tool (observe relevant parameters)?

---

## 1. Current Flow (Recap)

- **NCL** (e.g. Nickel) exports a sandbox profile to **JSON** (skill_id, mode, cmd, env, mounts, rlimits, seccomp, etc.).
- **omni-sandbox** (Rust): loads JSON, builds the command for **nsjail** (Linux) or **sandbox-exec** (macOS), spawns it with timeout, captures stdout/stderr and returns `ExecutionResult`.
- The **tool** (Python script, bash, etc.) runs **inside** that sandbox (nsjail container or Seatbelt profile).

So the “sandbox” is the process tree: Rust executor → nsjail/sandbox-exec → child process (the actual tool). To monitor “the sandbox running the tool,” we need to observe that process (or its subtree).

---

## 2. Can eBPF Monitor This? (Linux)

**Yes.** On **Linux**, eBPF can attach to the sandboxed process and trace relevant kernel events.

### 2.1 What eBPF can observe

- **Syscalls**: e.g. `openat`, `execve`, `connect`, `accept`, `read`, `write` — via tracepoints `raw_syscalls/sys_enter`, `sys_exit` or per-syscall tracepoints. Filter by **PID** (or cgroup) so we only see the sandboxed process.
- **File paths**: from syscall arguments (e.g. `openat` path). So we can log “which files the tool opened.”
- **Network**: `connect`, `accept`, etc. — we can see addresses/ports.
- **Resource usage**: if the sandbox runs in a **cgroup**, we can use cgroup-based eBPF or read cgroup stats (memory, CPU) for the sandbox.

So the “parameters” we can monitor include: **which syscalls**, **file paths**, **network connections**, and (with cgroup) **resource usage**.

### 2.2 How to attach: PID vs cgroup

- **By PID**: We need the **PID of the process(es) we care about**. Today the Rust executor uses `cmd.output()` and does not expose the child PID. To use eBPF by PID we could:
  - Change the executor to **spawn** the process (e.g. `spawn()` instead of `output()`), obtain the **process handle / PID**, then (in parallel or in another thread) **attach an eBPF program** that filters by this PID (or by the process group). After the process exits we detach. So: **yes, we can**, but the executor would need to expose or use the child PID for the duration of the run.
- **By cgroup**: Create a **cgroup** for this run, put the sandbox process (e.g. nsjail) into it (e.g. via `cgroups v2` and set the child’s cgroup in the executor, or run nsjail with a cgroup config if it supports it). Then attach eBPF to the **cgroup** (e.g. cgroup skb for network, or tracepoints with cgroup filter). This way we don’t need to know the exact PID of the inner child; we monitor “everything in this cgroup.” So: **yes**, and often **cleaner** for “monitor the whole sandbox” (all processes started by nsjail for this run).

So: **we can use eBPF to monitor the sandbox** — either by attaching to the spawned process PID (with a small executor change) or by running the sandbox in a cgroup and attaching eBPF to that cgroup.

### 2.3 Practical stack (Linux)

- **bpftrace** or **libbpf** (or bcc): write a small program that attaches to e.g. `tracepoint:raw_syscalls:sys_enter` and filters by PID or cgroup; print or aggregate syscall id, args (e.g. path for openat), timestamp. Optionally export to a log or metrics.
- **Rust**: the executor (or a companion “monitor” service) could spawn the sandbox, get PID/cgroup, then either (a) invoke a bpftrace script with that PID/cgroup, or (b) load a small eBPF program (via libbpf-rs or similar) that filters by that PID/cgroup and forwards events to userspace. So the **integration point** is: executor gives “PID or cgroup for this run”; the eBPF side uses that to filter.

---

## 3. macOS (Seatbelt): No eBPF

eBPF is a **Linux kernel** feature. On **macOS** (Seatbelt / sandbox-exec) we **cannot** use eBPF.

For similar observability on macOS we’d use:

- **DTrace** (if available): script by process or PID to trace syscalls / file access.
- **EndpointSecurity** (Apple API): subscribe to events (e.g. file access, process execution) and filter by process. This is the modern way to “monitor what a process does” on macOS.

So: **eBPF only on Linux**; on macOS we’d use DTrace or EndpointSecurity for “monitor sandbox running the tool.”

---

## 4. Summary

| Question                                                      | Answer                                                                                                                                                                                                                               |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Can we use eBPF to monitor the sandbox when it runs the tool? | **Yes, on Linux.** Attach eBPF to the process PID (or cgroup) of the sandbox; trace syscalls, file paths, network, and optionally cgroup resource usage.                                                                             |
| What “parameters” can we monitor?                             | Syscalls (and their arguments, e.g. file paths, addresses), network connections, and with cgroup: memory/CPU usage for the sandbox.                                                                                                  |
| What changes in our stack?                                    | Executor may need to expose **PID** (e.g. spawn then wait, instead of only `output()`) or run the sandbox in a **cgroup** and pass that cgroup to the eBPF monitor. NCL/sandbox profile stays as is; eBPF is an **add-on** observer. |
| macOS?                                                        | No eBPF; use **DTrace** or **EndpointSecurity** for similar monitoring of the sandboxed process.                                                                                                                                     |

So: **yes, we can use eBPF (on Linux) to monitor the sandbox running the tool**; the executor needs to provide a hook (PID or cgroup) for the eBPF program to attach to, and we can observe syscalls, file access, network, and optionally resource usage.
