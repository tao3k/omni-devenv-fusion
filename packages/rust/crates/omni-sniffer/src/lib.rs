#![allow(clippy::doc_markdown, clippy::uninlined_format_args)]

use std::path::Path;
use thiserror::Error;
use git2::{Repository, StatusOptions, Status};

/// Errors for `OmniSniffer` operations.
#[derive(Debug, Error)]
pub enum SnifferError {
    #[error("Failed to open git repository at {0}")]
    RepoOpen(std::path::PathBuf),

    #[error("Git repository has no head reference")]
    NoHead,

    #[error("Git status scan failed: {0}")]
    StatusScan(String),

    #[error("Failed to read scratchpad: {0}")]
    ScratchpadRead(std::path::PathBuf),
}

/// Holographic snapshot structure (Atomic Snapshot)
#[derive(Debug, serde::Serialize)]
pub struct EnvironmentSnapshot {
    pub git_branch: String,
    pub git_modified: usize,
    pub git_staged: usize,
    pub active_context_lines: usize,
    pub dirty_files: Vec<String>,
}

impl EnvironmentSnapshot {
    /// Render as human-readable prompt string (Phase 43 compatible)
    #[must_use]
    pub fn to_prompt_string(&self) -> String {
        let dirty_desc = if self.dirty_files.is_empty() {
            "Clean".to_string()
        } else {
            let count = self.dirty_files.len();
            let preview = self.dirty_files.iter().take(3).cloned().collect::<Vec<_>>().join(", ");
            if count > 3 {
                format!("{count} files ({preview}, ...)")
            } else {
                format!("{count} files ({preview})")
            }
        };

        format!(
            "[LIVE ENVIRONMENT STATE]\n\
            - Git: Branch: {} | Modified: {} | Staged: {} | Status: {}\n\
            - Active Context: {} lines in SCRATCHPAD.md",
            self.git_branch,
            self.git_modified,
            self.git_staged,
            dirty_desc,
            self.active_context_lines
        )
    }
}

pub struct OmniSniffer {
    repo_path: std::path::PathBuf,
}

impl OmniSniffer {
    pub fn new<P: AsRef<Path>>(root: P) -> Self {
        Self {
            repo_path: root.as_ref().to_path_buf(),
        }
    }

    /// Get Git status (uses libgit2, 10-50x faster than subprocess)
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

    /// Scan Scratchpad (IO-intensive, Rust advantage)
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

    /// Aggregate snapshot
    pub fn get_snapshot(&self) -> EnvironmentSnapshot {
        let (branch, modified, staged, dirty_files) = self.scan_git().unwrap_or_else(|_| (
            "unavailable".to_string(),
            0,
            0,
            vec![],
        ));

        let context_lines = self.scan_context();

        EnvironmentSnapshot {
            git_branch: branch,
            git_modified: modified,
            git_staged: staged,
            active_context_lines: context_lines,
            dirty_files,
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
        };

        let prompt = snapshot.to_prompt_string();
        assert!(prompt.contains("[LIVE ENVIRONMENT STATE]"));
        assert!(prompt.contains("Branch: main"));
        assert!(prompt.contains("Modified: 3"));
    }
}
