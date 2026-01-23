//! Tests for sniffer module - environment sniffing.

use omni_types::EnvironmentSnapshot;

#[test]
fn test_snapshot_rendering() {
    let snapshot = EnvironmentSnapshot {
        git_branch: "main".to_string(),
        git_modified: 3,
        git_staged: 1,
        active_context_lines: 42,
        dirty_files: vec!["src/main.rs".to_string(), "Cargo.toml".to_string()],
        timestamp: 0.0,
    };

    let prompt = snapshot.to_prompt_string();
    assert!(prompt.contains("[LIVE ENVIRONMENT STATE]"));
    assert!(prompt.contains("Branch: main"));
    assert!(prompt.contains("Modified: 3"));
}
