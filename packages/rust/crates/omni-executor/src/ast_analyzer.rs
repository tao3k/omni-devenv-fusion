//! AST-based Semantic Analyzer for Shell Commands.
//!
//! Uses ast-grep (tree-sitter) to parse and analyze shell commands:
//! - Security analysis (dangerous patterns)
//! - Variable taint tracking
//! - Command classification (read/write)
//! - Intent extraction

use std::collections::HashSet;
use std::path::PathBuf;

use serde::Serialize;

// Use ast-grep's language support directly
use ast_grep_core::Doc;
use ast_grep_core::tree_sitter::{StrDoc, TsPre};
use ast_grep_language::Bash;

/// Analysis result of a shell command.
#[derive(Debug, Clone, Serialize)]
pub struct CommandAnalysis {
    /// Whether the command is safe to execute.
    pub is_safe: bool,
    /// Whether the command has side effects (mutation).
    pub is_mutation: bool,
    /// Detected variables in the command.
    pub variables: Vec<VariableInfo>,
    /// Detected file paths in the command.
    pub file_paths: Vec<PathBuf>,
    /// Detected command name.
    pub command_name: Option<String>,
    /// Security violations found.
    pub violations: Vec<SecurityViolation>,
    /// AST fingerprint for caching.
    pub fingerprint: String,
}

/// Variable information extracted from AST.
#[derive(Debug, Clone, Serialize)]
pub struct VariableInfo {
    /// Variable name as parsed from the command.
    pub name: String,
    /// Optional resolved value when available.
    pub value: Option<String>,
    /// Whether this variable may include untrusted input.
    pub is_tainted: bool,
}

/// Security violation detected during analysis.
#[derive(Debug, Clone, Serialize)]
pub struct SecurityViolation {
    /// Severity assigned to this violation.
    pub severity: ViolationSeverity,
    /// Stable rule identifier.
    pub rule: String,
    /// Human-readable description for logs and diagnostics.
    pub message: String,
    /// AST node kind where the violation was detected.
    pub node_kind: String,
}

/// Severity levels for command security checks.
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub enum ViolationSeverity {
    /// Immediately reject command execution.
    Blocked,
    /// Allow execution but report a warning.
    Warning,
    /// Informational finding for diagnostics only.
    Info,
}

/// Shell command analyzer using AST.
pub struct AstCommandAnalyzer {
    /// Dangerous command patterns (high severity).
    _dangerous_commands: HashSet<&'static str>,
    /// Mutation indicators.
    mutation_keywords: HashSet<&'static str>,
}

impl Default for AstCommandAnalyzer {
    fn default() -> Self {
        Self {
            _dangerous_commands: HashSet::from(["rm", "mkfs", "dd", "chmod", "chown"]),
            mutation_keywords: HashSet::from([
                "rm", "mv", "cp", "save", "touch", "mkdir", "chmod", "chown", "echo", "print",
                "write", "tee", "sed", "awk",
            ]),
        }
    }
}

impl AstCommandAnalyzer {
    /// Create a new analyzer.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Analyze a shell command using AST.
    #[must_use]
    pub fn analyze(&self, cmd: &str) -> CommandAnalysis {
        // Parse the command into AST
        let doc = match StrDoc::<Bash>::try_new(cmd, Bash) {
            Ok(doc) => doc,
            Err(e) => {
                return CommandAnalysis {
                    is_safe: false,
                    is_mutation: Self::classify_by_keywords(cmd),
                    variables: vec![],
                    file_paths: vec![],
                    command_name: None,
                    violations: vec![SecurityViolation {
                        severity: ViolationSeverity::Warning,
                        rule: "PARSE_ERROR".to_string(),
                        message: format!("Failed to parse command: {e}"),
                        node_kind: "root".to_string(),
                    }],
                    fingerprint: hash_command(cmd),
                };
            }
        };

        let source = doc.get_source();

        let mut variables = HashSet::new();
        let mut file_paths = HashSet::new();
        let mut command_name = None;
        let mut violations = vec![];

        // Use TsPre for pre-order traversal of tree-sitter nodes
        let root_node = doc.tree.root_node();
        for node in TsPre::new(&root_node) {
            let kind = node.kind();

            // Get node text for analysis
            let node_text = match node.utf8_text(source.as_bytes()) {
                Ok(text) => text.to_string(),
                Err(_) => continue,
            };

            // Extract command name from first word
            if command_name.is_none() && kind == "word" {
                command_name = Some(node_text.clone());
            }

            // Extract variables ($VAR, ${VAR})
            if kind == "variable_name" || kind == "simple_expansion" {
                variables.insert(node_text.clone());
            }

            // Extract command substitutions
            if kind == "command_substitution" {
                variables.insert("COMMAND_SUBS".to_string());
            }

            // Extract file paths from strings
            if kind == "string" {
                let text = node_text.trim_matches('"').trim_matches('\'');
                if text.starts_with('/') || text.starts_with("./") || text.starts_with("../") {
                    file_paths.insert(PathBuf::from(text.to_string()));
                }
            }

            // Check for dangerous patterns
            Self::check_node_danger(kind, &node_text, &mut violations);
        }

        // Classify as mutation if command matches
        let is_mutation = if let Some(ref cmd_name) = command_name {
            self.mutation_keywords.contains(cmd_name.as_str())
        } else {
            Self::classify_by_keywords(cmd)
        };

        // Final safety check
        let is_safe = violations
            .iter()
            .all(|v| v.severity != ViolationSeverity::Blocked);

        CommandAnalysis {
            is_safe,
            is_mutation,
            variables: variables
                .into_iter()
                .map(|name| VariableInfo {
                    name: name.clone(),
                    value: None,
                    is_tainted: name.starts_with('$') || name.starts_with("COMMAND"),
                })
                .collect(),
            file_paths: file_paths.into_iter().collect(),
            command_name,
            violations,
            fingerprint: hash_command(cmd),
        }
    }

    /// Check a node for dangerous patterns.
    fn check_node_danger(kind: &str, text: &str, violations: &mut Vec<SecurityViolation>) {
        // Check for fork bomb
        if kind == "function_definition" && text.contains(":|:&") {
            violations.push(SecurityViolation {
                severity: ViolationSeverity::Blocked,
                rule: "FORK_BOMB".to_string(),
                message: "Fork bomb detected".to_string(),
                node_kind: kind.to_string(),
            });
        }

        // Check for dangerous redirections
        if kind == "redirect" && (text.contains("> /etc/") || text.contains("> /dev/")) {
            violations.push(SecurityViolation {
                severity: ViolationSeverity::Blocked,
                rule: "DANGEROUS_REDIRECT".to_string(),
                message: "Dangerous redirection to system directory".to_string(),
                node_kind: kind.to_string(),
            });
        }

        // Check for rm -rf patterns
        if text.contains("rm") && text.contains("-rf") && text.contains('/') {
            violations.push(SecurityViolation {
                severity: ViolationSeverity::Blocked,
                rule: "RM_RF_ROOT".to_string(),
                message: "rm -rf / detected".to_string(),
                node_kind: kind.to_string(),
            });
        }
    }

    /// Classify command by keyword (fallback when AST parsing fails).
    fn classify_by_keywords(cmd: &str) -> bool {
        let cmd_lower = cmd.to_lowercase();
        let mutation_keywords = ["rm", "mv", "cp", "save", "touch", "mkdir"];
        for keyword in &mutation_keywords {
            if cmd_lower.starts_with(keyword) {
                return true;
            }
        }
        false
    }
}

/// Hash command for caching purposes.
fn hash_command(cmd: &str) -> String {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};

    let mut hasher = DefaultHasher::new();
    cmd.hash(&mut hasher);
    format!("{:x}", hasher.finish())
}
