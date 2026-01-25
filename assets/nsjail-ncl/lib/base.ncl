# lib/base.ncl - Base configuration module
#
# Provides common configuration patterns and defaults with Schema pattern:
# - Base config with required fields
# - Common environment variables
# - Logging configuration
# - Default working directory
#
# Usage:
#   let base = import "./lib/base.ncl" in
#   base.logging  # => logging config

# ============================================
# INTERNAL: Schema Definition (hidden from public API)
# Using standard contracts for runtime validation
# ============================================

# Non-empty string contract
let NonEmptyStringContract =
  std.contract.from_predicate (fun val =>
    std.is_string val && val != ""
  )
in

# Mode enumeration contract
let ModeContract =
  std.contract.from_predicate (fun val =>
    std.is_string val && std.array.elem val ["ONCE", "CGROUP", "LISTEN", "EXEC"]
  )
in

let Schema = {
  name | NonEmptyStringContract,
  mode | ModeContract | default = "ONCE",
  hostname | default = "NSJAIL",
  description | default = "",
}
in

# ============================================
# PUBLIC: Common Configurations
# ============================================

# Default environment for most applications
let default_env = [
  "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
  "LANG=en_US.UTF-8",
  "LANGUAGE=en_US:en",
]
in

# Logging configuration
let logging = {
  log_level = "INFO",
  log = "/var/log/nsjail.log",
}
in

# Working directory
let working_dir_fn = fun dir =>
  { working_dir = dir }
in

# Default working directory to /tmp
let default_cwd = working_dir_fn "/tmp" in

# Transient directory for temp files
let transient_dir_fn = fun dir =>
  {
    transient = {
      enable = true,
      dest_dir = dir,
      delete = true,
    },
  }
in

# Root filesystem configuration
let rootfs_fn = fun path =>
  {
    rootfs = path,
    read_only = false,
  }
in

# Read-only root filesystem
let read_only_rootfs_fn = fun path =>
  {
    rootfs = path,
    read_only = true,
  }
in

# Logging helper
let with_logging_fn = fun log_path =>
  fun log_level =>
    {
      log = log_path,
      log_level = log_level,
    }
in

# Default logging
let default_logging = with_logging_fn "/var/log/nsjail.log" "INFO" in

# Process title
let proc_title_fn = fun title =>
  { proc_title = title }
in

# Enable cgroup
let cgroup_fn = fun name =>
  {
    cgroup = {
      name = name,
      mem_max = "512M",
      cpu_max = "100000",
    },
  }
in

# CPU affinity
let cpu_affinity_fn = fun cpus =>
  {
    cgroup = {
      cpu_affinity = cpus,
    },
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
      default_env = default_env,
      logging = logging,
      working_dir = working_dir_fn,
      default_cwd = default_cwd,
      transient_dir = transient_dir_fn,
      rootfs = rootfs_fn,
      read_only_rootfs = read_only_rootfs_fn,
      with_logging = with_logging_fn,
      default_logging = default_logging,
      proc_title = proc_title_fn,
      cgroup = cgroup_fn,
      cpu_affinity = cpu_affinity_fn,
    },
  },

  # Convenience exports (direct access)
  default_env = default_env,
  logging = logging,
  working_dir = working_dir_fn,
  default_cwd = default_cwd,
  transient_dir = transient_dir_fn,
  rootfs = rootfs_fn,
  read_only_rootfs = read_only_rootfs_fn,
  with_logging = with_logging_fn,
  default_logging = default_logging,
  proc_title = proc_title_fn,
  cgroup = cgroup_fn,
  cpu_affinity = cpu_affinity_fn,
}
