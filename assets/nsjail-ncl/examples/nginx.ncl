# Minimal nginx isolation configuration
#
# Provides lightweight web server isolation:
# - User-mode networking
# - Basic resource limits
# - Essential mounts only
#
# Usage:
#   nickel main.ncl --file examples/nginx.ncl > nginx.cfg
#   nsjail -C nginx.cfg -l /var/log/nsjail.log --uid 1000 --gid 1000 --
let mounts = import "../lib/mounts.ncl" in
let rlimitMod = import "../lib/rlimit.ncl" in
let network = import "../lib/network.ncl" in
let uidmapMod = import "../lib/uidmap.ncl" in
let seccomp = import "../lib/seccomp.ncl" in

{
  name = "nginx-minimal",
  description = "Lightweight nginx isolation",

  mode = "ONCE",
  hostname = "nginx-nsjail",

  clone_newnet = false,
  user_net = {
    enable = true,
    inet4_addr = "172.17.0.40",
    inet6_addr = "",
    keep_addr = 0,
  },

  uidmap = uidmapMod.simple 0 0 1000 1000,

  rlimit_as = 2048,
  rlimit_fsize = 1024,
  rlimit_nofile = 256,
  rlimit_nproc = 128,
  rlimit_cpu_type = "INF",

  mount = [
    mounts.proc "/proc",
    mounts.tmpfs "/tmp" "256M",
    mounts.tmpfs "/var/log/nginx" "50M",
    mounts.tmpfs "/var/run" "10M",
    mounts.bind "/lib" "/lib",
    mounts.bind "/lib64" "/lib64",
    mounts.bind "/usr" "/usr",
    mounts.bind "/etc" "/etc",
    mounts.bind "/var/www" "/var/www",
    mounts.bind "/var/log/nginx" "/var/log/nginx",
    mounts.bind "/var/run/nginx" "/var/run/nginx",
  ],

  env = [
    "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
  ],

  seccomp_mode = 2,
  seccomp_string = seccomp.block_dangerous.seccomp_string,

  cmd = ["/usr/sbin/nginx", "-g", "daemon off;"],
}
