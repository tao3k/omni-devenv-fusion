# lib/mounts.ncl - Mount configuration module
#
# Provides composable mount configuration with Schema pattern:
# - Bind mounts
# - tmpfs mounts
# - proc/sys mounts
# - Content mounts (passwd, group files)
# - Device mounts
#
# Usage:
#   let mounts = import "./lib/mounts.ncl" in
#   mounts.bind "/etc" "/etc"  # Create bind mount

# ============================================
# INTERNAL: Schema Definition (hidden from public API)
# Using standard contracts for runtime validation
# ============================================

# Mount entry contract
let MountEntryContract =
  std.contract.from_predicate (fun val =>
    std.is_record val
    && std.record.has_field "dst" val
  )
in

# Boolean contract
let BoolContract = std.contract.from_predicate (fun val => std.is_bool val) in

let Schema = {
  # Mount array
  mount
    | std.contract.from_predicate (fun val =>
      std.is_array val && std.array.all MountEntryContract val
    ),

  # Whether to mount /proc
  mount_proc | BoolContract,
}
in

# ============================================
# PUBLIC: Mount Builders
# ============================================

# Create a bind mount
let bind_fn = fun src_path =>
  fun dst_path =>
    {
      src = src_path,
      dst = dst_path,
      is_bind = true,
      rw = false,
    }
in

# Create a read-write bind mount
let bind_rw_fn = fun src_path =>
  fun dst_path =>
    {
      src = src_path,
      dst = dst_path,
      is_bind = true,
      rw = true,
    }
in

# Create a tmpfs mount
let tmpfs_fn = fun dst_path =>
  fun size =>
    {
      dst = dst_path,
      fstype = "tmpfs",
      rw = true,
      src = "",
    }
in

# Create a proc mount
let proc_fn = fun dst_path =>
  {
    dst = dst_path,
    fstype = "proc",
    rw = false,
  }
in

# Create a sysfs mount
let sysfs_fn = fun dst_path =>
  {
    dst = dst_path,
    fstype = "sysfs",
    rw = false,
  }
in

# Create a devpts mount
let devpts_fn = fun dst_path =>
  {
    dst = dst_path,
    fstype = "devpts",
    rw = true,
  }
in

# Create a content mount (for passwd/group files)
let content_fn = fun mount_content =>
  fun dst_path =>
    {
      src_content = mount_content,
      dst = dst_path,
    }
in

# ============================================
# PUBLIC: Preset Mount Lists
# ============================================

# Essential mounts for minimal isolation
let minimal_mounts = [
  proc_fn "/proc",
  tmpfs_fn "/tmp" "1G",
  bind_fn "/lib" "/lib",
  bind_fn "/usr" "/usr",
  bind_fn "/bin" "/bin",
]
in

# Standard mounts for web services
let web_mounts = [
  proc_fn "/proc",
  tmpfs_fn "/tmp" "1G",
  bind_fn "/lib" "/lib",
  bind_fn "/lib64" "/lib64",
  bind_fn "/usr" "/usr",
  bind_fn "/etc" "/etc",
  bind_fn "/var/log" "/var/log",
  bind_fn "/var/run" "/var/run",
]
in

# GUI application mounts (Firefox-like)
let gui_mounts = [
  proc_fn "/proc",
  tmpfs_fn "/tmp" "2G",
  tmpfs_fn "/dev/shm" "512M",
  bind_fn "/lib" "/lib",
  bind_fn "/lib64" "/lib64",
  bind_fn "/usr" "/usr",
  bind_fn "/usr/share" "/usr/share",
  bind_fn "/etc/fonts" "/etc/fonts",
  bind_fn "/dev/urandom" "/dev/urandom",
  bind_fn "/dev/null" "/dev/null",
  tmpfs_fn "/run/user/1000" "100M",
]
in

# Java application mounts (Tomcat-like)
let java_mounts = [
  proc_fn "/proc",
  tmpfs_fn "/tmp" "1G",
  bind_fn "/lib" "/lib",
  bind_fn "/lib64" "/lib64",
  bind_fn "/usr" "/usr",
  bind_fn "/etc" "/etc",
  bind_fn "/var/lib/tomcat8" "/var/lib/tomcat8",
  bind_fn "/var/log/tomcat8" "/var/log/tomcat8",
  bind_fn "/var/cache/tomcat8" "/var/cache/tomcat8",
  bind_fn "/usr/share/tomcat8" "/usr/share/tomcat8",
  bind_fn "/usr/share/java" "/usr/share/java",
]
in

# ============================================
# PUBLIC: Mount Helpers
# ============================================

# Add mounts to a config
let with_mounts_fn = fun mounts =>
  fun config =>
    config & { mount = mounts }
in

# Add a single mount
let add_mount_fn = fun mount =>
  fun config =>
    config & { mount = config.mount @ [mount] }
in

# Add common home directory mounts
let home_mounts_fn = fun home_path =>
  fun user_id =>
    [
      bind_rw_fn home_path "/user/home",
      tmpfs_fn "/user/.config" "100M",
      tmpfs_fn "/user/.cache" "200M",
      bind_fn "/dev/urandom" "/dev/urandom",
    ]
in

# ============================================
# PUBLIC: Module Export
# ============================================
{
  # Module structure (following Tweag pattern)
  Module = {
    Schema | not_exported = {},
    config = {
      bind = bind_fn,
      bind_rw = bind_rw_fn,
      tmpfs = tmpfs_fn,
      proc = proc_fn,
      sysfs = sysfs_fn,
      devpts = devpts_fn,
      content = content_fn,
      minimal = minimal_mounts,
      web = web_mounts,
      gui = gui_mounts,
      java = java_mounts,
      with_mounts = with_mounts_fn,
      add_mount = add_mount_fn,
      home_mounts = home_mounts_fn,
    },
  },

  # Convenience exports (direct access)
  bind = bind_fn,
  bind_rw = bind_rw_fn,
  tmpfs = tmpfs_fn,
  proc = proc_fn,
  sysfs = sysfs_fn,
  devpts = devpts_fn,
  content = content_fn,
  minimal = minimal_mounts,
  web = web_mounts,
  gui = gui_mounts,
  java = java_mounts,
  with_mounts = with_mounts_fn,
  add_mount = add_mount_fn,
  home_mounts = home_mounts_fn,
}
