//! Skills Scanner Module
//!
//! Scans skill directories for SKILL.md and @skill_command scripts.

pub mod metadata;
pub mod scanner;
pub mod skill_command;
pub mod tools;

// Re-export common types from submodules
pub use metadata::{
    AssetRecord, DataRecord, DecoratorArgs, DocsAvailable, IndexToolEntry, ReferencePath,
    ReferenceRecord, ScanConfig, SkillIndexEntry, SkillMetadata, SkillStructure, SnifferRule,
    StructureItem, SyncReport, TemplateRecord, TestRecord, ToolAnnotations, ToolRecord,
    calculate_sync_ops,
};
pub use scanner::SkillScanner;
pub use tools::ToolsScanner;
