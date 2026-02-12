//! Sandbox executor implementations
//!
//! Executes pre-generated sandbox configurations.
//! This module does NOT parse NCL - it reads exported JSON.

use pyo3::prelude::*;
use serde::Deserialize;
use std::path::Path;
use std::time::Instant;
use tokio::process::Command;

/// Unified sandbox configuration (from NCL-exported JSON)
#[pyclass]
#[derive(Debug, Clone, Deserialize)]
pub struct SandboxConfig {
    /// Unique skill identifier
    #[pyo3(get)]
    pub skill_id: String,

    /// Execution mode: "EXEC" or "ONCE"
    #[pyo3(get)]
    pub mode: String,

    /// Container hostname
    #[pyo3(get)]
    pub hostname: String,

    /// Command to execute
    #[pyo3(get)]
    pub cmd: Vec<String>,

    /// Environment variables
    #[pyo3(get)]
    pub env: Vec<String>,

    /// Mount configurations
    #[pyo3(get)]
    pub mounts: Vec<MountConfig>,

    /// Max memory in bytes
    #[pyo3(get)]
    pub rlimit_as: u64,

    /// Max CPU seconds
    #[pyo3(get)]
    pub rlimit_cpu: u64,

    /// Max file size in bytes
    #[pyo3(get)]
    pub rlimit_fsize: u64,

    /// Seccomp mode (0=disabled, 2=enabled)
    #[pyo3(get)]
    pub seccomp_mode: u32,

    /// Log level
    #[pyo3(get)]
    pub log_level: String,
}

#[pymethods]
impl SandboxConfig {
    #[new]
    #[allow(clippy::too_many_arguments)]
    fn new(
        skill_id: String,
        mode: String,
        hostname: String,
        cmd: Vec<String>,
        env: Vec<String>,
        mounts: Vec<MountConfig>,
        rlimit_as: u64,
        rlimit_cpu: u64,
        rlimit_fsize: u64,
        seccomp_mode: u32,
        log_level: String,
    ) -> Self {
        SandboxConfig {
            skill_id,
            mode,
            hostname,
            cmd,
            env,
            mounts,
            rlimit_as,
            rlimit_cpu,
            rlimit_fsize,
            seccomp_mode,
            log_level,
        }
    }
}

/// Mount configuration
#[pyclass]
#[derive(Debug, Clone, Deserialize)]
pub struct MountConfig {
    /// Source path
    #[pyo3(get)]
    pub src: String,

    /// Destination path
    #[pyo3(get)]
    pub dst: String,

    /// Filesystem type
    #[pyo3(get)]
    pub fstype: String,

    /// Read-write access
    #[pyo3(get)]
    pub rw: bool,
}

#[pymethods]
impl MountConfig {
    #[new]
    fn new(src: String, dst: String, fstype: String, rw: bool) -> Self {
        MountConfig {
            src,
            dst,
            fstype,
            rw,
        }
    }
}

/// Execution result returned to Python
#[pyclass]
#[derive(Debug, Clone)]
pub struct ExecutionResult {
    /// Whether execution succeeded
    #[pyo3(get)]
    pub success: bool,

    /// Process exit code
    #[pyo3(get)]
    pub exit_code: Option<i32>,

    /// Standard output
    #[pyo3(get)]
    pub stdout: String,

    /// Standard error
    #[pyo3(get)]
    pub stderr: String,

    /// Execution time in milliseconds
    #[pyo3(get)]
    pub execution_time_ms: u64,

    /// Memory used in bytes
    #[pyo3(get)]
    pub memory_used_bytes: Option<u64>,

    /// Error message if failed
    #[pyo3(get)]
    pub error: Option<String>,
}

#[pymethods]
impl ExecutionResult {
    #[new]
    fn new(
        success: bool,
        exit_code: Option<i32>,
        stdout: String,
        stderr: String,
        execution_time_ms: u64,
        memory_used_bytes: Option<u64>,
        error: Option<String>,
    ) -> Self {
        ExecutionResult {
            success,
            exit_code,
            stdout,
            stderr,
            execution_time_ms,
            memory_used_bytes,
            error,
        }
    }
}

/// Sandbox executor trait - unified interface for all sandbox backends
#[async_trait::async_trait]
pub trait SandboxExecutor: Send + Sync {
    /// Execute a skill in the sandbox
    async fn execute(&self, config_path: &Path, input: &str) -> Result<ExecutionResult, String>;

    /// Get the executor name (e.g., "nsjail", "seatbelt")
    fn name(&self) -> &str;
}

/// Execute a command with resource limits
async fn execute_with_limits(
    mut cmd: Command,
    timeout_secs: u64,
    _max_memory_bytes: u64,
) -> Result<ExecutionResult, String> {
    use tokio::time::timeout;

    let start_time = Instant::now();

    // Execute with timeout
    match timeout(std::time::Duration::from_secs(timeout_secs), cmd.output()).await {
        Ok(output) => match output {
            Ok(o) => {
                let elapsed = start_time.elapsed();
                Ok(ExecutionResult {
                    success: o.status.success(),
                    exit_code: o.status.code(),
                    stdout: String::from_utf8_lossy(&o.stdout).to_string(),
                    stderr: String::from_utf8_lossy(&o.stderr).to_string(),
                    execution_time_ms: elapsed.as_millis() as u64,
                    memory_used_bytes: None,
                    error: None,
                })
            }
            Err(e) => Ok(ExecutionResult {
                success: false,
                exit_code: None,
                stdout: String::new(),
                stderr: String::new(),
                execution_time_ms: start_time.elapsed().as_millis() as u64,
                memory_used_bytes: None,
                error: Some(format!("Failed to execute: {}", e)),
            }),
        },
        Err(_) => Ok(ExecutionResult {
            success: false,
            exit_code: Some(-1),
            stdout: String::new(),
            stderr: String::from("Timeout: execution exceeded limit"),
            execution_time_ms: start_time.elapsed().as_millis() as u64,
            memory_used_bytes: None,
            error: Some(String::from("Timeout")),
        }),
    }
}

mod nsjail;
mod seatbelt;

pub use nsjail::NsJailExecutor;
pub use seatbelt::SeatbeltExecutor;
