# main.ncl - Nickel-nsjail Configuration System
#
# A modular configuration system for nsjail using Nickel language.
# Inspired by Nix module system patterns.
#
# Usage:
#   nickel export -f yaml examples/apache.ncl > apache.cfg
#   nickel export -f yaml examples/firefox.ncl > firefox.cfg
#
# Or import directly:
#   let apache = import "examples/apache.ncl" in
#   nickel export -f yaml <(echo "import \"examples/apache.ncl\"") > apache.cfg

# ============================================
# Import library modules
# ============================================
let lib_types = import "./lib/types.ncl" in
let lib_modules = import "./lib/modules.ncl" in
let lib_mode = import "./lib/mode.ncl" in
let lib_mounts = import "./lib/mounts.ncl" in
let lib_rlimit = import "./lib/rlimit.ncl" in
let lib_network = import "./lib/network.ncl" in
let lib_uidmap = import "./lib/uidmap.ncl" in
let lib_seccomp = import "./lib/seccomp.ncl" in

# ============================================
# Module Composition Utilities
# ============================================

# Merge multiple records
let merge_all = fun modules =>
  std.array.fold_left (fun a => fun b => a & b) {} modules
in

# Conditionally include a module
let when = fun condition =>
  fun module =>
    if condition then module else {}
in

# Include if record has enable == true
let maybe = fun module =>
  if std.record.has_field "enable" module && module.enable == true then
    module
  else
    {}
in

# ============================================
# Type Definitions
# ============================================
let NsjailConfig = {
  # Required fields
  name | default = "",
  mode | default = "ONCE",
  hostname | default = "NSJAIL",
  description | default = "",

  # Optional fields
  cmd | default = [],
  env | default = [],
  mount | default = [],
  uidmap | default = {},
  gidmap | default = [],

  # Resource limits
  rlimit_as | default = 0,
  rlimit_data | default = 0,
  rlimit_fsize | default = 0,
  rlimit_stack | default = 0,
  rlimit_core | default = 0,
  rlimit_cpu | default = 0,
  rlimit_cpu_type | default = "INF",
  rlimit_nofile | default = 0,
  rlimit_nproc | default = 0,

  # Networking
  clone_newnet | default = false,
  clone_newuser | default = false,
  clone_newpid | default = false,
  clone_newns | default = false,

  # Seccomp
  seccomp_mode | default = 2,
  seccomp_string | default = [],

  # Logging
  log | default = "",
  log_level | default = "INFO",
}
in

# ============================================
# Base Configuration
# ============================================

# Create a base configuration
let make_config = fun name =>
  {
    name = name,
    mode = "ONCE",
    hostname = "NSJAIL",
    description = "",
    cmd = [],
    env = [],
    mount = [],
    uidmap = {},
    gidmap = [],
    clone_newnet = false,
    clone_newuser = false,
    clone_newpid = false,
    clone_newns = false,
    seccomp_mode = 2,
    seccomp_string = [],
    log = "",
    log_level = "INFO",
  }
in

# ============================================
# Module Aliases (for convenience)
# ============================================
let mode = lib_mode in
let mounts = lib_mounts in
let rlimit = lib_rlimit in
let network = lib_network in
let uidmap = lib_uidmap in
let seccomp = lib_seccomp in

# ============================================
# Configuration Builders
# ============================================

# Apply seccomp filter to config
let with_seccomp = fun config =>
  fun seccomp_config =>
    config & seccomp_config
in

# Apply UID/GID mapping
let with_uidmap = fun config =>
  fun mapping =>
    config & mapping
in

# Apply resource limits
let with_rlimit = fun config =>
  fun limits =>
    config & limits
in

# Apply network configuration
let with_network = fun config =>
  fun net_config =>
    config & net_config
in

# Apply mounts
let with_mounts = fun config =>
  fun mounts_list =>
    config & { mount = mounts_list }
in

# ============================================
# Validation Helpers
# ============================================

# Validate that required fields are present
let validate = fun config =>
  if config.name == "" then
    std.contract.custom
      (fun label value =>
        'Error { message = "Config must have a non-empty 'name' field" }
      )
      config
  else if config.cmd == [] then
    std.contract.custom
      (fun label value =>
        'Error { message = "Config must have a 'cmd' field with at least one command" }
      )
      config
  else
    config
in

# ============================================
# Export Configuration
# ============================================
{
  # Version
  version = "1.0.0",

  # Utilities
  merge_all = merge_all,
  when = when,
  maybe = maybe,

  # Type definitions
  NsjailConfig = NsjailConfig,

  # Builders
  make_config = make_config,
  validate = validate,
  with_seccomp = with_seccomp,
  with_uidmap = with_uidmap,
  with_rlimit = with_rlimit,
  with_network = with_network,
  with_mounts = with_mounts,

  # Re-export modules
  mode = mode,
  mounts = mounts,
  rlimit = rlimit,
  network = network,
  uidmap = uidmap,
  seccomp = seccomp,
}
