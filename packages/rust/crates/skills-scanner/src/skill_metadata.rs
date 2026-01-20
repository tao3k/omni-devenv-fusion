//! Skill Metadata - Parsed metadata from SKILL.md YAML frontmatter.
//!
//! This module contains the `SkillMetadata` struct which represents the metadata
//! extracted from the YAML frontmatter in a skill's SKILL.md file.
//!
//! Also defines `SkillStructure` which represents the canonical skill structure
//! as defined in `settings.yaml` under `skills.architecture.structure`.
//!
//! # Example
//!
//! ```ignore
//! use skills_scanner::SkillMetadata;
//!
//! let metadata = SkillMetadata {
//!     skill_name: "writer".to_string(),
//!     version: "1.1.0".to_string(),
//!     description: "Text manipulation skill".to_string(),
//!     routing_keywords: vec!["write".to_string(), "edit".to_string()],
//!     authors: vec!["omni-dev-fusion".to_string()],
//!     intents: vec!["Update documentation".to_string()],
//! };
//! ```

use schemars::JsonSchema as SchemarsJsonSchema;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

/// Parsed skill metadata from SKILL.md YAML frontmatter.
///
/// This struct represents the metadata extracted from the YAML frontmatter
/// in a skill's SKILL.md file, following the structure defined in
/// settings.yaml under `skills.architecture`.
#[derive(Debug, Clone, Deserialize, Serialize, SchemarsJsonSchema, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub struct SkillMetadata {
    /// Skill name (typically derived from directory name)
    #[serde(default)]
    pub skill_name: String,
    /// Version from frontmatter (e.g., "1.0.0")
    #[serde(default)]
    pub version: String,
    /// Human-readable description of the skill
    #[serde(default)]
    pub description: String,
    /// Keywords for semantic routing and hybrid search
    /// These are used by the skill injector to determine which skills
    /// should be loaded for a given task.
    #[serde(default)]
    pub routing_keywords: Vec<String>,
    /// Skill authors
    #[serde(default)]
    pub authors: Vec<String>,
    /// Supported intents/actions
    #[serde(default)]
    pub intents: Vec<String>,
    /// External documentation references declared in SKILL.md frontmatter
    /// These are loaded into context when the skill is active
    #[serde(default)]
    pub require_refs: Vec<ReferencePath>,
    /// Repository URL for trusted source verification
    #[serde(default)]
    pub repository: String,
}

impl Default for SkillMetadata {
    fn default() -> Self {
        Self {
            skill_name: String::new(),
            version: String::new(),
            description: String::new(),
            routing_keywords: Vec::new(),
            authors: Vec::new(),
            intents: Vec::new(),
            require_refs: Vec::new(),
            repository: String::new(),
        }
    }
}

impl SkillMetadata {
    /// Create a new empty metadata.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Create a metadata with a specific skill name.
    #[must_use]
    pub fn with_name(name: impl Into<String>) -> Self {
        Self {
            skill_name: name.into(),
            ..Self::default()
        }
    }

    /// Check if the metadata has any routing keywords.
    #[must_use]
    pub fn has_routing_keywords(&self) -> bool {
        !self.routing_keywords.is_empty()
    }

    /// Get routing keywords as a space-separated string for logging/debugging.
    #[must_use]
    pub fn keywords_summary(&self) -> String {
        self.routing_keywords.join(", ")
    }
}

// =============================================================================
// Tool Record - Functions with @skill_command decorator
// =============================================================================

/// A discovered tool from script scanning.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct ToolRecord {
    /// Full tool name (e.g., "git.commit")
    pub tool_name: String,
    /// Human-readable description
    pub description: String,
    /// Parent skill name (e.g., "git")
    pub skill_name: String,
    /// Physical file path (e.g., "assets/skills/git/scripts/commit.py")
    pub file_path: String,
    /// Function name in the Python file
    pub function_name: String,
    /// Execution mode (e.g., "script", "library")
    pub execution_mode: String,
    /// Keywords for vector search (includes skill routing_keywords)
    pub keywords: Vec<String>,
    /// SHA256 hash of file content (for incremental indexing)
    pub file_hash: String,
    /// JSON schema for tool parameters
    #[serde(default)]
    pub input_schema: String,
    /// Raw docstring content
    #[serde(default)]
    pub docstring: String,
}

impl ToolRecord {
    /// Create a new tool record.
    #[must_use]
    pub fn new(
        tool_name: String,
        description: String,
        skill_name: String,
        file_path: String,
        function_name: String,
    ) -> Self {
        Self {
            tool_name,
            description,
            skill_name,
            file_path,
            function_name,
            execution_mode: String::new(),
            keywords: Vec::new(),
            file_hash: String::new(),
            input_schema: String::new(),
            docstring: String::new(),
        }
    }
}

// =============================================================================
// Template Record - Jinja2 templates
// =============================================================================

/// A discovered template from templates/ directory.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct TemplateRecord {
    /// Template name relative to skill (e.g., "git/commit_message.j2")
    pub template_name: String,
    /// Human-readable description
    pub description: String,
    /// Parent skill name
    pub skill_name: String,
    /// Physical file path
    pub file_path: String,
    /// Template variables extracted from the file
    pub variables: Vec<String>,
    /// Template content preview (first 500 chars)
    pub content_preview: String,
    /// Keywords for search
    pub keywords: Vec<String>,
    /// SHA256 hash of file content
    pub file_hash: String,
}

impl TemplateRecord {
    /// Create a new template record.
    #[must_use]
    pub fn new(
        template_name: String,
        description: String,
        skill_name: String,
        file_path: String,
        variables: Vec<String>,
    ) -> Self {
        Self {
            template_name,
            description,
            skill_name,
            file_path,
            variables,
            content_preview: String::new(),
            keywords: Vec::new(),
            file_hash: String::new(),
        }
    }
}

// =============================================================================
// Reference Record - Markdown documentation (for RAG)
// =============================================================================

/// A discovered reference document from references/ directory.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct ReferenceRecord {
    /// Reference name relative to skill (e.g., "git/smart-commit-workflow.md")
    pub ref_name: String,
    /// Title extracted from markdown (first H1 or filename)
    pub title: String,
    /// Parent skill name
    pub skill_name: String,
    /// Physical file path
    pub file_path: String,
    /// Content preview (first 500 chars)
    pub content_preview: String,
    /// Keywords extracted from headings and content
    pub keywords: Vec<String>,
    /// Section headings found in the document
    pub sections: Vec<String>,
    /// SHA256 hash of file content
    pub file_hash: String,
}

impl ReferenceRecord {
    /// Create a new reference record.
    #[must_use]
    pub fn new(ref_name: String, title: String, skill_name: String, file_path: String) -> Self {
        Self {
            ref_name,
            title,
            skill_name,
            file_path,
            content_preview: String::new(),
            keywords: Vec::new(),
            sections: Vec::new(),
            file_hash: String::new(),
        }
    }
}

// =============================================================================
// Asset Record - Static resources (guides, docs)
// =============================================================================

/// A discovered asset from assets/ directory.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct AssetRecord {
    /// Asset name relative to skill (e.g., "git/Backlog.md")
    pub asset_name: String,
    /// Title extracted from content
    pub title: String,
    /// Parent skill name
    pub skill_name: String,
    /// Physical file path
    pub file_path: String,
    /// Content preview
    pub content_preview: String,
    /// Keywords for search
    pub keywords: Vec<String>,
    /// SHA256 hash of file content
    pub file_hash: String,
}

impl AssetRecord {
    /// Create a new asset record.
    #[must_use]
    pub fn new(asset_name: String, title: String, skill_name: String, file_path: String) -> Self {
        Self {
            asset_name,
            title,
            skill_name,
            file_path,
            content_preview: String::new(),
            keywords: Vec::new(),
            file_hash: String::new(),
        }
    }
}

// =============================================================================
// Data Record - Data files (JSON, CSV, etc.)
// =============================================================================

/// A discovered data file from data/ directory.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct DataRecord {
    /// Data file name relative to skill (e.g., "git/config.json")
    pub data_name: String,
    /// Data format (json, csv, yaml, etc.)
    pub format: String,
    /// Parent skill name
    pub skill_name: String,
    /// Physical file path
    pub file_path: String,
    /// Top-level keys/fields in the data
    pub fields: Vec<String>,
    /// Content preview
    pub content_preview: String,
    /// Keywords for search
    pub keywords: Vec<String>,
    /// SHA256 hash of file content
    pub file_hash: String,
}

impl DataRecord {
    /// Create a new data record.
    #[must_use]
    pub fn new(
        data_name: String,
        format: String,
        skill_name: String,
        file_path: String,
        fields: Vec<String>,
    ) -> Self {
        Self {
            data_name,
            format,
            skill_name,
            file_path,
            fields,
            content_preview: String::new(),
            keywords: Vec::new(),
            file_hash: String::new(),
        }
    }
}

// =============================================================================
// Test Record - Test files
// =============================================================================

/// A discovered test file from tests/ directory.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct TestRecord {
    /// Test name relative to skill (e.g., "git/test_git_commands.py")
    pub test_name: String,
    /// Parent skill name
    pub skill_name: String,
    /// Physical file path
    pub file_path: String,
    /// Test function names found
    pub test_functions: Vec<String>,
    /// Test class names found
    pub test_classes: Vec<String>,
    /// Docstring content
    pub docstring: String,
    /// Keywords for search
    pub keywords: Vec<String>,
    /// SHA256 hash of file content
    pub file_hash: String,
}

impl TestRecord {
    /// Create a new test record.
    #[must_use]
    pub fn new(
        test_name: String,
        skill_name: String,
        file_path: String,
        test_functions: Vec<String>,
        test_classes: Vec<String>,
    ) -> Self {
        Self {
            test_name,
            skill_name,
            file_path,
            test_functions,
            test_classes,
            docstring: String::new(),
            keywords: Vec::new(),
            file_hash: String::new(),
        }
    }
}

/// Scan configuration for a skill directory.
#[derive(Debug, Clone)]
pub struct ScanConfig {
    /// Base path to skills directory
    pub skills_dir: PathBuf,
    /// Include optional directories (templates, tests, etc.)
    pub include_optional: bool,
    /// Skip validation (for faster scanning)
    pub skip_validation: bool,
}

impl Default for ScanConfig {
    fn default() -> Self {
        Self {
            skills_dir: PathBuf::from("assets/skills"),
            include_optional: true,
            skip_validation: false,
        }
    }
}

impl ScanConfig {
    /// Create a default configuration.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Set the skills directory.
    #[must_use]
    pub fn with_skills_dir(mut self, dir: impl Into<PathBuf>) -> Self {
        self.skills_dir = dir.into();
        self
    }

    /// Enable/disable optional directory scanning.
    #[must_use]
    pub fn include_optional(mut self, include: bool) -> Self {
        self.include_optional = include;
        self
    }

    /// Enable/disable validation.
    #[must_use]
    pub fn skip_validation(mut self, skip: bool) -> Self {
        self.skip_validation = skip;
        self
    }
}

// =============================================================================
// Skill Structure - Canonical structure from settings.yaml
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

impl Default for SkillStructure {
    fn default() -> Self {
        // Default structure matching settings.yaml
        Self {
            required: vec![
                StructureItem {
                    path: "SKILL.md".to_string(),
                    description: "Skill metadata (YAML frontmatter) and system prompts".to_string(),
                    item_type: "file".to_string(),
                },
                // tools.py is deprecated - no longer required
            ],
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
// Reference Path - Strongly typed path for require_refs
// =============================================================================

/// Strongly-typed reference path for external documentation.
///
/// Ensures:
/// - Not empty
/// - Valid UTF-8
/// - No absolute paths (security)
/// - No path traversal ".." sequences
/// - Valid file extension (.md, .pdf, .txt, etc.)
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, SchemarsJsonSchema)]
#[serde(try_from = "String", into = "String")]
pub struct ReferencePath(String);

impl ReferencePath {
    /// Valid extensions for reference files.
    const VALID_EXTENSIONS: &[&str] = &["md", "pdf", "txt", "html", "json", "yaml", "yml"];

    /// Create a new ReferencePath from a string.
    ///
    /// Returns `Err` if the path is invalid.
    pub fn new(path: impl Into<String>) -> Result<Self, String> {
        let path = path.into();

        // Check not empty
        if path.trim().is_empty() {
            return Err("Reference path cannot be empty".to_string());
        }

        // Check no absolute paths
        if path.starts_with('/') {
            return Err(format!(
                "Reference path must be relative, got absolute path: {}",
                path
            ));
        }

        // Check no path traversal
        if path.contains("..") {
            return Err(format!(
                "Reference path cannot contain path traversal '..': {}",
                path
            ));
        }

        // Check valid extension
        let ext = path.split('.').last().unwrap_or("");
        if !ext.is_empty() && !Self::VALID_EXTENSIONS.contains(&ext) {
            return Err(format!(
                "Invalid reference file extension '{}'. Valid: {:?}",
                ext,
                Self::VALID_EXTENSIONS
            ));
        }

        Ok(Self(path))
    }

    /// Get the reference path as a string slice.
    #[must_use]
    pub fn as_str(&self) -> &str {
        &self.0
    }

    /// Get the file extension.
    #[must_use]
    pub fn extension(&self) -> Option<&str> {
        self.0.split('.').last()
    }

    /// Get the parent directory.
    #[must_use]
    pub fn parent(&self) -> Option<&str> {
        self.0.rsplitn(2, '/').nth(1)
    }
}

impl std::fmt::Display for ReferencePath {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl From<ReferencePath> for String {
    fn from(val: ReferencePath) -> Self {
        val.0
    }
}

impl TryFrom<String> for ReferencePath {
    type Error = String;

    fn try_from(value: String) -> Result<Self, Self::Error> {
        Self::new(value)
    }
}

// =============================================================================
// Skill Index Entry - Full skill representation for skill_index.json
// =============================================================================

/// Represents a complete skill entry for the JSON index file.
///
/// This struct contains all fields needed for skill_index.json including
/// metadata from SKILL.md frontmatter and discovered tools from scripts.
#[derive(Debug, Clone, Serialize, Deserialize, SchemarsJsonSchema, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct SkillIndexEntry {
    /// Skill name (from frontmatter or directory name)
    pub name: String,
    /// Human-readable description
    pub description: String,
    /// Semantic version
    pub version: String,
    /// Path to skill directory
    pub path: String,
    /// Discovered tools (from script scanning)
    pub tools: Vec<IndexToolEntry>,
    /// Routing keywords for semantic search
    pub routing_keywords: Vec<String>,
    /// Supported intents
    pub intents: Vec<String>,
    /// Skill authors
    pub authors: Vec<String>,
    /// Available documentation types
    #[serde(default)]
    pub docs_available: DocsAvailable,
    /// Open source compliance info
    #[serde(default)]
    pub oss_compliant: Vec<String>,
    /// Compliance details
    #[serde(default)]
    pub compliance_details: Vec<String>,
    /// External documentation references (from frontmatter)
    #[serde(default)]
    pub require_refs: Vec<ReferencePath>,
}

/// Tool entry in the skill index.
#[derive(Debug, Clone, Serialize, Deserialize, SchemarsJsonSchema, PartialEq, Eq)]
pub struct IndexToolEntry {
    /// Tool name (e.g., "writer.write_text")
    pub name: String,
    /// Tool description
    pub description: String,
}

/// Documentation availability flags.
#[derive(Debug, Clone, Serialize, Deserialize, SchemarsJsonSchema, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct DocsAvailable {
    /// Whether SKILL.md exists
    #[serde(default)]
    pub skill_md: bool,
    /// Whether README.md exists
    #[serde(default)]
    pub readme: bool,
    /// Whether a guide file exists
    #[serde(default)]
    pub guide: bool,
    /// Whether prompts directory exists
    #[serde(default)]
    pub prompts: bool,
    /// Whether tests directory exists
    #[serde(default)]
    pub tests: bool,
}

impl Default for DocsAvailable {
    fn default() -> Self {
        Self {
            skill_md: true,
            readme: false,
            guide: false,
            prompts: false,
            tests: false,
        }
    }
}

impl SkillIndexEntry {
    /// Create a new skill index entry.
    #[must_use]
    pub fn new(name: String, description: String, version: String, path: String) -> Self {
        Self {
            name,
            description,
            version,
            path,
            tools: Vec::new(),
            routing_keywords: Vec::new(),
            intents: Vec::new(),
            authors: vec!["omni-dev-fusion".to_string()],
            docs_available: DocsAvailable::default(),
            oss_compliant: Vec::new(),
            compliance_details: Vec::new(),
            require_refs: Vec::new(),
        }
    }

    /// Add a tool to this entry.
    pub fn add_tool(&mut self, tool: IndexToolEntry) {
        self.tools.push(tool);
    }

    /// Check if this skill has any tools.
    #[must_use]
    pub fn has_tools(&self) -> bool {
        !self.tools.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_skill_metadata_default() {
        let metadata = SkillMetadata::default();
        assert!(metadata.skill_name.is_empty());
        assert!(metadata.version.is_empty());
        assert!(metadata.routing_keywords.is_empty());
    }

    #[test]
    fn test_skill_metadata_with_name() {
        let metadata = SkillMetadata::with_name("writer");
        assert_eq!(metadata.skill_name, "writer");
    }

    #[test]
    fn test_skill_metadata_has_keywords() {
        let mut metadata = SkillMetadata::default();
        assert!(!metadata.has_routing_keywords());

        metadata.routing_keywords = vec!["write".to_string(), "edit".to_string()];
        assert!(metadata.has_routing_keywords());
    }

    #[test]
    fn test_skill_metadata_keywords_summary() {
        let metadata = SkillMetadata {
            skill_name: "writer".to_string(),
            routing_keywords: vec!["write".to_string(), "edit".to_string()],
            ..SkillMetadata::default()
        };

        assert_eq!(metadata.keywords_summary(), "write, edit");
    }

    #[test]
    fn test_tool_record_new() {
        let record = ToolRecord::new(
            "writer.write_text".to_string(),
            "Write text to file".to_string(),
            "writer".to_string(),
            "/path/to/scripts/text.py".to_string(),
            "write_text".to_string(),
        );

        assert_eq!(record.tool_name, "writer.write_text");
        assert_eq!(record.skill_name, "writer");
        assert_eq!(record.function_name, "write_text");
    }

    #[test]
    fn test_scan_config_defaults() {
        let config = ScanConfig::default();
        assert_eq!(config.skills_dir, PathBuf::from("assets/skills"));
        assert!(config.include_optional);
        assert!(!config.skip_validation);
    }

    #[test]
    fn test_scan_config_builder() {
        let config = ScanConfig::new()
            .with_skills_dir("/custom/skills")
            .include_optional(false)
            .skip_validation(true);

        assert_eq!(config.skills_dir, PathBuf::from("/custom/skills"));
        assert!(!config.include_optional);
        assert!(config.skip_validation);
    }
}
