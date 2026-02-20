//! Skill Metadata - Parsed metadata from SKILL.md YAML frontmatter.
//!
//! This module contains the `SkillMetadata` struct which represents the metadata
//! extracted from the YAML frontmatter in a skill's SKILL.md file.
//!
//! Also defines `SkillStructure` which represents the canonical skill structure
//! as defined in `settings.yaml` under `skills.architecture.structure`.

use schemars::JsonSchema as SchemarsJsonSchema;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// Parsed skill metadata from SKILL.md YAML frontmatter.
#[derive(Debug, Clone, Default, Deserialize, Serialize, SchemarsJsonSchema, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub struct SkillMetadata {
    /// Unique name identifying this skill.
    #[serde(default)]
    pub skill_name: String,
    /// Semantic version string (e.g., "1.0.0").
    #[serde(default)]
    pub version: String,
    /// Human-readable description of the skill's purpose.
    #[serde(default)]
    pub description: String,
    /// Keywords used for semantic routing and skill selection.
    #[serde(default)]
    pub routing_keywords: Vec<String>,
    /// Authors who created or maintain this skill.
    #[serde(default)]
    pub authors: Vec<String>,
    /// Intents this skill can handle (for intent-based routing).
    #[serde(default)]
    pub intents: Vec<String>,
    /// Paths to required reference files or skills.
    #[serde(default)]
    pub require_refs: Vec<ReferencePath>,
    /// Repository URL for the skill source code.
    #[serde(default)]
    pub repository: String,
    /// Permissions required by this skill (e.g., "filesystem:read", "network:http")
    /// Zero Trust: Empty permissions means NO access to any capabilities.
    #[serde(default)]
    pub permissions: Vec<String>,
}

impl SkillMetadata {
    /// Creates a new empty `SkillMetadata` instance.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Creates a `SkillMetadata` with the specified skill name.
    #[must_use]
    pub fn with_name(name: impl Into<String>) -> Self {
        Self {
            skill_name: name.into(),
            ..Self::default()
        }
    }

    /// Returns `true` if the skill has routing keywords defined.
    #[must_use]
    pub fn has_routing_keywords(&self) -> bool {
        !self.routing_keywords.is_empty()
    }

    /// Returns a comma-separated summary of routing keywords.
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
    /// Rule type: "`file_exists`" or "`file_pattern`"
    #[serde(rename = "type")]
    pub rule_type: String,
    /// Glob pattern or filename to match
    pub pattern: String,
}

impl SnifferRule {
    /// Creates a new `SnifferRule` with the given type and pattern.
    pub fn new(rule_type: impl Into<String>, pattern: impl Into<String>) -> Self {
        Self {
            rule_type: rule_type.into(),
            pattern: pattern.into(),
        }
    }
}

// =============================================================================
// Tool Annotations - MCP Protocol Safety Annotations
// =============================================================================

/// Safety and behavior annotations for tools (MCP Protocol compliant).
///
/// These annotations help the agent understand the safety implications
/// of using a tool, enabling smarter execution decisions.
#[derive(Debug, Clone, Default, Deserialize, Serialize, PartialEq, Eq, SchemarsJsonSchema)]
#[serde(rename_all = "camelCase")]
#[allow(clippy::struct_excessive_bools)]
pub struct ToolAnnotations {
    /// Read-only operations that don't modify system state.
    #[serde(default)]
    pub read_only: bool,
    /// Operations that modify or delete data.
    #[serde(default)]
    pub destructive: bool,
    /// Operations that can be safely repeated without side effects.
    #[serde(default)]
    pub idempotent: bool,
    /// Operations that interact with external/open systems.
    #[serde(default)]
    pub open_world: bool,
}

impl ToolAnnotations {
    /// Creates a new `ToolAnnotations` with all defaults (safe defaults).
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Creates annotations for a read-only tool.
    #[must_use]
    pub fn read_only() -> Self {
        Self {
            read_only: true,
            destructive: false,
            idempotent: true,
            open_world: false,
        }
    }

    /// Creates annotations for a destructive tool.
    #[must_use]
    pub fn destructive() -> Self {
        Self {
            read_only: false,
            destructive: true,
            idempotent: false,
            open_world: false,
        }
    }

    /// Creates annotations for a network-accessible tool.
    #[must_use]
    pub fn open_world() -> Self {
        Self {
            read_only: false,
            destructive: false,
            idempotent: false,
            open_world: true,
        }
    }
}

// =============================================================================
// Decorator Arguments - Extracted from @skill_command decorator
// =============================================================================

/// Arguments extracted from @`skill_command` decorator kwargs.
#[derive(Debug, Clone, Default, Deserialize, Serialize, PartialEq, Eq)]
pub struct DecoratorArgs {
    /// Explicit tool name from decorator (overrides function name).
    #[serde(default)]
    pub name: Option<String>,
    /// Human-readable description of what the tool does.
    #[serde(default)]
    pub description: Option<String>,
    /// Category for organizing tools (e.g., "read", "write", "query").
    #[serde(default)]
    pub category: Option<String>,
    /// Whether this tool modifies external state.
    #[serde(default)]
    pub destructive: Option<bool>,
    /// Whether this tool only reads data.
    #[serde(default)]
    pub read_only: Option<bool>,
    /// MCP Resource URI.  When set, this command is also exposed as a
    /// read-only MCP Resource at the given URI (e.g. `omni://skill/git/status`).
    #[serde(default)]
    pub resource_uri: Option<String>,
}

// =============================================================================
// Tool Record
// =============================================================================

/// Represents a discovered tool/function within a skill.
///
/// This struct is enriched with metadata extracted from:
/// - AST parsing of decorator kwargs
/// - Function signature analysis
/// - Docstring parsing
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct ToolRecord {
    /// Name of the tool function.
    pub tool_name: String,
    /// Human-readable description of what the tool does.
    pub description: String,
    /// Name of the skill this tool belongs to.
    pub skill_name: String,
    /// File path where the tool is defined.
    pub file_path: String,
    /// Name of the function implementing this tool.
    pub function_name: String,
    /// Execution mode (e.g., "sync", "async", "script").
    pub execution_mode: String,
    /// Keywords for tool discovery and routing.
    pub keywords: Vec<String>,
    /// Intents this tool can fulfill (inherited from skill).
    #[serde(default)]
    pub intents: Vec<String>,
    /// Hash of the source file for change detection.
    pub file_hash: String,
    /// JSON schema for tool input validation.
    #[serde(default)]
    pub input_schema: String,
    /// Documentation string from the function docstring.
    #[serde(default)]
    pub docstring: String,
    /// Category inferred from decorator or function signature.
    #[serde(default)]
    pub category: String,
    /// MCP protocol safety annotations.
    #[serde(default)]
    pub annotations: ToolAnnotations,
    /// Parameter names inferred from function signature.
    #[serde(default)]
    pub parameters: Vec<String>,
    /// Full tool names (skill.tool) this skill tool refers to for docs (`SkillToolsRefers`).
    #[serde(default)]
    pub skill_tools_refers: Vec<String>,
    /// MCP Resource URI.  Non-empty means this tool is also an MCP Resource.
    #[serde(default)]
    pub resource_uri: String,
}

impl ToolRecord {
    /// Creates a new `ToolRecord` with required fields.
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
            intents: Vec::new(),
            file_hash: String::new(),
            input_schema: String::new(),
            docstring: String::new(),
            category: String::new(),
            annotations: ToolAnnotations::default(),
            parameters: Vec::new(),
            skill_tools_refers: Vec::new(),
            resource_uri: String::new(),
        }
    }

    /// Creates a fully populated `ToolRecord` with all enrichment data.
    #[must_use]
    #[allow(clippy::too_many_arguments)]
    pub fn with_enrichment(
        tool_name: String,
        description: String,
        skill_name: String,
        file_path: String,
        function_name: String,
        execution_mode: String,
        keywords: Vec<String>,
        intents: Vec<String>,
        file_hash: String,
        docstring: String,
        category: String,
        annotations: ToolAnnotations,
        parameters: &[super::skill_command::parser::ParsedParameter],
        input_schema: String,
        skill_tools_refers: Vec<String>,
        resource_uri: String,
    ) -> Self {
        // Extract parameter names from ParsedParameter vector
        let param_names: Vec<String> = parameters.iter().map(|p| p.name.clone()).collect();
        Self {
            tool_name,
            description,
            skill_name,
            file_path,
            function_name,
            execution_mode,
            keywords,
            intents,
            file_hash,
            input_schema,
            docstring,
            category,
            annotations,
            parameters: param_names,
            skill_tools_refers,
            resource_uri,
        }
    }
}

// =============================================================================
// Reference Path
// =============================================================================

/// A validated relative path to a reference document (md, pdf, txt, html, json, yaml, yml).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, SchemarsJsonSchema)]
#[serde(try_from = "String", into = "String")]
pub struct ReferencePath(String);

impl ReferencePath {
    const VALID_EXTENSIONS: &[&str] = &["md", "pdf", "txt", "html", "json", "yaml", "yml"];

    /// Creates a new `ReferencePath` after validating the path format.
    ///
    /// # Errors
    ///
    /// Returns an error when the path is empty, absolute, contains `..`,
    /// or has an unsupported file extension.
    pub fn new(path: impl Into<String>) -> Result<Self, String> {
        let path = path.into();
        if path.trim().is_empty() {
            return Err("Reference path cannot be empty".to_string());
        }
        if path.starts_with('/') {
            return Err(format!("Reference path must be relative: {path}"));
        }
        if path.contains("..") {
            return Err(format!("Reference path cannot contain '..': {path}"));
        }
        let ext = path.rsplit('.').next().unwrap_or("");
        if !ext.is_empty() && !Self::VALID_EXTENSIONS.contains(&ext) {
            return Err(format!("Invalid reference extension '{ext}'"));
        }
        Ok(Self(path))
    }

    /// Returns the reference path as a string slice.
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

/// Represents a skill entry in the skill index (skills.json).
#[derive(Debug, Clone, Serialize, Deserialize, SchemarsJsonSchema, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct SkillIndexEntry {
    /// Name of the skill.
    pub name: String,
    /// Human-readable description.
    pub description: String,
    /// Semantic version.
    pub version: String,
    /// Relative path to the skill directory.
    pub path: String,
    /// List of tools provided by this skill.
    pub tools: Vec<IndexToolEntry>,
    /// Keywords for semantic routing.
    pub routing_keywords: Vec<String>,
    /// Intents this skill handles.
    pub intents: Vec<String>,
    /// Authors of the skill.
    pub authors: Vec<String>,
    /// Documentation availability status.
    #[serde(default)]
    pub docs_available: DocsAvailable,
    /// Open source compliance status.
    #[serde(default)]
    pub oss_compliant: Vec<String>,
    /// Compliance check details.
    #[serde(default)]
    pub compliance_details: Vec<String>,
    /// Required reference paths.
    #[serde(default)]
    pub require_refs: Vec<ReferencePath>,
    /// Sniffer rules for skill activation (declarative).
    #[serde(default)]
    pub sniffing_rules: Vec<SnifferRule>,
    /// Permissions declared by this skill (Zero Trust: empty = no access).
    #[serde(default)]
    pub permissions: Vec<String>,
    /// Reference docs from `references/*.md` (`metadata.for_tools` per doc).
    #[serde(default)]
    pub references: Vec<ReferenceRecord>,
}

/// A tool entry in the skill index.
#[derive(Debug, Clone, Serialize, Deserialize, SchemarsJsonSchema, PartialEq, Eq)]
pub struct IndexToolEntry {
    /// Name of the tool.
    pub name: String,
    /// Description of what the tool does.
    pub description: String,
    /// Category for organizing tools (e.g., "read", "write", "query").
    #[serde(default)]
    pub category: String,
    /// JSON schema for tool input validation (MCP protocol format).
    #[serde(default)]
    pub input_schema: String,
    /// Hash of the source file for incremental sync.
    #[serde(default)]
    pub file_hash: String,
}

/// Documentation availability status for a skill.
#[derive(Debug, Clone, Serialize, Deserialize, SchemarsJsonSchema, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct DocsAvailable {
    /// Whether SKILL.md exists.
    #[serde(default)]
    pub skill_md: bool,
    /// Whether README.md exists.
    #[serde(default)]
    pub readme: bool,
    /// Whether tests exist.
    #[serde(default)]
    pub tests: bool,
}

impl Default for DocsAvailable {
    fn default() -> Self {
        Self {
            skill_md: true,
            readme: false,
            tests: false,
        }
    }
}

impl SkillIndexEntry {
    /// Creates a new `SkillIndexEntry` with required fields.
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
            references: Vec::new(),
        }
    }

    /// Adds a tool to this skill entry.
    pub fn add_tool(&mut self, tool: IndexToolEntry) {
        self.tools.push(tool);
    }

    /// Returns `true` if the skill has at least one tool.
    #[must_use]
    pub fn has_tools(&self) -> bool {
        !self.tools.is_empty()
    }
}

// =============================================================================
// Skill Structure
// =============================================================================

/// Represents the canonical skill structure as defined in settings.yaml.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SkillStructure {
    /// Required items that must exist in a valid skill.
    pub required: Vec<StructureItem>,
    /// Default items that are created when generating a new skill.
    pub default: Vec<StructureItem>,
    /// Optional items that may be present.
    #[serde(default)]
    pub optional: Vec<StructureItem>,
}

/// A single item in the skill structure definition.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StructureItem {
    /// Path or pattern for the item.
    pub path: String,
    /// Description of what this item represents.
    #[serde(default)]
    pub description: String,
    /// Type of item ("file" or "dir").
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
    /// Creates a new `SkillStructure` with default values.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Returns the paths of all default directories.
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

/// Represents a discovered template file within a skill.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct TemplateRecord {
    /// Name of the template.
    pub template_name: String,
    /// Description of the template's purpose.
    pub description: String,
    /// Skill this template belongs to.
    pub skill_name: String,
    /// Path to the template file.
    pub file_path: String,
    /// Variable names used in the template.
    pub variables: Vec<String>,
    /// Preview of the template content.
    #[serde(default)]
    pub content_preview: String,
    /// Keywords for template discovery.
    #[serde(default)]
    pub keywords: Vec<String>,
    /// Hash of the template file.
    #[serde(default)]
    pub file_hash: String,
}

impl TemplateRecord {
    /// Creates a new `TemplateRecord` with required fields.
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

/// Deserialize a single string or array of strings into `Vec<String>`.
fn de_string_or_vec<'de, D>(deserializer: D) -> Result<Vec<String>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    use serde::de::{self, Visitor};
    use std::fmt;
    struct StringOrVec;
    impl<'de> Visitor<'de> for StringOrVec {
        type Value = Vec<String>;
        fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
            formatter.write_str("a string or array of strings")
        }
        fn visit_str<E: de::Error>(self, v: &str) -> Result<Vec<String>, E> {
            Ok(if v.is_empty() {
                vec![]
            } else {
                vec![v.to_string()]
            })
        }
        fn visit_seq<A: serde::de::SeqAccess<'de>>(
            self,
            mut seq: A,
        ) -> Result<Vec<String>, A::Error> {
            let mut out = Vec::new();
            while let Some(s) = seq.next_element::<String>()? {
                if !s.is_empty() {
                    out.push(s);
                }
            }
            Ok(out)
        }
    }
    deserializer.deserialize_any(StringOrVec)
}

/// Deserialize `Option` of string or array of strings into `Option<Vec<String>>`.
fn de_opt_string_or_vec<'de, D>(deserializer: D) -> Result<Option<Vec<String>>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    use serde::de::{self, Visitor};
    use std::fmt;
    struct OptStringOrVec;
    impl<'de> Visitor<'de> for OptStringOrVec {
        type Value = Option<Vec<String>>;
        fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
            formatter.write_str("optional string or array of strings")
        }
        fn visit_none<E: de::Error>(self) -> Result<Option<Vec<String>>, E> {
            Ok(None)
        }
        fn visit_some<D2: serde::Deserializer<'de>>(
            self,
            d: D2,
        ) -> Result<Option<Vec<String>>, D2::Error> {
            let v = de_string_or_vec(d)?;
            Ok(if v.is_empty() { None } else { Some(v) })
        }
    }
    deserializer.deserialize_option(OptStringOrVec)
}

/// Represents a reference document discovered in a skill's `references/` directory.
///
/// See `docs/reference/skill-data-hierarchy-and-references.md`: references are
/// subordinate to the skill; each may be tied to one or more skills/tools (e.g. graph docs).
/// `for_skills` and `for_tools` are lists so one reference can apply to multiple skills or tools.
#[derive(Debug, Clone, Deserialize, Serialize, SchemarsJsonSchema, PartialEq, Eq)]
pub struct ReferenceRecord {
    /// Name of the reference (e.g. filename stem).
    pub ref_name: String,
    /// Title of the reference document (from frontmatter or first heading).
    pub title: String,
    /// Primary skill (first of `for_skills` or parent path); kept for backward compatibility.
    pub skill_name: String,
    /// Path to the reference file (relative to repo or absolute).
    pub file_path: String,
    /// List of skills this reference applies to; derived from `for_tools` (skill part of each `skill.tool`) or from path when `for_tools` is absent.
    #[serde(default, deserialize_with = "de_string_or_vec")]
    pub for_skills: Vec<String>,
    /// If set, list of full tool names this reference is for (e.g. `["git.smart_commit", "researcher.run_research_graph"]`).
    #[serde(default, deserialize_with = "de_opt_string_or_vec", alias = "for_tool")]
    pub for_tools: Option<Vec<String>>,
    /// Document type: `"reference"` for references/*.md; `"comprehensive"` reserved for SKILL.md.
    #[serde(default = "default_ref_doc_type")]
    pub doc_type: String,
    /// Preview of the content.
    #[serde(default)]
    pub content_preview: String,
    /// Keywords for reference discovery.
    #[serde(default)]
    pub keywords: Vec<String>,
    /// Section headings in the document.
    #[serde(default)]
    pub sections: Vec<String>,
    /// Hash of the reference file.
    #[serde(default)]
    pub file_hash: String,
}

fn default_ref_doc_type() -> String {
    "reference".to_string()
}

impl ReferenceRecord {
    /// Creates a new `ReferenceRecord` with required fields.
    #[must_use]
    pub fn new(ref_name: String, title: String, skill_name: String, file_path: String) -> Self {
        let for_skills = if skill_name.is_empty() {
            vec![]
        } else {
            vec![skill_name.clone()]
        };
        Self {
            ref_name,
            title,
            skill_name,
            file_path,
            for_skills,
            for_tools: None,
            doc_type: "reference".to_string(),
            content_preview: String::new(),
            keywords: Vec::new(),
            sections: Vec::new(),
            file_hash: String::new(),
        }
    }

    /// Builder: set optional list of tools this reference is for.
    #[must_use]
    pub fn with_for_tools(mut self, for_tools: Option<Vec<String>>) -> Self {
        self.for_tools = for_tools;
        self
    }

    /// Returns true if this reference applies to the given full tool name.
    #[must_use]
    pub fn applies_to_tool(&self, full_tool_name: &str) -> bool {
        self.for_tools
            .as_ref()
            .is_some_and(|v| v.iter().any(|t| t.as_str() == full_tool_name))
    }
}

// =============================================================================
// Asset Record
// =============================================================================

/// Represents an asset file discovered in a skill.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct AssetRecord {
    /// Name of the asset.
    pub asset_name: String,
    /// Title of the asset.
    pub title: String,
    /// Skill this asset belongs to.
    pub skill_name: String,
    /// Path to the asset file.
    pub file_path: String,
    /// Preview of the asset content.
    #[serde(default)]
    pub content_preview: String,
    /// Keywords for asset discovery.
    #[serde(default)]
    pub keywords: Vec<String>,
    /// Hash of the asset file.
    #[serde(default)]
    pub file_hash: String,
}

impl AssetRecord {
    /// Creates a new `AssetRecord` with required fields.
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

/// Represents a data file discovered in a skill.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct DataRecord {
    /// Name of the data.
    pub data_name: String,
    /// Format of the data (e.g., "json", "csv").
    pub format: String,
    /// Skill this data belongs to.
    pub skill_name: String,
    /// Path to the data file.
    pub file_path: String,
    /// Field names in the data.
    pub fields: Vec<String>,
    /// Preview of the data content.
    #[serde(default)]
    pub content_preview: String,
    /// Keywords for data discovery.
    #[serde(default)]
    pub keywords: Vec<String>,
    /// Hash of the data file.
    #[serde(default)]
    pub file_hash: String,
}

impl DataRecord {
    /// Creates a new `DataRecord` with required fields.
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

/// Represents a test file discovered in a skill.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct TestRecord {
    /// Name of the test.
    pub test_name: String,
    /// Skill this test belongs to.
    pub skill_name: String,
    /// Path to the test file.
    pub file_path: String,
    /// Names of test functions.
    pub test_functions: Vec<String>,
    /// Names of test classes.
    pub test_classes: Vec<String>,
    /// Docstring of the test module.
    #[serde(default)]
    pub docstring: String,
    /// Keywords for test discovery.
    #[serde(default)]
    pub keywords: Vec<String>,
    /// Hash of the test file.
    #[serde(default)]
    pub file_hash: String,
}

impl TestRecord {
    /// Creates a new `TestRecord` with required fields.
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

/// Configuration for scanning skills.
#[derive(Debug, Clone)]
pub struct ScanConfig {
    /// Path to the skills directory.
    pub skills_dir: PathBuf,
    /// Whether to include optional items in the scan.
    pub include_optional: bool,
    /// Whether to skip structure validation.
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
    /// Creates a new `ScanConfig` with default values.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Sets the skills directory path.
    #[must_use]
    pub fn with_skills_dir(mut self, dir: impl Into<PathBuf>) -> Self {
        self.skills_dir = dir.into();
        self
    }
}

// Note: Comprehensive tests are in tests/

// =============================================================================
// Sync Report - For comparing scanned tools with existing index
// =============================================================================

/// Report of sync operations between scanned tools and existing index.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SyncReport {
    /// Tools that are new and need to be added.
    pub added: Vec<ToolRecord>,
    /// Tools that have changed and need to be updated.
    pub updated: Vec<ToolRecord>,
    /// Tool names that were deleted.
    pub deleted: Vec<String>,
    /// Count of unchanged tools (fast path hit).
    pub unchanged_count: usize,
}

impl SyncReport {
    /// Creates a new empty `SyncReport`.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }
}

/// Calculate sync operations between scanned tools and existing index.
///
/// Uses `file_hash` for fast-path comparison to skip unchanged tools.
///
/// Args:
///   scanned: Vector of scanned `ToolRecord` objects
///   existing: Vector of existing `IndexToolEntry` objects
///
/// Returns:
///   `SyncReport` with lists of added, updated, deleted, and unchanged tools.
#[must_use]
pub fn calculate_sync_ops(scanned: Vec<ToolRecord>, existing: &[IndexToolEntry]) -> SyncReport {
    let mut report = SyncReport::new();

    // Build a map of existing tools by name for quick lookup
    let existing_map: std::collections::HashMap<String, &IndexToolEntry> = existing
        .iter()
        .map(|tool| (tool.name.clone(), tool))
        .collect();

    // Track which existing tools were matched
    let mut matched_existing: std::collections::HashSet<String> = std::collections::HashSet::new();

    for tool in scanned {
        let tool_name = format!("{}.{}", tool.skill_name, tool.tool_name);

        if let Some(existing_tool) = existing_map.get(&tool_name) {
            // Tool exists - check if it changed via file_hash
            if tool.file_hash == existing_tool.file_hash {
                // Unchanged - fast path
                report.unchanged_count += 1;
            } else {
                // Changed - needs update
                report.updated.push(tool);
            }
            matched_existing.insert(tool_name);
        } else {
            // New tool - needs to be added
            report.added.push(tool);
        }
    }

    // Find deleted tools (in existing but not in scanned)
    for (tool_name, _) in existing_map {
        if !matched_existing.contains(&tool_name) {
            report.deleted.push(tool_name);
        }
    }

    report
}

// =============================================================================
// Resource Record - MCP Resource metadata
// =============================================================================

/// Represents a discovered MCP Resource from @`skill_resource` decorated functions.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct ResourceRecord {
    /// Resource name (from decorator or function name).
    pub name: String,
    /// Human-readable description of the resource.
    pub description: String,
    /// Full resource URI (e.g., `<omni://skill/knowledge/graph_stats>`).
    pub resource_uri: String,
    /// MIME type of the resource content.
    pub mime_type: String,
    /// Name of the skill this resource belongs to.
    pub skill_name: String,
    /// File path where the resource provider is defined.
    pub file_path: String,
    /// Name of the function implementing this resource.
    pub function_name: String,
    /// Hash of the source file for change detection.
    pub file_hash: String,
}

impl ResourceRecord {
    /// Create a new `ResourceRecord`.
    #[must_use]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        name: String,
        description: String,
        resource_uri: String,
        mime_type: String,
        skill_name: String,
        file_path: String,
        function_name: String,
        file_hash: String,
    ) -> Self {
        Self {
            name,
            description,
            resource_uri,
            mime_type,
            skill_name,
            file_path,
            function_name,
            file_hash,
        }
    }
}

// =============================================================================
// Prompt Record - MCP Prompt metadata
// =============================================================================

/// Represents a discovered MCP Prompt from @prompt decorated functions.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct PromptRecord {
    /// Prompt name (from decorator or function name).
    pub name: String,
    /// Human-readable description of the prompt.
    pub description: String,
    /// Name of the skill this prompt belongs to.
    pub skill_name: String,
    /// File path where the prompt is defined.
    pub file_path: String,
    /// Name of the function implementing this prompt.
    pub function_name: String,
    /// Hash of the source file for change detection.
    pub file_hash: String,
    /// Parameter names for the prompt template.
    #[serde(default)]
    pub parameters: Vec<String>,
}

impl PromptRecord {
    /// Create a new `PromptRecord`.
    #[must_use]
    pub fn new(
        name: String,
        description: String,
        skill_name: String,
        file_path: String,
        function_name: String,
        file_hash: String,
        parameters: Vec<String>,
    ) -> Self {
        Self {
            name,
            description,
            skill_name,
            file_path,
            function_name,
            file_hash,
            parameters,
        }
    }
}
