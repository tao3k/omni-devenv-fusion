# Nickel-Rust Responsibilities Boundary

> **Version**: 1.0.0
> **Date**: 2026-02-08
> **Purpose**: Define clear boundaries between Nickel (configuration) and Rust (execution)

---

## Core Principle

```
Nickel: "WHAT" (policy, types, constraints)
Rust:   "HOW"  (execution, isolation, monitoring)
```

---

## Nickel Responsibilities

| Responsibility           | Description                              | Examples                                      |
| ------------------------ | ---------------------------------------- | --------------------------------------------- |
| **Type Definitions**     | Define data structures for configuration | `SandboxConfig`, `Profile`, `BackendConfig`   |
| **Validation Contracts** | Validate inputs at export time           | `max_memory_mb > 0`, `allowed_syscalls != []` |
| **Policy Composition**   | Combine security policies                | `strict & { network = "deny" }`               |
| **Profile Inheritance**  | Define profile hierarchies               | `strict` inherits from `base`                 |
| **Backend Descriptions** | Describe backend capabilities            | `nsjail.supports = ["seccomp", "cgroups"]`    |
| **Preset Generation**    | Generate reusable configurations         | `rlimits.small`, `network.deny`               |

### Nickel MUST NOT

- Parse or interpret sandbox configurations
- Execute commands or spawn processes
- Monitor resource usage
- Handle IPC or communicate with sandboxed processes

---

## Rust Responsibilities

| Responsibility          | Description                 | Examples                                 |
| ----------------------- | --------------------------- | ---------------------------------------- |
| **Command Execution**   | Spawn sandboxed processes   | `Command::new("nsjail")`, `sandbox-exec` |
| **Resource Monitoring** | Track CPU, memory, time     | `cgroup` stats, `/proc` monitoring       |
| **IPC Handling**        | Capture stdout/stderr       | `Child::output()`                        |
| **Policy Enforcement**  | Apply OS-level restrictions | `setrlimit`, `namespaces`, `seccomp`     |
| **Result Aggregation**  | Collect execution results   | `ExecutionResult { stdout, exit_code }`  |

### Rust MUST NOT

- Define configuration types or contracts
- Compose security policies
- Validate configuration semantics
- Choose between backends (Nickel decides)

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ Nickel Layer (Policy & Types)                                    │
│                                                                  │
│ 1. Define types (interface.ncl)                                 │
│ 2. Compose profiles (profiles/strict.ncl)                        │
│ 3. Describe backends (backends/nsjail.ncl)                       │
│ 4. Generate final config                                         │
│    ↓ nickel export --format json                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ JSON Output (SSOT)                                               │
│                                                                  │
│ {                                                               │
│   "backend": "nsjail",                                          │
│   "profile": "strict",                                          │
│   "cmd": ["python", "script.py"],                               │
│   "resources": { "max_memory_mb": 128 },                        │
│   "network": { "mode": "deny" }                                 │
│ }                                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Rust Layer (Execution)                                           │
│                                                                  │
│ 1. Read JSON (serde::Deserialize)                              │
│ 2. Select backend implementation (NO decision, just execution)   │
│ 3. Execute with selected backend                                │
│ 4. Return ExecutionResult                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Boundary Examples

### GOOD: Clear Separation

**Nickel** (`profiles/strict.ncl`):

```nickel
{
  name = "strict",
  max_memory_mb = 32,
  network_mode = "deny",
  allowed_syscalls = ["read", "write", "exit"],
}
```

**Rust** (`executor/nsjail.rs`):

```rust
// Read JSON
let config: SandboxConfig = serde_json::from_str(&json)?;

// Apply limits
cmd.arg("--rlimit_as").arg(config.max_memory_mb * 1024 * 1024);

// Execute
let output = cmd.output().await?;
```

### BAD: Violation of Boundaries

**Rust** (DON'T DO THIS):

```rust
// Rust decides policy - VIOLATION
let network_policy = if config.max_memory_mb < 64 {
    "deny"
} else {
    "localhost"
};
```

**Nickel** (DON'T DO THIS):

```nickel
// Nickel executes - VIOLATION
let result = std.sys.exec("nsjail", ["--mode", "EXEC", "--", "python"])
```

---

## Interface Contract

### Nickel Exports to Rust

```nickel
# interface.ncl - Types that Rust deserializes

{
  # SandboxConfig: Main configuration for Rust
  SandboxConfig :: {
    id :: String,
    backend :: [| 'nsjail, 'seatbelt |],
    cmd :: [String],
    env :: { _ :: String } | default = {},
    resources :: {
      max_memory_mb :: Number,
      max_cpu_seconds :: Number,
    },
    network :: {
      enabled :: Bool,
      mode :: [| 'deny, 'localhost, 'full |],
    },
    filesystem :: {
      mode :: [| 'chroot, 'ro |],
      allowed_paths :: [String] | default = [],
    },
  },
}
```

### Rust Returns to Nickel (via Python)

```python
# Python aggregates results
@dataclass
class ExecutionResult:
    success: bool
    exit_code: int | None
    stdout: str
    stderr: str
    execution_time_ms: int
    memory_used_bytes: int | None
```

---

## Platform-Specific Behavior

| Aspect                | Linux                | macOS                   |
| --------------------- | -------------------- | ----------------------- |
| **Backend**           | nsjail               | seatbelt                |
| **Syscall Filtering** | seccomp              | Seatbelt rules          |
| **Resource Limits**   | rlimits, cgroups     | rlimits                 |
| **Network Isolation** | namespaces           | Seatbelt                |
| **Nickel Role**       | Define nsjail config | Define seatbelt profile |
| **Rust Role**         | Execute nsjail       | Execute sandbox-exec    |

---

## Summary

| Layer      | Role                       | Examples                                                 |
| ---------- | -------------------------- | -------------------------------------------------------- |
| **Nickel** | Policy, Types, Composition | `max_memory_mb`, `allowed_syscalls`, profile inheritance |
| **Rust**   | Execution, Monitoring      | Spawn nsjail, capture output, track memory               |
| **Python** | Orchestration              | Export NCL, invoke Rust, aggregate results               |

**Golden Rule**: Nickel describes what; Rust performs how.
