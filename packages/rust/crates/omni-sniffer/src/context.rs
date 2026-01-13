//! Scratchpad context scanning.
//!
//! Scans the SCRATCHPAD.md file for active context.

use std::io::BufRead;

/// Scan scratchpad for active context lines.
///
/// Returns the number of lines in the SCRATCHPAD.md file.
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

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;
    use std::fs;

    #[test]
    fn test_scan_scratchpad_nonexistent() {
        let dir = TempDir::new().unwrap();
        let lines = scan_scratchpad_context(dir.path());
        assert_eq!(lines, 0);
    }

    #[test]
    fn test_scan_scratchpad_with_content() {
        let dir = TempDir::new().unwrap();
        let scratchpad = dir.path().join(".memory/active_context/SCRATCHPAD.md");
        fs::create_dir_all(scratchpad.parent().unwrap()).unwrap();
        fs::write(&scratchpad, "Line 1\nLine 2\nLine 3").unwrap();
        let lines = scan_scratchpad_context(dir.path());
        assert_eq!(lines, 3);
    }
}
