//! Script Scanner - Phase 62: Direct Python Bindings
//!
//! Provides direct Python bindings for scanning skill tools.
//! Scans all directories defined in settings.yaml's skills.architecture.
//!
//! Phase 64: Added scan_skill() and scan_skill_from_content() for parsing
//! SKILL.md frontmatter (replaces python-frontmatter dependency).

use crate::vector::PyToolRecord;
use omni_vector::{ScriptScanner, SkillScanner, SkillStructure};
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
/// decorated with @skill_command in all skill directories defined by
/// settings.yaml's skills.architecture (scripts/, templates/, references/, etc.).
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
    let script_scanner = ScriptScanner::new();
    let skills_path = Path::new(&base_path);

    if !skills_path.exists() {
        return Vec::new();
    }

    // Get the canonical skill structure from settings.yaml
    let structure = SkillStructure::default();

    // Step 1: Scan SKILL.md files to get routing_keywords
    match skill_scanner.scan_all(skills_path, None) {
        Ok(metadatas) => {
            // Step 2: For each skill, scan ALL directories defined in structure
            // (scripts/, templates/, references/, assets/, data/, tests/)
            let mut all_tools: Vec<omni_vector::ToolRecord> = Vec::new();

            for metadata in &metadatas {
                let skill_path = skills_path.join(&metadata.skill_name);

                // Use scan_with_structure to scan all relevant directories
                if let Ok(tools) = script_scanner.scan_with_structure(
                    &skill_path,
                    &metadata.skill_name,
                    &metadata.routing_keywords,
                    &structure,
                ) {
                    all_tools.extend(tools);
                }
            }

            all_tools.into_iter().map(|t| t.into()).collect()
        }
        Err(_) => Vec::new(),
    }
}

/// Export full skill index to JSON file.
///
/// This function scans all skills and writes a complete skill_index.json
/// including metadata from SKILL.md frontmatter and discovered tools.
///
/// Args:
///   base_path: Base directory containing skills (e.g., "assets/skills")
///   output_path: Path for the output JSON file (e.g., "assets/skills/skill_index.json")
///
/// Returns:
///   PyResult with JSON string of the index on success, or error on failure
#[pyfunction]
#[pyo3(signature = (base_path, output_path))]
pub fn export_skill_index(base_path: String, output_path: String) -> PyResult<String> {
    let skill_scanner = SkillScanner::new();
    let script_scanner = ScriptScanner::new();
    let skills_path = Path::new(&base_path);
    let output = Path::new(&output_path);

    if !skills_path.exists() {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "Skills directory does not exist: {}",
            base_path
        )));
    }

    // Convert the error to a string for PyErr
    skill_scanner
        .scan_all_full_to_index(skills_path, output, None, &script_scanner)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    // Read and return the generated JSON
    let json_content = std::fs::read_to_string(output)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

    Ok(json_content)
}

/// Get JSON Schema for skill index.
///
/// Returns the JSON Schema as a string that can be used by Python
/// for validation and documentation.
///
/// Returns:
///   PyResult with JSON schema string on success, or error on failure
#[pyfunction]
pub fn get_skill_index_schema() -> PyResult<String> {
    let schema = skills_scanner::skill_index_schema();
    Ok(schema)
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
