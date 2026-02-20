//! Persistence helpers for atomic JSON writes.

use anyhow::{Context, Result};
use std::io::Write;
use std::path::Path;

/// Write text content atomically:
/// - ensure parent directory exists
/// - write to a temp file in the same directory
/// - fsync file + rename into place
pub(crate) fn atomic_write_text(path: &Path, content: &str) -> Result<()> {
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    std::fs::create_dir_all(parent).with_context(|| {
        format!(
            "failed to create parent directory for persistence path {}",
            path.display()
        )
    })?;

    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|name| !name.is_empty())
        .unwrap_or("state.json");
    let temp_name = format!(".{}.{}.tmp", file_name, uuid::Uuid::new_v4());
    let temp_path = parent.join(temp_name);

    let mut temp_file = std::fs::File::create(&temp_path).with_context(|| {
        format!(
            "failed to create temporary persistence file {}",
            temp_path.display()
        )
    })?;
    temp_file
        .write_all(content.as_bytes())
        .with_context(|| format!("failed to write temporary file {}", temp_path.display()))?;
    temp_file
        .sync_all()
        .with_context(|| format!("failed to fsync temporary file {}", temp_path.display()))?;

    std::fs::rename(&temp_path, path).with_context(|| {
        format!(
            "failed to rename temporary file {} to {}",
            temp_path.display(),
            path.display()
        )
    })?;

    Ok(())
}
