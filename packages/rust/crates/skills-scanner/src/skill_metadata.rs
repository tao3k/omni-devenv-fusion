//! Skill Metadata - Parsed metadata from SKILL.md YAML frontmatter.
//!
//! This module contains the `SkillMetadata` struct which represents the metadata
//! extracted from the YAML frontmatter in a skill's SKILL.md file.
//!
//! Also defines `SkillStructure` which represents the canonical skill structure
//! as defined in `settings.yaml` under `skills.architecture.structure`.

use schemars::JsonSchema as SchemarsJsonSchema;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

/// Parsed skill metadata from SKILL.md YAML frontmatter.
#[derive(Debug, Clone, Deserialize, Serialize, SchemarsJsonSchema, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub struct SkillMetadata {
    #[serde(default)]
    pub skill_name: String,
    #[serde(default)]
    pub version: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub routing_keywords: Vec<String>,
    #[serde(default)]
    pub authors: Vec<String>,
    #[serde(default)]
    pub intents: Vec<String>,
    #[serde(default)]
    pub require_refs: Vec<ReferencePath>,
    #[serde(default)]
    pub repository: String,
    /// Permissions required by this skill (e.g., "filesystem:read", "network:http")
    /// Zero Trust: Empty permissions means NO access to any capabilities.
    #[serde(default)]
    pub permissions: Vec<String>,
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
            permissions: Vec::new(),
        }
    }
}

impl SkillMetadata {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    #[must_use]
    pub fn with_name(name: impl Into<String>) -> Self {
        Self {
            skill_name: name.into(),
            ..Self::default()
        }
    }

    #[must_use]
    pub fn has_routing_keywords(&self) -> bool {
        !self.routing_keywords.is_empty()
    }

    #[must_use]
    pub fn keywords_summary(&self) -> String {
        self.routing_keywords.join(", ")
    }
}

// =============================================================================
// Sniffer Rule - Declarative rules for skill activation
// =============================================================================

/// A single sniffer rule (typically from extensions/sniffer/rules.toml).
#[derive(Debug, Clone, Deserialize, Serialize, SchemarsJsonSchema, PartialEq, Eq)]
pub struct SnifferRule {
    /// Rule type: "file_exists" or "file_pattern"
    #[serde(rename = "type")]
    pub rule_type: String,
    /// Glob pattern or filename to match
    pub pattern: String,
}

impl SnifferRule {
    pub fn new(rule_type: impl Into<String>, pattern: impl Into<String>) -> Self {
        Self {
            rule_type: rule_type.into(),
            pattern: pattern.into(),
        }
    }
}

// =============================================================================
// Tool Record
// =============================================================================

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct ToolRecord {
    pub tool_name: String,
    pub description: String,
    pub skill_name: String,
    pub file_path: String,
    pub function_name: String,
    pub execution_mode: String,
    pub keywords: Vec<String>,
    pub file_hash: String,
    #[serde(default)]
    pub input_schema: String,
    #[serde(default)]
    pub docstring: String,
}

impl ToolRecord {
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
// Reference Path
// =============================================================================

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, SchemarsJsonSchema)]
#[serde(try_from = "String", into = "String")]
pub struct ReferencePath(String);

impl ReferencePath {
    const VALID_EXTENSIONS: &[&str] = &["md", "pdf", "txt", "html", "json", "yaml", "yml"];

    pub fn new(path: impl Into<String>) -> Result<Self, String> {
        let path = path.into();
        if path.trim().is_empty() {
            return Err("Reference path cannot be empty".to_string());
        }
        if path.starts_with('/') {
            return Err(format!("Reference path must be relative: {}", path));
        }
        if path.contains("..") {
            return Err(format!("Reference path cannot contain '..': {}", path));
        }
        let ext = path.split('.').last().unwrap_or("");
        if !ext.is_empty() && !Self::VALID_EXTENSIONS.contains(&ext) {
            return Err(format!("Invalid reference extension '{}'", ext));
        }
        Ok(Self(path))
    }

    #[must_use]
    pub fn as_str(&self) -> &str {
        &self.0
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
// Skill Index Entry
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize, SchemarsJsonSchema, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct SkillIndexEntry {
    pub name: String,
    pub description: String,
    pub version: String,
    pub path: String,
    pub tools: Vec<IndexToolEntry>,
    pub routing_keywords: Vec<String>,
    pub intents: Vec<String>,
    pub authors: Vec<String>,
    #[serde(default)]
    pub docs_available: DocsAvailable,
    #[serde(default)]
    pub oss_compliant: Vec<String>,
    #[serde(default)]
    pub compliance_details: Vec<String>,
    #[serde(default)]
    pub require_refs: Vec<ReferencePath>,
    /// Sniffer rules for skill activation (declarative)
    #[serde(default)]
    pub sniffing_rules: Vec<SnifferRule>,
    /// Permissions declared by this skill (Zero Trust: empty = no access)
    #[serde(default)]
    pub permissions: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, SchemarsJsonSchema, PartialEq, Eq)]
pub struct IndexToolEntry {
    pub name: String,
    pub description: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, SchemarsJsonSchema, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct DocsAvailable {
    #[serde(default)]
    pub skill_md: bool,
    #[serde(default)]
    pub readme: bool,
    #[serde(default)]
    pub guide: bool,
    #[serde(default)]
    pub prompts: bool,
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
            sniffing_rules: Vec::new(),
            permissions: Vec::new(),
        }
    }

    pub fn add_tool(&mut self, tool: IndexToolEntry) {
        self.tools.push(tool);
    }

    #[must_use]
    pub fn has_tools(&self) -> bool {
        !self.tools.is_empty()
    }
}

// =============================================================================
// Skill Structure
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SkillStructure {
    pub required: Vec<StructureItem>,
    pub default: Vec<StructureItem>,
    #[serde(default)]
    pub optional: Vec<StructureItem>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StructureItem {
    pub path: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub item_type: String,
}

impl Default for SkillStructure {
    fn default() -> Self {
        Self {
            required: vec![StructureItem {
                path: "SKILL.md".to_string(),
                description: "Skill metadata".to_string(),
                item_type: "file".to_string(),
            }],
            default: vec![
                StructureItem {
                    path: "scripts/".to_string(),
                    description: "Standalone executables".to_string(),
                    item_type: "dir".to_string(),
                },
                StructureItem {
                    path: "templates/".to_string(),
                    description: "Jinja2 templates".to_string(),
                    item_type: "dir".to_string(),
                },
                StructureItem {
                    path: "references/".to_string(),
                    description: "Markdown documentation".to_string(),
                    item_type: "dir".to_string(),
                },
            ],
            optional: Vec::new(),
        }
    }
}

impl SkillStructure {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

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
// Template Record
// =============================================================================

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct TemplateRecord {
    pub template_name: String,
    pub description: String,
    pub skill_name: String,
    pub file_path: String,
    pub variables: Vec<String>,
    #[serde(default)]
    pub content_preview: String,
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub file_hash: String,
}

impl TemplateRecord {
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
// Reference Record
// =============================================================================

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct ReferenceRecord {
    pub ref_name: String,
    pub title: String,
    pub skill_name: String,
    pub file_path: String,
    #[serde(default)]
    pub content_preview: String,
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub sections: Vec<String>,
    #[serde(default)]
    pub file_hash: String,
}

impl ReferenceRecord {
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
// Asset Record
// =============================================================================

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct AssetRecord {
    pub asset_name: String,
    pub title: String,
    pub skill_name: String,
    pub file_path: String,
    #[serde(default)]
    pub content_preview: String,
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub file_hash: String,
}

impl AssetRecord {
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
// Data Record
// =============================================================================

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct DataRecord {
    pub data_name: String,
    pub format: String,
    pub skill_name: String,
    pub file_path: String,
    pub fields: Vec<String>,
    #[serde(default)]
    pub content_preview: String,
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub file_hash: String,
}

impl DataRecord {
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
// Test Record
// =============================================================================

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct TestRecord {
    pub test_name: String,
    pub skill_name: String,
    pub file_path: String,
    pub test_functions: Vec<String>,
    pub test_classes: Vec<String>,
    #[serde(default)]
    pub docstring: String,
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub file_hash: String,
}

impl TestRecord {
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

// =============================================================================
// Scan Config
// =============================================================================

#[derive(Debug, Clone)]
pub struct ScanConfig {
    pub skills_dir: PathBuf,
    pub include_optional: bool,
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
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    #[must_use]
    pub fn with_skills_dir(mut self, dir: impl Into<PathBuf>) -> Self {
        self.skills_dir = dir.into();
        self
    }
}

// Note: Comprehensive tests are in tests/
