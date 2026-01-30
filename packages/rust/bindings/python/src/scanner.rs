//! Script Scanner - Direct Python Bindings
//!
//! Provides direct Python bindings for scanning skill tools.
//! Scans all directories defined in settings.yaml's skills.architecture.
//!
//! Added scan_skill() and scan_skill_from_content() for parsing
//! SKILL.md frontmatter (replaces python-frontmatter dependency).

use crate::vector::PyToolRecord;
use omni_vector::{SkillScanner, ToolsScanner};
use pyo3::prelude::*;
use skills_scanner::SkillMetadata;
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
        }
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
