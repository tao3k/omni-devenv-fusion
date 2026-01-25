# lib/types.ncl - Type definitions and Contracts for nsjail configurations
#
# This module provides:
# - Type definitions for all nsjail configuration fields
# - Runtime contracts for validation
# - Default values for optional fields

# ============================================
# Field Types
# ============================================

# Mode type: ONCE, CGROUP, LISTEN, EXEC
let Mode = fun val =>
  if std.string.is_match val "^(ONCE|CGROUP|LISTEN|EXEC)$" then
    val
  else
    std.contract.custom
      (fun label value =>
        'Error { message = "Mode must be one of: ONCE, CGROUP, LISTEN, EXEC" }
      )
      val
in

# UID/GID mapping entry
let UidGidMapEntry = {
  inside_id | default = "",
  outside_id | default = "",
  count | default = 1,
}
in

# Mount entry
let MountEntry = {
  src | default = "",
  src_content | default = "",
  dst,
  fstype | default = "",
  rw | default = false,
  is_bind | default = true,
  mandatory | default = true,
  prefix_src_env | default = "",
}
in

# RLIMIT type
let RlimitType =
  std.contract.from_predicate (fun val =>
    std.string.is_match val "^(INF|SOFT|HARD|SEM|MSG)$"
  )
in

# Network configuration
let NetworkConfig = {
  clone_newnet | default = false,
  clone_newuser | default = true,
  clone_newpid | default = true,
  clone_newns | default = true,
  user_net | default = {},
  macvlan_iface | default = "",
  macvlan_vs_ip | default = "",
  macvlan_vs_nm | default = "",
  macvlan_vs_gw | default = "",
}
in

# Execution configuration
let ExecConfig = {
  path,
  arg | default = "",
  arg_delim | default = " ",
  chroot | default = "",
  user | default = "",
  group | default = "",
}
in

# Seccomp configuration
let SeccompConfig = {
  seccomp_string : Array String | default = [],
  seccomp_mode : Number | default = 0,
}
in

# ============================================
# Main Config Type
# ============================================

# Complete nsjail configuration type (using contracts for runtime validation)
let NsjailConfig = {
  # Identity
  name,
  description | default = "",

  # Execution mode
  mode | default = "ONCE",
  hostname | default = "NSJAIL",
  cwd | default = "/",

  # Time limits
  time_limit | default = 0,
  max_conns | default = 0,
  max_conns_per_ip | default = 0,

  # Resource limits
  rlimit_as | default = 0,
  rlimit_core | default = 0,
  rlimit_cpu | default = 0,
  rlimit_cpu_type | default = "INF",
  rlimit_data | default = 0,
  rlimit_fsize | default = 0,
  rlimit_nofile | default = 0,
  rlimit_nproc | default = 0,
  rlimit_stack | default = 0,

  # Identity mappings
  uidmap | default = [],
  gidmap | default = [],
  uid | default = "",
  gid | default = "",

  # Capabilities
  cap | default = [],
  drop_cap | default = [],

  # Environment
  envar | default = [],

  # Mounts
  mount | default = [],
  mount_proc | default = true,

  # Network
  network | default = {},

  # Execution
  exec_bin | default = {},
  exec_shell | default = "",

  # Security
  seccomp | default = {},

  # Logging
  log_level | default = "info",
  log_file | default = "",

  # Booleans
  keep_caps | default = false,
  keep_env | default = false,
  keep_fds | default = false,
  no_new_privs | default = true,
  read_only | default = false,
  disable_no_new_privs_start | default = false,
  skip_seccomp_compiler_check | default = false,
}
in

# ============================================
# Validation Contracts
# ============================================

# Contract for validating a complete config
let NsjailContract = fun val =>
  let checked = val | NsjailConfig in
  # Additional runtime validations
  if checked.mode == "LISTEN" && checked.network == {} then
    std.contract.custom
      (fun label value =>
        'Error { message = "Network config required for LISTEN mode" }
      )
      checked
  else if checked.exec_bin == {} && checked.exec_shell == "" then
    std.contract.custom
      (fun label value =>
        'Error { message = "Either exec_bin or exec_shell must be specified" }
      )
      checked
  else
    checked
in

# ============================================
# Exports
# ============================================
{
  Mode = Mode,
  UidGidMapEntry = UidGidMapEntry,
  MountEntry = MountEntry,
  NetworkConfig = NetworkConfig,
  ExecConfig = ExecConfig,
  SeccompConfig = SeccompConfig,
  NsjailConfig = NsjailConfig,
  NsjailContract = NsjailContract,
}
