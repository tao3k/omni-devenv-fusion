# Why Nix

> Our environment and build are managed by Nix. Together with Nickel-generated sandbox profiles, Nix + Nickel form a **safe and efficient** environment solution for development and skill execution.

---

## Nix manages our environment and build

We use **Nix** as the single source of truth for:

- **Development environment**: Rust, Python, uv, and system dependencies. Enter it with `direnv allow` at the project root; the Nix shell activates automatically and provides a hermetic toolchain so every contributor gets the same setup.
- **Build**: The project build and toolchain are declared in the Nix flake (or `devenv.nix`). No “it works on my machine”—the environment is reproducible and version-controlled.

So: **Nix is the overall environment**. It defines what is available (compilers, runtimes, libs) and how the project is built.

---

## Skills and complex environments

When **skills** need to run in **complex or isolated environments** (e.g. a specific Python version, extra system libs, or a locked dependency set), we run them **inside Nix**. Nix supplies the exact environment for that skill; the agent and the rest of the stack stay on the same story. So:

- Day-to-day dev: Nix + direnv for your shell and build.
- Skill execution: Nix can provide a dedicated environment per skill when needed—reproducible and consistent.

---

## Nickel + Nix: sandbox profiles and overall environment

**Nickel** is used for **sandbox configuration**: it generates **profiles** that define _what_ is allowed (resource limits, network, syscalls, mounts). Those profiles are consumed by the Rust execution layer (e.g. nsjail, Seatbelt) to run code in a restricted sandbox.

| Layer      | Role                          | Example                                         |
| ---------- | ----------------------------- | ----------------------------------------------- |
| **Nix**    | Overall environment and build | Dev shell, skill runtimes, system deps          |
| **Nickel** | Sandbox policy (profiles)     | `strict`, `base`, resource limits, network deny |

- **Nickel** = _what_ is restricted (policy, types, contracts). It does not execute; it exports JSON/config that Rust reads.
- **Rust** = _how_ (spawn sandbox, enforce limits, monitor).
- **Nix** = _where_ and _with what_ (which tools and libs exist in the environment).

So: **Nickel-generated sandbox profiles** plus **Nix-managed environments** give you:

1. **Safety**: Sandbox profiles restrict what a process can do (memory, CPU, network, syscalls).
2. **Efficiency**: Nix provides exactly the environment needed, with no extra drift or ad-hoc installs.

Together, **Nix + Nickel** are the environment and isolation solution we use for development and for running skills in complex or locked environments.

---

## Where to go next

| Topic             | Document                                                                              |
| ----------------- | ------------------------------------------------------------------------------------- |
| Enter the Nix env | [Getting Started](../tutorials/getting-started.md) (Step 1: `direnv allow`)           |
| Nickel vs Rust    | [Nickel–Rust responsibilities](../reference/nickel-rust-responsibilities.md)          |
| Sandbox design    | [NCL-driven sandbox architecture](../architecture/NCL-driven-sandbox-architecture.md) |
