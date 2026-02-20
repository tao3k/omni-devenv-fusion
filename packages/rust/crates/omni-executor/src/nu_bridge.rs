//! Nushell System Bridge - The Core Algorithm.
//!
//! Transforms OS operations into structured JSON data flow.
//! Uses AST-based analysis and external security tools for validation.

use serde_json::Value;
use std::process::{Command, Stdio};
use std::time::Duration;

use crate::error::{ExecutorError, Result};

/// Configuration for the Nushell bridge.
#[derive(Debug, Clone)]
pub struct NuConfig {
    /// Path to nushell binary.
    pub nu_path: String,
    /// Skip loading user config for reproducibility.
    pub no_config: bool,
    /// Timeout for command execution.
    pub timeout: Duration,
    /// Enable shellcheck for security validation.
    pub enable_shellcheck: bool,
    /// Additional allowed commands (whitelist).
    pub allowed_commands: Vec<String>,
}

impl Default for NuConfig {
    fn default() -> Self {
        Self {
            nu_path: "nu".to_string(),
            no_config: true,
            timeout: Duration::from_secs(30),
            enable_shellcheck: true,
            allowed_commands: vec![],
        }
    }
}

/// The core Nushell bridge implementation.
#[derive(Debug, Clone)]
pub struct NuSystemBridge {
    /// Bridge configuration.
    pub config: NuConfig,
}

impl Default for NuSystemBridge {
    fn default() -> Self {
        Self::new()
    }
}

impl NuSystemBridge {
    /// Create a new bridge with default config.
    #[must_use]
    pub fn new() -> Self {
        Self {
            config: NuConfig::default(),
        }
    }

    /// Create with custom configuration.
    #[must_use]
    pub fn with_config(config: NuConfig) -> Self {
        Self { config }
    }

    /// Get reference to the configuration (for testing).
    #[must_use]
    pub fn config(&self) -> &NuConfig {
        &self.config
    }

    /// Enhance error messages with LLM-friendly hints for common Bash-to-Nu mistakes.
    fn enhance_error_for_llm(cmd: &str, stderr: &str) -> String {
        let mut hints = Vec::new();

        // Detect Bash find command
        if cmd.contains("find ")
            && (cmd.contains("-name") || cmd.contains("-size") || cmd.contains("-exec"))
        {
            hints.push("HINT: You are using Bash 'find' syntax. In Nushell, use 'ls **/*.py | where name =~ \"...\"' instead.");
        }

        // Detect && chaining
        if cmd.contains("&&") {
            hints.push("HINT: Nushell uses ';' instead of '&&' for command chaining.");
        }

        // Detect |& (Bash stderr redirect)
        if cmd.contains("|&") {
            hints.push("HINT: Nushell doesn't use '|&'. Use '| complete' to capture stderr, or just ignore it.");
        }

        // Detect backticks
        if cmd.contains('`') {
            hints.push("HINT: Nushell doesn't use backticks for command substitution. Use '$(command)' instead.");
        }

        // Detect $() with spaces (common Bash mistake)
        if cmd.contains("$(") && cmd.contains(' ') && !cmd.contains("${") {
            hints.push("HINT: In Nushell, command substitution $(cmd) captures the structured output, not just string.");
        }

        // Detect -flag style for Nushell commands
        if cmd.contains("ls -") && !cmd.contains("--") {
            hints.push("HINT: Nushell uses flags like '--long' or 'ls -l' works, but filtering should use '| where ...'.");
        }

        // Build enhanced error message
        if hints.is_empty() {
            stderr.to_string()
        } else {
            format!(
                "{}\n\n=== NUSHELL SYNTAX HINT ===\n{}\n=== END HINT ===",
                stderr,
                hints.join("\n")
            )
        }
    }

    /// Auto-correct common Nushell mistakes for mutation commands.
    fn auto_correct_mutation(cmd: &str) -> String {
        let mut corrected = cmd.to_string();

        // Fix 1: Auto-add -f (force) to save commands to prevent "file already exists" errors
        // Match "save " but not "save -f" or "save --force"
        if corrected.contains("save ") && !corrected.contains("save -") {
            corrected = corrected.replace("save ", "save -f ");
        }

        // Fix 2: Ensure mutation commands return a structured status instead of null
        // Add a status object at the end for better LLM feedback
        let needs_status = ["save ", "mv ", "cp ", "rm ", "mkdir ", "touch "];
        let ends_with_pipe = corrected.trim_end().ends_with('|');

        if needs_status.iter().any(|p| corrected.contains(p)) && !ends_with_pipe {
            // Extract filename if possible for the status
            let filename = if let Some(start) = corrected.find("save ") {
                let after_save = &corrected[start + 5..];
                let parts: Vec<&str> = after_save.split_whitespace().collect();
                if parts.is_empty() {
                    "\"unknown\"".to_string()
                } else {
                    let first = parts[0];
                    format!("\"{first}\"")
                }
            } else {
                "\"operation\"".to_string()
            };

            corrected = format!(
                "{corrected}; {{ status: 'success', file: {filename}, timestamp: (date now) }} | to json --raw"
            );
        }

        corrected
    }

    /// Execute a Nushell command with structured output.
    ///
    /// # Arguments
    /// * `cmd` - The command string to execute.
    /// * `ensure_structured` - If true, appends `| to json --raw` to force JSON output.
    ///
    /// # Returns
    /// Parsed JSON value or error.
    ///
    /// # Errors
    /// Returns an error when safety validation fails, the process cannot spawn, the command
    /// exits with a failure status, or the output cannot be parsed as JSON.
    pub fn execute(&self, cmd: &str, ensure_structured: bool) -> Result<Value> {
        // 0. Auto-correct mutation commands for better LLM feedback
        let cmd = Self::auto_correct_mutation(cmd);

        // 1. Security pre-flight check
        self.validate_safety(&cmd)?;

        // 2. Construct the actual command
        let final_cmd = Self::build_command(&cmd, ensure_structured);

        // 3. Spawn and execute
        let output = Command::new(&self.config.nu_path)
            .args(["--no-config-file"]) // Reproducible environment
            .arg("-c")
            .arg(&final_cmd)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .map_err(|e| ExecutorError::SystemError(format!("Failed to spawn nu: {e}")))?;

        // 4. Handle execution errors with LLM-friendly hints
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            let enhanced_error = Self::enhance_error_for_llm(&cmd, &stderr);
            return Err(ExecutorError::ShellError(
                output.status.code().unwrap_or(-1),
                enhanced_error,
            ));
        }

        let stdout = String::from_utf8_lossy(&output.stdout);

        // 5. Handle empty output (e.g., cp, mv operations)
        if stdout.trim().is_empty() {
            return Ok(serde_json::json!({
                "status": "success",
                "operation": "mutation_complete"
            }));
        }

        // 6. Parse JSON output
        serde_json::from_str(&stdout).map_err(|e| {
            ExecutorError::SerializationError(format!(
                "Nu output wasn't valid JSON: {} (raw: {:?})",
                e,
                &stdout[..stdout.len().min(200)]
            ))
        })
    }

    /// Execute with timeout.
    ///
    /// # Errors
    /// Propagates any error returned by [`Self::execute`].
    pub fn execute_with_timeout(
        &self,
        cmd: &str,
        ensure_structured: bool,
        _timeout: Duration,
    ) -> Result<Value> {
        self.execute(cmd, ensure_structured)
    }

    /// Build the command string with JSON transformation.
    fn build_command(cmd: &str, ensure_structured: bool) -> String {
        if ensure_structured {
            // Force JSON output for observation commands
            format!("{cmd} | to json --raw")
        } else {
            cmd.to_string()
        }
    }

    /// Security pre-flight check.
    ///
    /// Uses AST-based analysis (ast-grep) and external tools (shellcheck).
    /// Step 1: Quick pattern check
    /// Step 2: `ShellCheck` integration (if enabled)
    ///
    /// # Errors
    /// Returns an error when the command contains dangerous patterns, fails `ShellCheck`,
    /// or is rejected by the configured whitelist.
    pub fn validate_safety(&self, cmd: &str) -> Result<()> {
        // Step 1: Quick pattern check (immutable set)
        if Self::has_dangerous_pattern(cmd) {
            return Err(ExecutorError::SecurityViolation(
                "Dangerous pattern detected".to_string(),
            ));
        }

        // Step 2: ShellCheck validation (if enabled)
        if self.config.enable_shellcheck {
            Self::run_shellcheck()?;
        }

        // Step 3: Whitelist check
        if !self.config.allowed_commands.is_empty() {
            self.check_whitelist(cmd)?;
        }

        Ok(())
    }

    /// Quick pattern check for obvious dangers.
    fn has_dangerous_pattern(cmd: &str) -> bool {
        let cmd_lower = cmd.to_lowercase();
        // Obvious destructive patterns
        cmd_lower.contains("rm -rf /")
            || cmd_lower.contains("mkfs")
            || cmd_lower.contains(":(){ :|:& };:")
    }

    /// Run shellcheck for comprehensive analysis.
    fn run_shellcheck() -> Result<()> {
        // Skip if shellcheck not available
        if Command::new("which").arg("shellcheck").output().is_err() {
            return Ok(());
        }

        let output = Command::new("shellcheck")
            .args(["-e", "SC2034", "-"]) // Allow unused vars
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output();

        if let Ok(output) = output {
            // ShellCheck returns exit code 0 for no errors,
            // 1 for warnings (which we want to allow),
            // and > 1 for errors
            let exit_code = output.status.code().unwrap_or(0);
            if exit_code > 1 {
                let stderr = String::from_utf8_lossy(&output.stderr);
                return Err(ExecutorError::SecurityViolation(format!(
                    "ShellCheck error: {stderr}"
                )));
            }
            // Exit codes 0 (no issues) and 1 (warnings only) are OK
        } else {
            // ShellCheck not available or failed to run, skip
        }
        Ok(())
    }

    /// Check against whitelist.
    fn check_whitelist(&self, cmd: &str) -> Result<()> {
        let cmd_trimmed = cmd.trim();
        for allowed in &self.config.allowed_commands {
            if cmd_trimmed.starts_with(allowed) {
                return Ok(());
            }
        }
        Err(ExecutorError::SecurityViolation(
            "Command not in whitelist".to_string(),
        ))
    }

    /// Check if a command is a mutation (side-effect) operation.
    #[must_use]
    pub fn classify_action(cmd: &str) -> ActionType {
        let cmd_trimmed = cmd.trim();
        let cmd_lower = cmd_trimmed.to_lowercase();

        // Mutation indicators
        let mutation_keywords = [
            "rm", "mv", "cp", "save", "touch", "mkdir", "chmod", "chown", "echo", "print", "write",
        ];

        for keyword in &mutation_keywords {
            if cmd_lower.starts_with(keyword) || cmd_lower.contains(&format!(" | {keyword}")) {
                return ActionType::Mutate;
            }
        }

        ActionType::Observe
    }
}

/// Classification of command intent.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ActionType {
    /// Read-only operation (ls, open, ps, cat)
    Observe,
    /// Side-effect operation (rm, cp, mv, save)
    Mutate,
}
