//! omni-security - Security Scanner & Sandbox for Omni `DevEnv`
//!
//! ## Modules
//!
//! - `security`: Secret scanning and permission gatekeeper
//! - `sandbox`: Isolated execution environment for harvested skills
//!
//! ## Features
//!
//! - O(n) linear-time regex matching via `RegexSet`
//! - Pre-compiled patterns at startup (Lazy static)
//! - Zero-copy scanning for large files
//! - Fail-fast on first detected secret
//! - Docker/NsJail sandboxing for safe test execution
//!
//! Patterns follow ODF-REP Security Standards.

mod sandbox;

pub use sandbox::{SandboxConfig, SandboxError, SandboxMode, SandboxResult, SandboxRunner};

use regex::RegexSet;
use serde::Serialize;
use std::sync::LazyLock;

/// Security violation detected during scan
#[derive(Debug, Clone, Serialize)]
pub struct SecurityViolation {
    /// Rule identifier (e.g., `AWS_ACCESS_KEY`)
    pub rule_id: String,
    /// Human-readable description of the violation
    pub description: String,
    /// Redacted snippet showing context
    pub snippet: String,
}

static SECRET_PATTERNS: LazyLock<RegexSet> = LazyLock::new(|| {
    match RegexSet::new([
        r"AKIA[0-9A-Z]{16}",                    // AWS Access Key ID
        r"(?i)sk_(test|live)_[0-9a-zA-Z]{24}",  // Stripe Secret Key (test or live)
        r"xox[baprs]-([0-9a-zA-Z\-]{10,48})",   // Slack Token (allows hyphens in token)
        r"-----BEGIN [A-Z ]+ PRIVATE KEY-----", // PEM Private Key
        r#"(?i)(api_key|access_token|secret)\s*[:=]\s*["'][A-Za-z0-9_=-]{16,}["']"#, // Generic API Key
    ]) {
        Ok(set) => set,
        Err(err) => panic!("invalid regex pattern in security scanner: {err}"),
    }
});

static PATTERN_NAMES: &[&str] = &[
    "AWS Access Key",
    "Stripe Secret Key",
    "Slack Token",
    "PEM Private Key",
    "Generic High-Entropy Secret",
];

/// `SecretScanner` - High-performance secret detection using `RegexSet`
///
/// Uses `RegexSet` for O(n) scanning regardless of pattern count.
/// Patterns are compiled once at startup via Lazy static.
pub struct SecretScanner;

impl SecretScanner {
    /// Scan content for secrets (Fail-fast on first match)
    ///
    /// Returns None if content is clean, Some(SecurityViolation) if secrets found.
    pub fn scan(content: &str) -> Option<SecurityViolation> {
        // O(n) matching - single pass through content
        let matches = SECRET_PATTERNS.matches(content);

        if let Some(idx) = matches.iter().next() {
            let description = PATTERN_NAMES
                .get(idx)
                .copied()
                .unwrap_or("Unknown Secret")
                .to_string();

            return Some(SecurityViolation {
                rule_id: format!("SEC-{:03}", idx + 1),
                description,
                snippet: "[REDACTED]".to_string(),
            });
        }
        None
    }

    /// Scan and return all violations (non-fail-fast)
    pub fn scan_all(content: &str) -> Vec<SecurityViolation> {
        let matches = SECRET_PATTERNS.matches(content);
        let mut violations = Vec::new();

        for idx in &matches {
            let description = PATTERN_NAMES
                .get(idx)
                .copied()
                .unwrap_or("Unknown Secret")
                .to_string();

            violations.push(SecurityViolation {
                rule_id: format!("SEC-{:03}", idx + 1),
                description,
                snippet: "[REDACTED]".to_string(),
            });
        }
        violations
    }

    /// Check if content contains any secrets (boolean check only)
    pub fn contains_secrets(content: &str) -> bool {
        SECRET_PATTERNS.is_match(content)
    }
}

// =============================================================================
// Permission Gatekeeper - Access Control for Skills
// =============================================================================

/// `PermissionGatekeeper` - Zero Trust Access Control
///
/// Validates skill tool calls against declared permissions.
///
/// Permission Format:
/// - Exact: "filesystem:read" allows only "filesystem:read"
/// - Wildcard category: "filesystem:*" allows any "filesystem:*" tool
/// - Admin: "*" allows everything
pub struct PermissionGatekeeper;

impl PermissionGatekeeper {
    /// Check if a tool execution is allowed by the given permissions.
    ///
    /// `tool_name`: Full tool name (e.g., `filesystem.read_file`).
    /// `permissions`: Permission patterns (e.g., [`filesystem:*`]).
    ///
    /// Returns `true` when at least one permission pattern matches the tool.
    #[must_use]
    pub fn check(tool_name: &str, permissions: &[String]) -> bool {
        for pattern in permissions {
            if Self::matches_pattern(tool_name, pattern) {
                return true;
            }
        }
        false
    }

    fn matches_pattern(tool: &str, pattern: &str) -> bool {
        // Admin permission allows everything
        if pattern == "*" {
            return true;
        }

        // Handle wildcard patterns
        // "filesystem:*" should match "filesystem.read_file"
        if let Some(prefix) = pattern.strip_suffix(":*") {
            let standardized_prefix = prefix.replace(':', ".");
            return tool.starts_with(&standardized_prefix);
        }

        if let Some(prefix) = pattern.strip_suffix(".*") {
            return tool.starts_with(prefix);
        }

        // Normalize separators for comparison
        let normalized_tool = tool.replace(':', ".");
        let normalized_pattern = pattern.replace(':', ".");

        normalized_tool == normalized_pattern
    }
}
