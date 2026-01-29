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

use crate::skill_metadata::{
    IndexToolEntry, ReferencePath, SkillIndexEntry, SkillMetadata, SkillStructure, SnifferRule,
};

/// TOML structure for rules.toml parsing.
#[derive(Debug, Deserialize)]
struct RulesToml {
    #[serde(default, rename = "match")]
    matches: Vec<RuleMatch>,
}

/// Single match rule in rules.toml.
#[derive(Debug, Deserialize)]
struct RuleMatch {
    #[serde(rename = "type")]
    rule_type: Option<String>,
    pattern: Option<String>,
}

/// Parse extensions/sniffer/rules.toml for sniffer rules.
///
/// Returns a vector of `SnifferRule` extracted from the TOML file.
/// If the file doesn't exist or is invalid, returns an empty vector.
#[inline]
fn parse_rules_toml(skill_path: &Path) -> Vec<SnifferRule> {
    let rules_path = skill_path.join("extensions/sniffer/rules.toml");
    if !rules_path.exists() {
        return Vec::new();
    }

    let content = match fs::read_to_string(&rules_path) {
        Ok(c) => c,
        Err(e) => {
            log::warn!("Failed to read rules.toml: {}", e);
            return Vec::new();
        }
    };

    let rules_toml: RulesToml = match toml::from_str(&content) {
        Ok(r) => r,
        Err(e) => {
            log::warn!("Failed to parse rules.toml: {}", e);
            return Vec::new();
        }
    };

    let mut rules = Vec::new();
    for rule in rules_toml.matches {
        if let (Some(rule_type), Some(pattern)) = (rule.rule_type, rule.pattern) {
            rules.push(SnifferRule::new(rule_type, pattern));
        }
    }

    log::debug!("Parsed {} sniffer rules from {:?}", rules.len(), rules_path);

    rules
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
    #[serde(default)]
    require_refs: Option<Vec<String>>,
    #[serde(default)]
    repository: Option<String>,
    /// Permissions required by this skill (e.g., "filesystem:read", "network:http")
    #[serde(default)]
    permissions: Option<Vec<String>>,
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
    pub fn build_index_entry(
        &self,
        metadata: SkillMetadata,
        tools: &[crate::skill_metadata::ToolRecord],
        skill_path: &Path,
    ) -> SkillIndexEntry {
        let path = format!("assets/skills/{}", metadata.skill_name);

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

        // Add permissions (Zero Trust: empty = no access)
        entry.permissions = metadata.permissions;

        // Add sniffer rules from rules.toml
        entry.sniffing_rules = parse_rules_toml(skill_path);

        // Add tools (tool.tool_name already includes skill_name prefix from tools_scanner)
        let mut seen_names: Vec<String> = Vec::new();
        for tool in tools {
            if !seen_names.contains(&tool.tool_name) {
                seen_names.push(tool.tool_name.clone());
                let tool_entry = IndexToolEntry {
                    name: tool.tool_name.clone(),
                    description: tool.description.clone(),
                    category: tool.category.clone(),
                    input_schema: tool.input_schema.clone(),
                    file_hash: tool.file_hash.clone(),
                };
                entry.add_tool(tool_entry);
            }
        }

        entry
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
                    permissions: Vec::new(),
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
            permissions: frontmatter_data.permissions.unwrap_or_default(),
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
pub fn extract_frontmatter(content: &str) -> Option<String> {
    let start_marker = "---";
    let end_marker = "---";

    // Find first --- marker
    let start = content.find(start_marker)?;
    let content_after_start = &content[start + start_marker.len()..];

    // Find closing --- marker
    let end = content_after_start.find(end_marker)?;

    Some(content_after_start[..end].to_string())
}

// Note: Comprehensive tests are in tests/test_skill_scanner.rs
