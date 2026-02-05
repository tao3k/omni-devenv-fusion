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
mod search_ops;
mod store;
mod tool_ops;
pub mod tool_record;

pub use tool_record::PyToolRecord;

// Re-export helper functions for use in PyVectorStore methods
use analytics::{get_all_file_hashes_async, get_analytics_table_async};
use doc_ops::{add_documents_async, add_single_async, delete_async, delete_by_file_path_async};
use search_ops::{
    create_index_async, load_tool_registry_async, scan_skill_tools_raw, search_async,
    search_filtered_async, search_hybrid_async, search_tools_async,
};
use store::{create_vector_store, store_count, store_drop_table, store_new};

// ============================================================================
// PyVectorStore - Main vector store class
// ============================================================================

/// Python wrapper for VectorStore (omni-vector / LanceDB)
#[pyclass]
pub struct PyVectorStore {
    path: String,
    dimension: usize,
    enable_keyword_index: bool,
}

#[pymethods]
impl PyVectorStore {
    // -------------------------------------------------------------------------
    // Store Lifecycle
    // -------------------------------------------------------------------------

    #[new]
    #[pyo3(signature = (path, dimension = 1536, enable_keyword_index = false))]
    fn new(path: String, dimension: usize, enable_keyword_index: bool) -> PyResult<Self> {
        store_new(path, dimension, enable_keyword_index)
    }

    fn count(&self, table_name: String) -> PyResult<u32> {
        store_count(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            table_name,
        )
    }

    fn drop_table(&self, table_name: String) -> PyResult<()> {
        store_drop_table(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            table_name,
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
            &table_name,
            ids,
            vectors,
            contents,
            metadatas,
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
            &table_name.unwrap_or_else(|| "skills".to_string()),
            file_paths,
        )
    }

    // -------------------------------------------------------------------------
    // Search Operations
    // -------------------------------------------------------------------------

    fn search(&self, table_name: String, query: Vec<f32>, limit: usize) -> PyResult<Vec<String>> {
        search_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            &table_name,
            query,
            limit,
        )
    }

    fn search_filtered(
        &self,
        table_name: String,
        query: Vec<f32>,
        limit: usize,
        where_filter: Option<String>,
    ) -> PyResult<Vec<String>> {
        search_filtered_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            &table_name,
            query,
            limit,
            where_filter,
        )
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
            &table_name,
        )
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
            &base_path,
            &table_name,
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
            &table_name,
        )
    }

    fn get_analytics_table(&self, table_name: Option<String>) -> PyResult<Py<PyAny>> {
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        get_analytics_table_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            &table_name,
        )
    }

    // -------------------------------------------------------------------------
    // Tool Operations
    // -------------------------------------------------------------------------

    #[pyo3(signature = (table_name, query_vector, query_text=None, limit=5, threshold=0.0))]
    fn search_tools(
        &self,
        table_name: Option<String>,
        query_vector: Vec<f32>,
        query_text: Option<String>,
        limit: usize,
        threshold: f32,
    ) -> PyResult<Vec<Py<PyAny>>> {
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        search_tools_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            &table_name,
            query_vector,
            query_text,
            limit,
            threshold,
        )
    }

    fn load_tool_registry(&self, table_name: Option<String>) -> PyResult<Vec<Py<PyAny>>> {
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        load_tool_registry_async(
            &self.path,
            self.dimension,
            self.enable_keyword_index,
            &table_name,
        )
    }
}

/// Create a vector store (exported as create_vector_store in Python)
#[pyfunction]
#[pyo3(name = "create_vector_store", signature = (path, dimension = 1536, enable_keyword_index = false))]
pub fn create_vector_store_py(
    path: String,
    dimension: usize,
    enable_keyword_index: bool,
) -> PyResult<PyVectorStore> {
    create_vector_store(path, dimension, enable_keyword_index)
}
