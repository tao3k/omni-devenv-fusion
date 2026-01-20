//! Skill Scanner - Parses SKILL.md files for metadata and routing keywords.
//!
//! This module provides the `SkillScanner` struct which scans skill directories
//! and extracts metadata from SKILL.md YAML frontmatter.
//!
//! # Architecture
//!
//! Follows the skill structure defined in `settings.yaml` under `skills.architecture`:
//! - Required: `SKILL.md` - Skill metadata (YAML frontmatter) and system prompts
//! - Default: `scripts/` - Standalone executables (tools)
//!   NOTE: `tools.py` is deprecated - use `scripts/` instead
//!
//! # Example
//!
//! ```ignore
//! use skills_scanner::SkillScanner;
//!
//! let scanner = SkillScanner::new();
//! let metadatas = scanner.scan_all(PathBuf::from("assets/skills")).unwrap();
//!
//! for metadata in metadatas {
//!     println!("Skill: {} - {} keywords", metadata.skill_name, metadata.routing_keywords.len());
//! }
//! ```

use std::fs;
use std::path::{Path, PathBuf};

use serde::Deserialize;

use crate::script_scanner::ScriptScanner;
use crate::skill_metadata::{
    IndexToolEntry, ReferencePath, SkillIndexEntry, SkillMetadata, SkillStructure,
};

/// YAML frontmatter structure (inner YAML in SKILL.md).
#[derive(Debug, Deserialize, PartialEq, Default)]
struct SkillFrontmatter {
    #[serde(default)]
    name: Option<String>,
    #[serde(default)]
    version: Option<String>,
    #[serde(default)]
    description: Option<String>,
    #[serde(default)]
    routing_keywords: Option<Vec<String>>,
    #[serde(default)]
    authors: Option<Vec<String>>,
    #[serde(default)]
    intents: Option<Vec<String>>,
    #[serde(default)]
    require_refs: Option<Vec<String>>,
    #[serde(default)]
    repository: Option<String>,
}

/// Skill Scanner - Extracts metadata from SKILL.md files.
///
/// Scans skill directories to extract:
/// - Skill name, version, description
/// - `routing_keywords` for hybrid search
/// - Authors and intents
///
/// # Usage
///
/// ```ignore
/// use skills_scanner::SkillScanner;
///
/// let scanner = SkillScanner::new();
///
/// // Scan single skill
/// let metadata = scanner.scan_skill(PathBuf::from("assets/skills/writer")).unwrap();
///
/// // Scan all skills
/// let all_metadatas = scanner.scan_all(PathBuf::from("assets/skills")).unwrap();
/// ```
#[derive(Debug)]
pub struct SkillScanner {
    /// Reserved for future configuration options
    #[allow(dead_code)]
    config: (),
}

#[derive(Debug, Default)]
#[allow(dead_code)]
struct ScanConfig {
    base_path: PathBuf,
}

impl SkillScanner {
    /// Create a new skill scanner with default settings.
    #[must_use]
    pub fn new() -> Self {
        Self { config: () }
    }

    /// Get the default skill structure (from settings.yaml).
    #[must_use]
    pub fn default_structure() -> SkillStructure {
        SkillStructure::default()
    }

    /// Validate a skill directory against the canonical structure.
    ///
    /// Returns `true` if the skill has all required files.
    #[must_use]
    pub fn validate_structure(skill_path: &Path, structure: &SkillStructure) -> bool {
        if !skill_path.exists() {
            return false;
        }

        // Check that all required files exist
        for item in &structure.required {
            if item.item_type == "file" {
                let required_path = skill_path.join(&item.path);
                if !required_path.exists() {
                    log::debug!(
                        "Missing required file: {:?} for skill: {:?}",
                        item.path,
                        skill_path
                    );
                    return false;
                }
            }
        }

        true
    }

    /// Scan a single skill directory and extract its metadata.
    ///
    /// Returns `Ok(Some(metadata))` if SKILL.md is found and valid.
    /// Returns `Ok(None)` if SKILL.md is missing.
    /// Returns `Err(...)` if SKILL.md exists but cannot be parsed.
    ///
    /// # Arguments
    ///
    /// * `skill_path` - Path to the skill directory (e.g., "assets/skills/writer")
    /// * `structure` - Optional skill structure for validation (uses default if None)
    ///
    /// # Examples
    ///
    /// ```ignore
    /// let scanner = SkillScanner::new();
    /// let metadata = scanner.scan_skill(PathBuf::from("assets/skills/writer"), None).unwrap();
    ///
    /// match metadata {
    ///     Some(m) => println!("Found skill: {}", m.skill_name),
    ///     None => println!("No SKILL.md found"),
    /// }
    /// ```
    pub fn scan_skill(
        &self,
        skill_path: &Path,
        structure: Option<&SkillStructure>,
    ) -> Result<Option<SkillMetadata>, Box<dyn std::error::Error>> {
        let skill_md_path = skill_path.join("SKILL.md");

        if !skill_md_path.exists() {
            log::debug!("SKILL.md not found for skill: {:?}", skill_path);
            return Ok(None);
        }

        // Validate structure if provided
        if let Some(structure) = structure {
            if !Self::validate_structure(skill_path, structure) {
                log::warn!(
                    "Skill at {:?} does not match required structure",
                    skill_path
                );
            }
        }

        let content = fs::read_to_string(&skill_md_path)?;
        let metadata = self.parse_skill_md(&content, skill_path)?;

        log::info!(
            "Scanned skill metadata: {} (v{}) - {} keywords",
            metadata.skill_name,
            metadata.version,
            metadata.routing_keywords.len()
        );

        Ok(Some(metadata))
    }

    /// Scan all skills in a base directory.
    ///
    /// Returns a vector of skill metadata for all skills with valid SKILL.md.
    /// Skills without SKILL.md are silently skipped.
    ///
    /// # Arguments
    ///
    /// * `base_path` - Path to the skills directory (e.g., "assets/skills")
    /// * `structure` - Optional skill structure for validation (uses default if None)
    ///
    /// # Examples
    ///
    /// ```ignore
    /// let scanner = SkillScanner::new();
    /// let structure = SkillScanner::default_structure();
    /// let metadatas = scanner.scan_all(PathBuf::from("assets/skills"), Some(&structure)).unwrap();
    ///
    /// println!("Found {} skills", metadatas.len());
    /// ```
    pub fn scan_all(
        &self,
        base_path: &Path,
        structure: Option<&SkillStructure>,
    ) -> Result<Vec<SkillMetadata>, Box<dyn std::error::Error>> {
        let mut metadatas = Vec::new();

        if !base_path.exists() {
            log::warn!("Skills base directory not found: {:?}", base_path);
            return Ok(metadatas);
        }

        for entry in fs::read_dir(base_path)? {
            let entry = entry?;
            let path = entry.path();

            if path.is_dir() {
                if let Some(metadata) = self.scan_skill(&path, structure)? {
                    metadatas.push(metadata);
                }
            }
        }

        log::info!("Scanned {} skills from {:?}", metadatas.len(), base_path);
        Ok(metadatas)
    }

    /// Scan all skills and write to skill-index.json.
    ///
    /// This is a convenience method that scans all skills and writes
    /// the metadata to a JSON file for consumption by Python.
    ///
    /// # Arguments
    ///
    /// * `base_path` - Path to the skills directory (e.g., "assets/skills")
    /// * `output_path` - Path for the output JSON file
    /// * `structure` - Optional skill structure for validation (uses default if None)
    ///
    /// # Examples
    ///
    /// ```ignore
    /// let scanner = SkillScanner::new();
    /// scanner.scan_all_to_index(
    ///     PathBuf::from("assets/skills"),
    ///     PathBuf::from("assets/skills/skill-index.json"),
    ///     None
    /// ).unwrap();
    /// ```
    pub fn scan_all_to_index(
        &self,
        base_path: &Path,
        output_path: &Path,
        structure: Option<&SkillStructure>,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let metadatas = self.scan_all(base_path, structure)?;

        // Create parent directories if needed
        if let Some(parent) = output_path.parent() {
            fs::create_dir_all(parent)?;
        }

        // Write as JSON
        let json = serde_json::to_string_pretty(&metadatas)?;
        fs::write(output_path, json)?;

        log::info!(
            "Wrote skill-index.json with {} skills to {:?}",
            metadatas.len(),
            output_path
        );

        Ok(())
    }

    /// Build a full SkillIndexEntry from metadata and tools.
    ///
    /// Combines skill metadata from SKILL.md frontmatter with discovered
    /// tools from the script scanner to create a complete skill index entry.
    ///
    /// # Arguments
    ///
    /// * `metadata` - Skill metadata from SKILL.md
    /// * `tools` - Tools discovered in the skill's scripts directory
    /// * `skill_path` - Path to the skill directory
    ///
    /// # Examples
    ///
    /// ```ignore
    /// let scanner = SkillScanner::new();
    /// let script_scanner = ScriptScanner::new();
    ///
    /// let metadata = scanner.scan_skill(&skill_path, None).unwrap().unwrap();
    /// let tools = script_scanner.scan_scripts(&skill_path.join("scripts"), &metadata.skill_name, &metadata.routing_keywords).unwrap();
    ///
    /// let entry = scanner.build_index_entry(metadata, &tools, &skill_path);
    /// ```
    pub fn build_index_entry(
        &self,
        metadata: SkillMetadata,
        tools: &[crate::skill_metadata::ToolRecord],
        _skill_path: &Path,
    ) -> SkillIndexEntry {
        let path = format!(r#""assets/skills/{}""#, metadata.skill_name);

        let mut entry = SkillIndexEntry::new(
            metadata.skill_name.clone(),
            metadata.description.clone(),
            metadata.version.clone(),
            path,
        );

        // Add routing keywords
        entry.routing_keywords = metadata.routing_keywords;

        // Add intents
        entry.intents = metadata.intents;

        // Add authors
        entry.authors = metadata.authors;

        // Add require_refs from frontmatter
        entry.require_refs = metadata.require_refs;

        // Add tools
        for tool in tools {
            let tool_entry = IndexToolEntry {
                name: format!("{}.{}", metadata.skill_name, tool.tool_name),
                description: tool.description.clone(),
            };
            entry.add_tool(tool_entry);
        }

        entry
    }

    /// Scan all skills and write to skill_index.json with full metadata.
    ///
    /// This method:
    /// 1. Scans all skill directories for metadata (SKILL.md frontmatter)
    /// 2. Scans scripts/ directories for @skill_command decorated functions
    /// 3. Combines metadata with discovered tools
    /// 4. Writes the complete skill_index.json
    ///
    /// # Arguments
    ///
    /// * `base_path` - Path to the skills directory (e.g., "assets/skills")
    /// * `output_path` - Path for the output JSON file
    /// * `structure` - Optional skill structure for validation (uses default if None)
    /// * `script_scanner` - Script scanner for discovering tools
    ///
    /// # Examples
    ///
    /// ```ignore
    /// let scanner = SkillScanner::new();
    /// let script_scanner = ScriptScanner::new();
    ///
    /// scanner.scan_all_full_to_index(
    ///     PathBuf::from("assets/skills"),
    ///     PathBuf::from("assets/skills/skill_index.json"),
    ///     None,
    ///     &script_scanner
    /// ).unwrap();
    /// ```
    pub fn scan_all_full_to_index(
        &self,
        base_path: &Path,
        output_path: &Path,
        structure: Option<&SkillStructure>,
        script_scanner: &ScriptScanner,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let metadatas = self.scan_all(base_path, structure)?;

        let mut entries: Vec<SkillIndexEntry> = Vec::new();

        for metadata in metadatas {
            let skill_path = base_path.join(&metadata.skill_name);

            // Scan for tools in scripts directory
            let scripts_path = skill_path.join("scripts");
            let tools = if scripts_path.exists() {
                script_scanner.scan_scripts(
                    &scripts_path,
                    &metadata.skill_name,
                    &metadata.routing_keywords,
                )?
            } else {
                Vec::new()
            };

            // Build full entry
            let entry = self.build_index_entry(metadata, &tools, &skill_path);
            entries.push(entry);
        }

        // Create parent directories if needed
        if let Some(parent) = output_path.parent() {
            fs::create_dir_all(parent)?;
        }

        // Write as JSON
        let json = serde_json::to_string_pretty(&entries)?;
        fs::write(output_path, json)?;

        log::info!(
            "Wrote skill_index.json with {} skills to {:?}",
            entries.len(),
            output_path
        );

        Ok(())
    }

    /// Parse YAML frontmatter from SKILL.md content.
    ///
    /// This is a public method to allow external parsing if needed.
    ///
    /// # Arguments
    ///
    /// * `content` - Raw content of the SKILL.md file
    /// * `skill_path` - Path to the skill directory (for extracting skill name)
    ///
    /// # Examples
    ///
    /// ```ignore
    /// let content = std::fs::read_to_string("assets/skills/writer/SKILL.md").unwrap();
    /// let metadata = scanner.parse_skill_md(&content, PathBuf::from("writer")).unwrap();
    /// ```
    pub fn parse_skill_md(
        &self,
        content: &str,
        skill_path: &Path,
    ) -> Result<SkillMetadata, Box<dyn std::error::Error>> {
        // Extract skill name from path if not already set
        let skill_name = skill_path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();

        // Find YAML frontmatter (between first and second ---)
        let frontmatter = match extract_frontmatter(content) {
            Some(fm) => fm,
            None => {
                log::warn!("No YAML frontmatter found in SKILL.md for: {}", skill_name);
                return Ok(SkillMetadata {
                    skill_name,
                    version: String::new(),
                    description: String::new(),
                    routing_keywords: Vec::new(),
                    authors: Vec::new(),
                    intents: Vec::new(),
                    require_refs: Vec::new(),
                    repository: String::new(),
                });
            }
        };

        // Parse YAML frontmatter
        let frontmatter_data: SkillFrontmatter = serde_yaml::from_str(&frontmatter)
            .map_err(|e| anyhow::anyhow!("Failed to parse SKILL.md frontmatter: {}", e))?;

        Ok(SkillMetadata {
            skill_name,
            version: frontmatter_data.version.unwrap_or_default(),
            description: frontmatter_data.description.unwrap_or_default(),
            routing_keywords: frontmatter_data.routing_keywords.unwrap_or_default(),
            authors: frontmatter_data.authors.unwrap_or_default(),
            intents: frontmatter_data.intents.unwrap_or_default(),
            require_refs: frontmatter_data.require_refs.map_or_else(Vec::new, |refs| {
                refs.into_iter()
                    .filter_map(|r| ReferencePath::new(r).ok())
                    .collect()
            }),
            repository: frontmatter_data.repository.unwrap_or_default(),
        })
    }
}

impl Default for SkillScanner {
    fn default() -> Self {
        Self::new()
    }
}

/// Extract YAML frontmatter from markdown content.
///
/// Returns `Some(String)` if frontmatter is found, `None` otherwise.
///
/// # Examples
///
/// ```ignore
/// let content = r#"---
/// name: "test"
/// version: "1.0"
/// ---
/// # Content
/// "#;
///
/// let frontmatter = extract_frontmatter(content).unwrap();
/// assert!(frontmatter.contains("name:"));
/// assert!(frontmatter.contains("version:"));
/// ```
fn extract_frontmatter(content: &str) -> Option<String> {
    let start_marker = "---";
    let end_marker = "---";

    // Find first --- marker
    let start = content.find(start_marker)?;
    let content_after_start = &content[start + start_marker.len()..];

    // Find closing --- marker
    let end = content_after_start.find(end_marker)?;

    Some(content_after_start[..end].to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_parse_skill_md_with_frontmatter() {
        let content = r#"---
name: "writer"
version: "1.1.0"
description: "Text manipulation skill"
routing_keywords: ["write", "edit", "polish"]
authors: ["omni-dev-fusion"]
intents: ["Update documentation"]
---

# Writer Skill
"#;

        let scanner = SkillScanner::new();
        let temp_dir = TempDir::new().unwrap();
        let skill_path = temp_dir.path().join("writer");

        let metadata = scanner.parse_skill_md(content, &skill_path).unwrap();

        assert_eq!(metadata.skill_name, "writer");
        assert_eq!(metadata.version, "1.1.0");
        assert_eq!(metadata.description, "Text manipulation skill");
        assert_eq!(metadata.routing_keywords, vec!["write", "edit", "polish"]);
        assert_eq!(metadata.authors, vec!["omni-dev-fusion"]);
        assert_eq!(metadata.intents, vec!["Update documentation"]);
    }

    #[test]
    fn test_parse_skill_md_without_frontmatter() {
        let content = "# Writer Skill\n\nJust a skill without frontmatter.";

        let scanner = SkillScanner::new();
        let temp_dir = TempDir::new().unwrap();
        let skill_path = temp_dir.path().join("writer");

        let metadata = scanner.parse_skill_md(content, &skill_path).unwrap();

        assert_eq!(metadata.skill_name, "writer");
        assert!(metadata.version.is_empty());
        assert!(metadata.routing_keywords.is_empty());
    }

    #[test]
    fn test_scan_skill_missing_skill_md() {
        let scanner = SkillScanner::new();
        let temp_dir = TempDir::new().unwrap();
        let skill_path = temp_dir.path().join("empty_skill");
        std::fs::create_dir_all(&skill_path).unwrap();

        let result = scanner.scan_skill(&skill_path, None).unwrap();
        assert!(result.is_none());
    }

    #[test]
    fn test_scan_all_multiple_skills() {
        let temp_dir = TempDir::new().unwrap();
        let skills_dir = temp_dir.path().join("skills");
        std::fs::create_dir_all(&skills_dir).unwrap();

        // Create writer skill
        let writer_path = skills_dir.join("writer");
        std::fs::create_dir_all(&writer_path).unwrap();
        std::fs::write(
            &writer_path.join("SKILL.md"),
            r#"---
name: "writer"
version: "1.0"
routing_keywords: ["write", "edit"]
---
# Writer
"#,
        )
        .unwrap();

        // Create git skill
        let git_path = skills_dir.join("git");
        std::fs::create_dir_all(&git_path).unwrap();
        std::fs::write(
            &git_path.join("SKILL.md"),
            r#"---
name: "git"
version: "1.0"
routing_keywords: ["commit", "branch"]
---
# Git
"#,
        )
        .unwrap();

        let scanner = SkillScanner::new();
        let metadatas = scanner.scan_all(&skills_dir, None).unwrap();

        assert_eq!(metadatas.len(), 2);
        assert!(metadatas.iter().any(|m| m.skill_name == "writer"));
        assert!(metadatas.iter().any(|m| m.skill_name == "git"));
    }

    #[test]
    fn test_extract_frontmatter() {
        let content = r#"---
name: "test"
version: "1.0"
---
# Content
"#;

        let frontmatter = extract_frontmatter(content).unwrap();
        assert!(frontmatter.contains("name:"));
        assert!(frontmatter.contains("version:"));
    }

    #[test]
    fn test_extract_frontmatter_no_frontmatter() {
        let content = "# Just content\nNo frontmatter here.";
        assert!(extract_frontmatter(content).is_none());
    }

    #[test]
    fn test_skill_scanner_new() {
        let _scanner = SkillScanner::new();
        // Just verify it can be created
        assert!(true);
    }

    // Note: Comprehensive integration tests are in tests/skill_scanner.rs
    // These basic tests verify core functionality without complex setup.
}
