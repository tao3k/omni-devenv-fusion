//! Scratchpad context scanning.
//!
//! Scans the SCRATCHPAD.md file for active context.

use std::io::BufRead;

/// Scan scratchpad for active context lines.
///
/// Returns the number of lines in the SCRATCHPAD.md file.
#[must_use]
pub fn scan_scratchpad_context(repo_path: &std::path::Path) -> usize {
    let scratchpad = repo_path.join(".memory/active_context/SCRATCHPAD.md");
    if !scratchpad.exists() {
        return 0;
    }

    // Quick line count without loading entire file
    if let Ok(file) = std::fs::File::open(&scratchpad) {
        return std::io::BufReader::new(file).lines().count();
    }
    0
}
