//! Skills Scanner - Modular skill directory scanning for Omni-Dev-Fusion.
//!
//! This crate provides modular scanning capabilities for skill directories:
//! - `SkillScanner` - Parses SKILL.md for metadata and routing keywords
//! - `ScriptScanner` - Scans scripts/ for @skill_command decorated functions
//!
//! # Architecture
//!
//! ```text
//! skills-scanner/src/
//! ├── lib.rs              # Main module and exports
//! ├── skill_metadata.rs   # SkillMetadata, ToolRecord, ScanConfig
//! ├── skill_scanner.rs    # SKILL.md parser
//! └── script_scanner.rs   # @skill_command script parser
//! ```
//!
//! # Usage
//!
//! ```ignore
//! use skills_scanner::{SkillScanner, ScriptScanner, SkillMetadata, ToolRecord};
//!
//! // Scan for skill metadata
//! let skill_scanner = SkillScanner::new();
//! let metadatas = skill_scanner.scan_all(PathBuf::from("assets/skills")).unwrap();
//!
//! // Scan for tools in scripts
//! let script_scanner = ScriptScanner::new();
//! let tools = script_scanner.scan_scripts(
//!     PathBuf::from("assets/skills/writer/scripts"),
//!     "writer",
//!     &["write", "edit"]
//! ).unwrap();
//! ```
//!
//! # Integration with omni-vector
//!
//! This crate is designed to be used by `omni-vector` for indexing skills:
//!
//! ```ignore
//! use skills_scanner::{SkillScanner, ScriptScanner, SkillMetadata, ToolRecord};
//!
//! // In omni-vector's skill.rs:
//! fn index_skills(base_path: &str) -> Result<()> {
//!     let skill_scanner = SkillScanner::new();
//!     let script_scanner = ScriptScanner::new();
//!
//!     for metadata in skill_scanner.scan_all(Path::new(base_path))? {
//!         let tools = script_scanner.scan_scripts(
//!             &metadata.skill_path.join("scripts"),
//!             &metadata.skill_name,
//!             &metadata.routing_keywords
//!         )?;
//!         // Index tools with routing_keywords
//!     }
//!     Ok(())
//! }
//! ```

// ============================================================================
// Module Declarations
// ============================================================================

pub mod document_scanner;
pub mod script_scanner;
pub mod skill_metadata;
pub mod skill_scanner;

// ============================================================================
// Re-exports
// ============================================================================

pub use document_scanner::{DirectoryInventory, DocumentScanner, FileEntry, SkillInventory};
pub use script_scanner::ScriptScanner;
pub use skill_metadata::{
    AssetRecord, DataRecord, DocsAvailable, IndexToolEntry, ReferencePath, ReferenceRecord,
    ScanConfig, SkillIndexEntry, SkillMetadata, SkillStructure, StructureItem, TemplateRecord,
    TestRecord, ToolRecord,
};
pub use skill_scanner::SkillScanner;

// ============================================================================
// JSON Schema Generation
// ============================================================================

/// Generate JSON Schema for SkillIndexEntry.
///
/// Returns the JSON schema as a string that can be used by Python
/// for validation and documentation.
pub fn skill_index_schema() -> String {
    let schema = schemars::schema_for!(SkillIndexEntry);
    serde_json::to_string_pretty(&schema).unwrap_or_default()
}

// ============================================================================
// Version
// ============================================================================

/// Crate version.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    #[test]
    fn test_full_scan_workflow() {
        let temp_dir = TempDir::new().unwrap();
        let skills_dir = temp_dir.path().join("skills");
        fs::create_dir_all(&skills_dir).unwrap();

        // Create writer skill
        let writer_path = skills_dir.join("writer");
        fs::create_dir_all(&writer_path).unwrap();
        fs::write(
            &writer_path.join("SKILL.md"),
            r#"---
name: "writer"
version: "1.1.0"
routing_keywords: ["write", "edit", "polish"]
---
# Writer
"#,
        )
        .unwrap();

        let writer_scripts = writer_path.join("scripts");
        fs::create_dir_all(&writer_scripts).unwrap();
        fs::write(
            &writer_scripts.join("text.py"),
            r#"
@skill_command(name="write_text")
def write_text(content: str) -> str:
    '''Write text to file.'''
    return "written"
"#,
        )
        .unwrap();

        // Create git skill
        let git_path = skills_dir.join("git");
        fs::create_dir_all(&git_path).unwrap();
        fs::write(
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

        // Scan metadatas
        let skill_scanner = SkillScanner::new();
        let metadatas = skill_scanner.scan_all(&skills_dir, None).unwrap();
        assert_eq!(metadatas.len(), 2);

        // Scan scripts for writer
        let script_scanner = ScriptScanner::new();
        let writer_metadata = metadatas.iter().find(|m| m.skill_name == "writer").unwrap();
        let tools = script_scanner
            .scan_scripts(&writer_scripts, "writer", &writer_metadata.routing_keywords)
            .unwrap();

        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0].tool_name, "writer.write_text");
        // Verify routing keywords are included
        assert!(tools[0].keywords.contains(&"write".to_string()));
    }

    #[test]
    fn test_version_constant() {
        assert!(!VERSION.is_empty());
    }
}
