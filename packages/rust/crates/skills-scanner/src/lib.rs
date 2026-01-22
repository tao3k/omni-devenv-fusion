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
    ScanConfig, SkillIndexEntry, SkillMetadata, SkillStructure, SnifferRule, StructureItem,
    TemplateRecord, TestRecord, ToolRecord,
};
pub use skill_scanner::{SkillScanner, extract_frontmatter};

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

// Note: Comprehensive tests are in tests/
