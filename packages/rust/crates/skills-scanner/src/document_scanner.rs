//! Document Scanner - Scans non-script directories for inventory.
//!
//! This module provides scanners for:
//! - `DocumentScanner`: Scans templates/, references/, assets/, data/, tests/
//! - Returns file inventory with metadata from settings.yaml
//!
//! # Usage
//!
//! ```ignore
//! use skills_scanner::{DocumentScanner, SkillScanner, SkillStructure};
//!
//! let doc_scanner = DocumentScanner::new();
//! let skill_scanner = SkillScanner::new();
//! let structure = SkillStructure::default();
//!
//! // Get file inventory for a skill
//! let inventory = doc_scanner.scan_skill_inventory(skill_path, skill_name, &structure);
//! ```

use std::fs;
use std::path::Path;

use hex;
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

use crate::skill_metadata::SkillStructure;

/// A scanned file entry.
#[derive(Debug, Clone)]
pub struct FileEntry {
    /// Relative path from skill (e.g., "scripts/commit.py")
    pub relative_path: String,
    /// File name (e.g., "commit.py")
    pub file_name: String,
    /// File extension (e.g., "py", "md", "j2")
    pub file_type: String,
    /// Description from settings.yaml (e.g., "Standalone executables")
    pub description: String,
    /// SHA256 hash of file content
    pub file_hash: String,
    /// File size in bytes
    pub file_size: u64,
}

impl FileEntry {
    /// Create a new file entry.
    #[must_use]
    pub fn new(
        relative_path: String,
        file_name: String,
        file_type: String,
        description: String,
        file_hash: String,
        file_size: u64,
    ) -> Self {
        Self {
            relative_path,
            file_name,
            file_type,
            description,
            file_hash,
            file_size,
        }
    }
}

/// Inventory result for a single directory.
#[derive(Debug, Clone)]
pub struct DirectoryInventory {
    /// Directory name (e.g., "scripts", "templates")
    pub dir_name: String,
    /// Description from settings.yaml
    pub description: String,
    /// Files in this directory
    pub files: Vec<FileEntry>,
    /// Total file count
    pub file_count: usize,
    /// Total size in bytes
    pub total_size: u64,
}

impl DirectoryInventory {
    /// Create a new directory inventory.
    #[must_use]
    pub fn new(dir_name: String, description: String) -> Self {
        Self {
            dir_name,
            description,
            files: Vec::new(),
            file_count: 0,
            total_size: 0,
        }
    }
}

/// Complete inventory for a skill.
#[derive(Debug, Clone)]
pub struct SkillInventory {
    /// Skill name
    pub skill_name: String,
    /// Directory inventories
    pub directories: Vec<DirectoryInventory>,
    /// Total file count across all directories
    pub total_files: usize,
    /// Total size in bytes
    pub total_size: u64,
}

impl Default for SkillInventory {
    fn default() -> Self {
        Self {
            skill_name: String::new(),
            directories: Vec::new(),
            total_files: 0,
            total_size: 0,
        }
    }
}

/// Document Scanner - Scans non-script directories for inventory.
#[derive(Debug)]
pub struct DocumentScanner;

impl DocumentScanner {
    /// Create a new document scanner.
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    /// Scan a skill directory and return inventory of all document directories.
    pub fn scan_skill_inventory(
        &self,
        skill_path: &Path,
        skill_name: &str,
        structure: &SkillStructure,
    ) -> SkillInventory {
        let mut inventory = SkillInventory {
            skill_name: skill_name.to_string(),
            directories: Vec::new(),
            total_files: 0,
            total_size: 0,
        };

        // Get directories from structure
        let script_dirs = structure.script_directories();

        // Create a map of dir_name -> description from structure
        let dir_descriptions: std::collections::HashMap<String, String> = structure
            .default
            .iter()
            .filter(|item| item.item_type == "dir")
            .map(|item| {
                let dir_name = item.path.trim_end_matches('/').to_string();
                (dir_name.clone(), item.description.clone())
            })
            .collect();

        for dir_name in script_dirs {
            // Skip scripts - those are handled by ScriptScanner
            if dir_name == "scripts" {
                continue;
            }

            let dir_path = skill_path.join(dir_name);
            if !dir_path.exists() || !dir_path.is_dir() {
                continue;
            }

            let description = dir_descriptions
                .get(dir_name)
                .cloned()
                .unwrap_or_else(|| String::from("Custom directory"));

            let mut dir_inventory = DirectoryInventory::new(dir_name.to_string(), description);

            // Scan files in this directory
            for entry in WalkDir::new(&dir_path).into_iter().filter_map(|e| e.ok()) {
                let path = entry.path();
                if path.is_dir() {
                    continue;
                }

                // Get relative path from skill
                let relative_path = path
                    .strip_prefix(skill_path)
                    .ok()
                    .and_then(|p| Some(p.to_string_lossy().to_string()))
                    .unwrap_or_else(|| path.to_string_lossy().to_string());

                let file_name = path
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or_default()
                    .to_string();

                let file_type = path
                    .extension()
                    .and_then(|e| e.to_str())
                    .unwrap_or("unknown")
                    .to_string();

                // Compute file hash and size
                let metadata = match fs::metadata(path) {
                    Ok(m) => m,
                    Err(_) => continue,
                };

                let file_size = metadata.len();

                let content = match fs::read(path) {
                    Ok(c) => c,
                    Err(_) => continue,
                };

                let mut hasher = Sha256::new();
                hasher.update(&content);
                let file_hash = hex::encode(hasher.finalize());

                let file_entry = FileEntry::new(
                    relative_path,
                    file_name,
                    file_type,
                    String::new(), // Individual files don't have descriptions
                    file_hash,
                    file_size,
                );

                dir_inventory.files.push(file_entry);
                dir_inventory.total_size += file_size;
            }

            if !dir_inventory.files.is_empty() {
                // Extract values BEFORE moving dir_inventory
                dir_inventory.file_count = dir_inventory.files.len();
                let file_count = dir_inventory.files.len();
                let dir_size = dir_inventory.total_size;
                inventory.directories.push(dir_inventory);
                inventory.total_files += file_count;
                inventory.total_size += dir_size;
            }
        }

        inventory
    }

    /// Scan all skills and return combined inventory.
    pub fn scan_all_skills(
        &self,
        base_path: &Path,
        structure: &SkillStructure,
    ) -> Vec<SkillInventory> {
        let mut inventories = Vec::new();

        if !base_path.exists() {
            return inventories;
        }

        let entries = match fs::read_dir(base_path) {
            Ok(entries) => entries,
            Err(_) => return inventories,
        };

        for entry in entries {
            let entry = match entry {
                Ok(entry) => entry,
                Err(_) => continue,
            };
            let path = entry.path();

            if !path.is_dir() {
                continue;
            }

            let skill_name = path
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or_default()
                .to_string();

            if skill_name.starts_with('.') || skill_name.starts_with('_') {
                continue;
            }

            let inventory = self.scan_skill_inventory(&path, &skill_name, structure);
            if !inventory.directories.is_empty() {
                inventories.push(inventory);
            }
        }

        inventories
    }
}

impl Default for DocumentScanner {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use std::io::Write;
    use tempfile::TempDir;

    #[test]
    fn test_scan_templates_directory() {
        let temp_dir = TempDir::new().unwrap();
        let skill_path = temp_dir.path().join("git");
        let templates_dir = skill_path.join("templates");
        std::fs::create_dir_all(&templates_dir).unwrap();

        // Create template files
        let tmpl1 = r#"Hello {{ name }}"#;
        let tmpl_file1 = templates_dir.join("greeting.j2");
        let mut file = File::create(&tmpl_file1).unwrap();
        file.write_all(tmpl1.as_bytes()).unwrap();

        let structure = SkillStructure::default();
        let scanner = DocumentScanner::new();
        let inventory = scanner.scan_skill_inventory(&skill_path, "git", &structure);

        // Should have templates directory
        let tmpl_inv = inventory
            .directories
            .iter()
            .find(|d| d.dir_name == "templates");
        assert!(tmpl_inv.is_some(), "templates directory not found");
        assert_eq!(tmpl_inv.unwrap().file_count, 1);
    }

    #[test]
    fn test_scan_references_directory() {
        let temp_dir = TempDir::new().unwrap();
        let skill_path = temp_dir.path().join("git");
        let refs_dir = skill_path.join("references");
        std::fs::create_dir_all(&refs_dir).unwrap();

        let ref_content = "# Smart Commit Workflow\n\nSome content.";
        let ref_file = refs_dir.join("smart-commit-workflow.md");
        let mut file = File::create(&ref_file).unwrap();
        file.write_all(ref_content.as_bytes()).unwrap();

        let structure = SkillStructure::default();
        let scanner = DocumentScanner::new();
        let inventory = scanner.scan_skill_inventory(&skill_path, "git", &structure);

        let refs_inv = inventory
            .directories
            .iter()
            .find(|d| d.dir_name == "references");
        assert!(refs_inv.is_some(), "references directory not found");
        assert_eq!(refs_inv.unwrap().file_count, 1);
        assert_eq!(refs_inv.unwrap().files[0].file_type, "md");
    }

    #[test]
    fn test_scan_skips_scripts() {
        let temp_dir = TempDir::new().unwrap();
        let skill_path = temp_dir.path().join("git");
        let scripts_dir = skill_path.join("scripts");
        let templates_dir = skill_path.join("templates");
        std::fs::create_dir_all(&scripts_dir).unwrap();
        std::fs::create_dir_all(&templates_dir).unwrap();

        // Create files in both directories
        let _ = std::fs::write(scripts_dir.join("test.py"), "def test(): pass");
        let _ = std::fs::write(templates_dir.join("test.j2"), "{{ test }}");

        let structure = SkillStructure::default();
        let scanner = DocumentScanner::new();
        let inventory = scanner.scan_skill_inventory(&skill_path, "git", &structure);

        // Should only have templates, not scripts
        assert!(
            !inventory
                .directories
                .iter()
                .any(|d| d.dir_name == "scripts")
        );
        assert!(
            inventory
                .directories
                .iter()
                .any(|d| d.dir_name == "templates")
        );
    }

    #[test]
    fn test_scan_empty_directories() {
        let temp_dir = TempDir::new().unwrap();
        let git_dir = temp_dir.path().join("git");
        std::fs::create_dir_all(&git_dir).unwrap();

        // Only create SKILL.md, no other directories
        let _ = std::fs::write(git_dir.join("SKILL.md"), "# Git Skill");

        let structure = SkillStructure::default();
        let scanner = DocumentScanner::new();
        let inventory = scanner.scan_skill_inventory(&git_dir, "git", &structure);

        // No document directories with files
        assert!(inventory.directories.is_empty());
    }

    #[test]
    fn test_document_scanner_new() {
        let _scanner = DocumentScanner::new();
        assert!(true);
    }

    #[test]
    fn test_file_entry_new() {
        let entry = FileEntry::new(
            "templates/greeting.j2".to_string(),
            "greeting.j2".to_string(),
            "j2".to_string(),
            "Jinja2 template".to_string(),
            "abc123".to_string(),
            100,
        );
        assert_eq!(entry.relative_path, "templates/greeting.j2");
        assert_eq!(entry.file_type, "j2");
        assert_eq!(entry.file_size, 100);
    }

    #[test]
    fn test_directory_inventory_new() {
        let inv = DirectoryInventory::new("templates".to_string(), "Jinja2 templates".to_string());
        assert_eq!(inv.dir_name, "templates");
        assert_eq!(inv.description, "Jinja2 templates");
        assert_eq!(inv.file_count, 0);
    }

    #[test]
    fn test_skill_inventory_default() {
        let inv = SkillInventory::default();
        assert!(inv.skill_name.is_empty());
        assert!(inv.directories.is_empty());
        assert_eq!(inv.total_files, 0);
    }
}
