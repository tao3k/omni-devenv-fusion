# Apache HTTP Server isolation configuration
#
# Usage:
#   nickel export -f yaml examples/apache.ncl > apache.cfg
#   nsjail -C apache.cfg -l /var/log/nsjail.log --uid 1000 --gid 1000 --
let modeMod = import "../lib/mode.ncl" in
let mounts = import "../lib/mounts.ncl" in
let rlimitMod = import "../lib/rlimit.ncl" in
let network = import "../lib/network.ncl" in
let uidmapMod = import "../lib/uidmap.ncl" in
let seccomp = import "../lib/seccomp.ncl" in

# Apache web server configuration
{
  name = "apache-httpd",
  description = "Apache HTTP Server with network isolation",

  # Execution mode
  mode = "ONCE",

  # Hostname
  hostname = "apache-nsjail",

  # Network configuration - user-mode networking
  clone_newnet = false,
  user_net = {
    enable = true,
    inet4_addr = "172.17.0.10",
    inet6_addr = "",
    keep_addr = 0,
  },

  # UID mapping (1000 -> 1000)
  uidmap = uidmapMod.simple 0 0 1000 1000,

  # Resource limits for web server
  rlimit_as = 2048,
  rlimit_fsize = 1024,
  rlimit_nofile = 256,
  rlimit_nproc = 128,
  rlimit_cpu_type = "INF",

  # Mount points
  mount = [
    mounts.proc "/proc",
    mounts.tmpfs "/tmp" "512M",
    mounts.tmpfs "/var/log/apache2" "100M",
    mounts.tmpfs "/var/run" "10M",
    mounts.bind "/lib" "/lib",
    mounts.bind "/lib64" "/lib64",
    mounts.bind "/usr" "/usr",
    mounts.bind "/etc" "/etc",
    mounts.bind "/var/www" "/var/www",
    mounts.bind "/var/log/apache2" "/var/log/apache2",
    mounts.bind "/var/run/apache2" "/var/run/apache2",
  ],

  # Seccomp filter
  seccomp_mode = 2,
  seccomp_string = seccomp.block_dangerous.seccomp_string,

  # Environment
  env = [
    "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "APACHE_RUN_USER=www-data",
    "APACHE_RUN_GROUP=www-data",
    "APACHE_PID_FILE=/var/run/apache2/apache2.pid",
  ],

  # Command
  cmd = ["/usr/sbin/apache2ctl", "-k", "start"],
}
