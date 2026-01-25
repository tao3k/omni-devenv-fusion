# Java/Tomcat application isolation configuration
#
# Provides:
# - Network isolation
# - JVM-friendly resource limits
# - Tomcat-specific mounts
#
# Usage:
#   nickel main.ncl --file examples/tomcat.ncl > tomcat.cfg
#   nsjail -C tomcat.cfg -l /var/log/nsjail.log --uid 1000 --gid 1000 --
let mounts = import "../lib/mounts.ncl" in
let rlimitMod = import "../lib/rlimit.ncl" in
let network = import "../lib/network.ncl" in
let uidmapMod = import "../lib/uidmap.ncl" in
let seccomp = import "../lib/seccomp.ncl" in

{
  name = "tomcat-sandbox",
  description = "Apache Tomcat with JVM isolation",

  # Execution mode
  mode = "ONCE",

  # Hostname
  hostname = "tomcat-nsjail",

  # Network configuration
  clone_newnet = false,
  user_net = {
    enable = true,
    inet4_addr = "172.17.0.30",
    inet6_addr = "",
    keep_addr = 0,
  },

  # UID mapping
  uidmap = uidmapMod.simple 0 0 1000 1000,

  # Resource limits for Java
  rlimit_as = 2048,
  rlimit_fsize = 1024,
  rlimit_nofile = 1024,
  rlimit_cpu_type = "INF",

  # Mount points
  mount = [
    mounts.proc "/proc",
    mounts.tmpfs "/tmp" "1G",
    mounts.bind "/lib" "/lib",
    mounts.bind "/lib64" "/lib64",
    mounts.bind "/usr" "/usr",
    mounts.bind "/etc" "/etc",
    mounts.bind "/etc/ssl" "/etc/ssl",
    mounts.bind "/var/lib/tomcat8" "/var/lib/tomcat8",
    mounts.bind "/var/log/tomcat8" "/var/log/tomcat8",
    mounts.bind "/var/cache/tomcat8" "/var/cache/tomcat8",
    mounts.bind "/usr/share/tomcat8" "/usr/share/tomcat8",
    mounts.bind "/usr/share/java" "/usr/share/java",
    mounts.bind "/usr/lib/jvm" "/usr/lib/jvm",
    mounts.bind "/var/run" "/var/run",
  ],

  # Environment variables
  env = [
    "JAVA_HOME=/usr/lib/jvm/default-java",
    "JRE_HOME=/usr/lib/jvm/default-java",
    "CATALINA_HOME=/usr/share/tomcat8",
    "CATALINA_BASE=/var/lib/tomcat8",
    "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "LANG=en_US.UTF-8",
  ],

  # Seccomp filter
  seccomp_mode = 2,
  seccomp_string = seccomp.block_dangerous.seccomp_string,

  # Command - Tomcat
  cmd = ["/usr/share/tomcat8/bin/catalina.sh", "run"],
}
