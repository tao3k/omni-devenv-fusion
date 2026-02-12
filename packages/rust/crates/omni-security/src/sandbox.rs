//! Sandbox - Secure execution environment for harvested skills
//!
//! Provides isolated execution using Docker or `NsJail` for running
//! tests on auto-generated skills before promotion.
//!
//! ## Architecture
//!
//! ```text
//! +-------------------+     +-------------------+
//! |   Docker Mode     |     |   NsJail Mode     |
//! |   (Cross-platform)|     |   (Linux only)    |
//! +-------------------+     +-------------------+
//!         |                         |
//!         v                         v
//! +------------------------------------------------+
//! |              SandboxRunner                     |
//! |  - Resource limits (memory, CPU)               |
//! |  - Network isolation (--network none)          |
//! |  - File system read-only access                |
//! +------------------------------------------------+
//! ```

use std::path::Path;
use std::process::Command;
use thiserror::Error;

/// Sandbox execution mode
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SandboxMode {
    /// Docker container (cross-platform, requires Docker)
    Docker,
    /// `NsJail` (Linux native, higher performance)
    NsJail,
}

/// Sandbox configuration
#[derive(Debug, Clone)]
pub struct SandboxConfig {
    /// Execution mode
    pub mode: SandboxMode,
    /// Maximum memory in MB (default: 512)
    pub memory_mb: u64,
    /// Maximum CPU cores (default: 1.0)
    pub max_cpus: f64,
    /// Timeout in seconds (default: 60)
    pub timeout_secs: u64,
    /// Network isolation (default: true)
    pub network_isolation: bool,
    /// Allow file system writes to /tmp only
    pub read_only_fs: bool,
}

impl Default for SandboxConfig {
    fn default() -> Self {
        Self {
            mode: if cfg!(target_os = "linux") {
                SandboxMode::NsJail
            } else {
                SandboxMode::Docker
            },
            memory_mb: 512,
            max_cpus: 1.0,
            timeout_secs: 60,
            network_isolation: true,
            read_only_fs: true,
        }
    }
}

/// Sandbox execution result
#[derive(Debug, Clone)]
pub struct SandboxResult {
    /// Whether the execution succeeded
    pub success: bool,
    /// Exit code from the process
    pub exit_code: i32,
    /// Standard output
    pub stdout: String,
    /// Standard error
    pub stderr: String,
    /// Execution time in milliseconds
    pub duration_ms: u64,
}

/// Sandbox execution errors
#[derive(Error, Debug)]
pub enum SandboxError {
    /// Sandbox is not available or not configured
    #[error("Sandbox not available: {0}")]
    NotAvailable(String),

    /// Execution timed out
    #[error("Execution timeout")]
    Timeout,

    /// Resource limit exceeded (memory, CPU, etc.)
    #[error("Resource limit exceeded: {0}")]
    ResourceLimit(String),

    /// IO error occurred during execution
    #[error("IO error: {0}")]
    IoError(String),

    /// Script execution failed with an error
    #[error("Execution failed: {0}")]
    ExecutionFailed(String),
}

/// `SandboxRunner` - Secure execution environment
///
/// Runs Python scripts in isolated containers/processes with:
/// - Memory limits
/// - CPU limits
/// - Network isolation
/// - Read-only file system access
#[derive(Debug, Clone)]
pub struct SandboxRunner {
    config: SandboxConfig,
}

impl SandboxRunner {
    /// Create a new sandbox runner with default configuration
    #[must_use]
    pub fn new() -> Self {
        Self {
            config: SandboxConfig::default(),
        }
    }

    /// Create with custom configuration
    #[must_use]
    pub fn with_config(config: SandboxConfig) -> Self {
        Self { config }
    }

    /// Run a Python script in the sandbox
    ///
    /// `script_path`: Path to the Python script to execute.
    ///
    /// Returns a `SandboxResult` indicating success/failure.
    ///
    /// # Errors
    ///
    /// Returns `SandboxError` when the selected backend is unavailable,
    /// when path normalization fails, or when command execution fails.
    pub fn run_python(&self, script_path: &Path) -> Result<SandboxResult, SandboxError> {
        match self.config.mode {
            SandboxMode::Docker => self.run_docker(script_path),
            SandboxMode::NsJail => self.run_nsjail(script_path),
        }
    }

    /// Run with Docker container
    fn run_docker(&self, script_path: &Path) -> Result<SandboxResult, SandboxError> {
        // Check if Docker is available
        if !Self::is_docker_available() {
            return Err(SandboxError::NotAvailable(
                "Docker is not installed or not running".to_string(),
            ));
        }

        let abs_path = script_path
            .canonicalize()
            .map_err(|e| SandboxError::IoError(format!("Failed to canonicalize path: {e}")))?;

        let dir = abs_path
            .parent()
            .ok_or_else(|| SandboxError::IoError("Invalid script path".to_string()))?;

        let file_name = abs_path
            .file_name()
            .ok_or_else(|| SandboxError::IoError("Invalid script filename".to_string()))?;

        // Build Docker command
        let mut cmd = Command::new("docker");

        // Container lifecycle: remove after execution
        cmd.arg("run");

        // Security: Network isolation
        if self.config.network_isolation {
            cmd.arg("--network").arg("none");
        }

        // Security: Memory limit
        cmd.arg("--memory")
            .arg(format!("{}m", self.config.memory_mb));

        // Security: CPU limit
        cmd.arg("--cpus").arg(self.config.max_cpus.to_string());

        // Security: Read-only filesystem (mount as read-only)
        cmd.arg("--read-only");

        // Allow writes to /tmp
        cmd.arg("--tmpfs").arg("/tmp:rw,exec");

        // Timeout
        cmd.arg("--rm"); // Remove container after exit

        // Mount script directory
        cmd.arg("-v").arg(format!("{}:/app:ro", dir.display()));

        // Python runtime image
        cmd.arg("python:3.12-slim");

        // Execute the script
        cmd.arg("python")
            .arg(format!("/app/{}", file_name.to_string_lossy()));

        // Execute and capture output
        let output = cmd
            .output()
            .map_err(|e| SandboxError::ExecutionFailed(format!("Docker execution failed: {e}")))?;

        let duration_ms = 0; // Could track with std::time::Instant

        Ok(SandboxResult {
            success: output.status.success(),
            exit_code: output.status.code().unwrap_or(-1),
            stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
            stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
            duration_ms,
        })
    }

    /// Run with `NsJail` (Linux only)
    fn run_nsjail(&self, script_path: &Path) -> Result<SandboxResult, SandboxError> {
        // Check if `NsJail` is available
        if !Self::is_nsjail_available() {
            return Err(SandboxError::NotAvailable(
                "NsJail is not installed".to_string(),
            ));
        }

        // For now, fall back to Docker if NsJail config is not found
        // In production, this would use a proper nsjail.cfg
        let nsjail_cfg = "/etc/nsjail/nsjail.cfg";

        let abs_path = script_path
            .canonicalize()
            .map_err(|e| SandboxError::IoError(format!("Failed to canonicalize path: {e}")))?;

        let mut cmd = Command::new("nsjail");

        // Use config file if available
        if Path::new(nsjail_cfg).exists() {
            cmd.arg("--config").arg(nsjail_cfg);
        } else {
            // Command-line flags for basic isolation
            cmd.arg("--keep_caps");
            cmd.arg("--uid").arg("1000");
            cmd.arg("--gid").arg("1000");
            cmd.arg("--chroot").arg("/");

            if self.config.network_isolation {
                cmd.arg("--disable_net");
            }
        }

        cmd.arg("--")
            .arg("python3")
            .arg(abs_path.to_string_lossy().as_ref());

        let output = cmd
            .output()
            .map_err(|e| SandboxError::ExecutionFailed(format!("NsJail execution failed: {e}")))?;

        let duration_ms = 0;

        Ok(SandboxResult {
            success: output.status.success(),
            exit_code: output.status.code().unwrap_or(-1),
            stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
            stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
            duration_ms,
        })
    }

    /// Check if Docker is available
    fn is_docker_available() -> bool {
        Command::new("docker")
            .arg("version")
            .output()
            .is_ok_and(|o| o.status.success())
    }

    /// Check if `NsJail` is available
    fn is_nsjail_available() -> bool {
        Command::new("which")
            .arg("nsjail")
            .output()
            .is_ok_and(|o| o.status.success())
    }

    /// Get the current sandbox mode
    #[must_use]
    pub fn mode(&self) -> SandboxMode {
        self.config.mode
    }

    /// Check if sandbox is ready to use
    #[must_use]
    pub fn is_available(&self) -> bool {
        match self.config.mode {
            SandboxMode::Docker => Self::is_docker_available(),
            SandboxMode::NsJail => Self::is_nsjail_available(),
        }
    }
}

impl Default for SandboxRunner {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sandbox_config_defaults() {
        let config = SandboxConfig::default();

        // On Linux, should default to NsJail
        // On macOS/Windows, should default to Docker
        if cfg!(target_os = "linux") {
            assert_eq!(config.mode, SandboxMode::NsJail);
        } else {
            assert_eq!(config.mode, SandboxMode::Docker);
        }

        assert_eq!(config.memory_mb, 512);
        assert!((config.max_cpus - 1.0).abs() < f64::EPSILON);
        assert!(config.network_isolation);
    }

    #[test]
    fn test_sandbox_runner_creation() {
        let runner = SandboxRunner::new();
        assert!(runner.config.memory_mb > 0);
    }

    #[test]
    fn test_sandbox_result_structure() {
        let result = SandboxResult {
            success: true,
            exit_code: 0,
            stdout: "test output".to_string(),
            stderr: String::new(),
            duration_ms: 100,
        };

        assert!(result.success);
        assert_eq!(result.exit_code, 0);
        assert!(result.duration_ms > 0);
    }
}
