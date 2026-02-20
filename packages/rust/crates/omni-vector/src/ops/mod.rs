//! Administrative and maintenance operations for VectorStore.

mod agentic;
mod cache;
pub mod column_read;
mod maintenance;
mod migration;
mod observability;
mod partitioning;
mod scalar;
mod types;
mod vector_index;

pub use agentic::{AgenticSearchConfig, QueryIntent};
pub use cache::{DatasetCache, DatasetCacheConfig};
pub use column_read::{get_intents_at, get_routing_keywords_at, get_utf8_at};
pub use migration::{
    MigrateResult, MigrationItem, OMNI_SCHEMA_VERSION, schema_version_from_schema,
};
pub use types::{
    CompactionStats, DocumentRow, FragmentInfo, IndexBuildProgress, IndexCacheStats, IndexStats,
    IndexStatus, IndexThresholds, MergeInsertStats, QueryMetrics, Recommendation,
    TableColumnAlteration, TableColumnType, TableHealthReport, TableInfo, TableNewColumn,
    TableVersionInfo,
};
