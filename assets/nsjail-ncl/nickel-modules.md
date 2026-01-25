# Nickel Module System for nsjail-configs

This document describes the module system pattern used in nsjail-configs, based on the [Tweag Nickel modules article](https://www.tweag.io/blog/2024-06-20-nickel-modules/).

## Overview

The module system provides:

- **Schema definition** - Type contracts hidden from consumers
- **Module composition** - Merge multiple modules with `merge` and `compose_all`
- **Clear separation** - Internal Schema vs public API

## Module Structure

Every lib module follows this pattern:

```nickel
# lib/<module>.ncl

# 1. Define contracts (standard contracts for runtime validation)
let MyFieldContract = std.contract.from_predicate (fun val => ...) in

# 2. Define Schema (internal, hidden from consumers)
let Schema = {
  field | MyFieldContract,
  other_field | default = "value",
} in

# 3. Define builders and presets
let my_builder = fun arg => { field = arg } in
let my_preset = { field = "default" } in

# 4. Export with Module wrapper
{
  Module = {
    Schema | not_exported = {},
    config = {
      builder = my_builder,
      preset = my_preset,
    },
  },
  # Convenience exports
  builder = my_builder,
  preset = my_preset,
}
```

## Key Concepts

### Schema vs Config

- **Schema** - Defines expected structure and contracts. Hidden from consumers using `not_exported = {}`.
- **Config** - The actual values/data exposed to consumers.

### Standard Contracts

Use `std.contract.from_predicate` for runtime validation:

```nickel
# String contract
let StringContract = std.contract.from_predicate (fun val => std.is_string val) in

# Number contract (non-negative)
let NumberContract = std.contract.from_predicate (fun val => std.is_number val && val >= 0) in

# Enum contract
let ModeContract = std.contract.from_predicate (fun val =>
  std.is_string val && std.array.elem val ["ONCE", "LISTEN", "CGROUP", "EXEC"]
) in

# Array contract
let StringArrayContract = std.contract.from_predicate (fun val =>
  std.is_array val && std.array.all (fun x => std.is_string x) val
) in

# Record contract
let UserNetContract = std.contract.from_predicate (fun val =>
  std.is_record val
  && std.record.has_field "enable" val
  && std.is_bool val.enable
) in
```

### Cross-Field Validation

Combine contracts with record merge for validation across multiple fields:

```nickel
let ListenModeContract = std.contract.from_predicate (fun val =>
  if val.mode == "LISTEN" && (val.port == null || val.port == 0) then
    false
  else
    true
) in

let Schema = {
  mode | ModeContract | default = "ONCE",
  port | NumberContract | default = 0,
} & ListenModeContract
```

## Module Composition

Use `lib/module.ncl` helpers to combine modules:

```nickel
let Module = import "./lib/module.ncl" in
let mode = import "./lib/mode.ncl" in
let mounts = import "./lib/mounts.ncl" in
let network = import "./lib/network.ncl" in
let rlimit = import "./lib/rlimit.ncl" in
let uidmap = import "./lib/uidmap.ncl" in
let seccomp = import "./lib/seccomp.ncl" in

# Merge two modules
let base_config = Module.merge mode.once mounts.web in

# Or compose multiple modules
let full_config = Module.compose_all [
  mode.once,
  mounts.web,
  network.pasta,
  rlimit.web,
  uidmap.simple 0 0 1000 1000,
] & {
  name = "my-app",
  cmd = ["/bin/app"],
} in

full_config
```

## Available Modules

| Module        | Purpose                                     | Key Exports                             |
| ------------- | ------------------------------------------- | --------------------------------------- |
| `mode.ncl`    | Execution mode (ONCE, LISTEN, CGROUP, EXEC) | `once`, `listen`, `cgroup`              |
| `mounts.ncl`  | Mount configuration                         | `bind`, `tmpfs`, `proc`, `web`          |
| `network.ncl` | Network isolation                           | `pasta`, `isolated`, `disabled`         |
| `rlimit.ncl`  | Resource limits                             | `memory`, `cpu`, `web`, `gui`           |
| `uidmap.ncl`  | UID/GID mapping                             | `simple`, `map_root_to_user`            |
| `seccomp.ncl` | Seccomp filter                              | `block_dangerous`, `restrictive`        |
| `base.ncl`    | Common defaults                             | `default_env`, `logging`, `default_cwd` |

## Best Practices

### Naming Conventions

- Import modules with `Mod` suffix to avoid conflicts with field names:
  ```nickel
  let modeMod = import "../lib/mode.ncl" in
  let rlimitMod = import "../lib/rlimit.ncl" in
  let uidmapMod = import "../lib/uidmap.ncl" in
  ```

### Avoid Recursive References

Nickel doesn't allow recursive `let` bindings. Define functions inline in the export record:

```nickel
# Bad (causes infinite recursion)
let my_func = fun x => x in
{ my_func = my_func }  # Recursive!

# Good
{ my_func = fun x => x }
```

### Contract Placement

Put contracts on Schema fields, not on convenience exports:

```nickel
# Schema (with contracts)
let Schema = {
  name | NonEmptyStringContract,
  port | PortContract,
} in

# Module export (Schema hidden, convenience exports without contracts)
{
  Module = { Schema | not_exported = {}, config = { ... } },
  name = "default",  # No contract needed for convenience export
  port = 8080,
}
```

## Verification

```bash
# Typecheck all modules
for f in lib/*.ncl; do nickel typecheck "$f"; done

# Format all files
for f in lib/*.ncl examples/*.ncl; do nickel format "$f"; done

# Export examples to verify
for f in examples/*.ncl; do nickel export -f yaml "$f" > /dev/null; done
```

## References

- [Tweag: Nickel Modules](https://www.tweag.io/blog/2024-06-20-nickel-modules/)
- [Nickel Contracts](https://nickel-lang.org/manual/stable/contracts)
