# lib/mode.ncl - Execution mode module
#
# Defines execution modes for nsjail with Schema pattern:
# - ONCE: Run command once and exit
# - CGROUP: Run with cgroup management
# - LISTEN: Listen on ports (server mode)
# - EXEC: Execute and return output
#
# Usage:
#   let mode = import "./lib/mode.ncl" in
#   mode.once  # => { mode = "ONCE" }

# ============================================
# INTERNAL: Schema Definition (hidden from public API)
# Using standard contracts for runtime validation
# ============================================

# Mode enumeration contract
let ModeContract =
  std.contract.from_predicate (fun val =>
    std.is_string val && std.array.elem val ["ONCE", "CGROUP", "LISTEN", "EXEC"]
  )
in

# Port validation contract (non-negative number)
let PortContract =
  std.contract.from_predicate (fun val =>
    std.is_number val && val >= 0
  )
in

# Cross-field validation: LISTEN mode requires a port
let ListenModeContract =
  std.contract.from_predicate (fun val =>
    if val.mode == "LISTEN" && (val.port == null || val.port == 0) then
      false
    else
      true
  )
in

# Complete Schema using standard contracts
let Schema =
  {
    mode | ModeContract | default = "ONCE",
    port | PortContract | default = 0,
    hostname | default = "NSJAIL",
    description | default = "",
  }
  & ListenModeContract
in

# ============================================
# PUBLIC: Mode Builders
# ============================================

# Generic mode builder
let mode = fun mode_name =>
  {
    mode = mode_name,
  }
in

# Server mode with port
let server = fun port =>
  {
    mode = "LISTEN",
    port = port,
  }
in

# Mode presets
let once = {
  mode = "ONCE",
}
in

let cgroup = {
  mode = "CGROUP",
}
in

let exec_mode = {
  mode = "EXEC",
}
in

# ============================================
# PUBLIC: Module Export
# ============================================
{
  # Module structure (following Tweag pattern)
  Module = {
    Schema | not_exported = {},
    config = {
      mode = mode,
      once = once,
      cgroup = cgroup,
      listen = server,
      exec = exec_mode,
    },
  },

  # Convenience exports (direct access)
  mode = mode,
  once = once,
  cgroup = cgroup,
  listen = server,
  exec = exec_mode,
}
