//! Tests for omni-sandbox crate

use std::path::PathBuf;
use tempfile::TempDir;

#[cfg(test)]
mod tests {
    use omni_sandbox::{
        ExecutionResult, MountConfig, NsJailExecutor, SandboxConfig, SeatbeltExecutor,
        detect_platform, is_nsjail_available, is_seatbelt_available,
    };

    /// Test platform detection returns valid value
    #[test]
    fn test_detect_platform() {
        let platform = detect_platform();
        // Should be one of: linux, macos, unknown
        assert!(
            platform == "linux" || platform == "macos" || platform == "unknown",
            "Platform should be valid, got: {}",
            platform
        );
    }

    /// Test platform detection on current OS
    #[test]
    fn test_detect_platform_matches_os() {
        let platform = detect_platform();
        #[cfg(target_os = "linux")]
        assert_eq!(platform, "linux");
        #[cfg(target_os = "macos")]
        assert_eq!(platform, "macos");
    }

    /// Test nsjail availability check
    #[test]
    fn test_nsjail_availability() {
        // This test just verifies the function runs without panic
        // Actual availability depends on whether nsjail is installed
        let _result = is_nsjail_available();
    }

    /// Test seatbelt availability check (macOS only)
    #[test]
    fn test_seatbelt_availability() {
        // This test just verifies the function runs without panic
        // Actual availability depends on whether sandbox-exec is installed
        let _result = is_seatbelt_available();
    }

    /// Test SandboxConfig creation
    #[test]
    fn test_sandbox_config_creation() {
        let config = SandboxConfig {
            skill_id: "test-skill".to_string(),
            mode: "EXEC".to_string(),
            hostname: "test-container".to_string(),
            cmd: vec!["/bin/ls".to_string(), "/tmp".to_string()],
            env: vec!["PATH=/usr/bin".to_string()],
            mounts: vec![MountConfig {
                src: "/tmp".to_string(),
                dst: "/tmp".to_string(),
                fstype: "tmpfs".to_string(),
                rw: true,
            }],
            rlimit_as: 100_000_000,
            rlimit_cpu: 60,
            rlimit_fsize: 10_000_000,
            seccomp_mode: 2,
            log_level: "info".to_string(),
        };

        assert_eq!(config.skill_id, "test-skill");
        assert_eq!(config.mode, "EXEC");
        assert_eq!(config.rlimit_as, 100_000_000);
        assert!(!config.cmd.is_empty());
        assert!(!config.env.is_empty());
        assert!(!config.mounts.is_empty());
    }

    /// Test ExecutionResult creation
    #[test]
    fn test_execution_result_creation() {
        let result = ExecutionResult {
            success: true,
            exit_code: Some(0),
            stdout: "test output".to_string(),
            stderr: "".to_string(),
            execution_time_ms: 100,
            memory_used_bytes: Some(1024),
            error: None,
        };

        assert!(result.success);
        assert_eq!(result.exit_code, Some(0));
        assert_eq!(result.stdout, "test output");
        assert!(result.error.is_none());
    }

    /// Test ExecutionResult error case
    #[test]
    fn test_execution_result_error() {
        let result = ExecutionResult {
            success: false,
            exit_code: Some(1),
            stdout: "".to_string(),
            stderr: "command not found".to_string(),
            execution_time_ms: 50,
            memory_used_bytes: None,
            error: Some("Execution failed".to_string()),
        };

        assert!(!result.success);
        assert_eq!(result.exit_code, Some(1));
        assert!(result.error.is_some());
    }

    /// Test MountConfig creation
    #[test]
    fn test_mount_config_creation() {
        let mount = MountConfig {
            src: "/data".to_string(),
            dst: "/app/data".to_string(),
            fstype: "bind".to_string(),
            rw: false,
        };

        assert_eq!(mount.src, "/data");
        assert_eq!(mount.dst, "/app/data");
        assert!(!mount.rw);
    }

    /// Test NsJailExecutor creation
    #[test]
    fn test_nsjail_executor_creation() {
        let executor = NsJailExecutor::new(None, 60);
        // Verify executor was created (path should be default "nsjail")
        // We can't easily test the internal path, but we can verify no panic
        let _name = executor.name();
        assert_eq!(_name, "nsjail");
    }

    /// Test NsJailExecutor with custom path
    #[test]
    fn test_nsjail_executor_custom_path() {
        let executor = NsJailExecutor::new(Some("/custom/path/nsjail".to_string()), 120);
        assert_eq!(executor.name(), "nsjail");
    }

    /// Test SeatbeltExecutor creation
    #[test]
    fn test_seatbelt_executor_creation() {
        let executor = SeatbeltExecutor::new(60);
        let _name = executor.name();
        assert_eq!(_name, "seatbelt");
    }

    /// Test SeatbeltExecutor name
    #[test]
    fn test_seatbelt_executor_name() {
        let executor = SeatbeltExecutor::new(30);
        assert_eq!(executor.name(), "seatbelt");
    }

    /// Test that executor names are correct
    #[test]
    fn test_executor_names() {
        let nsjail = NsJailExecutor::new(None, 60);
        let seatbelt = SeatbeltExecutor::new(60);

        assert_eq!(nsjail.name(), "nsjail");
        assert_eq!(seatbelt.name(), "seatbelt");
    }

    /// Test config fields are accessible
    #[test]
    fn test_config_fields_accessible() {
        let config = SandboxConfig {
            skill_id: "field-test".to_string(),
            mode: "EXEC".to_string(),
            hostname: "test-host".to_string(),
            cmd: vec!["/bin/ls".to_string()],
            env: vec![],
            mounts: vec![],
            rlimit_as: 1000,
            rlimit_cpu: 10,
            rlimit_fsize: 500,
            seccomp_mode: 0,
            log_level: "info".to_string(),
        };

        // Verify all fields are accessible
        let _ = config.skill_id.as_str();
        let _ = config.mode.as_str();
        let _ = config.hostname.as_str();
        let _ = config.cmd.len();
        let _ = config.env.len();
        let _ = config.mounts.len();
        let _ = config.rlimit_as;
        let _ = config.rlimit_cpu;
        let _ = config.rlimit_fsize;
        let _ = config.seccomp_mode;
        let _ = config.log_level.as_str();

        assert_eq!(config.skill_id, "field-test");
    }

    /// Test that config with multiple mounts works
    #[test]
    fn test_config_multiple_mounts() {
        let mounts = [
            MountConfig {
                src: "/etc".to_string(),
                dst: "/etc".to_string(),
                fstype: "bind".to_string(),
                rw: false,
            },
            MountConfig {
                src: "/usr/lib".to_string(),
                dst: "/usr/lib".to_string(),
                fstype: "bind".to_string(),
                rw: false,
            },
            MountConfig {
                src: "/tmp".to_string(),
                dst: "/tmp".to_string(),
                fstype: "tmpfs".to_string(),
                rw: true,
            },
        ];

        assert_eq!(mounts.len(), 3);

        // First mount should be read-only
        assert!(!mounts[0].rw);
        // Last mount should be writable
        assert!(mounts[2].rw);
    }
}

/// Test file operations (mock tests for CI)
#[test]
fn test_temp_dir_creation() {
    let temp_dir = TempDir::new().expect("should create temp dir");
    let path = temp_dir.path();
    assert!(path.exists());
}

/// Test PathBuf operations
#[test]
fn test_pathbuf_operations() {
    let mut path = PathBuf::new();
    path.push("/usr");
    path.push("bin");
    path.push("ls");

    assert_eq!(path.to_string_lossy(), "/usr/bin/ls");
}
