//! Git operations for the sniffer.
//!
//! Uses libgit2 for fast git operations.

use git2::{Repository, Status, StatusOptions};

use crate::error::SnifferError;

/// Scan git repository status using libgit2.
///
/// Returns tuple of (branch, modified_count, staged_count, dirty_files).
pub fn scan_git_status(
    repo_path: &std::path::Path,
) -> Result<(String, usize, usize, Vec<String>), SnifferError> {
    let repo =
        Repository::open(repo_path).map_err(|_| SnifferError::RepoOpen(repo_path.to_path_buf()))?;

    // 1. Get branch
    let head = repo.head().map_err(|_| SnifferError::NoHead)?;
    let branch = head.shorthand().unwrap_or("unknown").to_string();

    // 2. Scan status
    let mut opts = StatusOptions::new();
    opts.include_untracked(true);

    let statuses = repo
        .statuses(Some(&mut opts))
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
