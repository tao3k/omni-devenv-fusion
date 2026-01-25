# Firefox GUI application isolation configuration
#
# Provides:
# - Full network isolation with user-mode networking
# - X11 display forwarding
# - PulseAudio socket forwarding
# - Home directory access
# - Restricted seccomp filter
#
# Usage:
#   nickel export -f yaml examples/firefox.ncl > firefox.cfg
#   nsjail -C firefox.cfg -l /var/log/nsjail.log --uid 1000 --gid 1000 --
let modeMod = import "../lib/mode.ncl" in
let mounts = import "../lib/mounts.ncl" in
let rlimitMod = import "../lib/rlimit.ncl" in
let network = import "../lib/network.ncl" in
let uidmapMod = import "../lib/uidmap.ncl" in
let seccomp = import "../lib/seccomp.ncl" in

{
  name = "firefox-sandbox",
  description = "Firefox web browser with sandbox isolation",

  # Execution mode
  mode = "ONCE",

  # Hostname
  hostname = "firefox-nsjail",

  # Network configuration - user-mode networking
  clone_newnet = false,
  user_net = {
    enable = true,
    inet4_addr = "172.17.0.20",
    inet6_addr = "",
    keep_addr = 0,
  },

  # UID mapping (current user -> root inside jail)
  uidmap = uidmapMod.simple 0 0 1000 1000,

  # Resource limits for GUI browser
  rlimit_as = 262144,
  rlimit_fsize = 1024,
  rlimit_nofile = 1024,
  rlimit_cpu = 1000,
  rlimit_cpu_type = "SOFT",

  # Mount points
  mount = [
    # System files
    mounts.proc "/proc",
    mounts.tmpfs "/tmp" "2G",
    mounts.tmpfs "/dev/shm" "512M",
    mounts.bind "/lib" "/lib",
    mounts.bind "/lib64" "/lib64",
    mounts.bind "/usr" "/usr",
    mounts.bind "/usr/share" "/usr/share",

    # Fonts
    mounts.bind "/etc/fonts" "/etc/fonts",
    mounts.bind "/usr/share/fonts" "/usr/share/fonts",

    # X11 and display
    mounts.bind "/tmp/.X11-unix" "/tmp/.X11-unix",
    mounts.tmpfs "/mnt" "10M",

    # PulseAudio
    mounts.bind_rw "/run/user/1000/pulse" "/run/user/1000/pulse",

    # Home directory (browse and download)
    mounts.bind_rw "/Users/guangtao" "/user/home",
    mounts.tmpfs "/user/.cache" "500M",
    mounts.tmpfs "/user/.config" "100M",

    # D-Bus
    mounts.bind "/run/dbus" "/run/dbus",

    # Random devices
    mounts.bind "/dev/urandom" "/dev/urandom",
    mounts.bind "/dev/null" "/dev/null",
  ],

  # Environment variables
  env = [
    "DISPLAY=:0",
    "XAUTHORITY=/user/.Xauthority",
    "PULSE_SERVER=/run/user/1000/pulse/native",
    "HOME=/user/home",
    "PATH=/usr/local/bin:/usr/bin:/bin",
    "LANG=en_US.UTF-8",
    "LANGUAGE=en_US:en",
  ],

  # Seccomp filter (restrictive)
  seccomp_mode = 2,
  seccomp_string = seccomp.restrictive.seccomp_string,

  # Command - Firefox
  cmd = [
    "/usr/bin/firefox",
    "--no-remote",
    "--new-instance",
    "-profile",
    "/user/home/.mozilla/firefox/default",
  ],
}
