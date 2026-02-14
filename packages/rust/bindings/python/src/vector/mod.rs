//! Vector Store - Python Bindings for omni-vector / LanceDB
//!
//! ## Module Structure (by functionality)
//!
//! ```text
//! vector/
//!   ├── mod.rs           # PyVectorStore definition and public API
//!   ├── store.rs         # Store lifecycle (new, count, drop_table)
//!   ├── doc_ops.rs       # Document operations (add, delete)
//!   ├── search_ops.rs    # Search operations (search, search_tools, scan)
//!   ├── tool_ops.rs      # Tool indexing operations
//!   ├── analytics.rs     # Analytics operations
//!   └── tool_record.rs   # PyToolRecord wrapper
//! ```

use pyo3::prelude::*;

mod analytics;
mod doc_ops;
mod ipc;
mod search_ops;
mod store;
mod tool_ops;
pub mod tool_record;

pub use tool_record::PyToolRecord;

// Re-export helper functions for use in PyVectorStore methods
use analytics::{get_all_file_hashes_async, get_analytics_table_async};
use doc_ops::{
    add_documents_async, add_documents_partitioned_async, add_single_async, delete_async,
    delete_by_file_path_async, merge_insert_documents_async, replace_documents_async,
};
use search_ops::{
    agentic_search_async, create_index_async, load_tool_registry_async, scan_skill_tools_raw,
    search_hybrid_async, search_optimized_async, search_optimized_ipc_async, search_tools_async,
    search_tools_ipc_async,
};
use store::{
    create_vector_store, store_add_columns, store_alter_columns, store_analyze_table_health,
    store_analyze_table_health_ipc, store_auto_index_if_needed, store_check_migrations,
    store_compact, store_count, store_create_bitmap_index, store_create_btree_index,
    store_create_hnsw_index, store_create_index_background, store_create_optimal_vector_index,
    store_drop_columns, store_drop_table, store_get_fragment_stats, store_get_index_cache_stats,
    store_get_query_metrics, store_get_table_info, store_list_versions, store_migrate, store_new,
    store_suggest_partition_column,
};

// ============================================================================
// PyVectorStore - Main vector store class
// ============================================================================

/// Python wrapper for VectorStore (omni-vector / LanceDB)
#[pyclass]
pub struct PyVectorStore {
    path: String,
    dimension: usize,
    enable_keyword_index: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
}

#[pymethods]
impl PyVectorStore {
    // -------------------------------------------------------------------------
    // Store Lifecycle
    // -------------------------------------------------------------------------

    #[new]
    #[pyo3(signature = (path, dimension = 1536, enable_keyword_index = false, index_cache_size_bytes = None, max_cached_tables = None))]
    fn new(
        path: String,
        dimension: usize,
        enable_keyword_index: bool,
        index_cache_size_bytes: Option<usize>,
        max_cached_tables: Option<usize>,
    ) -> PyResult<Self> {
        store_new(
            path,
            dimension,
            enable_keyword_index,
            index_cache_size_bytes,
            max_cached_tables,
        )
    }

    fn count(&self, table_name: String) -> PyResult<u32> {
        store_count(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    fn drop_table(&self, table_name: String) -> PyResult<()> {
        store_drop_table(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    fn get_table_info(&self, table_name: String) -> PyResult<String> {
        store_get_table_info(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    fn list_versions(&self, table_name: String) -> PyResult<String> {
        store_list_versions(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    fn get_fragment_stats(&self, table_name: String) -> PyResult<String> {
        store_get_fragment_stats(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    fn analyze_table_health(&self, table_name: String) -> PyResult<String> {
        store_analyze_table_health(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    fn analyze_table_health_ipc(
        &self,
        py: Python<'_>,
        table_name: String,
    ) -> PyResult<Py<pyo3::types::PyBytes>> {
        let bytes = store_analyze_table_health_ipc(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )?;
        Ok(pyo3::types::PyBytes::new(py, &bytes).unbind())
    }

    fn compact(&self, table_name: String) -> PyResult<String> {
        store_compact(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    /// List pending schema migrations for a table. Returns JSON array of {from_version, to_version, description}.
    fn check_migrations(&self, table_name: String) -> PyResult<String> {
        store_check_migrations(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    /// Run pending schema migrations for a table. Returns JSON object {applied: [[from,to],...], rows_processed}.
    fn migrate(&self, table_name: String) -> PyResult<String> {
        store_migrate(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    fn get_query_metrics(&self, table_name: String) -> PyResult<String> {
        store_get_query_metrics(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    fn get_index_cache_stats(&self, table_name: String) -> PyResult<String> {
        store_get_index_cache_stats(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    /// Create a BTree index on a column (exact match / range). Returns index stats as JSON.
    fn create_btree_index(&self, table_name: String, column: String) -> PyResult<String> {
        store_create_btree_index(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
            column,
        )
    }

    /// Create a Bitmap index on a column (low-cardinality). Returns index stats as JSON.
    fn create_bitmap_index(&self, table_name: String, column: String) -> PyResult<String> {
        store_create_bitmap_index(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
            column,
        )
    }

    /// Create an IVF+HNSW vector index. Requires at least 50 rows. Returns index stats as JSON.
    fn create_hnsw_index(&self, table_name: String) -> PyResult<String> {
        store_create_hnsw_index(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    /// Start building the vector index in a background task. Returns immediately; index builds asynchronously.
    fn create_index_background(&self, table_name: String) -> PyResult<()> {
        store_create_index_background(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    /// Create the best vector index for table size (HNSW small tables, IVF_FLAT large). Returns index stats as JSON.
    fn create_optimal_vector_index(&self, table_name: String) -> PyResult<String> {
        store_create_optimal_vector_index(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    /// Suggest a partition column for the table if large and schema supports it (e.g. skill_name). Returns None if not applicable.
    fn suggest_partition_column(&self, table_name: String) -> PyResult<Option<String>> {
        store_suggest_partition_column(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    /// Create vector/FTS/scalar indexes if table meets row thresholds. Returns last index stats as JSON or None.
    fn auto_index_if_needed(&self, table_name: String) -> PyResult<Option<String>> {
        store_auto_index_if_needed(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
        )
    }

    fn add_columns(&self, table_name: String, payload_json: String) -> PyResult<()> {
        store_add_columns(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
            payload_json,
        )
    }

    fn alter_columns(&self, table_name: String, payload_json: String) -> PyResult<()> {
        store_alter_columns(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
            payload_json,
        )
    }

    fn drop_columns(&self, table_name: String, columns: Vec<String>) -> PyResult<()> {
        store_drop_columns(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            table_name,
            columns,
        )
    }

    // -------------------------------------------------------------------------
    // Document Operations
    // -------------------------------------------------------------------------

    fn add_documents(
        &self,
        table_name: String,
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
    ) -> PyResult<()> {
        add_documents_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
            ids,
            vectors,
            contents,
            metadatas,
        )
    }

    fn add_documents_partitioned(
        &self,
        table_name: String,
        partition_by: String,
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
    ) -> PyResult<()> {
        add_documents_partitioned_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
            &partition_by,
            ids,
            vectors,
            contents,
            metadatas,
        )
    }

    fn replace_documents(
        &self,
        table_name: String,
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
    ) -> PyResult<()> {
        replace_documents_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
            ids,
            vectors,
            contents,
            metadatas,
        )
    }

    fn merge_insert_documents(
        &self,
        table_name: String,
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
        match_on: Option<String>,
    ) -> PyResult<String> {
        merge_insert_documents_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
            ids,
            vectors,
            contents,
            metadatas,
            match_on.unwrap_or_else(|| "id".to_string()),
        )
    }

    fn add(
        &self,
        table_name: String,
        content: String,
        vector: Vec<f32>,
        metadata: String,
    ) -> PyResult<()> {
        add_single_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
            content,
            vector,
            metadata,
        )
    }

    fn delete(&self, table_name: String, ids: Vec<String>) -> PyResult<()> {
        delete_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
            ids,
        )
    }

    fn delete_by_file_path(
        &self,
        table_name: Option<String>,
        file_paths: Vec<String>,
    ) -> PyResult<()> {
        delete_by_file_path_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name.unwrap_or_else(|| "skills".to_string()),
            file_paths,
        )
    }

    // -------------------------------------------------------------------------
    // Search Operations
    // -------------------------------------------------------------------------

    fn search_optimized(
        &self,
        table_name: String,
        query: Vec<f32>,
        limit: usize,
        options_json: Option<String>,
    ) -> PyResult<Vec<String>> {
        search_optimized_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
            query,
            limit,
            options_json,
        )
    }

    /// Search and return Arrow IPC stream bytes (single RecordBatch) for zero-copy consumption.
    /// Use: ``pyarrow.ipc.open_stream(io.BytesIO(bytes)).read_all()``. See search-result-batch-contract.md.
    fn search_optimized_ipc(
        &self,
        py: Python<'_>,
        table_name: String,
        query: Vec<f32>,
        limit: usize,
        options_json: Option<String>,
    ) -> PyResult<Py<pyo3::types::PyBytes>> {
        let bytes = search_optimized_ipc_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
            query,
            limit,
            options_json,
        )?;
        Ok(pyo3::types::PyBytes::new(py, &bytes).unbind())
    }

    fn search_hybrid(
        &self,
        table_name: String,
        query: Vec<f32>,
        keywords: Vec<String>,
        limit: usize,
    ) -> PyResult<Vec<String>> {
        let query_text = keywords.first().cloned().unwrap_or_default();
        search_hybrid_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
            query,
            query_text,
            limit,
        )
    }

    fn create_index(&self, table_name: String) -> PyResult<()> {
        create_index_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
        )
    }

    /// Return canonical hybrid-search profile owned by Rust runtime.
    fn get_search_profile(&self) -> PyResult<Py<PyAny>> {
        Python::attach(|py| {
            let field_boosting = pyo3::types::PyDict::new(py);
            field_boosting.set_item("name_token_boost", 0.5)?;
            field_boosting.set_item("exact_phrase_boost", 1.5)?;

            let profile = pyo3::types::PyDict::new(py);
            profile.set_item("semantic_weight", 1.0)?;
            profile.set_item("keyword_weight", 1.5)?;
            profile.set_item("rrf_k", 10)?;
            profile.set_item("implementation", "rust-native-weighted-rrf")?;
            profile.set_item("strategy", "weighted_rrf_field_boosting")?;
            profile.set_item("field_boosting", field_boosting)?;
            Ok(profile.into_pyobject(py)?.into())
        })
    }

    // -------------------------------------------------------------------------
    // Tool Indexing Operations
    // -------------------------------------------------------------------------

    fn index_skill_tools(&self, base_path: String, table_name: Option<String>) -> PyResult<usize> {
        use tool_ops::index_skill_tools_async;

        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        index_skill_tools_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &base_path,
            &table_name,
        )
    }

    fn index_skill_tools_dual(
        &self,
        base_path: String,
        skills_table: Option<String>,
        router_table: Option<String>,
    ) -> PyResult<(usize, usize)> {
        use tool_ops::index_skill_tools_dual_async;

        let skills_table = skills_table.unwrap_or_else(|| "skills".to_string());
        let router_table = router_table.unwrap_or_else(|| "router".to_string());
        index_skill_tools_dual_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &base_path,
            &skills_table,
            &router_table,
        )
    }

    fn scan_skill_tools_raw(&self, base_path: String) -> PyResult<Vec<String>> {
        scan_skill_tools_raw(&base_path)
    }

    /// Get complete skill index with full metadata (routing_keywords, intents, authors, etc.)
    ///
    /// This scans the filesystem directly and returns all SkillIndexEntry data as JSON.
    /// Uses `SkillScanner::build_index_entry` for consistent tool deduplication.
    fn get_skill_index(&self, base_path: String) -> PyResult<String> {
        use omni_scanner::{SkillScanner, ToolsScanner};
        use std::path::Path;

        let skill_scanner = SkillScanner::new();
        let script_scanner = ToolsScanner::new();
        let skills_path = Path::new(&base_path);

        if !skills_path.exists() {
            return Ok("[]".to_string());
        }

        let metadatas = skill_scanner
            .scan_all(skills_path, None)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        // Build SkillIndexEntry for each skill with its tools
        // Reuse build_index_entry for consistent deduplication logic
        let mut skill_entries: Vec<omni_scanner::SkillIndexEntry> = Vec::new();

        for metadata in metadatas {
            let skill_path = skills_path.join(&metadata.skill_name);
            let skill_scripts_path = &skill_path;

            // Scan tools for this skill (returns ToolRecord, not IndexToolEntry)
            let tool_records: Vec<omni_scanner::ToolRecord> = match script_scanner.scan_scripts(
                skill_scripts_path,
                &metadata.skill_name,
                &metadata.routing_keywords,
                &metadata.intents,
            ) {
                Ok(tools) => tools,
                Err(e) => {
                    eprintln!(
                        "Warning: Failed to scan tools for '{}': {}",
                        metadata.skill_name, e
                    );
                    Vec::new()
                }
            };

            // build_index_entry handles tool deduplication internally
            let entry =
                skill_scanner.build_index_entry(metadata, &tool_records, skill_scripts_path);
            skill_entries.push(entry);
        }

        serde_json::to_string(&skill_entries)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    }

    fn list_all_tools(&self, table_name: Option<String>) -> PyResult<String> {
        use tool_ops::list_all_tools_async;

        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        list_all_tools_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
        )
    }

    /// List all skill-declared resources (rows with non-empty resource_uri).
    fn list_all_resources(&self, table_name: Option<String>) -> PyResult<String> {
        use tool_ops::list_all_resources_async;

        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        list_all_resources_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
        )
    }

    // -------------------------------------------------------------------------
    // Analytics Operations
    // -------------------------------------------------------------------------

    fn get_all_file_hashes(&self, table_name: Option<String>) -> PyResult<String> {
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        get_all_file_hashes_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
        )
    }

    fn get_analytics_table(&self, table_name: Option<String>) -> PyResult<Py<PyAny>> {
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        get_analytics_table_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
        )
    }

    // -------------------------------------------------------------------------
    // Tool Operations
    // -------------------------------------------------------------------------

    #[pyo3(signature = (
        table_name,
        query_vector,
        query_text=None,
        limit=5,
        threshold=0.0,
        confidence_profile_json=None,
        rerank=true
    ))]
    fn search_tools(
        &self,
        table_name: Option<String>,
        query_vector: Vec<f32>,
        query_text: Option<String>,
        limit: usize,
        threshold: f32,
        confidence_profile_json: Option<String>,
        rerank: bool,
    ) -> PyResult<Vec<Py<PyAny>>> {
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        search_tools_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
            query_vector,
            query_text,
            limit,
            threshold,
            confidence_profile_json,
            rerank,
        )
    }

    #[pyo3(signature = (table_name, query_vector, query_text=None, limit=5, threshold=0.0, rerank=true))]
    fn search_tools_ipc(
        &self,
        table_name: Option<String>,
        query_vector: Vec<f32>,
        query_text: Option<String>,
        limit: usize,
        threshold: f32,
        rerank: bool,
    ) -> PyResult<Vec<u8>> {
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        search_tools_ipc_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
            query_vector,
            query_text,
            limit,
            threshold,
            rerank,
        )
    }

    #[pyo3(signature = (table_name, query_vector, query_text=None, limit=5, threshold=0.0, intent=None, confidence_profile_json=None, rerank=true, skill_name_filter=None, category_filter=None, semantic_weight=None, keyword_weight=None))]
    fn agentic_search(
        &self,
        table_name: String,
        query_vector: Vec<f32>,
        query_text: Option<String>,
        limit: usize,
        threshold: f32,
        intent: Option<String>,
        confidence_profile_json: Option<String>,
        rerank: bool,
        skill_name_filter: Option<String>,
        category_filter: Option<String>,
        semantic_weight: Option<f32>,
        keyword_weight: Option<f32>,
    ) -> PyResult<Vec<Py<PyAny>>> {
        let table = if table_name.is_empty() {
            "skills".to_string()
        } else {
            table_name
        };
        agentic_search_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table,
            query_vector,
            query_text,
            limit,
            threshold,
            intent,
            confidence_profile_json,
            rerank,
            skill_name_filter,
            category_filter,
            semantic_weight,
            keyword_weight,
        )
    }

    #[pyo3(signature = (table_name, confidence_profile_json=None))]
    fn load_tool_registry(
        &self,
        table_name: Option<String>,
        confidence_profile_json: Option<String>,
    ) -> PyResult<Vec<Py<PyAny>>> {
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        load_tool_registry_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            self.index_cache_size_bytes,
            self.max_cached_tables,
            &table_name,
            confidence_profile_json,
        )
    }
}

/// Create a vector store (exported as create_vector_store in Python)
#[pyfunction]
#[pyo3(
    name = "create_vector_store",
    signature = (path, dimension = 1536, enable_keyword_index = false, index_cache_size_bytes = None, max_cached_tables = None)
)]
pub fn create_vector_store_py(
    path: String,
    dimension: usize,
    enable_keyword_index: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
) -> PyResult<PyVectorStore> {
    create_vector_store(
        path,
        dimension,
        enable_keyword_index,
        index_cache_size_bytes,
        max_cached_tables,
    )
}
