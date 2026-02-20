//! Skills Scanner Module
//!
//! Scans skill directories for SKILL.md and @`skill_command` scripts.

pub mod canonical;
pub mod metadata;
pub mod prompt;
pub mod resource;
pub mod scanner;
pub mod skill_command;
pub mod tools;

// Re-export common types from submodules
pub use canonical::{CanonicalSkillPayload, CanonicalToolEntry};
pub use metadata::{
    AssetRecord, DataRecord, DecoratorArgs, DocsAvailable, IndexToolEntry, PromptRecord,
    ReferencePath, ReferenceRecord, ResourceRecord, ScanConfig, SkillIndexEntry, SkillMetadata,
    SkillStructure, SnifferRule, StructureItem, SyncReport, TemplateRecord, TestRecord,
    ToolAnnotations, ToolRecord, calculate_sync_ops,
};
pub use prompt::PromptScanner;
pub use resource::ResourceScanner;
pub use scanner::SkillScanner;
pub use tools::ToolsScanner;
