//! High-performance environment sniffer using libgit2.
//!
//! The sensory system of the Omni DevEnv.

use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::error::SnifferError;
use crate::git::scan_git_status;
use crate::context::scan_scratchpad_context;
use omni_types::EnvironmentSnapshot;

/// High-performance environment sniffer using libgit2.
/// The sensory system of the Omni DevEnv.
pub struct OmniSniffer {
    repo_path: std::path::PathBuf,
}

impl OmniSniffer {
    /// Create a new sniffer for the given repository root.
    pub fn new<P: AsRef<Path>>(root: P) -> Self {
        Self {
            repo_path: root.as_ref().to_path_buf(),
        }
    }

    /// Get Git status using libgit2 (10-50x faster than subprocess).
    ///
    /// # Errors
    ///
    /// Returns [`SnifferError`] if repository cannot be opened or scanned.
    pub fn scan_git(&self) -> Result<(String, usize, usize, Vec<String>), SnifferError> {
        scan_git_status(&self.repo_path)
    }

    /// Scan Scratchpad for active context (IO-intensive).
    pub fn scan_context(&self) -> usize {
        scan_scratchpad_context(&self.repo_path)
    }

    /// Get a complete environment snapshot with timestamp.
    ///
    /// Returns [`EnvironmentSnapshot`] containing all sensory data.
    #[must_use]
    pub fn get_snapshot(&self) -> EnvironmentSnapshot {
        let (branch, modified, staged, dirty_files) = self.scan_git().unwrap_or_else(|_| (
            "unavailable".to_string(),
            0,
            0,
            vec![],
        ));

        let context_lines = self.scan_context();

        // Get current timestamp
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);

        EnvironmentSnapshot {
            git_branch: branch,
            git_modified: modified,
            git_staged: staged,
            active_context_lines: context_lines,
            dirty_files,
            timestamp,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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
}
