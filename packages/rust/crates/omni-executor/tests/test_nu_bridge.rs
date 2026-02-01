//! Integration tests for Nushell system bridge.

use omni_executor::{ActionType, NuConfig, NuSystemBridge};

#[test]
fn test_new_bridge_has_default_config() {
    let bridge = NuSystemBridge::new();
    assert_eq!(bridge.config.nu_path, "nu");
    assert!(bridge.config.enable_shellcheck);
}

#[test]
fn test_bridge_with_custom_config() {
    let config = NuConfig {
        nu_path: "/usr/bin/nu".to_string(),
        enable_shellcheck: false,
        ..Default::default()
    };
    let bridge = NuSystemBridge::with_config(config);

    assert_eq!(bridge.config.nu_path, "/usr/bin/nu");
    assert!(!bridge.config.enable_shellcheck);
}

#[test]
fn test_classify_action_ls() {
    assert_eq!(NuSystemBridge::classify_action("ls"), ActionType::Observe);
    assert_eq!(
        NuSystemBridge::classify_action("ls -la"),
        ActionType::Observe
    );
}

#[test]
fn test_classify_action_cat() {
    assert_eq!(
        NuSystemBridge::classify_action("cat file.txt"),
        ActionType::Observe
    );
}

#[test]
fn test_classify_action_rm() {
    assert_eq!(
        NuSystemBridge::classify_action("rm file.txt"),
        ActionType::Mutate
    );
}

#[test]
fn test_classify_action_cp() {
    assert_eq!(
        NuSystemBridge::classify_action("cp a b"),
        ActionType::Mutate
    );
}

#[test]
fn test_classify_action_mv() {
    assert_eq!(
        NuSystemBridge::classify_action("mv old new"),
        ActionType::Mutate
    );
}

#[test]
fn test_classify_action_mkdir() {
    assert_eq!(
        NuSystemBridge::classify_action("mkdir -p dir"),
        ActionType::Mutate
    );
}

#[test]
fn test_classify_action_echo() {
    assert_eq!(
        NuSystemBridge::classify_action("echo hello"),
        ActionType::Mutate
    );
}

#[test]
fn test_classify_action_with_pipe() {
    assert_eq!(
        NuSystemBridge::classify_action("ls | grep txt"),
        ActionType::Observe
    );
    assert_eq!(
        NuSystemBridge::classify_action("cat file.txt | wc -l"),
        ActionType::Observe
    );
}

#[test]
fn test_validate_safety_allows_safe_commands() {
    let bridge = NuSystemBridge::new();

    assert!(bridge.validate_safety("ls -la").is_ok());
    assert!(bridge.validate_safety("cat config.toml").is_ok());
    assert!(bridge.validate_safety("pwd").is_ok());
    assert!(bridge.validate_safety("echo hello").is_ok());
}

#[test]
fn test_validate_safety_blocks_dangerous() {
    let bridge = NuSystemBridge::new();

    assert!(bridge.validate_safety("rm -rf /").is_err());
    assert!(bridge.validate_safety("mkfs.ext4 /dev/sda").is_err());
}

#[test]
fn test_validate_safety_blocks_fork_bomb() {
    let bridge = NuSystemBridge::new();

    assert!(bridge.validate_safety(":(){ :|:& };:").is_err());
}

#[test]
fn test_config_default_values() {
    let config = NuConfig::default();

    assert_eq!(config.nu_path, "nu");
    assert!(config.no_config);
    assert!(config.enable_shellcheck);
    assert!(config.allowed_commands.is_empty());
}

#[test]
fn test_config_with_whitelist() {
    let config = NuConfig {
        allowed_commands: vec!["ls".to_string(), "cat".to_string()],
        ..Default::default()
    };
    let bridge = NuSystemBridge::with_config(config);

    assert!(bridge.validate_safety("ls file.txt").is_ok());
    assert!(bridge.validate_safety("cat file.txt").is_ok());
    assert!(bridge.validate_safety("rm file.txt").is_err());
}

#[test]
fn test_action_type_variants() {
    assert_eq!(ActionType::Observe, ActionType::Observe);
    assert_eq!(ActionType::Mutate, ActionType::Mutate);
    assert_ne!(ActionType::Observe, ActionType::Mutate);
}
