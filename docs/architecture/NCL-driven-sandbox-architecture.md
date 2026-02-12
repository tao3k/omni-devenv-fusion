# NCL-Driven Sandbox Architecture

> **Version**: 1.0.0
> **Date**: 2026-02-08
> **Architecture**: NCL-First Configuration, Rust-First Execution

## Overview

This document describes the NCL-driven sandbox architecture for omni-dev-fusion skill execution isolation. The architecture follows a **separation of concerns** principle:

- **NCL (Nickel)**: Single source of truth for sandbox configuration (types, validation, policies)
- **Rust**: High-performance execution layer (process spawning, resource monitoring, IPC)
- **Python**: Orchestration glue layer (NCL export, result aggregation)

### Key Design Principle

> **NCL generates final configuration. Rust executes without configuration parsing.**

This means:

1. NCL defines types, contracts, and policies
2. NCL exports to JSON/YAML format
3. Rust reads the exported JSON and executes the sandbox
4. Rust does NOT parse configuration logic—it only executes the pre-computed configuration

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        NCL Configuration Layer                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  packages/ncl/sandbox/                                               │    │
│  │  ├── main.ncl                 # Central export: import "sandbox"     │    │
│  │  ├── lib/                     # Base utilities                        │    │
│  │  │   ├── base.ncl            # Types, contracts                      │    │
│  │  │   ├── mounts.ncl          # Mount configurations                   │    │
│  │  │   ├── rlimits.ncl        # Resource limits                        │    │
│  │  │   ├── network.ncl        # Network policies                       │    │
│  │  │   ├── seccomp.ncl        # Syscall filters                        │    │
│  │  │   └── platform.ncl        # Platform detection                     │    │
│  │  ├── nsjail/                 # Linux nsjail executor                 │    │
│  │  │   └── main.ncl                                                 │    │
│  │  ├── seatbelt/               # macOS Seatbelt executor               │    │
│  │  │   └── main.ncl                                                 │    │
│  │  └── skill/                   # Pre-built skill configs               │    │
│  │      └── main.ncl                                                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                              │ nickel export --format json                   │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Generated Configs (JSON/YAML)                                       │    │
│  │  ~/.omni/sandbox/profiles/{skill_id}/                               │    │
│  │      ├── nsjail.json          # Linux sandbox config                 │    │
│  │      └── seatbelt.sb          # macOS sandbox profile                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Read JSON
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Rust Execution Layer                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  packages/rust/crates/omni-sandbox/                                  │    │
│  │  ├── src/                                                             │    │
│  │  │   ├── lib.rs              # PyO3 module exports                   │    │
│  │  │   ├── executor/           # Sandbox executor implementations       │    │
│  │  │   │   ├── mod.rs          # Unified executor trait                │    │
│  │  │   │   ├── nsjail.rs       # nsjail execution (read JSON, spawn)  │    │
│  │  │   │   ├── seatbelt.rs     # Seatbelt execution (read JSON)       │    │
│  │  │   │   └── common.rs       # Shared utilities                      │    │
│  │  │   ├── config/             # Config parsing (read-only)           │    │
│  │  │   │   └── mod.rs          # JSON → Rust struct mapping           │    │
│  │  │   └── monitor/             # Resource monitoring                   │    │
│  │  │       └── mod.rs          # CPU, memory, execution time tracking  │    │
│  │  └── Cargo.toml                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                              │ PyO3 bindings                                 │
│                              ▼                                               │
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Python Orchestration Layer                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  packages/python/core/src/omni/core/skills/                          │    │
│  │  ├── sandbox.py              # NclDrivenSandbox orchestrator        │    │
│  │  └── executor.py             # Async execution helpers               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## NCL Module Structure

### `packages/ncl/sandbox/lib/base.ncl`

Base type definitions shared across all sandbox implementations.

```nickel
# ============================================
# Base Type Definitions
# ============================================

# Platform enumeration
let Platform = fun val =>
  if std.string.is_match val "^(linux|macos|windows)$" then
    val
  else
    std.contract.custom
      (fun label value =>
        'Error { message = "Platform must be one of: linux, macos, windows" }
      )
      val
in

# Skill capability levels
let CapabilityLevel = fun val =>
  if std.string.is_match val "^(none|network_read|network_write|file_read|file_write|exec)$" then
    val
  else
    std.contract.custom
      (fun label value =>
        'Error { message = "Invalid capability level" }
      )
      val
in

# Resource limit type
let ResourceLimit = {
  value | default = 0,
  unit | default = "mb",  # kb, mb, gb, seconds
}
in

# ============================================
# Base Skill Config
# ============================================

let BaseSkillConfig = {
  # Identity
  skill_id,
  skill_name | default = "",
  skill_version | default = "1.0.0",

  # Platform targeting
  platform | default = "linux",

  # Capability grants
  capabilities | default = {
    network = "none",
    filesystem = "file_read",
    process = "none",
  },

  # Resource limits
  resources | default = {
    max_memory_mb | default = 256,
    max_cpu_seconds | default = 60,
    max_file_size_mb | default = 10,
    max_output_bytes | default = 1048576,  # 1MB
  },

  # Environment
  environment | default = [],

  # Working directory
  working_dir | default = "/tmp/skill",
}
in

# ============================================
# Exports
# ============================================
{
  Platform = Platform,
  CapabilityLevel = CapabilityLevel,
  ResourceLimit = ResourceLimit,
  BaseSkillConfig = BaseSkillConfig,
}
```

### `assets/knowledge/ncl/sandbox/skill/lib/types.ncl`

Type definitions for skill sandbox configurations.

```nickel
# ============================================
# Import base types
# ============================================
let base = import "../../lib/base.ncl" in

# ============================================
# Linux-specific Types (nsjail)
# ============================================

# nsjail execution mode
let NsjailMode = fun val =>
  if std.string.is_match val "^(ONCE|EXEC)$" then
    val
  else
    std.contract.custom
      (fun label value =>
        'Error { message = "NsjailMode must be ONCE or EXEC" }
      )
      val
in

# Mount point configuration
let NsJailMount = {
  src | default = "",
  dst,
  fstype | default = "bind",
  rw | default = false,
  mandatory | default = true,
}
in

# Seccomp policy level
let SeccompLevel = fun val =>
  if std.string.is_match val "^(disabled|basic|standard|strict)$" then
    val
  else
    std.contract.custom
      (fun label value =>
        'Error { message = "SeccompLevel must be disabled, basic, standard, or strict" }
      )
      val
in

# ============================================
# macOS-specific Types (Seatbelt)
// ===========================================

# Seatbelt profile entry
let SeatbeltEntry = {
  rule_type,  # allow, deny
  operation,
  prefix | default = "",
  regex | default = "",
}
in

# ============================================
# Skill Sandbox Configuration
# ============================================

let SkillSandboxConfig = {
  # Identity (from BaseSkillConfig)
  skill_id,
  skill_name | default = "",
  platform | default = "linux",

  # nsjail-specific (Linux)
  nsjail_mode | default = "EXEC",
  hostname | default = "skill-sandbox",
  mounts | default = [],
  readonly_mounts | default = [],
  seccomp_level | default = "standard",

  # Seatbelt-specific (macOS)
  seatbelt_rules | default = [],

  # Capability enforcement
  network_policy | default = "deny",  # deny, localhost, allow
  filesystem_policy | default = "chroot",  # chroot, whitelist, deny

  # Resource limits
  max_memory_mb | default = 256,
  max_cpu_seconds | default = 60,
  max_file_size_mb | default = 10,
  max_output_bytes | default = 1048576,

  # Execution
  cmd | default = [],
  env | default = [],
  timeout_seconds | default = 60,

  # Logging
  log_enabled | default = true,
  log_level | default = "info",
}
in

# ============================================
# Exports
# ============================================
{
  # Base types (re-export)
  Platform = base.Platform,
  CapabilityLevel = base.CapabilityLevel,
  ResourceLimit = base.ResourceLimit,
  BaseSkillConfig = base.BaseSkillConfig,

  # nsjail types
  NsjailMode = NsjailMode,
  NsJailMount = NsJailMount,
  SeccompLevel = SeccompLevel,

  # Seatbelt types
  SeatbeltEntry = SeatbeltEntry,

  # Main config
  SkillSandboxConfig = SkillSandboxConfig,
}
```

### `assets/knowledge/ncl/sandbox/skill/lib/policy.ncl`

Policy combinators for composing sandbox configurations.

```nickel
# ============================================
# Policy Combinators
# ============================================

# Merge two configurations
let merge_configs = fun base => fun override =>
  base & override
in

# Apply policy conditionally
let when = fun condition =>
  fun policy =>
    if condition then policy else {}
in

# Compose multiple policies
let compose = fun policies =>
  std.array.fold_left (fun acc => fun p => acc & p) {} policies
in

# ============================================
# Capability Policies
# ============================================

# Network capability policies
let network_policies = {
  deny = {
    network_policy = "deny",
  },

  localhost = {
    network_policy = "localhost",
  },

  allow = {
    network_policy = "allow",
  },

  whitelist = fun domains =>
    {
      network_policy = "whitelist",
      allowed_domains = domains,
    }
in

# Filesystem capability policies
let filesystem_policies = {
  chroot = {
    filesystem_policy = "chroot",
  },

  deny_all = {
    filesystem_policy = "deny",
  },

  whitelist = fun paths =>
    {
      filesystem_policy = "whitelist",
      allowed_paths = paths,
    }
in

# ============================================
# Resource Limit Policies
# ============================================

# Memory limits
let memory_limits = {
  minimal = {
    max_memory_mb = 64,
  },

  small = {
    max_memory_mb = 128,
  },

  medium = {
    max_memory_mb = 256,
  },

  large = {
    max_memory_mb = 512,
  },

  custom = fun mb =>
    {
      max_memory_mb = mb,
    }
in

# CPU time limits
let cpu_limits = {
  short = {
    max_cpu_seconds = 10,
  },

  medium = {
    max_cpu_seconds = 60,
  },

  long = {
    max_cpu_seconds = 300,
  },

  extended = {
    max_cpu_seconds = 3600,
  },
}
in

# ============================================
# Security Level Policies
# ============================================

# Seccomp levels
let security_levels = {
  permissive = {
    seccomp_level = "disabled",
    network_policy = "allow",
    filesystem_policy = "chroot",
    max_memory_mb = 512,
  },

  standard = {
    seccomp_level = "standard",
    network_policy = "localhost",
    filesystem_policy = "chroot",
    max_memory_mb = 256,
  },

  strict = {
    seccomp_level = "strict",
    network_policy = "deny",
    filesystem_policy = "whitelist",
    max_memory_mb = 128,
    max_cpu_seconds = 30,
  },
}
in

# ============================================
# Pre-built Skill Profiles
# ============================================

# Read-only data processing skill
let data_processing_profile = {
  skill_name = "data-processing",
  capabilities = {
    network = "none",
    filesystem = "file_read",
    process = "none",
  },
  resources = memory_limits.small & cpu_limits.medium,
  network_policy = "deny",
  filesystem_policy = "chroot",
  seccomp_level = "strict",
}
in

# Web scraping skill
let web_scraping_profile = {
  skill_name = "web-scraper",
  capabilities = {
    network = "network_read",
    filesystem = "file_write",
    process = "none",
  },
  resources = memory_limits.medium & cpu_limits.long,
  network_policy = "localhost",
  filesystem_policy = "whitelist",
  seccomp_level = "standard",
}
in

# Code execution skill (highest privileges)
let code_execution_profile = {
  skill_name = "code-execution",
  capabilities = {
    network = "network_read",
    filesystem = "file_write",
    process = "exec",
  },
  resources = memory_limits.large & cpu_limits.extended,
  network_policy = "allow",
  filesystem_policy = "chroot",
  seccomp_level = "standard",
}
in

# ============================================
# Exports
# ============================================
{
  merge_configs = merge_configs,
  when = when,
  compose = compose,
  network_policies = network_policies,
  filesystem_policies = filesystem_policies,
  memory_limits = memory_limits,
  cpu_limits = cpu_limits,
  security_levels = security_levels,
  data_processing_profile = data_processing_profile,
  web_scraping_profile = web_scraping_profile,
  code_execution_profile = code_execution_profile,
}
```

### `assets/knowledge/ncl/sandbox/skill/lib/nsjail.ncl`

nsjail-specific configuration module.

```nickel
# ============================================
# nsjail Configuration Module
# ============================================

let types = import "./types.ncl" in
let policy = import "./policy.ncl" in

# ============================================
# Seccomp Filter Definitions
# ============================================

let dangerous_syscalls = [
  "ptrace",
  "process_vm_readv",
  "process_vm_writev",
  "kexec_load",
  "reboot",
  "setuid",
  "setgid",
  "setreuid",
  "setregid",
  "setresuid",
  "setresgid",
  "chroot",
  "unshare",
  "clone",
  "fork",
  "vfork",
]
in

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
  "getsockopt",
  "setsockopt",
  "getpeername",
  "getsockname",
]
in

let file_write_syscalls = [
  "open",
  "openat",
  "creat",
  "unlink",
  "rename",
  "mkdir",
  "rmdir",
  "symlink",
  "link",
  "chmod",
  "chown",
  "truncate",
  "ftruncate",
]
in

# ============================================
# Seccomp Policy Builders
# ============================================

let seccomp_policies = {
  disabled = {
    seccomp_mode = 0,
    seccomp_string = [],
  },

  basic = {
    seccomp_mode = 2,
    seccomp_string = std.array.concat dangerous_syscalls [],
  },

  standard = {
    seccomp_mode = 2,
    seccomp_string = std.array.concat dangerous_syscalls network_syscalls,
  },

  strict = {
    seccomp_mode = 2,
    seccomp_string = std.array.concat
      dangerous_syscalls
      (std.array.concat network_syscalls file_write_syscalls),
  },
}
in

# ============================================
# Mount Configuration
# ============================================

let default_mounts = [
  {
    src = "",
    dst = "/proc",
    fstype = "proc",
    rw = false,
    mandatory = true,
  },
  {
    src = "",
    dst = "/dev",
    fstype = "tmpfs",
    rw = true,
    mandatory = true,
  },
  {
    src = "",
    dst = "/tmp",
    fstype = "tmpfs",
    rw = true,
    mandatory = true,
  },
]
in

let readonly_mounts = [
  {
    src = "",
    dst = "/usr",
    fstype = "bind",
    rw = false,
    mandatory = true,
  },
  {
    src = "",
    dst = "/lib",
    fstype = "bind",
    rw = false,
    mandatory = true,
  },
]
in

# ============================================
# Network Configuration
# ============================================

let network_configs = {
  deny = {
    clone_newnet = false,
    user_net = {},
  },

  localhost = {
    clone_newnet = true,
    user_net = {
      enable = true,
      ipv4 = "10.0.0.1",
    },
  },

  allow = {
    clone_newnet = true,
    user_net = {},
  },
}
in

# ============================================
# nsjail Configuration Builder
# ============================================

let make_nsjail_config = fun skill_config =>
  let policy_level = skill_config.seccomp_level in
  let net_policy = skill_config.network_policy in
  {
    # Required fields
    name = skill_config.skill_id,
    mode = skill_config.nsjail_mode,
    hostname = skill_config.hostname,

    # Command
    cmd = skill_config.cmd,
    env = skill_config.env,

    # Mounts
    mount = skill_config.mounts @ default_mounts,

    # RLIMIT
    rlimit_as = skill_config.max_memory_mb * 1024 * 1024,
    rlimit_cpu = skill_config.max_cpu_seconds,
    rlimit_cpu_type = "SOFT",
    rlimit_fsize = skill_config.max_file_size_mb * 1024 * 1024,
    rlimit_core = 0,
    rlimit_nofile = 1024,
    rlimit_nproc = 64,
    rlimit_stack = 8 * 1024 * 1024,

    # Network
    clone_newnet = net_policy != "deny",
    clone_newuser = true,
    clone_newpid = true,
    clone_newns = true,

    # Seccomp
    seccomp_mode = 2,
    seccomp_string = seccomp_policies.(policy_level).seccomp_string,

    # Logging
    log_level = skill_config.log_level,
    log = if skill_config.log_enabled then
      "/var/log/nsjail/%{skill_config.skill_id}.log"
    else
      "",

    # Execution constraints
    time_limit = skill_config.timeout_seconds,
    keep_caps = false,
    no_new_privs = true,
    read_only = skill_config.filesystem_policy == "whitelist",
  }
in

# ============================================
# Export
# ============================================
{
  dangerous_syscalls = dangerous_syscalls,
  network_syscalls = network_syscalls,
  file_write_syscalls = file_write_syscalls,
  seccomp_policies = seccomp_policies,
  default_mounts = default_mounts,
  readonly_mounts = readonly_mounts,
  network_configs = network_configs,
  make_nsjail_config = make_nsjail_config,
}
```

### `assets/knowledge/ncl/sandbox/skill/lib/seatbelt.ncl`

macOS Seatbelt-specific configuration module.

```nickel
# ============================================
# Seatbelt Configuration Module
# ============================================

let types = import "./types.ncl" in

# ============================================
# Mandatory Deny Patterns
# ============================================

let mandatory_deny_files = [
  # Shell configurations
  ".bashrc",
  ".bash_profile",
  ".zshrc",
  ".zprofile",
  ".fish/config.fish",

  # Git configurations
  ".gitconfig",
  ".git/hooks",

  # IDE configurations
  ".vscode",
  ".idea",
  ".atom",

  # Package manager configs
  ".npmrc",
  ".cargo/config",
  ".pip/pip.conf",

  # Security files
  ".ssh",
  ".gnupg",
  ".aws",
  ".kube",
  ".docker",

  # Agent configurations
  ".mcp.json",
  ".claude",
  ".cursor",
]
in

# ============================================
# Seatbelt Rule Builders
# ============================================

# Generate deny regex pattern
let deny_pattern = fun path =>
  '(deny file-write* (regex #"(%{path})(/|$)"))'
in

let deny_regex_pattern = fun regex =>
  '(deny file-write* (regex #"%{regex}"))'
in

# Allow read-only access to system directories
let system_readonly_rules = [
  "(allow file-read* (subpath /usr))",
  "(allow file-read* (subpath /System))",
  "(allow file-read* (subpath /Library))",
]
in

# Allow read-write to temp directories
let temp_rw_rules = [
  "(allow file-read* (subpath /tmp))",
  "(allow file-write* (subpath /tmp))",
]
in

# ============================================
# Network Rules
# ============================================

let network_rules = {
  deny = [
    "(deny network*)",
  ],

  localhost = [
    "(allow network-bind (local ip))",
    "(deny network*)",
  ],

  allow = [
    "(allow network*)",
  ],
}
in

# ============================================
# Process Rules
# ============================================

let process_rules = {
  none = [
    "(deny process*)",
  ],

  basic = [
    "(allow process-fork)",
  ],

  exec = [
    "(allow process-fork)",
    "(allow process-exec* (regex #'/usr/bin/'))",
    "(allow process-exec* (regex #'/bin/'))",
  ],
}
in

# ============================================
# Seatbelt Profile Builder
# ============================================

let make_seatbelt_profile = fun skill_config =>
  let deny_rules = std.array.map
    (fun path => deny_pattern path)
    mandatory_deny_files
  in
  let base_rules = std.array.concat deny_rules system_readonly_rules in
  let rw_rules = if skill_config.filesystem_policy == "chroot" then
    temp_rw_rules
  else
    []
  in
  let net_rules = network_rules.(skill_config.network_policy) in
  let proc_rules = process_rules.(skill_config.capabilities.process) in

  std.string.join "\n" (
    base_rules @ rw_rules @ net_rules @ proc_rules
  )
in

# ============================================
# Export
# ============================================
{
  mandatory_deny_files = mandatory_deny_files,
  deny_pattern = deny_pattern,
  deny_regex_pattern = deny_regex_pattern,
  system_readonly_rules = system_readonly_rules,
  temp_rw_rules = temp_rw_rules,
  network_rules = network_rules,
  process_rules = process_rules,
  make_seatbelt_profile = make_seatbelt_profile,
}
```

### `assets/knowledge/ncl/sandbox/skill/default.ncl`

Default skill sandbox configuration.

```nickel
# ============================================
# Default Skill Sandbox Configuration
# ============================================

let base = import "lib/base.ncl" in
let types = import "lib/types.ncl" in
let policy = import "lib/policy.ncl" in
let nsjail = import "lib/nsjail.ncl" in
let seatbelt = import "lib/seatbelt.ncl" in

# ============================================
# Default Configuration Builder
# ============================================

let make_default_config = fun skill_id =>
  {
    # Identity
    skill_id = skill_id,
    skill_name = skill_id,
    platform = "linux",

    # Standard security profile
    seccomp_level = "standard",
    network_policy = "localhost",
    filesystem_policy = "chroot",

    # Resource limits
    max_memory_mb = 256,
    max_cpu_seconds = 60,
    max_file_size_mb = 10,
    max_output_bytes = 1048576,

    # Execution defaults
    nsjail_mode = "EXEC",
    hostname = "omni-skill-%{skill_id}",
    cmd = [],
    env = [],
    timeout_seconds = 60,

    # Mounts
    mounts = nsjail.default_mounts,

    # Logging
    log_enabled = true,
    log_level = "info",
  }
in

# ============================================
# Export as Module
# ============================================

# Version
{
  version = "1.0.0",

  # Builders
  make_default_config = make_default_config,

  # Re-export modules
  base = base,
  types = types,
  policy = policy,
  nsjail = nsjail,
  seatbelt = seatbelt,
}
```

---

## Rust Execution Layer

### `packages/rust/crates/omni-sandbox/src/lib.rs`

```rust
//! omni-sandbox - NCL-driven sandbox execution layer
//!
//! # Architecture
//!
//! This module executes pre-generated sandbox configurations.
//! Configuration is produced by NCL and exported as JSON.
//! Rust reads JSON and performs execution - NO configuration parsing in Rust.

use pyo3::prelude::*;
use std::path::PathBuf;

pub mod executor;
pub mod config;
pub mod monitor;

/// Sandbox execution result
#[pyclass]
#[derive(Debug, Clone)]
pub struct ExecutionResult {
    #[pyo3(get)]
    pub success: bool,

    #[pyo3(get)]
    pub exit_code: Option<i32>,

    #[pyo3(get)]
    pub stdout: String,

    #[pyo3(get)]
    pub stderr: String,

    #[pyo3(get)]
    pub execution_time_ms: u64,

    #[pyo3(get)]
    pub memory_used_bytes: Option<u64>,

    #[pyo3(get)]
    pub error: Option<String>,
}

/// Resource usage snapshot
#[pyclass]
#[derive(Debug, Clone)]
pub struct ResourceUsage {
    #[pyo3(get)]
    pub memory_bytes: u64,

    #[pyo3(get)]
    pub cpu_time_seconds: f64,

    #[pyo3(get)]
    pub pid_count: u32,
}

/// Sandbox executor interface
#[async_trait::async_trait]
pub trait SandboxExecutor: Send + Sync {
    /// Execute a skill in the sandbox
    async fn eXecute(
        &Self,
        config_path: &PathBuf,
        input: &str,
    ) -> Result<ExecutionResult, String>;

    /// Get the executor name (e.g., "nsjail", "seatbelt")
    fn name(&self) -> &str;
}

/// Platform detection
#[pyfunction]
pub fn detect_platform() -> String {
    if cfg!(target_os = "linux") {
        "linux".to_string()
    } else if cfg!(target_os = "macos") {
        "macos".to_string()
    } else {
        "unknown".to_string()
    }
}

/// Export Python module
#[pymodule]
fn omni_sandbox(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(detect_platform, m))?;

    m.add_class::<ExecutionResult>()?;
    m.add_class::<ResourceUsage>()?;

    Ok(())
}
```

### `packages/rust/crates/omni-sandbox/src/executor/mod.rs`

```rust
//! Sandbox executor implementations

use crate::{ExecutionResult, SandboxExecutor};
use async_trait::async_trait;
use std::path::PathBuf;
use tokio::process::Command;

mod nsjail;
mod seatbelt;

pub use nsjail::NsJailExecutor;
pub use seatbelt::SeatbeltExecutor;

/// Unified sandbox configuration (from NCL-exported JSON)
#[derive(Debug, Clone, serde::Deserialize)]
pub struct SandboxConfig {
    pub skill_id: String,
    pub mode: String,
    pub hostname: String,
    pub cmd: Vec<String>,
    pub env: Vec<String>,
    pub mounts: Vec<MountConfig>,
    pub rlimit_as: u64,
    pub rlimit_cpu: u64,
    pub log_level: String,
}

#[derive(Debug, Clone, serde::Deserialize)]
pub struct MountConfig {
    pub src: String,
    pub dst: String,
    pub fstype: String,
    pub rw: bool,
}

/// Execute a command with sandbox constraints
async fn execute_with_limits(
    mut cmd: Command,
    timeout_secs: u64,
    max_memory_bytes: u64,
) -> Result<ExecutionResult, String> {
    use tokio::time::timeout;
    use std::os::unix::process::CommandExt;
    use nix::sys::resource::{Resource, setrlimit, ResourceLimit};

    let start_time = std::time::Instant::now();

    // Set memory limit via RLIMIT_AS
    if max_memory_bytes > 0 {
        let soft_limit = ResourceLimit::from(max_memory_bytes as u64);
        let hard_limit = ResourceLimit::from(max_memory_bytes as u64);

        unsafe {
            cmd.pre_exec(move || {
                let _ = setrlimit(Resource::RLIMIT_AS, soft_limit, hard_limit);
                Ok(())
            });
        }
    }

    // Execute with timeout
    let child = match timeout(
        std::time::Duration::from_secs(timeout_secs),
        cmd.output(),
    ).await {
        Ok(output) => match output {
            Ok(o) => o,
            Err(e) => return Err(format!("Failed to execute: {}", e)),
        },
        Err(_) => {
            return Ok(ExecutionResult {
                success: false,
                exit_code: Some(-1),
                stdout: String::new(),
                stderr: String::from("Timeout: execution exceeded limit"),
                execution_time_ms: start_time.elapsed().as_millis() as u64,
                memory_used_bytes: None,
                error: Some(String::from("Timeout")),
            });
        }
    };

    Ok(ExecutionResult {
        success: child.status.success(),
        exit_code: child.status.code(),
        stdout: String::from_utf8_lossy(&child.stdout).to_string(),
        stderr: String::from_utf8_lossy(&child.stderr).to_string(),
        execution_time_ms: start_time.elapsed().as_millis() as u64,
        memory_used_bytes: None, // Would need cgroup/procfs for accurate measurement
        error: None,
    })
}
```

### `packages/rust/crates/omni-sandbox/src/executor/nsjail.rs`

```rust
//! nsjail executor implementation
//!
//! Executes pre-generated nsjail configurations.
//! This module does NOT parse NCL - it reads exported JSON.

use super::{execute_with_limits, SandboxConfig};
use crate::{ExecutionResult, SandboxExecutor};
use serde::Deserialize;
use std::path::PathBuf;
use std::process::Command;
use tokio::process::Command as AsyncCommand;

/// Nsjail-specific configuration (from JSON export)
#[derive(Debug, Clone, Deserialize)]
pub struct NsJailJsonConfig {
    pub name: String,
    pub mode: String,
    pub hostname: String,
    pub cmd: Vec<String>,
    pub env: Vec<String>,
    pub mount: Vec<MountJson>,
    pub rlimit_as: u64,
    pub rlimit_cpu: u64,
    pub rlimit_fsize: u64,
    pub seccomp_mode: u32,
    pub seccomp_string: Vec<String>,
    pub log_level: String,
    pub log: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct MountJson {
    pub src: String,
    pub dst: String,
    pub fstype: String,
    pub rw: bool,
}

/// nsjail executor for Linux
#[derive(Debug, Clone)]
pub struct NsJailExecutor {
    nsjail_path: PathBuf,
    default_timeout: u64,
}

impl NsJailExecutor {
    pub fn new(nsjail_path: Option<PathBuf>, default_timeout: u64) -> Self {
        Self {
            nsjail_path: nsjail_path.unwrap_or_else(|| PathBuf::from("nsjail")),
            default_timeout,
        }
    }

    /// Load configuration from NCL-exported JSON
    pub fn load_config(&self, config_path: &PathBuf) -> Result<NsJailJsonConfig, String> {
        let content = std::fs::read_to_string(config_path)
            .map_err(|e| format!("Failed to read config: {}", e))?;

        serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse config JSON: {}", e))
    }
}

#[async_trait::async_trait]
impl SandboxExecutor for NsJailExecutor {
    fn name(&self) -> &str {
        "nsjail"
    }

    async fn execute(
        &self,
        config_path: &PathBuf,
        input: &str,
    ) -> Result<ExecutionResult, String> {
        // Load pre-generated configuration
        let config = self.load_config(config_path)?;

        // Build nsjail command
        let mut cmd = AsyncCommand::new(&self.nsjail_path);

        // Mode
        cmd.arg("--mode").arg(&config.mode);

        // Hostname
        cmd.arg("--hostname").arg(&config.hostname);

        // Command
        if !config.cmd.is_empty() {
            cmd.arg("--").args(&config.cmd);
        }

        // Environment
        for env in &config.env {
            cmd.arg("--env").arg(env);
        }

        // Mounts
        for mount in &config.mount {
            let mount_spec = if mount.rw {
                format!("{}:{}:{}", mount.src, mount.dst, mount.fstype)
            } else {
                format!("{}:{}:{}:ro", mount.src, mount.dst, mount.fstype)
            };
            cmd.arg("--mount").arg(mount_spec);
        }

        // RLIMIT
        if config.rlimit_as > 0 {
            cmd.arg("--rlimit_as").arg(config.rlimit_as.to_string());
        }
        if config.rlimit_cpu > 0 {
            cmd.arg("--rlimit_cpu").arg(config.rlimit_cpu.to_string());
        }
        if config.rlimit_fsize > 0 {
            cmd.arg("--rlimit_fsize").arg(config.rlimit_fsize.to_string());
        }

        // Seccomp
        if config.seccomp_mode > 0 {
            cmd.arg("--seccomp_mode").arg(config.seccomp_mode.to_string());
            // Note: seccomp_string would need to be written to a temp file
            // and passed via --seccomp_string
        }

        // Logging
        if !config.log.is_empty() {
            cmd.arg("--log").arg(&config.log);
        }
        cmd.arg("--log_level").arg(&config.log_level);

        // Execution limits
        let timeout = self.default_timeout;
        let memory = config.rlimit_as;

        // Execute
        execute_with_limits(cmd, timeout, memory).await
    }
}
```

---

## Python Orchestration Layer

### `packages/python/core/src/omni/core/skills/sandbox.py`

```python
"""NCL-Driven Sandbox Orchestrator

This module orchestrates the NCL export and Rust execution pipeline:

1. NCL configuration is exported to JSON via nickel CLI
2. Rust executor reads JSON and performs sandboxed execution
3. Results are aggregated and returned to the skill runner
"""

import asyncio
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List

from omni.foundation.config.paths import SKILLS_DIR


class Platform(Enum):
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"


@dataclass
class SandboxResult:
    """Result from sandboxed skill execution."""
    success: bool
    exit_code: Optional[int]
    stdout: str
    stderr: str
    execution_time_ms: int
    memory_used_bytes: Optional[int]
    error: Optional[str]


class NclDrivenSandbox:
    """NCL-driven sandbox orchestrator.

    Architecture:
    - NCL generates final configuration (types, policies, validation)
    - Python exports NCL to JSON via nickel CLI
    - Rust executor reads JSON and performs sandboxed execution

    This class ONLY handles orchestration - NOT configuration logic.
    """

    def __init__(
        self,
        ncl_dir: Optional[Path] = None,
        profile_dir: Optional[Path] = None,
        nsjail_path: Optional[Path] = None,
    ):
        """Initialize the sandbox orchestrator.

        Args:
            ncl_dir: Directory containing NCL configuration modules
            profile_dir: Directory to store exported JSON profiles
            nsjail_path: Path to nsjail binary (None = use system PATH)
        """
        self.ncl_dir = ncl_dir or Path("assets/knowledge/ncl/sandbox/skill")
        self.profile_dir = profile_dir or Path.home() / ".omni/sandbox/profiles"
        self.nsjail_path = nsjail_path

        # Import Rust executor
        try:
            from omni_sandbox import NsJailExecutor
            self._nsjail_executor = NsJailExecutor(str(nsjail_path)) if nsjail_path else NsJailExecutor()
        except ImportError:
            self._nsjail_executor = None

    def _export_ncl(self, ncl_path: Path, format: str = "json") -> Dict[str, Any]:
        """Export NCL configuration to JSON.

        Args:
            ncl_path: Path to NCL source file
            format: Export format (json, yaml, toml)

        Returns:
            Parsed configuration dictionary
        """
        result = subprocess.run(
            ["nickel", "export", "--format", format, str(ncl_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(f"NCL export failed: {result.stderr}")

        return json.loads(result.stdout)

    def _get_profile_path(self, skill_id: str, platform: Platform) -> Path:
        """Get the path to a pre-exported profile.

        Args:
            skill_id: Unique skill identifier
            platform: Target platform

        Returns:
            Path to the exported configuration file
        """
        profile_dir = self.profile_dir / skill_id
        profile_dir.mkdir(parents=True, exist_ok=True)

        if platform == Platform.LINUX:
            return profile_dir / "nsjail.json"
        else:
            return profile_dir / "seatbelt.sb"

    def export_profile(
        self,
        skill_id: str,
        skill_config: Dict[str, Any],
        platform: Platform = Platform.LINUX,
    ) -> Path:
        """Export a skill sandbox profile from NCL.

        Args:
            skill_id: Unique skill identifier
            skill_config: Skill-specific configuration
            platform: Target platform

        Returns:
            Path to exported configuration file
        """
        # Build NCL configuration
        ncl_template = self._load_ncl_template(skill_config)

        # Write temporary NCL file
        ncl_path = self.profile_dir / skill_id / "config.ncl"
        ncl_path.parent.mkdir(parents=True, exist_ok=True)
        ncl_path.write_text(ncl_template)

        # Export to JSON
        config_path = self._get_profile_path(skill_id, platform)
        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(ncl_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(f"NCL export failed: {result.stderr}")

        # Write exported config
        config_path.write_text(result.stdout)

        # Clean up temp NCL
        ncl_path.unlink()

        return config_path

    def _load_ncl_template(self, skill_config: Dict[str, Any]) -> str:
        """Generate NCL configuration from skill config.

        This is where NCL configuration templates are filled in.
        """
        # Load base template
        default_ncl = self.ncl_dir / "default.ncl"
        if not default_ncl.exists():
            raise FileNotFoundError(f"Default NCL template not found: {default_ncl}")

        # Generate skill-specific NCL
        template = default_ncl.read_text()

        # Replace placeholders with skill-specific values
        for key, value in skill_config.items():
            template = template.replace(f"${{{key}}}", str(value))

        return template

    async def execute(
        self,
        skill_id: str,
        command: List[str],
        input_data: Optional[str] = None,
        timeout: int = 60,
    ) -> SandboxResult:
        """Execute a command in the sandbox.

        Args:
            skill_id: Skill identifier (determines which profile to use)
            command: Command and arguments to execute
            input_data: Optional input to pass via stdin
            timeout: Execution timeout in seconds

        Returns:
            SandboxResult with execution outcome
        """
        if self._nsjail_executor is None:
            raise RuntimeError("Rust executor not available. Install omni-sandbox package.")

        profile_path = self._get_profile_path(skill_id, Platform.LINUX)

        if not profile_path.exists():
            raise FileNotFoundError(
                f"Sandbox profile not found: {profile_path}. "
                "Run export_profile() first."
            )

        # Execute via Rust executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: asyncio.run(self._nsjail_executor.execute(profile_path, input_data or "")),
        )

        return SandboxResult(
            success=result.success,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            execution_time_ms=result.execution_time_ms,
            memory_used_bytes=result.memory_used_bytes,
            error=result.error,
        )

    def execute_sync(
        self,
        skill_id: str,
        command: List[str],
        input_data: Optional[str] = None,
        timeout: int = 60,
    ) -> SandboxResult:
        """Synchronous version of execute()."""
        return asyncio.run(self.execute(skill_id, command, input_data, timeout))
```

---

## Usage Examples

### Example 1: Basic Skill Sandbox

```bash
# Export a basic skill sandbox configuration
nickel export --format json \
  --override 'skill_id "my-skill"' \
  --override 'cmd ["python", "main.py"]' \
  packages/ncl/sandbox/skill/main.ncl \
  > ~/.omni/sandbox/profiles/my-skill/nsjail.json
```

### Example 2: Custom Security Profile

```nickel
# custom-skill.ncl
let default = import "assets/knowledge/ncl/sandbox/skill/default.ncl" in

default.make_default_config "secure-skill" & {
  seccomp_level = "strict",
  network_policy = "deny",
  max_memory_mb = 128,
  cmd = ["python", "analyze.py"],
}
```

### Example 3: Python Integration

```python
from omni.core.skills.sandbox import NclDrivenSandbox, SandboxResult

sandbox = NclDrivenSandbox()

# Export profile first
profile_path = sandbox.export_profile(
    skill_id="data-processor",
    skill_config={
        "skill_id": "data-processor",
        "max_memory_mb": 256,
        "network_policy": "deny",
        "cmd": ["python", "process.py"],
    },
)

# Execute
result = sandbox.execute_sync(
    skill_id="data-processor",
    command=["python", "process.py"],
    input_data='{"data": "..."}',
    timeout=30,
)

print(f"Success: {result.success}")
print(f"Output: {result.stdout}")
```

---

## Configuration Flow

```
1. Define skill configuration in NCL
   ↓
2. Export to JSON (nickel export --format json)
   ↓
3. Store in profile directory
   ~/.omni/sandbox/profiles/{skill_id}/nsjail.json
   ↓
4. Rust executor reads JSON
   (NO NCL parsing in Rust)
   ↓
5. Execute with nsjail/seatbelt
   ↓
6. Return results
```

---

## Key Design Principles

| Principle                  | Description                                                        |
| -------------------------- | ------------------------------------------------------------------ |
| **NCL-First**              | All configuration logic lives in NCL (types, validation, policies) |
| **Rust-Execution**         | Rust reads pre-computed JSON, executes without config parsing      |
| **Separation of Concerns** | NCL = what, Rust = how                                             |
| **Platform Abstraction**   | Same NCL exports to nsjail (Linux) or Seatbelt (macOS)             |
| **Type Safety**            | NCL contracts validate at export time                              |
| **Auditability**           | Exported JSON files are human-readable configuration               |

---

## File Structure

```
packages/ncl/sandbox/                    # NCL Configuration Library
├── main.ncl                            # Central export point
├── lib/                                # Base utilities
│   ├── base.ncl                        # Types, contracts
│   ├── mounts.ncl                      # Mount configurations
│   ├── rlimits.ncl                    # Resource limits
│   ├── network.ncl                    # Network policies
│   ├── seccomp.ncl                    # Syscall filters
│   └── platform.ncl                    # Platform detection
├── nsjail/                             # Linux nsjail executor
│   └── main.ncl
├── seatbelt/                           # macOS Seatbelt executor
│   └── main.ncl
└── skill/                              # Pre-built skill configs
    └── main.ncl

packages/rust/crates/omni-sandbox/
├── src/
│   ├── lib.rs                      # PyO3 module
│   ├── executor/
│   │   ├── mod.rs                  # Executor trait
│   │   ├── nsjail.rs               # nsjail implementation
│   │   └── seatbelt.rs             # Seatbelt implementation
│   ├── config/
│   │   └── mod.rs                  # JSON config parsing
│   └── monitor/
│       └── mod.rs                  # Resource monitoring
└── Cargo.toml

packages/python/core/src/omni/core/skills/
├── sandbox.py                      # NclDrivenSandbox orchestrator
└── executor.py                     # Async execution helpers
```

---

_Document Version: 1.0.0_
_Last Updated: 2026-02-08_
_Architecture: NCL-First, Rust-Execution_
