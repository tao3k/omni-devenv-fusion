//! Tests for command analysis serialization and types.

use omni_executor::{
    AstCommandAnalyzer, CommandAnalysis, SecurityViolation, VariableInfo, ViolationSeverity,
};
use std::path::PathBuf;

#[test]
fn test_command_analysis_serialization() {
    let analysis = CommandAnalysis {
        is_safe: true,
        is_mutation: false,
        variables: vec![VariableInfo {
            name: "TEST".to_string(),
            value: Some("value".to_string()),
            is_tainted: false,
        }],
        file_paths: vec![PathBuf::from("/tmp/test")],
        command_name: Some("echo".to_string()),
        violations: vec![SecurityViolation {
            severity: ViolationSeverity::Warning,
            rule: "TEST_RULE".to_string(),
            message: "Test message".to_string(),
            node_kind: "test".to_string(),
        }],
        fingerprint: "abc123".to_string(),
    };

    // Test that the analysis can be serialized to JSON
    let json = serde_json::to_string(&analysis).expect("Should serialize to JSON");
    assert!(json.contains("is_safe"));
    assert!(json.contains("TEST"));
    assert!(json.contains("/tmp/test"));
}

#[test]
fn test_violation_severity_levels() {
    let blocked = SecurityViolation {
        severity: ViolationSeverity::Blocked,
        rule: "DANGEROUS".to_string(),
        message: "Blocked".to_string(),
        node_kind: "test".to_string(),
    };

    let warning = SecurityViolation {
        severity: ViolationSeverity::Warning,
        rule: "WARNING".to_string(),
        message: "Warning".to_string(),
        node_kind: "test".to_string(),
    };

    let info = SecurityViolation {
        severity: ViolationSeverity::Info,
        rule: "INFO".to_string(),
        message: "Info".to_string(),
        node_kind: "test".to_string(),
    };

    // Test serialization
    let blocked_json = serde_json::to_string(&blocked).expect("Serialize blocked");
    let warning_json = serde_json::to_string(&warning).expect("Serialize warning");
    let info_json = serde_json::to_string(&info).expect("Serialize info");

    assert!(blocked_json.contains("Blocked"));
    assert!(warning_json.contains("Warning"));
    assert!(info_json.contains("Info"));
}

#[test]
fn test_variable_info_is_tainted() {
    let normal_var = VariableInfo {
        name: "NORMAL".to_string(),
        value: Some("value".to_string()),
        is_tainted: false,
    };

    let tainted_var = VariableInfo {
        name: "$DANGER".to_string(),
        value: None,
        is_tainted: true,
    };

    assert!(!normal_var.is_tainted);
    assert!(tainted_var.is_tainted);
}

#[test]
fn test_empty_analysis() {
    let analyzer = AstCommandAnalyzer::new();
    let result = analyzer.analyze("true"); // Valid shell command that does nothing

    assert!(result.is_safe);
    assert!(!result.is_mutation);
    assert!(result.variables.is_empty());
    assert!(result.file_paths.is_empty());
}

#[test]
fn test_analysis_fingerprint_format() {
    let analyzer = AstCommandAnalyzer::new();
    let result = analyzer.analyze("ls");

    // Fingerprint should be a hex string
    assert!(!result.fingerprint.is_empty());
    assert!(result.fingerprint.chars().all(|c| c.is_ascii_hexdigit()));
}
