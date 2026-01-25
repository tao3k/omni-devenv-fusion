# lib/seccomp.ncl - Seccomp configuration module
#
# Provides seccomp filter configuration with Schema pattern:
# - Basic policies (KILL_PROCESS, ERRNO, TRAP, ALLOW)
# - Syscall whitelisting
# - Common syscall groups
#
# Usage:
#   let seccomp = import "./lib/seccomp.ncl" in
#   seccomp.block_dangerous  # => seccomp config

# ============================================
# INTERNAL: Schema Definition (hidden from public API)
# Using standard contracts for runtime validation
# ============================================

# Seccomp mode contract (0=disabled, 2=filter)
let SeccompModeContract =
  std.contract.from_predicate (fun val =>
    std.is_number val && (val == 0 || val == 1 || val == 2)
  )
in

# String array contract
let StringArrayContract =
  std.contract.from_predicate (fun val =>
    std.is_array val && std.array.all (fun x => std.is_string x) val
  )
in

let Schema = {
  seccomp_mode | SeccompModeContract | default = 2,
  seccomp_string | StringArrayContract | default = [],
}
in

# ============================================
# PUBLIC: Seccomp Actions
# ============================================
let Action = {
  kill = "KILL_PROCESS",
  errno = "ERRNO",
  trap = "TRAP",
  allow = "ALLOW",
  log = "LOG",
}
in

# ============================================
# PUBLIC: Syscall Groups
# ============================================

# Dangerous syscalls that should be blocked
let dangerous_syscalls = [
  "ptrace",
  "process_vm_readv",
  "process_vm_writev",
  "kexec_load",
  "kexec_file_load",
  "reboot",
  "swapon",
  "swapoff",
  "syslog",
  "acct",
  "settimeofday",
  "adjtimex",
  "clock_settime",
]
in

# Network-related syscalls
let network_syscalls = [
  "socket",
  "connect",
  "accept",
  "bind",
  "listen",
  "sendto",
  "recvfrom",
  "sendmsg",
  "recvmsg",
  "shutdown",
  "getsockname",
  "getpeername",
  "socketpair",
  "setsockopt",
  "getsockopt",
]
in

# ============================================
# PUBLIC: Seccomp Builders
# ============================================

# Create a basic seccomp config with dangerous syscalls blocked
let block_dangerous_policy = {
  seccomp_string = [
    "KILL_PROCESS {",
    "\tptrace,",
    "\tprocess_vm_readv,",
    "\tprocess_vm_writev,",
    "\tkexec_load,",
    "\tkexec_file_load,",
    "\treboot,",
    "\tswapon,",
    "\tswapoff,",
    "\tsyslog,",
    "\tacct,",
    "\tsettimeofday,",
    "\tadjtimex,",
    "\tclock_settime,",
    "}",
    "DEFAULT ALLOW",
  ],
}
in

# Create a restrictive seccomp config
let restrictive_policy = {
  seccomp_string = [
    "KILL_PROCESS {",
    "\tptrace,",
    "\tprocess_vm_readv,",
    "\tprocess_vm_writev,",
    "\tkexec_load,",
    "\tkexec_file_load,",
    "}",
    "ERRNO(38) {",
    "\tio_uring_setup,",
    "\tio_uring_enter,",
    "\tio_uring_register,",
    "}",
    "DEFAULT ALLOW",
  ],
}
in

# Disable seccomp (not recommended)
let disabled_policy = {
  seccomp_mode = 0,
  seccomp_string = [],
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
      Action = Action,
      dangerous_syscalls = dangerous_syscalls,
      network_syscalls = network_syscalls,
      block_dangerous = block_dangerous_policy,
      restrictive = restrictive_policy,
      disabled = disabled_policy,
    },
  },

  # Convenience exports (direct access)
  Action = Action,
  dangerous_syscalls = dangerous_syscalls,
  network_syscalls = network_syscalls,
  block_dangerous = block_dangerous_policy,
  restrictive = restrictive_policy,
  disabled = disabled_policy,
}
