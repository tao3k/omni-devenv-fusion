//! Skill Structure - Canonical structure from settings.yaml.
//!
//! This module defines `SkillStructure` and `StructureItem` which represent
//! the canonical skill structure as defined in `settings.yaml` under
//! `skills.architecture.structure`.

use serde::{Deserialize, Serialize};
use std::path::Path;

// =============================================================================
// Structure Item
// =============================================================================

/// A single file or directory in the skill structure.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StructureItem {
    /// Relative path from skill directory
    pub path: String,
    /// Description of the item
    #[serde(default)]
    pub description: String,
    /// Type: "file" or "dir"
    #[serde(default)]
    pub item_type: String,
}

// =============================================================================
// Skill Structure
// =============================================================================

/// Represents the canonical skill structure as defined in
/// `settings.yaml` under `skills.architecture.structure`.
///
/// Defines which files and directories should be scanned for each skill.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SkillStructure {
    /// Required files (e.g., SKILL.md, tools.py)
    pub required: Vec<StructureItem>,
    /// Default files/directories (scripts/, templates/, etc.)
    pub default: Vec<StructureItem>,
    /// Optional items (templates/, etc.)
    #[serde(default)]
    pub optional: Vec<StructureItem>,
}

impl Default for SkillStructure {
    fn default() -> Self {
        // Default structure matching settings.yaml
        Self {
            required: vec![StructureItem {
                path: "SKILL.md".to_string(),
                description: "Skill metadata (YAML frontmatter) and system prompts".to_string(),
                item_type: "file".to_string(),
            }],
            default: vec![
                StructureItem {
                    path: "scripts/".to_string(),
                    description: "Standalone executables (Python workflows, state management)"
                        .to_string(),
                    item_type: "dir".to_string(),
                },
                StructureItem {
                    path: "templates/".to_string(),
                    description: "Jinja2 templates for skill output".to_string(),
                    item_type: "dir".to_string(),
                },
                StructureItem {
                    path: "references/".to_string(),
                    description: "Markdown documentation for RAG ingestion".to_string(),
                    item_type: "dir".to_string(),
                },
                StructureItem {
                    path: "assets/".to_string(),
                    description: "Static resources, templates, guides".to_string(),
                    item_type: "dir".to_string(),
                },
                StructureItem {
                    path: "data/".to_string(),
                    description: "Data files (JSON, CSV, etc.)".to_string(),
                    item_type: "dir".to_string(),
                },
                StructureItem {
                    path: "tests/".to_string(),
                    description: "Pytest tests for this skill".to_string(),
                    item_type: "dir".to_string(),
                },
            ],
            optional: vec![],
        }
    }
}

impl SkillStructure {
    /// Create the default skill structure.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Get all directories to scan for tools.
    #[must_use]
    pub fn script_dirs(&self) -> Vec<&str> {
        self.default
            .iter()
            .filter(|i| i.item_type == "dir")
            .map(|i| i.path.trim_end_matches('/'))
            .collect()
    }

    /// Check if a path is a required file.
    pub fn is_required_file(&self, path: &Path) -> bool {
        let path_str = path.to_string_lossy();
        self.required
            .iter()
            .any(|i| i.item_type == "file" && i.path == path_str)
    }

    /// Get the required file paths.
    #[must_use]
    pub fn required_files(&self) -> Vec<&str> {
        self.required
            .iter()
            .filter(|i| i.item_type == "file")
            .map(|i| i.path.as_str())
            .collect()
    }

    /// Get directories to scan for scripts.
    #[must_use]
    pub fn script_directories(&self) -> Vec<&str> {
        self.default
            .iter()
            .filter(|i| i.item_type == "dir")
            .map(|i| i.path.trim_end_matches('/'))
            .collect()
    }
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_skill_structure_default() {
        let structure = SkillStructure::default();
        assert!(structure.required.iter().any(|i| i.path == "SKILL.md"));
        assert!(structure.default.iter().any(|i| i.path == "scripts/"));
        assert!(structure.default.iter().any(|i| i.path == "templates/"));
    }

    #[test]
    fn test_skill_structure_script_directories() {
        let structure = SkillStructure::default();
        let dirs = structure.script_directories();
        assert!(dirs.contains(&"scripts"));
        assert!(dirs.contains(&"templates"));
        assert!(dirs.contains(&"references"));
    }

    #[test]
    fn test_skill_structure_required_files() {
        let structure = SkillStructure::default();
        let files = structure.required_files();
        assert!(files.contains(&"SKILL.md"));
    }
}
