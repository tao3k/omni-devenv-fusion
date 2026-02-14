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

use std::collections::HashMap;

use crate::frontmatter::extract_frontmatter;
use crate::skills::canonical::{CanonicalSkillPayload, CanonicalToolEntry};
use crate::skills::metadata::{
    IndexToolEntry, ReferencePath, ReferenceRecord, SkillIndexEntry, SkillMetadata, SkillStructure,
    SnifferRule, ToolRecord,
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

    if log::log_enabled!(log::Level::Debug) {
        log::debug!("Parsed {} sniffer rules from {:?}", rules.len(), rules_path);
    }

    rules
}

/// Frontmatter for reference docs under `references/*.md` (see skill-data-hierarchy-and-references.md).
/// All reference fields live under a single `metadata` block (same pattern as SKILL.md).
#[derive(Debug, Deserialize)]
struct ReferenceFrontmatter {
    #[serde(default)]
    metadata: Option<ReferenceMetadataBlock>,
}

/// Contents of the `metadata` block in reference front matter.
#[derive(Debug, Deserialize)]
struct ReferenceMetadataBlock {
    /// Tool(s) this reference is for, full name e.g. git.smart_commit (string or array).
    #[serde(default, rename = "for_tools")]
    for_tools: Option<serde_yaml::Value>,
    #[serde(default)]
    title: Option<String>,
    /// Optional description (reserved for future use on ReferenceRecord).
    #[serde(default)]
    #[allow(dead_code)]
    description: Option<String>,
    #[serde(default)]
    routing_keywords: Option<Vec<String>>,
    #[serde(default)]
    intents: Option<Vec<String>>,
}

/// Derive unique skill names from a list of full tool names (e.g. "researcher.run_research_graph" -> "researcher").
fn skills_from_tool_list(tools: &[String]) -> Vec<String> {
    let mut skills: Vec<String> = tools
        .iter()
        .filter_map(|t| t.split('.').next().map(String::from))
        .filter(|s| !s.is_empty())
        .collect();
    skills.sort();
    skills.dedup();
    skills
}

fn yaml_value_to_string_vec(v: &serde_yaml::Value) -> Vec<String> {
    match v {
        serde_yaml::Value::String(s) => {
            if s.is_empty() {
                vec![]
            } else {
                vec![s.clone()]
            }
        }
        serde_yaml::Value::Sequence(seq) => seq
            .iter()
            .filter_map(|x| x.as_str().map(String::from))
            .filter(|s| !s.is_empty())
            .collect(),
        _ => vec![],
    }
}

fn yaml_value_to_opt_string_vec(v: &serde_yaml::Value) -> Option<Vec<String>> {
    let vec = yaml_value_to_string_vec(v);
    if vec.is_empty() { None } else { Some(vec) }
}

/// Scan `references/` under a skill directory and return reference records.
/// Parses YAML frontmatter for `for_tools` only; `for_skills` and `skill_name` are derived from tool full names.
fn scan_references(skill_path: &Path, skill_name: &str) -> Vec<ReferenceRecord> {
    let refs_dir = skill_path.join("references");
    if !refs_dir.is_dir() {
        return Vec::new();
    }

    let mut records = Vec::new();
    let read_dir = match fs::read_dir(&refs_dir) {
        Ok(d) => d,
        Err(e) => {
            log::debug!("Could not read references dir {:?}: {}", refs_dir, e);
            return records;
        }
    };

    for entry in read_dir.filter_map(Result::ok) {
        let path = entry.path();
        if path.extension().map_or(true, |e| e != "md") {
            continue;
        }
        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let ref_name = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unknown")
            .to_string();
        let file_path = path.to_string_lossy().to_string();

        let fm = extract_frontmatter(&content)
            .and_then(|s| serde_yaml::from_str::<ReferenceFrontmatter>(&s).ok());
        let meta = fm.as_ref().and_then(|f| f.metadata.as_ref());
        let for_tools = meta
            .and_then(|m| m.for_tools.as_ref())
            .and_then(yaml_value_to_opt_string_vec);
        let for_skills: Vec<String> = for_tools
            .as_ref()
            .map(|tools| skills_from_tool_list(tools))
            .filter(|v| !v.is_empty())
            .unwrap_or_else(|| vec![skill_name.to_string()]);
        let skill_name_primary = for_skills
            .first()
            .cloned()
            .unwrap_or_else(|| skill_name.to_string());
        let title = meta
            .and_then(|m| m.title.clone())
            .unwrap_or_else(|| ref_name.clone());

        let mut rec = ReferenceRecord::new(ref_name, title, skill_name_primary.clone(), file_path);
        rec.for_skills = for_skills;
        rec.for_tools = for_tools;
        if let Some(m) = meta {
            let mut kw = Vec::new();
            if let Some(ref r) = m.routing_keywords {
                kw.extend(r.clone());
            }
            if let Some(ref i) = m.intents {
                kw.extend(i.clone());
            }
            if !kw.is_empty() {
                rec.keywords = kw;
            }
        }
        records.push(rec);
    }

    if log::log_enabled!(log::Level::Debug) && !records.is_empty() {
        log::debug!(
            "Scanned {} reference(s) for skill {}",
            records.len(),
            skill_name
        );
    }
    records
}

/// YAML frontmatter structure (Anthropic official format with metadata block).
///
/// ```yaml
/// ---
/// name: <skill-identifier>
/// description: Use when <use-case-1>, <use-case-2>, or <use-case-3>.
/// metadata:
///   author: <name>
///   version: "x.x.x"
///   source: <url>
///   routing_keywords:
///     - "keyword1"
///     - "keyword2"
///   intents:
///     - "Intent description 1"
///     - "Intent description 2"
/// ---
/// ```
#[derive(Debug, Deserialize, PartialEq, Default)]
struct SkillFrontmatter {
    #[serde(default)]
    name: Option<String>,
    #[serde(default)]
    description: Option<String>,
    #[serde(default)]
    metadata: Option<SkillMetadataBlock>,
}

/// Metadata block for YAML parsing (internal use only).
#[derive(Debug, Deserialize, PartialEq, Default)]
struct SkillMetadataBlock {
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
#[derive(Debug, Clone)]
pub struct SkillScanner;

impl SkillScanner {
    /// Create a new skill scanner with default settings.
    #[must_use]
    pub fn new() -> Self {
        Self
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

    /// Scan all skills in a base directory with parallel processing.
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
        use rayon::prelude::*;
        use std::sync::Arc;

        if !base_path.exists() {
            log::warn!("Skills base directory not found: {:?}", base_path);
            return Ok(Vec::new());
        }

        // Collect all skill directories first
        let skill_dirs: Vec<PathBuf> = fs::read_dir(base_path)?
            .filter_map(|e| e.ok())
            .filter(|e| e.path().is_dir())
            .map(|e| e.path())
            .collect();

        // Arc wrap structure for thread-safe sharing
        let validate_struct = structure.map(|s| Arc::new(s.clone()));

        // Process in parallel using rayon
        let metadatas: Vec<SkillMetadata> = skill_dirs
            .par_iter()
            .filter_map(|skill_path| self.scan_skill_inner(skill_path, validate_struct.as_deref()))
            .collect();

        log::info!("Scanned {} skills from {:?}", metadatas.len(), base_path);
        Ok(metadatas)
    }

    /// Internal helper for parallel skill scanning.
    #[inline]
    fn scan_skill_inner(
        &self,
        skill_path: &Path,
        structure: Option<&SkillStructure>,
    ) -> Option<SkillMetadata> {
        let skill_md_path = skill_path.join("SKILL.md");
        if !skill_md_path.exists() {
            return None;
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

        // Read and parse the file
        let content = fs::read_to_string(&skill_md_path).ok()?;
        let metadata = self.parse_skill_md(&content, skill_path).ok()?;

        log::info!(
            "Scanned skill metadata: {} (v{}) - {} keywords",
            metadata.skill_name,
            metadata.version,
            metadata.routing_keywords.len()
        );

        Some(metadata)
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
        tools: &[ToolRecord],
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

        // Scan references/*.md (metadata.for_tools per doc)
        entry.references = scan_references(skill_path, &metadata.skill_name);

        entry
    }

    /// Build the canonical per-skill payload (Rust schema) from metadata, tools, and filesystem.
    ///
    /// Fills `skill_tools` (each tool + ref_key → path from references' `for_tools`) and
    /// `references` (ref_id → ReferenceRecord). Used to wire the agreed schema to the scanner.
    pub fn build_canonical_payload(
        &self,
        metadata: SkillMetadata,
        tools: &[ToolRecord],
        skill_path: &Path,
    ) -> CanonicalSkillPayload {
        let skill_md_path = skill_path.join("SKILL.md").to_string_lossy().to_string();
        let refs = scan_references(skill_path, &metadata.skill_name);
        let references: HashMap<String, ReferenceRecord> =
            refs.into_iter().map(|r| (r.ref_name.clone(), r)).collect();

        let mut skill_tools: HashMap<String, CanonicalToolEntry> = HashMap::new();
        for tool in tools {
            let mut skill_tool_references = HashMap::new();
            for rec in references.values() {
                if rec
                    .for_tools
                    .as_ref()
                    .map_or(false, |v| v.contains(&tool.tool_name))
                {
                    let ref_key = format!("{}.references.{}", metadata.skill_name, rec.ref_name);
                    skill_tool_references.insert(ref_key, rec.file_path.clone());
                }
            }
            let entry = CanonicalToolEntry {
                tool: tool.clone(),
                skill_tool_references,
            };
            skill_tools.insert(tool.tool_name.clone(), entry);
        }

        CanonicalSkillPayload {
            skill_name: metadata.skill_name.clone(),
            skill_md_path,
            metadata,
            skill_tools,
            references,
        }
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

        // Extract from metadata block (new format)
        let (version, routing_keywords, authors, intents, require_refs, repository, permissions) =
            match &frontmatter_data.metadata {
                Some(meta) => (
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
                    meta.require_refs.clone().unwrap_or_default(),
                    meta.source.clone().unwrap_or_default(),
                    meta.permissions.clone().unwrap_or_default(),
                ),
                None => {
                    log::warn!("No metadata block found in SKILL.md for: {}", skill_name);
                    (
                        String::new(),
                        Vec::new(),
                        Vec::new(),
                        Vec::new(),
                        Vec::new(),
                        String::new(),
                        Vec::new(),
                    )
                }
            };

        Ok(SkillMetadata {
            skill_name,
            version,
            description: frontmatter_data.description.unwrap_or_default(),
            routing_keywords,
            authors,
            intents,
            require_refs: require_refs
                .into_iter()
                .filter_map(|r| ReferencePath::new(r).ok())
                .collect(),
            repository,
            permissions,
        })
    }
}

impl Default for SkillScanner {
    fn default() -> Self {
        Self::new()
    }
}

// Note: Comprehensive tests are in tests/test_skill_scanner.rs
