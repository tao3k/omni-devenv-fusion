# lib/rlimit.ncl - Resource limit module
#
# Provides resource limit configuration with Schema pattern:
# - Memory limits (rlimit_as, rlimit_data)
# - File size limits (rlimit_fsize)
# - CPU limits (rlimit_cpu, rlimit_cpu_type)
# - File descriptor limits (rlimit_nofile)
# - Process limits (rlimit_nproc)
#
# Usage:
#   let rlimit = import "./lib/rlimit.ncl" in
#   rlimit.memory 1024  # => { rlimit_as = 1024 }

# ============================================
# INTERNAL: Schema Definition (hidden from public API)
# Using standard contracts for runtime validation
# ============================================

# Number contract (non-negative)
let NumberContract =
  std.contract.from_predicate (fun val =>
    std.is_number val && val >= 0
  )
in

# CPU type enumeration contract
let CpuTypeContract =
  std.contract.from_predicate (fun val =>
    std.is_string val && std.array.elem val ["INF", "SOFT", "HARD"]
  )
in

let Schema = {
  rlimit_as | NumberContract | default = 0,
  rlimit_data | NumberContract | default = 0,
  rlimit_fsize | NumberContract | default = 0,
  rlimit_stack | NumberContract | default = 0,
  rlimit_core | NumberContract | default = 0,
  rlimit_cpu | NumberContract | default = 0,
  rlimit_cpu_type | CpuTypeContract | default = "INF",
  rlimit_nofile | NumberContract | default = 0,
  rlimit_nproc | NumberContract | default = 0,
}
in

# ============================================
# PUBLIC: RLIMIT Builders
# ============================================

# Set memory address space limit (MB)
let memory_fn = fun mb =>
  {
    rlimit_as = mb * 1024,
  }
in

# Set data segment limit (MB)
let data_fn = fun mb =>
  {
    rlimit_data = mb * 1024,
  }
in

# Set maximum file size (MB)
let file_size_fn = fun mb =>
  {
    rlimit_fsize = mb * 1024,
  }
in

# Set CPU time limit (seconds)
let cpu_fn = fun seconds =>
  {
    rlimit_cpu = seconds,
    rlimit_cpu_type = "INF",
  }
in

# Set file descriptor limit
let file_descriptors_fn = fun n =>
  {
    rlimit_nofile = n,
  }
in

# Set process limit
let processes_fn = fun n =>
  {
    rlimit_nproc = n,
  }
in

# Set stack size (MB)
let stack_fn = fun mb =>
  {
    rlimit_stack = mb * 1024,
  }
in

# Set core dump size (MB)
let core_fn = fun mb =>
  {
    rlimit_core = mb * 1024,
  }
in

# ============================================
# PUBLIC: Preset RLIMIT Configurations
# ============================================

# Minimal restrictions for basic isolation
let minimal = {
  rlimit_as = 1024,
  rlimit_fsize = 1024,
  rlimit_nofile = 64,
  rlimit_cpu_type = "INF",
}
in

# Moderate restrictions for web services
let web = {
  rlimit_as = 2048,
  rlimit_fsize = 1024,
  rlimit_nofile = 256,
  rlimit_nproc = 128,
  rlimit_cpu_type = "INF",
}
in

# Restrictive for GUI applications
let gui = {
  rlimit_as = 262144,
  rlimit_fsize = 1024,
  rlimit_nofile = 1024,
  rlimit_cpu = 1000,
  rlimit_cpu_type = "SOFT",
}
in

# Restrictive for Java applications
let java = {
  rlimit_as = 2048,
  rlimit_fsize = 1024,
  rlimit_nofile = 1024,
  rlimit_cpu_type = "INF",
}
in

# Unrestricted (for testing only)
let unlimited = {
  rlimit_as = 0,
  rlimit_fsize = 0,
  rlimit_nofile = 0,
  rlimit_nproc = 0,
  rlimit_cpu_type = "INF",
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
      memory = memory_fn,
      data = data_fn,
      file_size = file_size_fn,
      cpu = cpu_fn,
      file_descriptors = file_descriptors_fn,
      processes = processes_fn,
      stack = stack_fn,
      core = core_fn,
      minimal = minimal,
      web = web,
      gui = gui,
      java = java,
      unlimited = unlimited,
    },
  },

  # Convenience exports (direct access)
  memory = memory_fn,
  data = data_fn,
  file_size = file_size_fn,
  cpu = cpu_fn,
  file_descriptors = file_descriptors_fn,
  processes = processes_fn,
  stack = stack_fn,
  core = core_fn,
  minimal = minimal,
  web = web,
  gui = gui,
  java = java,
  unlimited = unlimited,
}
