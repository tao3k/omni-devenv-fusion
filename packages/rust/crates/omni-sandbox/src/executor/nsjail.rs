//! nsjail executor implementation
//!
//! Executes pre-generated nsjail configurations.
//! This module does NOT parse NCL - it reads exported JSON.

use pyo3::prelude::*;
use serde::Deserialize;
use std::path::{Path, PathBuf};
use tokio::process::Command as AsyncCommand;

use super::ExecutionResult;
use super::SandboxExecutor;
use super::execute_with_limits;

/// Nsjail-specific configuration (from JSON export)
#[allow(clippy::struct_excessive_bools)]
#[derive(Debug, Clone, Deserialize)]
pub struct NsJailJsonConfig {
    pub name: String,
    pub mode: String,
    pub hostname: String,
    pub cmd: Vec<String>,
    pub env: Vec<String>,
    #[serde(default)]
    pub mount: Vec<MountJson>,
    #[serde(default)]
    pub rlimit_as: u64,
    #[serde(default)]
    pub rlimit_cpu: u64,
    #[serde(default)]
    pub rlimit_fsize: u64,
    #[serde(default)]
    pub rlimit_core: u64,
    #[serde(default)]
    pub rlimit_nofile: u64,
    #[serde(default)]
    pub rlimit_nproc: u64,
    #[serde(default)]
    pub rlimit_stack: u64,
    #[serde(default)]
    pub rlimit_cpu_type: String,
    #[serde(default)]
    pub seccomp_mode: u32,
    #[serde(default)]
    pub seccomp_string: Vec<String>,
    pub log_level: String,
    #[serde(default)]
    pub log: String,
    #[serde(default)]
    pub clone_newnet: bool,
    #[serde(default)]
    pub clone_newuser: bool,
    #[serde(default)]
    pub clone_newpid: bool,
    #[serde(default)]
    pub clone_newns: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct MountJson {
    pub src: String,
    pub dst: String,
    pub fstype: String,
    pub rw: bool,
}

/// nsjail executor for Linux
#[pyclass]
#[derive(Debug, Clone)]
pub struct NsJailExecutor {
    nsjail_path: PathBuf,
    default_timeout: u64,
}

#[pymethods]
impl NsJailExecutor {
    #[new]
    #[pyo3(signature = (nsjail_path=None, default_timeout=60))]
    /// Create a new `NsJailExecutor`.
    pub fn new(nsjail_path: Option<String>, default_timeout: u64) -> Self {
        let path = nsjail_path.map_or_else(|| PathBuf::from("nsjail"), PathBuf::from);

        Self {
            nsjail_path: path,
            default_timeout,
        }
    }

    /// Get executor name
    #[allow(clippy::unused_self)]
    #[must_use]
    pub fn name(&self) -> &'static str {
        "nsjail"
    }
}

impl NsJailExecutor {
    /// Load configuration from NCL-exported JSON
    ///
    /// # Errors
    ///
    /// Returns an error if the configuration file cannot be read or parsed as JSON.
    pub fn load_config(config_path: &Path) -> Result<NsJailJsonConfig, String> {
        let content = std::fs::read_to_string(config_path)
            .map_err(|e| format!("Failed to read config: {e}"))?;

        serde_json::from_str(&content).map_err(|e| format!("Failed to parse config JSON: {e}"))
    }
}

#[async_trait::async_trait]
impl SandboxExecutor for NsJailExecutor {
    fn name(&self) -> &'static str {
        "nsjail"
    }

    async fn execute(&self, config_path: &Path, _input: &str) -> Result<ExecutionResult, String> {
        // Load pre-generated configuration
        let config = Self::load_config(config_path)?;

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
            cmd.arg("--rlimit_fsize")
                .arg(config.rlimit_fsize.to_string());
        }
        if config.rlimit_core > 0 {
            cmd.arg("--rlimit_core").arg(config.rlimit_core.to_string());
        }
        if config.rlimit_nofile > 0 {
            cmd.arg("--rlimit_nofile")
                .arg(config.rlimit_nofile.to_string());
        }
        if config.rlimit_nproc > 0 {
            cmd.arg("--rlimit_nproc")
                .arg(config.rlimit_nproc.to_string());
        }
        if config.rlimit_stack > 0 {
            cmd.arg("--rlimit_stack")
                .arg(config.rlimit_stack.to_string());
        }

        // Seccomp
        if config.seccomp_mode > 0 {
            cmd.arg("--seccomp_mode")
                .arg(config.seccomp_mode.to_string());
        }

        // Network namespaces
        if config.clone_newnet {
            cmd.arg("--clone_newnet");
        }
        if config.clone_newuser {
            cmd.arg("--clone_newuser");
        }
        if config.clone_newpid {
            cmd.arg("--clone_newpid");
        }
        if config.clone_newns {
            cmd.arg("--clone_newns");
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
