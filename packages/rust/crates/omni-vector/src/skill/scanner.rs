//! `SkillScannerModule` - Skill manifest parsing from `SKILL.md`.
//!
//! Scans skill directories to extract:
//! - Skill name, version, description
//! - `routing_keywords` for hybrid search
//! - Authors and intents
//!
//! Follows Anthropic official `SKILL.md` format:
//! ```yaml
//! ---
//! name: <skill-identifier>
//! description: Use when <use-case-1>, <use-case-2>, or <use-case-3>.
//! metadata:
//!   author: <name>
//!   version: "x.x.x"
//!   source: <url>
//!   routing_keywords:
//!     - "keyword1"
//!     - "keyword2"
//!   intents:
//!     - "Intent description 1"
//!     - "Intent description 2"
//! ---
//! ```

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
pub struct SkillScannerModule;

impl SkillScannerModule {
    /// Create a new skill scanner module.
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    /// Scan a single skill directory and extract its manifest.
    ///
    /// Returns `Ok(Some(manifest))` if SKILL.md is found and valid.
    /// Returns `Ok(None)` if SKILL.md is missing or invalid.
    ///
    /// # Errors
    ///
    /// Returns an error if reading `SKILL.md` from disk fails.
    #[allow(clippy::unused_self)]
    pub fn scan_skill(
        &self,
        skill_path: &Path,
    ) -> Result<Option<SkillManifest>, Box<dyn std::error::Error>> {
        let skill_md_path = skill_path.join("SKILL.md");

        if !skill_md_path.exists() {
            log::debug!("SKILL.md not found for skill: {}", skill_path.display());
            return Ok(None);
        }

        let content = fs::read_to_string(&skill_md_path)?;
        let manifest = Self::parse_skill_md(&content, skill_path)?;

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
    ///
    /// # Errors
    ///
    /// Returns an error if the base directory cannot be read.
    #[allow(clippy::collapsible_if)]
    pub fn scan_all(
        &self,
        base_path: &Path,
    ) -> Result<Vec<SkillManifest>, Box<dyn std::error::Error>> {
        let mut manifests = Vec::new();

        if !base_path.exists() {
            log::warn!("Skills base directory not found: {}", base_path.display());
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

        log::info!(
            "Scanned {} skills from {}",
            manifests.len(),
            base_path.display()
        );
        Ok(manifests)
    }

    /// Parse YAML frontmatter from SKILL.md content.
    fn parse_skill_md(
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
        let Some(frontmatter) = extract_frontmatter(content) else {
            log::warn!("No YAML frontmatter found in SKILL.md for: {skill_name}");
            return Ok(SkillManifest {
                skill_name,
                version: String::new(),
                description: String::new(),
                routing_keywords: Vec::new(),
                authors: Vec::new(),
                intents: Vec::new(),
            });
        };

        // Parse YAML frontmatter (Anthropic official format)
        let frontmatter_parsed: SkillFrontmatter = serde_yaml::from_str(&frontmatter)?;

        // Extract from metadata block (new format)
        let (version, routing_keywords, authors, intents) =
            if let Some(meta) = &frontmatter_parsed.metadata {
                (
                    meta.version.clone().unwrap_or_default(),
                    meta.routing_keywords.clone().unwrap_or_default(),
                    // Support both "author" (single) and "authors" (multiple)
                    if let Some(authors_vec) = &meta.authors {
                        authors_vec.clone()
                    } else if let Some(a) = &meta.author {
                        vec![a.clone()]
                    } else {
                        Vec::new()
                    },
                    meta.intents.clone().unwrap_or_default(),
                )
            } else {
                log::warn!("No metadata block found in SKILL.md for: {skill_name}");
                (String::new(), Vec::new(), Vec::new(), Vec::new())
            };

        Ok(SkillManifest {
            skill_name,
            version,
            description: frontmatter_parsed.description.unwrap_or_default(),
            routing_keywords,
            authors,
            intents,
        })
    }
}

/// YAML frontmatter structure (Anthropic official format).
///
/// ```yaml
/// ---
/// name: <skill>
/// description: Use when...
/// metadata:
///   author: <name>
///   version: "x.x.x"
///   source: <url>
///   routing_keywords: [...]
///   intents: [...]
/// ---
/// ```
#[derive(Debug, Deserialize, PartialEq, Default)]
struct SkillFrontmatter {
    #[serde(default)]
    name: Option<String>,
    #[serde(default)]
    description: Option<String>,
    #[serde(default)]
    metadata: Option<SkillMetadata>,
}

#[derive(Debug, Deserialize, PartialEq, Default)]
struct SkillMetadata {
    #[serde(default)]
    author: Option<String>,
    #[serde(default)]
    authors: Option<Vec<String>>,
    #[serde(default)]
    version: Option<String>,
    #[serde(default)]
    source: Option<String>,
    #[serde(default)]
    routing_keywords: Option<Vec<String>>,
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

impl Default for SkillScannerModule {
    fn default() -> Self {
        Self::new()
    }
}
