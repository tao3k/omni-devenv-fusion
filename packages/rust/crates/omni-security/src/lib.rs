#![allow(clippy::doc_markdown)]

//! omni-security - High-Performance Secret Scanning for Omni DevEnv
//!
//! Features:
//! - O(n) linear-time regex matching via RegexSet
//! - Pre-compiled patterns at startup (Lazy static)
//! - Zero-copy scanning for large files
//! - Fail-fast on first detected secret
//!
//! Patterns follow ODF-REP Security Standards.

use once_cell::sync::Lazy;
use regex::RegexSet;
use serde::Serialize;

/// Security violation detected during scan
#[derive(Debug, Clone, Serialize)]
pub struct SecurityViolation {
    /// Rule identifier (e.g., "AWS_ACCESS_KEY")
    pub rule_id: String,
    /// Human-readable description of the violation
    pub description: String,
    /// Redacted snippet showing context
    pub snippet: String,
}

static SECRET_PATTERNS: Lazy<RegexSet> = Lazy::new(|| {
    RegexSet::new([
        r"AKIA[0-9A-Z]{16}",                    // AWS Access Key ID
        r"(?i)sk_(test|live)_[0-9a-zA-Z]{24}",  // Stripe Secret Key (test or live)
        r"xox[baprs]-([0-9a-zA-Z\-]{10,48})",   // Slack Token (allows hyphens in token)
        r"-----BEGIN [A-Z ]+ PRIVATE KEY-----", // PEM Private Key
        r#"(?i)(api_key|access_token|secret)\s*[:=]\s*["'][A-Za-z0-9_=-]{16,}["']"#, // Generic API Key
    ])
    .expect("Failed to compile security patterns")
});

static PATTERN_NAMES: &[&str] = &[
    "AWS Access Key",
    "Stripe Secret Key",
    "Slack Token",
    "PEM Private Key",
    "Generic High-Entropy Secret",
];

/// SecretScanner - High-performance secret detection using RegexSet
///
/// Uses RegexSet for O(n) scanning regardless of pattern count.
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

        for idx in matches.iter() {
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_aws_detection() {
        let text = "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE";
        let violation = SecretScanner::scan(text).expect("Should detect AWS Key");
        assert_eq!(violation.description, "AWS Access Key");
        assert_eq!(violation.rule_id, "SEC-001");
    }

    #[test]
    fn test_stripe_detection() {
        // Using a clearly fake/test key to avoid GitHub secret scanning false positives
        let text = "stripe_key = 'sk_test_000000000000000000000000000'";
        let violation = SecretScanner::scan(text).expect("Should detect Stripe Key");
        assert_eq!(violation.description, "Stripe Secret Key");
    }

    #[test]
    fn test_slack_detection() {
        let text = "xoxb-1234-5678-abcdefghijklmnop";
        let violation = SecretScanner::scan(text).expect("Should detect Slack Token");
        assert_eq!(violation.description, "Slack Token");
    }

    #[test]
    fn test_private_key_detection() {
        let text = "-----BEGIN RSA PRIVATE KEY-----\nMIIE...";
        let violation = SecretScanner::scan(text).expect("Should detect Private Key");
        assert_eq!(violation.description, "PEM Private Key");
    }

    #[test]
    fn test_generic_api_key() {
        let text = r#"api_key = "abcdefghijklmnopqrst""#;
        let violation = SecretScanner::scan(text).expect("Should detect Generic API Key");
        assert_eq!(violation.description, "Generic High-Entropy Secret");
    }

    #[test]
    fn test_safe_content() {
        let text = "This is a safe config file with no secrets.";
        assert!(SecretScanner::scan(text).is_none());
        assert!(!SecretScanner::contains_secrets(text));
    }

    #[test]
    fn test_scan_all() {
        // AWS key (24 chars) + Stripe key (32 chars, meets 24 char minimum)
        // Using clearly fake/test keys to avoid GitHub secret scanning false positives
        let text = "AWS: AKIAIOSFODNN7EXAMPLE and Stripe: sk_test_000000000000000000000000000";
        let violations = SecretScanner::scan_all(text);
        assert_eq!(violations.len(), 2);
    }
}

// =============================================================================
// Permission Gatekeeper - Access Control for Skills
// =============================================================================

/// PermissionGatekeeper - Zero Trust Access Control
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
    /// Args:
    ///     tool_name: Full tool name (e.g., "filesystem.read_file")
    ///     permissions: List of permission patterns (e.g., ["filesystem:*"])
    ///
    /// Returns:
    ///     True if allowed, False otherwise.
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
        let normalized_tool = tool.replace(":", ".");
        let normalized_pattern = pattern.replace(":", ".");

        normalized_tool == normalized_pattern
    }
}

#[cfg(test)]
mod permission_tests {
    use super::*;

    #[test]
    fn test_wildcard_permission() {
        let perms = vec!["filesystem:*".to_string()];
        assert!(PermissionGatekeeper::check("filesystem.read_file", &perms));
        assert!(PermissionGatekeeper::check("filesystem.write_file", &perms));
        assert!(!PermissionGatekeeper::check("git.status", &perms));
    }

    #[test]
    fn test_wildcard_with_colon_separator() {
        let perms = vec!["filesystem:*".to_string()];
        assert!(PermissionGatekeeper::check("filesystem:read", &perms));
        assert!(!PermissionGatekeeper::check("git:status", &perms));
    }

    #[test]
    fn test_exact_permission() {
        let perms = vec!["git.status".to_string()];
        assert!(PermissionGatekeeper::check("git.status", &perms));
        assert!(!PermissionGatekeeper::check("git.commit", &perms));
    }

    #[test]
    fn test_exact_permission_with_colon() {
        let perms = vec!["git:status".to_string()];
        assert!(PermissionGatekeeper::check("git.status", &perms));
        assert!(!PermissionGatekeeper::check("git.commit", &perms));
    }

    #[test]
    fn test_admin_permission() {
        let perms = vec!["*".to_string()];
        assert!(PermissionGatekeeper::check("any.thing", &perms));
        assert!(PermissionGatekeeper::check("filesystem.read", &perms));
    }

    #[test]
    fn test_empty_permissions() {
        assert!(!PermissionGatekeeper::check("filesystem.read", &[]));
        assert!(!PermissionGatekeeper::check("any.tool", &[]));
    }

    #[test]
    fn test_multiple_permissions() {
        let perms = vec!["git.status".to_string(), "filesystem:*".to_string()];
        assert!(PermissionGatekeeper::check("git.status", &perms));
        assert!(PermissionGatekeeper::check("filesystem.read", &perms));
        assert!(!PermissionGatekeeper::check("git.commit", &perms));
    }
}
