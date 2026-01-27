# Nickel-nsjail Configuration System

A modular configuration system for [nsjail](https://github.com/google/nsjail) using the [Nickel](https://nickel-lang.org/) language. Inspired by Nix module system patterns.

## Overview

This project provides a composable, type-safe way to generate nsjail configuration files. It follows the Nix module philosophy:

- **Modularity**: Each aspect (mounts, networking, rlimits, etc.) is a separate module
- **Composability**: Configurations are merged together
- **Reusability**: Preset configurations for common use cases
- **Type Safety**: Contract validation at merge time

## Directory Structure

```
nsjail-configs/
├── main.ncl              # Entry point with utilities
├── lib/
│   ├── types.ncl         # Type definitions and contracts
│   ├── modules.ncl       # Module composition utilities
│   ├── base.ncl          # Base configuration patterns
│   ├── mode.ncl          # Execution mode module
│   ├── mounts.ncl        # Mount configuration module
│   ├── rlimit.ncl        # Resource limit module
│   ├── network.ncl       # Network configuration module
│   ├── uidmap.ncl        # UID/GID mapping module
│   └── seccomp.ncl       # Seccomp configuration module
└── examples/
    ├── apache.ncl        # Apache HTTP Server
    ├── firefox.ncl       # Firefox GUI browser
    ├── tomcat.ncl        # Apache Tomcat
    └── nginx.ncl         # nginx web server
```

## Quick Start

### Prerequisites

- [Nickel](https://nickel-lang.org/) installed (`cargo install nickel` or `nix-shell`)
- nsjail installed on the target system

### Generate Configuration

```bash
# Generate Apache configuration
nickel export -f yaml examples/apache.ncl > apache.cfg

# Generate Firefox configuration
nickel export -f yaml examples/firefox.ncl > firefox.cfg

# Generate nginx configuration
nickel export -f yaml examples/nginx.ncl > nginx.cfg
```

To validate a configuration without generating output, use the `check` subcommand:

```bash
nickel check examples/apache.ncl
```

### Run nsjail

```bash
# Run with the generated configuration
nsjail -C apache.cfg -l /var/log/nsjail.log --uid 1000 --gid 1000 --

# For GUI applications with X11 forwarding
nsjail -C firefox.cfg -l /var/log/nsjail.log --uid 1000 --gid 1000 -- --x11
```

## Creating Custom Configurations

### Basic Configuration

```nickel
let myapp = let
  mounts = import "./lib/mounts.ncl"
  rlimit = import "./lib/rlimit.ncl"
  network = import "./lib/network.ncl"
  uidmap = import "./lib/uidmap.ncl"
in

{
  name = "myapp",
  mode = mode.once,
  hostname = "myapp-nsjail",

  # Network
  network = network.user_net { ipaddr = "172.17.0.50" },

  # UID mapping
  uidmap = uidmap.simple 0 0 1000 1000,

  # Resource limits
  rlimit = rlimit.minimal,

  # Mounts
  mount = [
    mounts.proc "/proc",
    mounts.tmpfs "/tmp" "512M",
    mounts.bind "/usr" "/usr",
    mounts.bind "/etc" "/etc",
  ],

  # Command
  cmd = ["/usr/bin/myapp"],
}
```

### Using Module Presets

```nickel
# Compose multiple presets
let config = {
  name = "webapp",
  mode = mode.once,
  hostname = "webapp",

  # Combine presets
  rlimit = rlimit @@ rlimit.web,

  # Custom mounts on top of preset
  mount = web_mounts @ [
    mounts.bind "/my/app" "/opt/app",
  ],
}
```

### Conditional Configuration

```nickel
let config = {
  name = "myapp",
  mode = mode.once,

  # Conditionally add logging
  log = if enable_logging then "/var/log/nsjail.log" else "",
}
```

## Module Reference

### mode

Execution modes for nsjail.

```nickel
mode.once      # ONCE - Run command once and exit
mode.cgroup    # CGROUP - Run in cgroup mode
mode.listen    # LISTEN - Listen on port for connections
mode.exec      # EXEC - Execute and wait
```

### mounts

Mount point builders.

```nickel
mounts.bind "/src" "/dst"          # Read-only bind mount
mounts.bind_rw "/src" "/dst"       # Read-write bind mount
mounts.tmpfs "/tmp" "1G"           # tmpfs with size
mounts.proc "/proc"                # proc filesystem
mounts.sysfs "/sys"                # sysfs filesystem
mounts.devpts "/dev/pts"           # devpts filesystem

# Preset mount lists
mounts.minimal_mounts
mounts.web_mounts
mounts.gui_mounts
mounts.java_mounts
```

### rlimit

Resource limit builders.

```nickel
rlimit.memory 1024         # 1GB address space
rlimit.cpu 3600            # 1 hour CPU time
rlimit.file_descriptors 256
rlimit.processes 128

# Preset configurations
rlimit.minimal
rlimit.web
rlimit.gui
rlimit.java
rlimit.unlimited
```

### network

Network isolation options.

```nickel
network.isolated       # Full network namespace isolation
network.disabled       # No networking
network.pasta          # User-mode networking (default)
network.user_net { ipaddr = "172.17.0.10" }  # Custom user_net

# DNS configuration
network.dns_google     # Use Google DNS (8.8.8.8, 8.8.4.4)
network.dns_cloudflare # Use Cloudflare DNS (1.1.1.1)
```

### uidmap

UID/GID mapping utilities.

```nickel
uidmap.simple 0 0 1000 1000       # Map uid 0->1000, gid 0->1000
uidmap.map_root_to_user "1000"    # Map root to user 1000
uidmap.id_map 1000 1000           # Both uid and gid mapping
```

### seccomp

Seccomp filter configuration.

```nickel
seccomp.block_dangerous  # Block dangerous syscalls
seccomp.restrictive      # Restrictive policy
seccomp.disabled         # Disable seccomp

# Access to action types
seccomp.Action.kill      # KILL_PROCESS
seccomp.Action.errno     # ERRNO
seccomp.Action.trap      # TRAP
seccomp.Action.allow     # ALLOW
seccomp.Action.log       # LOG
```

## Contract Validation

The system uses Nickel's contract system to validate configurations:

```nickel
# Invalid configuration will fail at merge time
let bad_config = {
  name = "",  # Empty name - will fail
  cmd = [],   # Empty cmd - will fail
}
```

## Best Practices

1. **Use Presets**: Start with a preset and customize
2. **Least Privilege**: Start with restrictive settings, relax as needed
3. **Test Configurations**: Use `nickel check config.ncl` to validate before running
4. **Log Appropriately**: Enable logging for troubleshooting
5. **UID Mapping**: Always map to a non-root user for production

## Contributing

1. Create a new example in `examples/`
2. Add new presets to existing modules
3. Create new modules for additional nsjail features
4. Update documentation

## License

MIT License - See LICENSE file for details.
