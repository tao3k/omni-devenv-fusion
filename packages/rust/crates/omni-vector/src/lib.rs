//! omni-vector - High-Performance Embedded Vector Database using LanceDB
//!
//! # Architecture (ODF-REP Compliant)
//!
//! ```text
//! omni-vector/src/
//! ├── lib.rs              # Main module and VectorStore struct
//! ├── error.rs            # VectorStoreError enum
//! ├── store.rs            # Store operations (kept for backward compat)
//! ├── search/             # Search operations
//! │   ├── mod.rs
//! │   ├── vector_search.rs
//! │   ├── hybrid_search.rs
//! │   └── filter.rs
//! ├── index.rs            # Index creation operations
//! ├── keyword/            # Tantivy-based keyword search (BM25)
//! │   ├── mod.rs
//! │   ├── index.rs
//! │   └── fusion.rs
//! ├── skill/              # Skill tool indexing
//! │   ├── mod.rs
//! │   └── scanner.rs
//! ├── checkpoint/         # Checkpoint storage
//! │   ├── mod.rs
//! │   ├── record.rs
//! │   └── store.rs
//! └── batch.rs            # RecordBatch utilities
//! ```

use std::path::Path;
use std::path::PathBuf;
use std::sync::Arc;

use anyhow::Result;
use futures::TryStreamExt;
use lance::dataset::Dataset;
use serde_json::Value;
use tokio::sync::Mutex;

// ============================================================================
// Re-exports from omni-lance
// ============================================================================

pub use omni_lance::{
    CONTENT_COLUMN, DEFAULT_DIMENSION, ID_COLUMN, METADATA_COLUMN, THREAD_ID_COLUMN, VECTOR_COLUMN,
    VectorRecordBatchReader, extract_optional_string, extract_string,
};

// ============================================================================
// Re-exports from skills-scanner
// ============================================================================

pub use skills_scanner::{
    DocumentScanner, SkillMetadata, SkillScanner, SkillStructure, ToolRecord, ToolsScanner,
};

// ============================================================================
// Re-exports from submodules
// ============================================================================

// Re-export ToolSearchResult from skill module for Python bindings
pub use skill::ToolSearchResult;

// Re-export checkpoint module
pub use checkpoint::{CheckpointRecord, CheckpointStore};

// Re-export keyword module for hybrid search
pub use keyword::{HybridSearchResult, KeywordIndex, RRF_K, apply_rrf, apply_weighted_rrf};

// ============================================================================
// Vector Store Implementation
// ============================================================================

/// High-performance embedded vector database using `LanceDB`.
#[derive(Clone)]
pub struct VectorStore {
    base_path: PathBuf,
    datasets: Arc<Mutex<dashmap::DashMap<String, lance::dataset::Dataset>>>,
    dimension: usize,
    keyword_index: Option<Arc<keyword::KeywordIndex>>,
}

impl VectorStore {
    /// Create a new vector store at the given path.
    pub async fn new(path: &str, dimension: Option<usize>) -> Result<Self, VectorStoreError> {
        let base_path = PathBuf::from(path);

        // Special case for in-memory mode
        if path == ":memory:" {
            return Ok(Self {
                base_path: PathBuf::from(":memory:"),
                datasets: Arc::new(Mutex::new(dashmap::DashMap::new())),
                dimension: dimension.unwrap_or(DEFAULT_DIMENSION),
                keyword_index: None,
            });
        }

        if let Some(parent) = base_path.parent() {
            if !parent.exists() {
                std::fs::create_dir_all(parent)?;
            }
        }
        if !base_path.exists() {
            std::fs::create_dir_all(&base_path)?;
        }

        Ok(Self {
            base_path,
            datasets: Arc::new(Mutex::new(dashmap::DashMap::new())),
            dimension: dimension.unwrap_or(DEFAULT_DIMENSION),
            keyword_index: None,
        })
    }

    /// Create a new vector store with optional keyword index for hybrid search.
    pub async fn new_with_keyword_index(
        path: &str,
        dimension: Option<usize>,
        enable_keyword_index: bool,
    ) -> Result<Self, VectorStoreError> {
        let base_path = PathBuf::from(path);

        if path == ":memory:" {
            return Ok(Self {
                base_path: PathBuf::from(":memory:"),
                datasets: Arc::new(Mutex::new(dashmap::DashMap::new())),
                dimension: dimension.unwrap_or(DEFAULT_DIMENSION),
                keyword_index: None,
            });
        }

        if let Some(parent) = base_path.parent() {
            if !parent.exists() {
                std::fs::create_dir_all(parent)?;
            }
        }
        if !base_path.exists() {
            std::fs::create_dir_all(&base_path)?;
        }

        let keyword_index = if enable_keyword_index {
            Some(Arc::new(keyword::KeywordIndex::new(&base_path)?))
        } else {
            None
        };

        Ok(Self {
            base_path,
            datasets: Arc::new(Mutex::new(dashmap::DashMap::new())),
            dimension: dimension.unwrap_or(DEFAULT_DIMENSION),
            keyword_index,
        })
    }

    /// Get the table path for a given table name.
    pub fn table_path(&self, table_name: &str) -> PathBuf {
        if self.base_path.as_os_str() == ":memory:" {
            PathBuf::from(format!(":memory:_{}", table_name))
        } else {
            self.base_path.join(format!("{table_name}.lance"))
        }
    }

    /// Create the schema for vector storage.
    pub fn create_schema(&self) -> Arc<lance::deps::arrow_schema::Schema> {
        Arc::new(lance::deps::arrow_schema::Schema::new(vec![
            lance::deps::arrow_schema::Field::new(
                ID_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                false,
            ),
            lance::deps::arrow_schema::Field::new(
                VECTOR_COLUMN,
                lance::deps::arrow_schema::DataType::FixedSizeList(
                    Arc::new(lance::deps::arrow_schema::Field::new(
                        "item",
                        lance::deps::arrow_schema::DataType::Float32,
                        true,
                    )),
                    i32::try_from(self.dimension).unwrap_or(1536),
                ),
                false,
            ),
            lance::deps::arrow_schema::Field::new(
                CONTENT_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                false,
            ),
            lance::deps::arrow_schema::Field::new(
                METADATA_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                true,
            ),
        ]))
    }
}

// ============================================================================
// Store Writer Operations
// ============================================================================

impl VectorStore {
    /// Add ToolRecords to the vector store with explicit Keyword Indexing.
    pub async fn add(
        &self,
        table_name: &str,
        tools: Vec<ToolRecord>,
    ) -> Result<(), VectorStoreError> {
        if tools.is_empty() {
            return Ok(());
        }

        // 1. Write to Keyword Index FIRST
        if let Some(kw_index) = &self.keyword_index {
            let search_results: Vec<skill::ToolSearchResult> = tools
                .iter()
                .map(|t| {
                    let full_name = format!(
                        "{}.{}",
                        t.skill_name,
                        t.tool_name.split('.').skip(1).collect::<Vec<_>>().join(".")
                    );
                    skill::ToolSearchResult {
                        name: full_name.clone(),
                        description: t.description.clone(),
                        input_schema: serde_json::json!({}),
                        score: 1.0,
                        skill_name: t.skill_name.clone(),
                        tool_name: t.tool_name.clone(),
                        file_path: t.file_path.clone(),
                        keywords: t.keywords.clone(),
                    }
                })
                .collect();
            let _ = kw_index.index_batch(&search_results);
        }

        // 2. Write to LanceDB
        let ids: Vec<String> = tools
            .iter()
            .map(|t| {
                format!(
                    "{}.{}",
                    t.skill_name,
                    t.tool_name.split('.').skip(1).collect::<Vec<_>>().join(".")
                )
            })
            .collect();
        let contents: Vec<String> = tools.iter().map(|t| t.description.clone()).collect();
        let metadatas: Vec<String> = tools.iter().map(|t| {
            serde_json::json!({
                "type": "command", "skill_name": t.skill_name, "command": t.tool_name, "tool_name": t.tool_name,
                "file_path": t.file_path, "function_name": t.function_name, "keywords": t.keywords,
                "file_hash": t.file_hash, "input_schema": t.input_schema, "docstring": t.docstring,
            }).to_string()
        }).collect();

        let dimension = self.dimension;
        let vectors: Vec<Vec<f32>> = ids
            .iter()
            .map(|id| {
                let mut vec = vec![0.0; dimension];
                let hash = id
                    .bytes()
                    .fold(0u64, |acc, b| acc.wrapping_mul(31).wrapping_add(b as u64));
                for (i, v) in vec.iter_mut().enumerate() {
                    *v = ((hash >> (i % 64)) as f32 / u64::MAX as f32) * 0.1;
                }
                vec
            })
            .collect();

        self.add_documents(table_name, ids, vectors, contents, metadatas)
            .await?;
        Ok(())
    }

    /// Add documents to the vector store.
    pub async fn add_documents(
        &self,
        table_name: &str,
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
    ) -> Result<(), VectorStoreError> {
        use lance::deps::arrow_array::{FixedSizeListArray, Float32Array, StringArray};

        if ids.is_empty() {
            return Ok(());
        }

        let dimension = vectors.first().ok_or(VectorStoreError::EmptyDataset)?.len();
        if dimension == 0 {
            return Err(VectorStoreError::InvalidEmbeddingDimension);
        }

        for vec in &vectors {
            if vec.len() != dimension {
                return Err(VectorStoreError::InvalidDimension {
                    expected: dimension,
                    actual: vec.len(),
                });
            }
        }

        let id_array = StringArray::from(ids.clone());
        let content_array = StringArray::from(contents.clone());
        let metadata_array = StringArray::from(metadatas.clone());
        let flat_values: Vec<f32> = vectors.into_iter().flatten().collect();
        let vector_array = FixedSizeListArray::try_new(
            Arc::new(lance::deps::arrow_schema::Field::new(
                "item",
                lance::deps::arrow_schema::DataType::Float32,
                true,
            )),
            i32::try_from(dimension).unwrap_or(1536),
            Arc::new(Float32Array::from(flat_values)),
            None,
        )
        .map_err(VectorStoreError::Arrow)?;

        let schema = self.create_schema();
        let batch = lance::deps::arrow_array::RecordBatch::try_new(
            schema.clone(),
            vec![
                Arc::new(id_array),
                Arc::new(vector_array),
                Arc::new(content_array),
                Arc::new(metadata_array),
            ],
        )
        .map_err(VectorStoreError::Arrow)?;

        let mut dataset = self.get_or_create_dataset(table_name, false).await?;
        let batches: Vec<Result<_, crate::error::ArrowError>> = vec![Ok(batch)];
        let iter = lance::deps::arrow_array::RecordBatchIterator::new(batches, schema);
        dataset
            .append(Box::new(iter), None)
            .await
            .map_err(VectorStoreError::LanceDB)?;
        log::info!("Added documents to table '{table_name}'");

        // DUAL WRITE: Also write to Keyword Index if enabled
        if let Some(ref kw_index) = self.keyword_index {
            log::info!("Indexing keywords for {} documents...", ids.len());
            let mut keyword_docs = Vec::new();
            for (i, meta_str) in metadatas.iter().enumerate() {
                if let Ok(meta) = serde_json::from_str::<serde_json::Value>(meta_str) {
                    let name = meta
                        .get("tool_name")
                        .and_then(|s| s.as_str())
                        .or_else(|| meta.get("command").and_then(|s| s.as_str()))
                        .or_else(|| meta.get("id").and_then(|s| s.as_str()))
                        .unwrap_or(&ids[i])
                        .to_string();
                    let category = meta
                        .get("skill_name")
                        .and_then(|s| s.as_str())
                        .or_else(|| meta.get("category").and_then(|s| s.as_str()))
                        .unwrap_or("unknown")
                        .to_string();
                    let kws: Vec<String> = meta
                        .get("keywords")
                        .and_then(|v| v.as_array())
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|v| v.as_str().map(|s| s.to_string()))
                                .collect()
                        })
                        .unwrap_or_default();
                    keyword_docs.push((name, contents[i].clone(), category, kws));
                }
            }
            if !keyword_docs.is_empty() {
                if let Err(e) = kw_index.bulk_upsert(keyword_docs) {
                    log::error!("Failed to update keyword index: {}", e);
                } else {
                    log::info!("Keyword Index Updated.");
                }
            }
        }
        Ok(())
    }

    async fn get_or_create_dataset(
        &self,
        table_name: &str,
        force_create: bool,
    ) -> Result<Dataset, VectorStoreError> {
        use crate::error::ArrowError;
        use lance::dataset::WriteParams;

        let table_path = self.table_path(table_name);
        let table_uri = table_path.to_string_lossy().into_owned();

        {
            let datasets = self.datasets.lock().await;
            if !force_create {
                if let Some(cached) = datasets.get(table_name) {
                    return Ok(cached.clone());
                }
            }
        }

        let is_memory_mode = self.base_path.as_os_str() == ":memory:";
        let dataset = if !is_memory_mode && table_path.exists() && !force_create {
            Dataset::open(table_uri.as_str()).await?
        } else {
            let schema = self.create_schema();
            let empty_batch = self.create_empty_batch(&schema)?;
            let batches: Vec<Result<_, ArrowError>> = vec![Ok(empty_batch)];
            let iter = lance::deps::arrow_array::RecordBatchIterator::new(batches, schema);
            let write_uri = if is_memory_mode {
                std::env::temp_dir()
                    .join(format!("omni_lance_{}", table_name))
                    .to_string_lossy()
                    .into_owned()
            } else {
                table_uri
            };
            Dataset::write(
                Box::new(iter),
                write_uri.as_str(),
                Some(WriteParams::default()),
            )
            .await
            .map_err(VectorStoreError::LanceDB)?
        };

        {
            let datasets = self.datasets.lock().await;
            datasets.insert(table_name.to_string(), dataset.clone());
        }
        Ok(dataset)
    }

    fn create_empty_batch(
        &self,
        schema: &Arc<lance::deps::arrow_schema::Schema>,
    ) -> Result<lance::deps::arrow_array::RecordBatch, VectorStoreError> {
        let dimension = self.dimension;
        let arrays: Vec<Arc<dyn lance::deps::arrow_array::Array>> = vec![
            Arc::new(lance::deps::arrow_array::StringArray::from(
                Vec::<String>::new(),
            )) as _,
            Arc::new(lance::deps::arrow_array::FixedSizeListArray::new_null(
                Arc::new(lance::deps::arrow_schema::Field::new(
                    "item",
                    lance::deps::arrow_schema::DataType::Float32,
                    true,
                )),
                i32::try_from(dimension).unwrap_or(1536),
                0,
            )) as _,
            Arc::new(lance::deps::arrow_array::StringArray::from(
                Vec::<String>::new(),
            )) as _,
            Arc::new(lance::deps::arrow_array::StringArray::from(
                Vec::<String>::new(),
            )) as _,
        ];
        lance::deps::arrow_array::RecordBatch::try_new(schema.clone(), arrays)
            .map_err(VectorStoreError::Arrow)
    }
}

// ============================================================================
// Store Reader Operations
// ============================================================================

impl VectorStore {
    /// Get all file hashes from a table for incremental sync.
    pub async fn get_all_file_hashes(&self, table_name: &str) -> Result<String, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok("{}".to_string());
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN, METADATA_COLUMN])?;
        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let mut hash_map = std::collections::HashMap::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let id_col = batch.column_by_name(ID_COLUMN);

            if let (Some(meta_col), Some(id_c)) = (metadata_col, id_col) {
                use lance::deps::arrow_array::{Array, StringArray};
                if let Some(metas) = meta_col.as_any().downcast_ref::<StringArray>() {
                    for i in 0..batch.num_rows() {
                        if metas.is_null(i) {
                            continue;
                        }
                        let metadata_str = metas.value(i);
                        let id = id_c
                            .as_any()
                            .downcast_ref::<StringArray>()
                            .map(|arr| arr.value(i).to_string())
                            .unwrap_or_default();
                        if let Ok(metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
                        {
                            if let (Some(path), Some(hash)) = (
                                metadata.get("file_path").and_then(|v| v.as_str()),
                                metadata.get("file_hash").and_then(|v| v.as_str()),
                            ) {
                                hash_map.insert(
                                    path.to_string(),
                                    serde_json::json!({ "hash": hash.to_string(), "id": id }),
                                );
                            }
                        }
                    }
                }
            }
        }
        serde_json::to_string(&hash_map).map_err(|e| VectorStoreError::General(format!("{}", e)))
    }

    /// Count documents in a table.
    pub async fn count(&self, table_name: &str) -> Result<u32, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(0);
        }
        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;
        Ok(u32::try_from(
            dataset
                .count_rows(None)
                .await
                .map_err(VectorStoreError::LanceDB)?,
        )
        .unwrap_or(0))
    }
}

// ============================================================================
// Store Admin Operations
// ============================================================================

impl VectorStore {
    /// Delete documents by ID.
    pub async fn delete(&self, table_name: &str, ids: Vec<String>) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }
        let mut dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;
        for id in ids {
            dataset
                .delete(&format!("{ID_COLUMN} = '{id}'"))
                .await
                .map_err(VectorStoreError::LanceDB)?;
        }
        Ok(())
    }

    /// Delete documents by file path.
    pub async fn delete_by_file_path(
        &self,
        table_name: &str,
        file_paths: Vec<String>,
    ) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }
        if file_paths.is_empty() {
            return Ok(());
        }

        let mut dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let file_paths_set: std::collections::HashSet<String> =
            file_paths.iter().cloned().collect();
        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN, METADATA_COLUMN])?;
        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let mut ids_to_delete: Vec<String> = Vec::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            use lance::deps::arrow_array::{Array, StringArray};
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let id_col = batch.column_by_name(ID_COLUMN);
            if let (Some(meta_col), Some(id_c)) = (metadata_col, id_col) {
                if let Some(metas) = meta_col.as_any().downcast_ref::<StringArray>() {
                    for i in 0..batch.num_rows() {
                        if metas.is_null(i) {
                            continue;
                        }
                        let metadata_str = metas.value(i);
                        let id = id_c
                            .as_any()
                            .downcast_ref::<StringArray>()
                            .map(|arr| arr.value(i).to_string())
                            .unwrap_or_default();
                        if let Ok(metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
                        {
                            if let Some(file_path) =
                                metadata.get("file_path").and_then(|v| v.as_str())
                            {
                                if file_paths_set.contains(file_path) {
                                    ids_to_delete.push(id);
                                }
                            }
                        }
                    }
                }
            }
        }

        if !ids_to_delete.is_empty() {
            dataset
                .delete(&format!("{ID_COLUMN} IN ('{}')", ids_to_delete.join("','")))
                .await
                .map_err(VectorStoreError::LanceDB)?;
        }
        Ok(())
    }

    /// Drop a table completely.
    pub async fn drop_table(&self, table_name: &str) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);
        {
            let datasets = self.datasets.lock().await;
            datasets.remove(table_name);
        }
        if table_path.exists() {
            std::fs::remove_dir_all(&table_path)?;
        }
        Ok(())
    }
}

// ============================================================================
// Skill Indexer Operations
// ============================================================================

impl VectorStore {
    /// Index all tools from skills scripts directory.
    pub async fn index_skill_tools(
        &self,
        base_path: &str,
        table_name: &str,
    ) -> Result<(), VectorStoreError> {
        let skill_scanner = SkillScanner::new();
        let script_scanner = ToolsScanner::new();
        let skills_path = Path::new(base_path);

        if !skills_path.exists() {
            log::warn!("Skills directory not found: {}", base_path);
            return Ok(());
        }

        let metadatas = skill_scanner.scan_all(skills_path, None).map_err(|e| {
            VectorStoreError::General(format!("Failed to scan skill metadata: {}", e))
        })?;
        if metadatas.is_empty() {
            log::info!("No skills with SKILL.md found");
            return Ok(());
        }

        let mut tools_map: std::collections::HashMap<String, ToolRecord> =
            std::collections::HashMap::new();

        for metadata in &metadatas {
            let skill_scripts_path = skills_path.join(&metadata.skill_name).join("scripts");
            let tools = script_scanner
                .scan_scripts(
                    &skill_scripts_path,
                    &metadata.skill_name,
                    &metadata.routing_keywords,
                )
                .map_err(|e| {
                    VectorStoreError::General(format!(
                        "Failed to scan scripts for skill '{}': {}",
                        metadata.skill_name, e
                    ))
                })?;
            for tool in tools {
                let tool_key = format!("{}.{}", tool.skill_name, tool.tool_name);
                if !tools_map.contains_key(&tool_key) {
                    tools_map.insert(tool_key, tool);
                }
            }
        }

        let all_tools: Vec<ToolRecord> = tools_map.into_values().collect();
        if all_tools.is_empty() {
            log::info!("No tools found in scripts");
            return Ok(());
        }

        let tool_count = all_tools.len();
        self.add(table_name, all_tools).await?;
        log::info!(
            "Indexed {} tools from {} skills",
            tool_count,
            metadatas.len()
        );
        Ok(())
    }

    /// Get tool records by skill name.
    pub async fn get_tools_by_skill(
        &self,
        _skill_name: &str,
    ) -> Result<Vec<ToolRecord>, VectorStoreError> {
        Ok(vec![])
    }

    /// Scan for skill tools without indexing (returns raw tool records as JSON).
    pub fn scan_skill_tools_raw(&self, base_path: &str) -> Result<Vec<String>, VectorStoreError> {
        let skill_scanner = SkillScanner::new();
        let script_scanner = ToolsScanner::new();
        let skills_path = Path::new(base_path);

        if !skills_path.exists() {
            log::warn!("Skills directory not found: {}", base_path);
            return Ok(vec![]);
        }

        let metadatas = skill_scanner.scan_all(skills_path, None).map_err(|e| {
            VectorStoreError::General(format!("Failed to scan skill metadata: {}", e))
        })?;
        let mut all_tools: Vec<ToolRecord> = Vec::new();

        for metadata in &metadatas {
            let skill_scripts_path = skills_path.join(&metadata.skill_name).join("scripts");
            let tools = script_scanner
                .scan_scripts(
                    &skill_scripts_path,
                    &metadata.skill_name,
                    &metadata.routing_keywords,
                )
                .map_err(|e| {
                    VectorStoreError::General(format!(
                        "Failed to scan scripts for skill '{}': {}",
                        metadata.skill_name, e
                    ))
                })?;
            all_tools.extend(tools);
        }

        let json_tools: Vec<String> = all_tools
            .into_iter()
            .map(|t| serde_json::to_string(&t).unwrap_or_default())
            .filter(|s| !s.is_empty())
            .collect();
        log::info!("Scanned {} skill tools", json_tools.len());
        Ok(json_tools)
    }

    /// List all tools from LanceDB as JSON.
    pub async fn list_all_tools(&self, table_name: &str) -> Result<String, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok("[]".to_string());
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let mut scanner = dataset.scan();
        scanner.project(&["id", "content", "metadata"])?;
        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let mut tools: Vec<serde_json::Value> = Vec::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            use lance::deps::arrow_array::StringArray;
            let id_col = batch.column_by_name("id");
            let content_col = batch.column_by_name("content");
            let metadata_col = batch.column_by_name("metadata");

            if let (Some(ids), Some(contents), Some(metas)) = (id_col, content_col, metadata_col) {
                if let (Some(id_arr), Some(content_arr), Some(meta_arr)) = (
                    ids.as_any().downcast_ref::<StringArray>(),
                    contents.as_any().downcast_ref::<StringArray>(),
                    metas.as_any().downcast_ref::<StringArray>(),
                ) {
                    use lance::deps::arrow_array::Array;
                    for i in 0..batch.num_rows() {
                        let id = id_arr.value(i).to_string();
                        let content = content_arr.value(i).to_string();
                        let metadata_str = if meta_arr.is_null(i) {
                            "{}".to_string()
                        } else {
                            meta_arr.value(i).to_string()
                        };
                        if let Ok(mut metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
                        {
                            metadata["id"] = serde_json::json!(id);
                            metadata["content"] = serde_json::json!(content);
                            tools.push(metadata);
                        }
                    }
                }
            }
        }
        serde_json::to_string(&tools).map_err(|e| VectorStoreError::General(format!("{}", e)))
    }

    /// High-performance tool search with integrated filtering and scoring.
    pub async fn search_tools(
        &self,
        table_name: &str,
        query_vector: &[f32],
        query_text: Option<&str>,
        limit: usize,
        threshold: f32,
    ) -> Result<Vec<skill::ToolSearchResult>, VectorStoreError> {
        use lance::deps::arrow_array::Array;

        let mut results_map: std::collections::HashMap<String, skill::ToolSearchResult> =
            std::collections::HashMap::new();
        let table_path = self.table_path(table_name);

        if table_path.exists() {
            if let Ok(dataset) = Dataset::open(table_path.to_string_lossy().as_ref()).await {
                let mut scanner = dataset.scan();
                scanner
                    .project(&[VECTOR_COLUMN, METADATA_COLUMN, CONTENT_COLUMN])
                    .ok();
                if let Ok(mut stream) = scanner.try_into_stream().await {
                    let query_len = query_vector.len();
                    while let Ok(Some(batch)) = stream.try_next().await {
                        let vector_col = batch.column_by_name(VECTOR_COLUMN);
                        let metadata_col = batch.column_by_name(METADATA_COLUMN);
                        let content_col = batch.column_by_name(CONTENT_COLUMN);

                        if let (Some(v_col), Some(m_col), Some(c_col)) =
                            (vector_col, metadata_col, content_col)
                        {
                            let vector_arr = v_col
                                .as_any()
                                .downcast_ref::<lance::deps::arrow_array::FixedSizeListArray>(
                            );
                            let metadata_arr = m_col
                                .as_any()
                                .downcast_ref::<lance::deps::arrow_array::StringArray>();
                            let content_arr = c_col
                                .as_any()
                                .downcast_ref::<lance::deps::arrow_array::StringArray>();

                            if let (Some(vector_arr), Some(metadata_arr), Some(content_arr)) =
                                (vector_arr, metadata_arr, content_arr)
                            {
                                use lance::deps::arrow_array::Array;
                                let values = vector_arr
                                    .values()
                                    .as_any()
                                    .downcast_ref::<lance::deps::arrow_array::Float32Array>(
                                );
                                if let Some(values) = values {
                                    for i in 0..batch.num_rows() {
                                        let mut distance_sq = 0.0f32;
                                        let values_len = values.len();
                                        for j in 0..query_len {
                                            let db_val = if j < values_len {
                                                values.value(i * values_len / batch.num_rows() + j)
                                            } else {
                                                0.0
                                            };
                                            let diff = db_val - query_vector[j];
                                            distance_sq += diff * diff;
                                        }
                                        let score = 1.0 / (1.0 + distance_sq.sqrt());

                                        if metadata_arr.is_null(i) {
                                            continue;
                                        }
                                        let metadata_str = metadata_arr.value(i);
                                        if let Ok(meta) =
                                            serde_json::from_str::<Value>(&metadata_str)
                                        {
                                            if meta.get("type").and_then(|t| t.as_str())
                                                != Some("command")
                                            {
                                                continue;
                                            }
                                            let name = meta
                                                .get("command")
                                                .and_then(|s| s.as_str())
                                                .unwrap_or("")
                                                .to_string();
                                            if name.is_empty() {
                                                continue;
                                            }
                                            let skill_name = meta
                                                .get("skill_name")
                                                .and_then(|s| s.as_str())
                                                .unwrap_or("")
                                                .to_string();
                                            let tool_name = meta
                                                .get("tool_name")
                                                .and_then(|s| s.as_str())
                                                .unwrap_or("")
                                                .to_string();
                                            let file_path = meta
                                                .get("file_path")
                                                .and_then(|s| s.as_str())
                                                .unwrap_or("")
                                                .to_string();
                                            let keywords: Vec<String> = meta
                                                .get("keywords")
                                                .and_then(|k| k.as_array())
                                                .map(|arr| {
                                                    arr.iter()
                                                        .filter_map(|k| {
                                                            k.as_str().map(|s| s.to_string())
                                                        })
                                                        .collect()
                                                })
                                                .unwrap_or_default();
                                            let input_schema = meta
                                                .get("input_schema")
                                                .cloned()
                                                .unwrap_or(Value::Object(serde_json::Map::new()));
                                            let description = content_arr.value(i).to_string();

                                            results_map.insert(
                                                name.clone(),
                                                skill::ToolSearchResult {
                                                    name,
                                                    description,
                                                    input_schema,
                                                    score,
                                                    skill_name,
                                                    tool_name,
                                                    file_path,
                                                    keywords,
                                                },
                                            );
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        if let Some(text) = query_text {
            if let Some(kw_index) = self.keyword_index.as_ref() {
                let vector_scores: Vec<(String, f32)> = results_map
                    .iter()
                    .map(|(name, res)| (name.clone(), res.score))
                    .collect();
                let kw_hits = kw_index.search(text, limit * 2)?;
                let kw_hits_for_lookup = kw_hits.clone();

                let fused_results = keyword::apply_weighted_rrf(
                    vector_scores,
                    kw_hits,
                    keyword::RRF_K,
                    keyword::SEMANTIC_WEIGHT,
                    keyword::KEYWORD_WEIGHT,
                    text,
                );

                let kw_lookup: std::collections::HashMap<String, skill::ToolSearchResult> =
                    kw_hits_for_lookup
                        .iter()
                        .map(|r| (r.tool_name.clone(), r.clone()))
                        .collect();
                let mut new_map: std::collections::HashMap<String, skill::ToolSearchResult> =
                    std::collections::HashMap::new();

                for fused in fused_results {
                    let tool_info = if let Some(orig) = results_map.get(&fused.tool_name) {
                        orig.clone()
                    } else if let Some(kw) = kw_lookup.get(&fused.tool_name) {
                        kw.clone()
                    } else {
                        continue;
                    };
                    let mut tool = tool_info;
                    tool.score = fused.rrf_score;
                    new_map.insert(fused.tool_name.clone(), tool);
                }
                results_map = new_map;
            }
        }

        let mut results: Vec<skill::ToolSearchResult> = results_map.into_values().collect();
        if threshold > 0.0 {
            results.retain(|r| r.score >= threshold);
        }
        results.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        results.truncate(limit);
        Ok(results)
    }

    /// Fast registry loading for MCP initialization.
    pub async fn load_tool_registry(
        &self,
        table_name: &str,
    ) -> Result<Vec<skill::ToolSearchResult>, VectorStoreError> {
        use lance::deps::arrow_array::Array;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(Vec::new());
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let mut scanner = dataset.scan();
        scanner.project(&[METADATA_COLUMN, CONTENT_COLUMN])?;
        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let mut tools: Vec<skill::ToolSearchResult> = Vec::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let content_col = batch.column_by_name(CONTENT_COLUMN);

            if let (Some(m_col), Some(c_col)) = (metadata_col, content_col) {
                let metadata_arr = m_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let content_arr = c_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();

                if let (Some(metadata_arr), Some(content_arr)) = (metadata_arr, content_arr) {
                    use lance::deps::arrow_array::Array;
                    for i in 0..batch.num_rows() {
                        if metadata_arr.is_null(i) {
                            continue;
                        }
                        let metadata_str = metadata_arr.value(i);
                        if let Ok(meta) = serde_json::from_str::<Value>(&metadata_str) {
                            if meta.get("type").and_then(|t| t.as_str()) != Some("command") {
                                continue;
                            }
                            let name = meta
                                .get("command")
                                .and_then(|s| s.as_str())
                                .unwrap_or("")
                                .to_string();
                            if name.is_empty() {
                                continue;
                            }
                            let skill_name = meta
                                .get("skill_name")
                                .and_then(|s| s.as_str())
                                .unwrap_or("")
                                .to_string();
                            let tool_name = meta
                                .get("tool_name")
                                .and_then(|s| s.as_str())
                                .unwrap_or("")
                                .to_string();
                            let file_path = meta
                                .get("file_path")
                                .and_then(|s| s.as_str())
                                .unwrap_or("")
                                .to_string();
                            let keywords: Vec<String> = meta
                                .get("keywords")
                                .and_then(|k| k.as_array())
                                .map(|arr| {
                                    arr.iter()
                                        .filter_map(|k| k.as_str().map(|s| s.to_string()))
                                        .collect()
                                })
                                .unwrap_or_default();
                            let input_schema = meta
                                .get("input_schema")
                                .cloned()
                                .unwrap_or(Value::Object(serde_json::Map::new()));
                            let description = content_arr.value(i).to_string();

                            tools.push(skill::ToolSearchResult {
                                name,
                                description,
                                input_schema,
                                score: 1.0,
                                skill_name,
                                tool_name,
                                file_path,
                                keywords,
                            });
                        }
                    }
                }
            }
        }
        Ok(tools)
    }
}

// ============================================================================
// Module Declarations
// ============================================================================

pub use error::VectorStoreError;
pub mod batch;
pub mod checkpoint;
pub mod error;
pub mod index;
pub mod keyword;
pub mod search;
pub mod skill;
