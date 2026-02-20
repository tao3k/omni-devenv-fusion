//! Seatbelt executor implementation
//!
//! Executes SBPL profiles on macOS via sandbox-exec.
//! This module reads pre-generated SBPL profiles and executes them.

use pyo3::prelude::*;
use std::path::Path;
use tokio::process::Command as AsyncCommand;

use super::ExecutionResult;
use super::SandboxExecutor;
use super::millis_to_u64;

/// Seatbelt executor for macOS
#[pyclass]
#[derive(Debug, Clone)]
pub struct SeatbeltExecutor;

#[pymethods]
impl SeatbeltExecutor {
    #[new]
    #[pyo3(signature = (default_timeout=60))]
    /// Create a new `SeatbeltExecutor`.
    #[must_use]
    pub fn new(default_timeout: u64) -> Self {
        let _ = default_timeout;
        Self
    }

    /// Get executor name
    #[allow(clippy::unused_self)]
    #[must_use]
    pub fn name(&self) -> &'static str {
        "seatbelt"
    }
}

impl SeatbeltExecutor {
    /// Build sandbox-exec command from SBPL content
    fn build_command(profile_path: &Path, cmd_vec: &[String]) -> AsyncCommand {
        let mut cmd = AsyncCommand::new("sandbox-exec");
        cmd.arg("-f").arg(profile_path);

        if !cmd_vec.is_empty() {
            cmd.arg("--").args(cmd_vec);
        }

        cmd
    }
}

#[async_trait::async_trait]
impl SandboxExecutor for SeatbeltExecutor {
    fn name(&self) -> &'static str {
        "seatbelt"
    }

    async fn execute(&self, profile_path: &Path, input: &str) -> Result<ExecutionResult, String> {
        // Parse optional command from input
        let cmd_vec: Vec<String> = if input.is_empty() {
            vec!["/bin/pwd".to_string()]
        } else {
            // Input could be JSON with command
            match serde_json::from_str::<serde_json::Value>(input) {
                Ok(json) => {
                    if let Some(cmd_arr) = json.get("cmd").and_then(|c| c.as_array()) {
                        cmd_arr
                            .iter()
                            .filter_map(|c| c.as_str().map(String::from))
                            .collect()
                    } else {
                        vec!["/bin/pwd".to_string()]
                    }
                }
                Err(_) => {
                    // Treat input as shell command
                    vec!["/bin/bash".to_string(), "-c".to_string(), input.to_string()]
                }
            }
        };

        // Build and execute command
        let mut command = Self::build_command(profile_path, &cmd_vec);

        // Note: sandbox-exec on macOS doesn't support stdin input in the same way
        // We execute without stdin pipe for simplicity

        let start_time = std::time::Instant::now();

        match command.output().await {
            Ok(output) => {
                let elapsed = start_time.elapsed();
                Ok(ExecutionResult {
                    success: output.status.success(),
                    exit_code: output.status.code(),
                    stdout: String::from_utf8_lossy(&output.stdout).to_string(),
                    stderr: String::from_utf8_lossy(&output.stderr).to_string(),
                    execution_time_ms: millis_to_u64(elapsed.as_millis()),
                    memory_used_bytes: None,
                    error: None,
                })
            }
            Err(e) => Ok(ExecutionResult {
                success: false,
                exit_code: None,
                stdout: String::new(),
                stderr: String::new(),
                execution_time_ms: millis_to_u64(start_time.elapsed().as_millis()),
                memory_used_bytes: None,
                error: Some(format!("Failed to execute: {e}")),
            }),
        }
    }
}
