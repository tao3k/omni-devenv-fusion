#![allow(clippy::doc_markdown, clippy::uninlined_format_args)]

//! High-performance environment sniffer for Omni DevEnv.
//!
//! Uses libgit2 for fast git operations and provides environment snapshots.

use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;
use git2::{Repository, StatusOptions, Status};
use omni_types::EnvironmentSnapshot;

/// Errors for `OmniSniffer` operations.
#[derive(Debug, Error)]
pub enum SnifferError {
    /// Cannot open the git repository
    #[error("Failed to open git repository at {0}")]
    RepoOpen(std::path::PathBuf),
    /// Git repository has no head (empty repo)
    #[error("Git repository has no head reference")]
    NoHead,
    /// Git status scan failed
    #[error("Git status scan failed: {0}")]
    StatusScan(String),
    /// Failed to read the scratchpad file
    #[error("Failed to read scratchpad: {0}")]
    ScratchpadRead(std::path::PathBuf),
}

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
        let repo = Repository::open(&self.repo_path)
            .map_err(|_| SnifferError::RepoOpen(self.repo_path.clone()))?;

        // 1. Get branch
        let head = repo.head().map_err(|_| SnifferError::NoHead)?;
        let branch = head
            .shorthand()
            .unwrap_or("unknown")
            .to_string();

        // 2. Scan status
        let mut opts = StatusOptions::new();
        opts.include_untracked(true);

        let statuses = repo.statuses(Some(&mut opts))
            .map_err(|e| SnifferError::StatusScan(e.to_string()))?;

        let mut modified = 0;
        let mut staged = 0;
        let mut dirty_files = Vec::new();

        for entry in statuses.iter() {
            let status = entry.status();
            let path = entry.path().unwrap_or("unknown").to_string();

            // Check Staged
            if status.contains(Status::INDEX_NEW)
                || status.contains(Status::INDEX_MODIFIED)
                || status.contains(Status::INDEX_DELETED)
            {
                staged += 1;
            }

            // Check Modified (Workdir)
            if status.contains(Status::WT_NEW)
                || status.contains(Status::WT_MODIFIED)
                || status.contains(Status::WT_DELETED)
            {
                modified += 1;
                dirty_files.push(path);
            }
        }

        Ok((branch, modified, staged, dirty_files))
    }

    /// Scan Scratchpad for active context (IO-intensive).
    pub fn scan_context(&self) -> usize {
        let scratchpad = self.repo_path.join(".memory/active_context/SCRATCHPAD.md");
        if !scratchpad.exists() {
            return 0;
        }

        // Quick line count without loading entire file
        use std::io::BufRead;
        if let Ok(file) = std::fs::File::open(&scratchpad) {
            return std::io::BufReader::new(file).lines().count();
        }
        0
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
