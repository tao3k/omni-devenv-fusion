//! Security Scanner & Permission Gatekeeper
//!
//! Provides:
//! - Secret scanning to detect API keys, tokens, and sensitive data
//! - Permission validation for skill tool execution (Zero Trust)
//! - AST-based security analysis for harvested skills
//! - Sandboxed execution for testing auto-generated skills

use crate::utils::run_safe;
use omni_ast::{SecurityScanner, SecurityViolation};
use omni_security::{
    PermissionGatekeeper, SandboxConfig, SandboxMode, SandboxResult, SandboxRunner, SecretScanner,
};
use pyo3::prelude::*;

/// Scan content for secrets (AWS keys, Stripe keys, Slack tokens, etc.)
/// Returns a violation message if secrets are found, None if clean.
/// Releases GIL for CPU-intensive regex scanning.
#[pyfunction]
pub fn scan_secrets(content: &str) -> Option<String> {
    run_safe(|| {
        Python::attach(|py| {
            Ok(py.detach(|| {
                SecretScanner::scan(content).map(|v| {
                    format!(
                        "[SECURITY VIOLATION] Found {}: {}",
                        v.rule_id, v.description
                    )
                })
            }))
        })
    })
    .unwrap_or(None)
}

/// Check if content contains any secrets (boolean check only).
/// More efficient than scan_secrets when you only need a boolean result.
/// Releases GIL for CPU-intensive regex scanning.
#[pyfunction]
pub fn contains_secrets(content: &str) -> bool {
    run_safe(|| Python::attach(|py| Ok(py.detach(|| SecretScanner::contains_secrets(content)))))
        .unwrap_or(false)
}

/// Python wrapper for SecurityViolation from omni-ast
#[pyclass]
#[derive(Debug, Clone)]
pub struct PySecurityViolation {
    /// Rule identifier (e.g., "SEC-IMPORT-001")
    pub rule_id: String,
    /// Human-readable description
    pub description: String,
    /// Line number where violation was found
    pub line: usize,
    /// Code snippet showing the violation
    pub snippet: String,
}

impl From<SecurityViolation> for PySecurityViolation {
    fn from(v: SecurityViolation) -> Self {
        Self {
            rule_id: v.rule_id,
            description: v.description,
            line: v.line,
            snippet: v.snippet,
        }
    }
}

/// Scan Python code for security violations using omni-ast.
///
/// This is the Level 1 defense in the Immune System, using ast-grep
/// for high-performance pattern matching.
///
/// Args:
///     code: Python source code to scan
///
/// Returns:
///     List of (rule_id, description, line, snippet) tuples for each violation.
///     Empty list if code is safe.
#[pyfunction]
pub fn scan_code_security(code: &str) -> Vec<(String, String, usize, String)> {
    run_safe(|| {
        let scanner = SecurityScanner::new();
        let violations = scanner.scan_all(code);
        Ok(violations
            .into_iter()
            .map(|v| (v.rule_id, v.description, v.line, v.snippet))
            .collect())
    })
    .unwrap_or_default()
}

/// Quick check if code is safe (no violations).
/// More efficient than scan_code_security when you only need a boolean.
#[pyfunction]
pub fn is_code_safe(code: &str) -> bool {
    run_safe(|| {
        let scanner = SecurityScanner::new();
        Ok(scanner.scan(code).is_ok())
    })
    .unwrap_or(false)
}

/// Check if a tool execution is allowed by the given permissions.
///
/// This implements Zero Trust access control for skills.
///
/// Args:
///     tool_name: Full tool name (e.g., "filesystem.read_file")
///     permissions: List of permission patterns (e.g., ["filesystem:*", "git:status"])
///
/// Returns:
///     True if allowed, False otherwise.
///
/// Examples:
///     # Wildcard category
///     check_permission("filesystem.read_file", ["filesystem:*"]) -> True
///
///     # Exact match
///     check_permission("git.status", ["git:status"]) -> True
///
///     # No permissions (Zero Trust)
///     check_permission("any.tool", []) -> False
///
///     # Admin permission
///     check_permission("any.tool", ["*"]) -> True
#[pyfunction]
pub fn check_permission(tool_name: &str, permissions: Vec<String>) -> bool {
    run_safe(|| Ok(PermissionGatekeeper::check(tool_name, &permissions))).unwrap_or(false)
}

/// Sandbox mode enumeration for Python
#[pyclass]
#[derive(Debug, Clone)]
pub enum PySandboxMode {
    /// Docker container (cross-platform)
    Docker,
    /// NsJail (Linux native)
    NsJail,
}

impl From<SandboxMode> for PySandboxMode {
    fn from(mode: SandboxMode) -> Self {
        match mode {
            SandboxMode::Docker => PySandboxMode::Docker,
            SandboxMode::NsJail => PySandboxMode::NsJail,
        }
    }
}

impl From<PySandboxMode> for SandboxMode {
    fn from(mode: PySandboxMode) -> Self {
        match mode {
            PySandboxMode::Docker => SandboxMode::Docker,
            PySandboxMode::NsJail => SandboxMode::NsJail,
        }
    }
}

/// Sandbox execution result for Python
#[pyclass]
#[derive(Debug, Clone)]
pub struct PySandboxResult {
    /// Whether execution succeeded
    pub success: bool,
    /// Exit code
    pub exit_code: i32,
    /// Standard output
    pub stdout: String,
    /// Standard error
    pub stderr: String,
    /// Execution duration in milliseconds
    pub duration_ms: u64,
}

impl From<SandboxResult> for PySandboxResult {
    fn from(result: SandboxResult) -> Self {
        Self {
            success: result.success,
            exit_code: result.exit_code,
            stdout: result.stdout,
            stderr: result.stderr,
            duration_ms: result.duration_ms,
        }
    }
}

/// Sandbox runner for secure execution of Python scripts
#[pyclass]
#[derive(Clone)]
pub struct PySandboxRunner {
    runner: SandboxRunner,
}

#[pymethods]
impl PySandboxRunner {
    /// Create a new sandbox runner
    #[new]
    fn new() -> Self {
        Self {
            runner: SandboxRunner::new(),
        }
    }

    /// Get the current sandbox mode
    fn mode(&self) -> PySandboxMode {
        PySandboxMode::from(self.runner.mode())
    }

    /// Check if sandbox is available
    fn is_available(&self) -> bool {
        self.runner.is_available()
    }

    /// Run a Python script in the sandbox
    ///
    /// Args:
    ///     script_path: Path to the Python script
    ///
    /// Returns:
    ///     PySandboxResult with execution outcome
    fn run_python(&self, script_path: String) -> PyResult<PySandboxResult> {
        let path = std::path::Path::new(&script_path);
        match self.runner.run_python(path) {
            Ok(result) => Ok(PySandboxResult::from(result)),
            Err(e) => Err(pyo3::exceptions::PyRuntimeError::new_err(format!(
                "Sandbox execution failed: {}",
                e
            ))),
        }
    }

    /// Run with Docker mode explicitly
    fn use_docker(&mut self) {
        let mut config = SandboxConfig::default();
        config.mode = SandboxMode::Docker;
        self.runner = SandboxRunner::with_config(config);
    }

    /// Run with NsJail mode explicitly (Linux only)
    fn use_nsjail(&mut self) {
        let mut config = SandboxConfig::default();
        config.mode = SandboxMode::NsJail;
        self.runner = SandboxRunner::with_config(config);
    }
}
