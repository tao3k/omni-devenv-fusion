//! Script Scanner - Direct Python Bindings
//!
//! Provides direct Python bindings for scanning skill tools.
//! Scans all directories defined in settings.yaml's skills.architecture.
//!
//! Added scan_skill() and scan_skill_from_content() for parsing
//! SKILL.md frontmatter (replaces python-frontmatter dependency).
//!
//! Enhanced with PySkillScanner for configurable scanning.

use crate::vector::PyToolRecord;
use omni_vector::{SkillScanner, ToolsScanner};
use pyo3::prelude::*;
use skills_scanner::{SkillMetadata, SkillStructure};
use std::path::Path;

/// Python wrapper for SkillMetadata
#[pyclass]
#[derive(Debug, Clone)]
pub struct PySkillMetadata {
    /// Skill name (typically derived from directory name)
    #[pyo3(get)]
    pub skill_name: String,
    /// Version from frontmatter (e.g., "1.0.0")
    #[pyo3(get)]
    pub version: String,
    /// Human-readable description of the skill
    #[pyo3(get)]
    pub description: String,
    /// Skill authors
    #[pyo3(get)]
    pub authors: Vec<String>,
    /// Keywords for semantic routing and hybrid search
    #[pyo3(get)]
    pub routing_keywords: Vec<String>,
    /// Supported intents/actions
    #[pyo3(get)]
    pub intents: Vec<String>,
    /// External documentation references
    #[pyo3(get)]
    pub require_refs: Vec<String>,
    /// Repository URL for trusted source verification
    #[pyo3(get)]
    pub repository: String,
    /// Permissions required by this skill (e.g., "filesystem:read", "network:http")
    /// Zero Trust: Empty permissions means NO access to any capabilities.
    #[pyo3(get)]
    pub permissions: Vec<String>,
}

impl From<SkillMetadata> for PySkillMetadata {
    fn from(m: SkillMetadata) -> Self {
        Self {
            skill_name: m.skill_name,
            version: m.version,
            description: m.description,
            authors: m.authors,
            routing_keywords: m.routing_keywords,
            intents: m.intents,
            require_refs: m.require_refs.into_iter().map(|r| r.to_string()).collect(),
            repository: m.repository,
            permissions: m.permissions,
        }
    }
}

/// PySkillScanner - Configurable Skill Scanner for Python
///
/// Provides configurable skill scanning with:
/// - Configurable skill structure validation
/// - Batch directory scanning
/// - Tool discovery in scripts/ directory
///
/// This is 10-50x faster than Python AST parsing for skill discovery.
///
/// # Example
///
/// ```python
/// from omni_core_rs import PySkillScanner
///
/// scanner = PySkillScanner("assets/skills")
/// skills = scanner.scan_all()
///
/// for skill in skills:
///     print(f"{skill.skill_name}: {skill.description}")
/// ```
#[pyclass]
pub struct PySkillScanner {
    inner: SkillScanner,
    tools_scanner: ToolsScanner,
    base_path: String,
}

#[pymethods]
impl PySkillScanner {
    /// Create a new skill scanner for the given base directory.
    #[new]
    #[pyo3(signature = (base_path))]
    fn new(base_path: String) -> Self {
        Self {
            inner: SkillScanner::new(),
            tools_scanner: ToolsScanner::new(),
            base_path,
        }
    }

    /// Scan all skills in the base directory.
    ///
    /// Returns a list of PySkillMetadata for all valid skills.
    ///
    /// # Returns
    ///
    /// List of PySkillMetadata objects, one per skill.
    fn scan_all(&self) -> Vec<PySkillMetadata> {
        let path = Path::new(&self.base_path);
        if !path.exists() {
            return Vec::new();
        }

        match self.inner.scan_all(path, None) {
            Ok(metadatas) => metadatas.into_iter().map(|m| m.into()).collect(),
            Err(_) => Vec::new(),
        }
    }

    /// Scan a single skill by name (relative to base path).
    ///
    /// Args:
    ///     skill_name: Name of the skill directory (e.g., "git", "writer")
    ///
    /// Returns:
    ///     PySkillMetadata if found, None otherwise.
    fn scan_skill(&self, skill_name: String) -> Option<PySkillMetadata> {
        let skill_path = Path::new(&self.base_path).join(&skill_name);
        if !skill_path.exists() {
            return None;
        }

        match self.inner.scan_skill(&skill_path, None) {
            Ok(Some(metadata)) => Some(metadata.into()),
            Ok(None) | Err(_) => None,
        }
    }

    /// Scan a skill and discover its tools.
    ///
    /// Scans the SKILL.md for metadata AND the scripts/ directory
    /// for @skill_command decorated functions.
    ///
    /// Args:
    ///     skill_name: Name of the skill directory
    ///
    /// Returns:
    ///     Tuple of (PySkillMetadata, List[PyToolRecord])
    fn scan_skill_with_tools(
        &self,
        skill_name: String,
    ) -> Option<(PySkillMetadata, Vec<PyToolRecord>)> {
        let skill_path = Path::new(&self.base_path).join(&skill_name);
        if !skill_path.exists() {
            return None;
        }

        match self.inner.scan_skill(&skill_path, None) {
            Ok(Some(metadata)) => {
                let scripts_path = skill_path.join("scripts");
                let tools = if scripts_path.exists() {
                    match self.tools_scanner.scan_scripts(
                        &scripts_path,
                        &metadata.skill_name,
                        &metadata.routing_keywords,
                        &[],
                    ) {
                        Ok(t) => t.into_iter().map(|t| t.into()).collect(),
                        Err(_) => Vec::new(),
                    }
                } else {
                    Vec::new()
                };
                Some((metadata.into(), tools))
            }
            Ok(None) | Err(_) => None,
        }
    }

    /// Scan all skills with their tools.
    ///
    /// More expensive than scan_all() but includes tool discovery.
    ///
    /// # Returns
    ///
    /// List of tuples: (PySkillMetadata, List[PyToolRecord])
    fn scan_all_with_tools(&self) -> Vec<(PySkillMetadata, Vec<PyToolRecord>)> {
        let path = Path::new(&self.base_path);
        if !path.exists() {
            return Vec::new();
        }

        let mut results = Vec::new();

        if let Ok(metadatas) = self.inner.scan_all(path, None) {
            for metadata in metadatas {
                let skill_path = path.join(&metadata.skill_name);
                let scripts_path = skill_path.join("scripts");

                let tools = if scripts_path.exists() {
                    match self.tools_scanner.scan_scripts(
                        &scripts_path,
                        &metadata.skill_name,
                        &metadata.routing_keywords,
                        &[],
                    ) {
                        Ok(t) => t.into_iter().map(|t| t.into()).collect(),
                        Err(_) => Vec::new(),
                    }
                } else {
                    Vec::new()
                };

                results.push((metadata.into(), tools));
            }
        }

        results
    }

    /// Validate skill structure against canonical structure.
    ///
    /// Args:
    ///     skill_name: Name of the skill directory
    ///
    /// Returns:
    ///     True if valid, False otherwise.
    fn validate_skill(&self, skill_name: String) -> bool {
        let skill_path = Path::new(&self.base_path).join(&skill_name);
        if !skill_path.exists() {
            return false;
        }

        let structure = SkillStructure::default();
        SkillScanner::validate_structure(&skill_path, &structure)
    }

    /// Get the base path for this scanner.
    #[getter]
    fn get_base_path(&self) -> String {
        self.base_path.clone()
    }
}

/// Scan a skills directory and return discovered tools.
///
/// This function uses the Rust ast-grep scanner to find all Python functions
/// decorated with @skill_command in the scripts/ directory of each skill.
///
/// Args:
///   base_path: Base directory containing skills (e.g., "assets/skills")
///
/// Returns:
///   List of PyToolRecord objects with discovered tools
#[pyfunction]
#[pyo3(signature = (base_path))]
pub fn scan_skill_tools(base_path: String) -> Vec<PyToolRecord> {
    let skill_scanner = SkillScanner::new();
    let script_scanner = ToolsScanner::new();
    let skills_path = Path::new(&base_path);

    if !skills_path.exists() {
        return Vec::new();
    }

    // Step 1: Scan SKILL.md files to get routing_keywords
    match skill_scanner.scan_all(skills_path, None) {
        Ok(metadatas) => {
            // Step 2: For each skill, scan ONLY the scripts/ directory
            // (consistent with export behavior in scan_all_full_to_index)
            let mut tools_map: std::collections::HashMap<String, omni_vector::ToolRecord> =
                std::collections::HashMap::new();

            for metadata in &metadatas {
                let skill_path = skills_path.join(&metadata.skill_name);
                let scripts_path = skill_path.join("scripts");

                if scripts_path.exists() {
                    if let Ok(tools) = script_scanner.scan_scripts(
                        &scripts_path,
                        &metadata.skill_name,
                        &metadata.routing_keywords,
                        &[], // Pass empty intents
                    ) {
                        // Deduplicate by tool_name (keep first occurrence)
                        for tool in tools {
                            let tool_key = format!("{}.{}", tool.skill_name, tool.tool_name);
                            if !tools_map.contains_key(&tool_key) {
                                tools_map.insert(tool_key, tool);
                            }
                        }
                    }
                }
            }

            tools_map.into_iter().map(|(_, t)| t.into()).collect()
        }
        Err(_) => Vec::new(),
    }
}

/// Scan a single skill directory and return its metadata (SKILL.md frontmatter).
///
/// This function parses the SKILL.md file in a skill directory and returns
/// the metadata as a PySkillMetadata object.
///
/// Args:
///   skill_path: Path to the skill directory (e.g., "assets/skills/git")
///
/// Returns:
///   PySkillMetadata if successful, None if skill not found or invalid
#[pyfunction]
#[pyo3(signature = (skill_path))]
pub fn scan_skill(skill_path: String) -> Option<PySkillMetadata> {
    let scanner = SkillScanner::new();
    let path = std::path::Path::new(&skill_path);

    if !path.exists() || !path.is_dir() {
        return None;
    }

    match scanner.scan_skill(path, None) {
        Ok(Some(metadata)) => Some(metadata.into()),
        Ok(None) | Err(_) => None,
    }
}

/// Parse SKILL.md content string and return metadata.
///
/// This function is useful for testing or when the content is already
/// available as a string (e.g., from a database or API).
///
/// Args:
///   content: The raw SKILL.md content including frontmatter
///   skill_name: Name of the skill (used for temporary file creation)
///
/// Returns:
///   PySkillMetadata with default values if parsing fails
#[pyfunction]
#[pyo3(signature = (content, skill_name))]
pub fn scan_skill_from_content(content: &str, skill_name: String) -> PySkillMetadata {
    let scanner = SkillScanner::new();
    let temp_path = std::path::Path::new("/tmp").join(&skill_name);

    match scanner.parse_skill_md(content, &temp_path) {
        Ok(metadata) => metadata.into(),
        Err(_) => PySkillMetadata {
            skill_name,
            version: "0.0.0".to_string(),
            description: String::new(),
            authors: Vec::new(),
            routing_keywords: Vec::new(),
            intents: Vec::new(),
            require_refs: Vec::new(),
            repository: String::new(),
            permissions: Vec::new(),
        },
    }
}

/// Python wrapper for SyncReport
#[pyclass]
#[derive(Debug, Clone)]
pub struct PySyncReport {
    /// Tools that are new and need to be added
    #[pyo3(get)]
    pub added: Vec<PyToolRecord>,
    /// Tools that have changed and need to be updated
    #[pyo3(get)]
    pub updated: Vec<PyToolRecord>,
    /// Tool names that were deleted
    #[pyo3(get)]
    pub deleted: Vec<String>,
    /// Count of unchanged tools (fast path hit)
    #[pyo3(get)]
    pub unchanged_count: usize,
}

impl From<skills_scanner::SyncReport> for PySyncReport {
    fn from(report: skills_scanner::SyncReport) -> Self {
        Self {
            added: report.added.into_iter().map(|t| t.into()).collect(),
            updated: report.updated.into_iter().map(|t| t.into()).collect(),
            deleted: report.deleted,
            unchanged_count: report.unchanged_count,
        }
    }
}

/// Calculate sync operations between scanned tools and existing index.
///
/// Uses file_hash for fast-path comparison to skip unchanged tools.
/// Returns a report with lists of added, updated, deleted, and unchanged tools.
///
/// Args:
///   scanned_tools_json: JSON array of scanned ToolRecord objects
///   existing_tools_json: JSON array of existing IndexToolEntry objects
///
/// Returns:
///   PySyncReport with sync operation details
#[pyfunction]
#[pyo3(signature = (scanned_tools_json, existing_tools_json))]
pub fn diff_skills(scanned_tools_json: &str, existing_tools_json: &str) -> PyResult<PySyncReport> {
    let scanned: Vec<omni_vector::ToolRecord> =
        serde_json::from_str(scanned_tools_json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Failed to parse scanned tools JSON: {}",
                e
            ))
        })?;

    let existing: Vec<skills_scanner::IndexToolEntry> = serde_json::from_str(existing_tools_json)
        .map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!(
            "Failed to parse existing tools JSON: {}",
            e
        ))
    })?;

    let report = skills_scanner::calculate_sync_ops(scanned, existing);

    Ok(report.into())
}

/// Scan a list of virtual file paths with their content.
///
/// This function allows scanning Python files without filesystem access,
/// which is useful for testing with temporary directories or processing
/// file content from databases/APIs.
///
/// Args:
///   files: List of tuples (file_path: str, content: str)
///   skill_name: Name of the skill (e.g., "git", "writer")
///   skill_keywords: Routing keywords from SKILL.md for keyword boosting
///   skill_intents: Intents from SKILL.md
///
/// Returns:
///   List of PyToolRecord objects from all scanned files
///
/// # Example
///
/// ```python
/// from omni_core_rs import scan_paths
///
/// files = [
///     ("/virtual/skill/scripts/tool_a.py", '''
///         @skill_command(name="tool_a")
///         def tool_a(param: str) -> str:
///             '''Tool A implementation.'''
///             return param
///     '''),
///     ("/virtual/skill/scripts/tool_b.py", '''
///         @skill_command(name="tool_b")
///         def tool_b(value: int) -> int:
///             '''Tool B implementation.'''
///             return value * 2
///     '''),
/// ]
///
/// tools = scan_paths(files, "test_skill", ["test"], ["testing"])
/// ```
#[pyfunction]
#[pyo3(signature = (files, skill_name, skill_keywords, skill_intents))]
pub fn scan_paths(
    files: Vec<(String, String)>,
    skill_name: String,
    skill_keywords: Vec<String>,
    skill_intents: Vec<String>,
) -> Vec<PyToolRecord> {
    let scanner = omni_vector::ToolsScanner::new();

    match scanner.scan_paths(&files, &skill_name, &skill_keywords, &skill_intents) {
        Ok(tools) => tools.into_iter().map(|t| t.into()).collect(),
        Err(_) => Vec::new(),
    }
}

/// Parse script content directly without reading from disk.
///
/// This is a lower-level function for parsing a single Python script.
/// For batch scanning multiple files, use `scan_paths` instead.
///
/// Args:
///   content: The Python script content as a string
///   file_path: Virtual file path (for metadata/logging only)
///   skill_name: Name of the parent skill
///   skill_keywords: Routing keywords from SKILL.md
///   skill_intents: Intents from SKILL.md
///
/// Returns:
///   List of PyToolRecord objects (usually 0 or 1)
///
/// # Example
///
/// ```python
/// from omni_core_rs import parse_script_content
///
/// content = """
/// @skill_command(name="my_tool")
/// def my_tool(param: str) -> str:
///     '''My tool description.'''
///     return param
/// """
///
/// tools = parse_script_content(content, "/virtual/path/tool.py", "test", [], [])
/// ```
#[pyfunction]
#[pyo3(signature = (content, file_path, skill_name, skill_keywords, skill_intents))]
pub fn parse_script_content(
    content: String,
    file_path: String,
    skill_name: String,
    skill_keywords: Vec<String>,
    skill_intents: Vec<String>,
) -> Vec<PyToolRecord> {
    let scanner = omni_vector::ToolsScanner::new();

    match scanner.parse_content(&content, &file_path, &skill_name, &skill_keywords, &skill_intents) {
        Ok(tools) => tools.into_iter().map(|t| t.into()).collect(),
        Err(_) => Vec::new(),
    }
}
