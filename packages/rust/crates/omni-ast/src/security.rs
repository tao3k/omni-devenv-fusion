//! Security Scanner - AST-based security analysis for harvested skills
//!
//! This module provides static analysis to detect potentially dangerous
//! code patterns in auto-generated skills before they are promoted.
//!
//! ## Security Rules
//!
//! - Forbidden imports: `os`, `subprocess`, `socket`, `eval`, `exec`
//! - Dangerous patterns: dynamic code execution, shell commands
//!
//! ## Usage
//!
//! ```rust
//! use omni_ast::{SecurityScanner, SecurityViolation};
//!
//! let scanner = SecurityScanner::new();
//! match scanner.scan("import os") {
//!     Ok(()) => println!("Code is safe"),
//!     Err(violation) => println!("Security issue: {}", violation.description),
//! }
//! ```

use std::collections::HashSet;

/// Security violation detected during AST analysis
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SecurityViolation {
    /// Rule identifier (e.g., "SEC-IMPORT-001")
    pub rule_id: String,
    /// Human-readable description
    pub description: String,
    /// Line number where violation was found
    pub line: usize,
    /// Code snippet showing the violation
    pub snippet: String,
}

/// Security Scanner Configuration
#[derive(Debug, Clone)]
pub struct SecurityConfig {
    /// Forbidden import modules
    pub forbidden_imports: HashSet<&'static str>,
    /// Forbidden function calls
    pub forbidden_calls: HashSet<&'static str>,
    /// Maximum nesting depth to detect complex obfuscation
    pub max_nesting_depth: usize,
}

impl Default for SecurityConfig {
    fn default() -> Self {
        Self {
            forbidden_imports: HashSet::from([
                "os",              // File/system operations
                "subprocess",      // Shell execution
                "socket",          // Network operations
                "ctypes",          // Dynamic library calls
                "threading",       // Multithreading (potential backdoor)
                "multiprocessing", // Multi-process
            ]),
            forbidden_calls: HashSet::from([
                "eval",       // Dynamic code execution
                "exec",       // Dynamic code execution
                "execfile",   // Python 2 file execution
                "compile",    // Code compilation
                "open",       // Direct file access (bypass filesystem tools)
                "__import__", // Dynamic import
            ]),
            max_nesting_depth: 5,
        }
    }
}

/// SecurityScanner - AST-based security analysis
///
/// Uses ast-grep for pattern matching and custom analysis
/// to detect dangerous code patterns in Python skills.
#[derive(Debug, Clone)]
pub struct SecurityScanner {
    config: SecurityConfig,
}

impl SecurityScanner {
    /// Create a new scanner with default security rules
    pub fn new() -> Self {
        Self {
            config: SecurityConfig::default(),
        }
    }

    /// Create a scanner with custom configuration
    pub fn with_config(config: SecurityConfig) -> Self {
        Self { config }
    }

    /// Scan code for security violations
    ///
    /// Returns Ok(()) if code passes all security checks.
    /// Returns Err(SecurityViolation) if a violation is found.
    pub fn scan(&self, code: &str) -> Result<(), SecurityViolation> {
        // Check for forbidden imports using pattern matching
        if let Err(v) = self.check_forbidden_imports(code) {
            return Err(v);
        }

        // Check for dangerous function calls
        if let Err(v) = self.check_forbidden_calls(code) {
            return Err(v);
        }

        // Check for suspicious patterns
        if let Err(v) = self.check_suspicious_patterns(code) {
            return Err(v);
        }

        Ok(())
    }

    /// Scan and return all violations (non-fail-fast)
    pub fn scan_all(&self, code: &str) -> Vec<SecurityViolation> {
        let mut violations = Vec::new();

        violations.extend(self.check_forbidden_imports_all(code));
        violations.extend(self.check_forbidden_calls_all(code));
        violations.extend(self.check_suspicious_patterns_all(code));

        violations
    }

    /// Check for forbidden imports and return all violations
    fn check_forbidden_imports_all(&self, code: &str) -> Vec<SecurityViolation> {
        use crate::scan;
        let mut violations = Vec::new();

        for forbidden in &self.config.forbidden_imports {
            // Check: `import <forbidden>`
            let pattern = format!("import {}", forbidden);
            if let Ok(matches) = scan(code, &pattern, crate::Lang::Python) {
                if let Some(first_match) = matches.first() {
                    let (line, snippet) = self.extract_line_info(code, first_match.start);
                    violations.push(SecurityViolation {
                        rule_id: format!(
                            "SEC-IMPORT-{:03}",
                            self.config
                                .forbidden_imports
                                .iter()
                                .position(|&x| x == *forbidden)
                                .unwrap_or(0)
                                + 1
                        ),
                        description: format!(
                            "Forbidden import: '{}' is not allowed in skills",
                            forbidden
                        ),
                        line,
                        snippet,
                    });
                }
            }

            // Check: `from <forbidden> import ...`
            let pattern = format!("from {} import", forbidden);
            if let Ok(matches) = scan(code, &pattern, crate::Lang::Python) {
                if let Some(first_match) = matches.first() {
                    let (line, snippet) = self.extract_line_info(code, first_match.start);
                    violations.push(SecurityViolation {
                        rule_id: format!(
                            "SEC-IMPORT-{:03}",
                            self.config
                                .forbidden_imports
                                .iter()
                                .position(|&x| x == *forbidden)
                                .unwrap_or(0)
                                + 1
                        ),
                        description: format!(
                            "Forbidden import from: '{}' is not allowed",
                            forbidden
                        ),
                        line,
                        snippet,
                    });
                }
            }
        }

        violations
    }

    /// Check for dangerous function calls and return all violations
    fn check_forbidden_calls_all(&self, code: &str) -> Vec<SecurityViolation> {
        use crate::scan;
        let mut violations = Vec::new();

        for forbidden in &self.config.forbidden_calls {
            let pattern = format!("{}($ARGS)", forbidden);
            if let Ok(matches) = scan(code, &pattern, crate::Lang::Python) {
                if let Some(first_match) = matches.first() {
                    let (line, snippet) = self.extract_line_info(code, first_match.start);
                    violations.push(SecurityViolation {
                        rule_id: format!(
                            "SEC-CALL-{:03}",
                            self.config
                                .forbidden_calls
                                .iter()
                                .position(|&x| x == *forbidden)
                                .unwrap_or(0)
                                + 1
                        ),
                        description: format!("Dangerous call: '{}()' is not allowed", forbidden),
                        line,
                        snippet,
                    });
                }
            }
        }

        violations
    }

    /// Check for suspicious patterns and return all violations
    fn check_suspicious_patterns_all(&self, code: &str) -> Vec<SecurityViolation> {
        use crate::scan;
        let mut violations = Vec::new();

        let suspicious = [
            ("eval(...)", "Dynamic code execution via eval()"),
            ("exec(...)", "Dynamic code execution via exec()"),
            ("getattr(...)", "Dynamic attribute access via getattr()"),
            ("setattr(...)", "Dynamic attribute setting via setattr()"),
            ("globals()", "Access to globals()"),
            ("locals()", "Access to locals()"),
        ];

        for (pattern, description) in suspicious {
            if let Ok(matches) = scan(code, pattern, crate::Lang::Python) {
                if let Some(first_match) = matches.first() {
                    let (line, snippet) = self.extract_line_info(code, first_match.start);
                    violations.push(SecurityViolation {
                        rule_id: "SEC-PATTERN-001".to_string(),
                        description: description.to_string(),
                        line,
                        snippet,
                    });
                }
            }
        }

        violations
    }

    /// Check for forbidden imports (first violation only)
    fn check_forbidden_imports(&self, code: &str) -> Result<(), SecurityViolation> {
        let violations = self.check_forbidden_imports_all(code);
        if let Some(v) = violations.into_iter().next() {
            return Err(v);
        }
        Ok(())
    }

    /// Check for dangerous function calls (first violation only)
    fn check_forbidden_calls(&self, code: &str) -> Result<(), SecurityViolation> {
        let violations = self.check_forbidden_calls_all(code);
        if let Some(v) = violations.into_iter().next() {
            return Err(v);
        }
        Ok(())
    }

    /// Check for suspicious patterns (first violation only)
    fn check_suspicious_patterns(&self, code: &str) -> Result<(), SecurityViolation> {
        let violations = self.check_suspicious_patterns_all(code);
        if let Some(v) = violations.into_iter().next() {
            return Err(v);
        }
        Ok(())
    }

    /// Extract line number and code snippet from byte position
    ///
    /// Uses the match's byte offset from ast-grep to accurately locate
    /// the violation in the source code.
    fn extract_line_info(&self, code: &str, byte_pos: usize) -> (usize, String) {
        // Count lines up to the byte position
        let line_number = code[..byte_pos.min(code.len())].lines().count();

        // Extract the line containing the match (unused, kept for future debugging)
        let _line = code[..byte_pos.min(code.len())]
            .rsplitn(2, '\n')
            .last()
            .unwrap_or("");

        // Extract the full line from the original string
        let full_line_start =
            if let Some(newline_pos) = code[..byte_pos.min(code.len())].rfind('\n') {
                newline_pos + 1
            } else {
                0
            };

        let full_line = if full_line_start < code.len() {
            if let Some(newline_pos2) = code[full_line_start..].find('\n') {
                &code[full_line_start..full_line_start + newline_pos2]
            } else {
                &code[full_line_start..]
            }
        } else {
            ""
        };

        // Truncate snippet to 80 characters for readability
        let snippet = full_line.chars().take(80).collect();

        (line_number, snippet)
    }
}

impl Default for SecurityScanner {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scanner_allows_safe_code() {
        let scanner = SecurityScanner::new();
        let safe_code = r#"
def hello(name: str) -> str:
    return f"Hello, {name}!"

class MyClass:
    def method(self):
        pass
"#;
        assert!(scanner.scan(safe_code).is_ok());
    }

    #[test]
    fn test_scanner_detects_forbidden_import() {
        let scanner = SecurityScanner::new();
        let dangerous_code = r#"
import os
def hello():
    pass
"#;
        let result = scanner.scan(dangerous_code);
        assert!(result.is_err());
        assert!(result.unwrap_err().description.contains("os"));
    }

    #[test]
    fn test_scanner_detects_dangerous_call() {
        let scanner = SecurityScanner::new();
        let dangerous_code = r#"
def execute():
    eval("1 + 1")
"#;
        let result = scanner.scan(dangerous_code);
        assert!(result.is_err());
        assert!(result.unwrap_err().description.contains("eval"));
    }

    #[test]
    fn test_scanner_detects_subprocess() {
        let scanner = SecurityScanner::new();
        let dangerous_code = r#"
import subprocess
subprocess.run(["ls"])
"#;
        let result = scanner.scan(dangerous_code);
        assert!(result.is_err());
    }

    #[test]
    fn test_scan_all_returns_multiple_violations() {
        let scanner = SecurityScanner::new();
        let code = r#"
import os
import subprocess
eval("x")
exec("y")
"#;
        let violations = scanner.scan_all(code);
        // scan_all collects all violations (non-fail-fast)
        // Expecting: 2 import violations + 2 call violations = 4
        assert!(
            violations.len() >= 3,
            "Expected at least 3 violations, got {}",
            violations.len()
        );
    }
}
