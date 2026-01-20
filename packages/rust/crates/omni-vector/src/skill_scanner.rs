//! Skill Scanner - Parses SKILL.md for metadata and routing keywords.
//!
//! Scans skill directories to extract:
//! - Skill name, version, description
//! - routing_keywords for hybrid search
//! - Authors and intents
//!
//! Follows the skill structure defined in settings.yaml:
//! - Required: SKILL.md (skill metadata)
//! - Required: tools.py (MCP tools)
//! - Default: scripts/ (standalone executables)

use std::fs;
use std::path::Path;
use std::result::Result;

use serde::Deserialize;

/// Parsed skill manifest from SKILL.md YAML frontmatter.
#[derive(Debug, Clone, Deserialize, PartialEq)]
pub struct SkillManifest {
    /// Skill name (from filename)
    pub skill_name: String,
    /// Version from frontmatter
    #[serde(default)]
    pub version: String,
    /// Human-readable description
    #[serde(default)]
    pub description: String,
    /// Keywords for semantic routing and hybrid search
    #[serde(default)]
    pub routing_keywords: Vec<String>,
    /// Skill authors
    #[serde(default)]
    pub authors: Vec<String>,
    /// Supported intents
    #[serde(default)]
    pub intents: Vec<String>,
}

/// Skill Scanner - Extracts metadata from SKILL.md files.
pub struct SkillScanner;

impl SkillScanner {
    /// Create a new skill scanner.
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    /// Scan a single skill directory and extract its manifest.
    ///
    /// Returns `Ok(Some(manifest))` if SKILL.md is found and valid.
    /// Returns `Ok(None)` if SKILL.md is missing or invalid.
    pub fn scan_skill(
        &self,
        skill_path: &Path,
    ) -> Result<Option<SkillManifest>, Box<dyn std::error::Error>> {
        let skill_md_path = skill_path.join("SKILL.md");

        if !skill_md_path.exists() {
            log::debug!("SKILL.md not found for skill: {:?}", skill_path);
            return Ok(None);
        }

        let content = fs::read_to_string(&skill_md_path)?;
        let manifest = self.parse_skill_md(&content, skill_path)?;

        log::info!(
            "Scanned skill manifest: {} (v{}) - {} keywords",
            manifest.skill_name,
            manifest.version,
            manifest.routing_keywords.len()
        );

        Ok(Some(manifest))
    }

    /// Scan all skills in a base directory.
    ///
    /// Returns a vector of skill manifests for all skills with valid SKILL.md.
    pub fn scan_all(
        &self,
        base_path: &Path,
    ) -> Result<Vec<SkillManifest>, Box<dyn std::error::Error>> {
        let mut manifests = Vec::new();

        if !base_path.exists() {
            log::warn!("Skills base directory not found: {:?}", base_path);
            return Ok(manifests);
        }

        for entry in fs::read_dir(base_path)? {
            let entry = entry?;
            let path = entry.path();

            if path.is_dir() {
                if let Some(manifest) = self.scan_skill(&path)? {
                    manifests.push(manifest);
                }
            }
        }

        log::info!("Scanned {} skills from {:?}", manifests.len(), base_path);
        Ok(manifests)
    }

    /// Parse YAML frontmatter from SKILL.md content.
    fn parse_skill_md(
        &self,
        content: &str,
        skill_path: &Path,
    ) -> Result<SkillManifest, Box<dyn std::error::Error>> {
        // Extract skill name from path
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
                return Ok(SkillManifest {
                    skill_name,
                    version: String::new(),
                    description: String::new(),
                    routing_keywords: Vec::new(),
                    authors: Vec::new(),
                    intents: Vec::new(),
                });
            }
        };

        // Parse YAML frontmatter
        let manifest: SkillFrontmatter = serde_yaml::from_str(&frontmatter)?;

        Ok(SkillManifest {
            skill_name,
            version: manifest.version.unwrap_or_default(),
            description: manifest.description.unwrap_or_default(),
            routing_keywords: manifest.routing_keywords.unwrap_or_default(),
            authors: manifest.authors.unwrap_or_default(),
            intents: manifest.intents.unwrap_or_default(),
        })
    }
}

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
}

/// Extract YAML frontmatter from markdown content.
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

impl Default for SkillScanner {
    fn default() -> Self {
        Self::new()
    }
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
        std::fs::create_dir_all(&skill_path).unwrap();

        let manifest = scanner.parse_skill_md(content, &skill_path).unwrap();

        assert_eq!(manifest.skill_name, "writer");
        assert_eq!(manifest.version, "1.1.0");
        assert_eq!(manifest.description, "Text manipulation skill");
        assert_eq!(manifest.routing_keywords, vec!["write", "edit", "polish"]);
        assert_eq!(manifest.authors, vec!["omni-dev-fusion"]);
        assert_eq!(manifest.intents, vec!["Update documentation"]);
    }

    #[test]
    fn test_parse_skill_md_without_frontmatter() {
        let content = "# Writer Skill\n\nJust a skill without frontmatter.";

        let scanner = SkillScanner::new();
        let temp_dir = TempDir::new().unwrap();
        let skill_path = temp_dir.path().join("writer");

        let manifest = scanner.parse_skill_md(content, &skill_path).unwrap();

        assert_eq!(manifest.skill_name, "writer");
        assert!(manifest.version.is_empty());
        assert!(manifest.routing_keywords.is_empty());
    }

    #[test]
    fn test_scan_skill_missing_skill_md() {
        let scanner = SkillScanner::new();
        let temp_dir = TempDir::new().unwrap();
        let skill_path = temp_dir.path().join("empty_skill");
        std::fs::create_dir_all(&skill_path).unwrap();

        let result = scanner.scan_skill(&skill_path).unwrap();
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
        let manifests = scanner.scan_all(&skills_dir).unwrap();

        assert_eq!(manifests.len(), 2);
        assert!(manifests.iter().any(|m| m.skill_name == "writer"));
        assert!(manifests.iter().any(|m| m.skill_name == "git"));
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
}
