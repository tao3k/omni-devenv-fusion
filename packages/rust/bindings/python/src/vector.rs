//! Vector Store - Python Bindings for omni-vector / LanceDB
//!
//! Phase 53/57: Provides semantic search and vector storage capabilities.

use omni_vector::{ToolRecord, VectorStore};
use pyo3::prelude::*;
use std::path::Path;

/// Python wrapper for ToolRecord (Phase 62)
/// Represents a discovered tool from script scanning.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyToolRecord {
    #[pyo3(get)]
    tool_name: String,
    #[pyo3(get)]
    description: String,
    #[pyo3(get)]
    skill_name: String,
    #[pyo3(get)]
    file_path: String,
    #[pyo3(get)]
    function_name: String,
    #[pyo3(get)]
    execution_mode: String,
    #[pyo3(get)]
    keywords: Vec<String>,
    #[pyo3(get)]
    input_schema: String,
    #[pyo3(get)]
    docstring: String,
}

impl From<&ToolRecord> for PyToolRecord {
    fn from(record: &ToolRecord) -> Self {
        Self {
            tool_name: record.tool_name.clone(),
            description: record.description.clone(),
            skill_name: record.skill_name.clone(),
            file_path: record.file_path.clone(),
            function_name: record.function_name.clone(),
            execution_mode: record.execution_mode.clone(),
            keywords: record.keywords.clone(),
            input_schema: record.input_schema.clone(),
            docstring: record.docstring.clone(),
        }
    }
}

impl From<ToolRecord> for PyToolRecord {
    fn from(record: ToolRecord) -> Self {
        Self::from(&record)
    }
}

/// Python wrapper for VectorStore (omni-vector / LanceDB)
#[pyclass]
pub struct PyVectorStore {
    path: String,
    dimension: usize,
}

#[pymethods]
impl PyVectorStore {
    #[new]
    fn new(path: String, dimension: Option<usize>) -> PyResult<Self> {
        let dimension = dimension.unwrap_or(1536);

        // Verify we can create the store
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        rt.block_on(async {
            VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })?;

        Ok(PyVectorStore { path, dimension })
    }

    fn add_documents(
        &self,
        table_name: String,
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
    ) -> PyResult<()> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .add_documents(&table_name, ids, vectors, contents, metadatas)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    fn search(&self, table_name: String, query: Vec<f32>, limit: usize) -> PyResult<Vec<String>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let query = query.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let results = store
                .search(&table_name, query, limit)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            // Return JSON strings for easier Python processing
            let json_results: Vec<String> = results
                .into_iter()
                .map(|r| serde_json::to_string(&r).unwrap_or_default())
                .collect();
            Ok(json_results)
        })
    }

    /// Search with metadata filtering.
    ///
    /// Args:
    ///   table_name: Name of the table
    ///   query: Query vector for semantic search
    ///   limit: Maximum number of results
    ///   where_filter: Optional JSON filter (e.g., {"domain": "python"})
    ///
    /// Returns:
    ///   List of JSON strings representing search results
    fn search_filtered(
        &self,
        table_name: String,
        query: Vec<f32>,
        limit: usize,
        where_filter: Option<String>,
    ) -> PyResult<Vec<String>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let query = query.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let results = store
                .search_filtered(&table_name, query, limit, where_filter)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            // Return JSON strings for easier Python processing
            let json_results: Vec<String> = results
                .into_iter()
                .map(|r| serde_json::to_string(&r).unwrap_or_default())
                .collect();
            Ok(json_results)
        })
    }

    /// Phase 67: Hybrid search with keyword boosting.
    ///
    /// Combines vector similarity with keyword matching for better relevance.
    /// Formula: Score = Vector_Score * 0.7 + Keyword_Match * 0.3
    ///
    /// Args:
    ///   table_name: Name of the table
    ///   query: Query vector for semantic search
    ///   keywords: Keywords to boost (matched against metadata.keywords)
    ///   limit: Maximum number of results
    ///
    /// Returns:
    ///   List of JSON strings representing search results
    fn search_hybrid(
        &self,
        table_name: String,
        query: Vec<f32>,
        keywords: Vec<String>,
        limit: usize,
    ) -> PyResult<Vec<String>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let query = query.clone();
        let keywords = keywords.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let results = store
                .search_hybrid(&table_name, query, keywords, limit)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            // Return JSON strings for easier Python processing
            let json_results: Vec<String> = results
                .into_iter()
                .map(|r| serde_json::to_string(&r).unwrap_or_default())
                .collect();
            Ok(json_results)
        })
    }

    fn create_index(&self, table_name: String) -> PyResult<()> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .create_index(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    fn delete(&self, table_name: String, ids: Vec<String>) -> PyResult<()> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .delete(&table_name, ids)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    fn count(&self, table_name: String) -> PyResult<u32> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .count(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    fn drop_table(&self, table_name: String) -> PyResult<()> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .drop_table(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Phase 62: Index all tools from skills scripts directory.
    ///
    /// Scans `base_path/skills/*/scripts/*.py` for `@skill_command` decorated
    /// functions and indexes them for discovery.
    ///
    /// Args:
    ///   base_path: Base directory containing skills (e.g., "assets/skills")
    ///   table_name: Table to store tool records (default: "skills")
    ///
    /// Returns:
    ///   Number of tools indexed
    fn index_skill_tools(&self, base_path: String, table_name: Option<String>) -> PyResult<usize> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .index_skill_tools(&base_path, &table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            // Return count of indexed tools (we can count from table)
            let count = store
                .count(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            Ok(count as usize)
        })
    }

    /// Phase 64: Scan for skill tools without indexing (sync version).
    ///
    /// This method discovers @skill_command decorated functions without
    /// attempting schema extraction. Returns raw tool records as JSON strings
    /// that can be processed by Python for schema extraction.
    ///
    /// Args:
    ///   base_path: Base directory containing skills (e.g., "assets/skills")
    ///
    /// Returns:
    ///   List of JSON strings representing tool records
    fn scan_skill_tools_raw(&self, base_path: String) -> PyResult<Vec<String>> {
        // Use the omni-vector scanner directly
        let scanner = omni_vector::ScriptScanner::new();
        let skills_path = Path::new(&base_path);

        if !skills_path.exists() {
            return Ok(vec![]);
        }

        let tools = scanner
            .scan_all(skills_path)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        // Convert to JSON strings
        let json_tools: Vec<String> = tools
            .into_iter()
            .map(|t| serde_json::to_string(&t).unwrap_or_default())
            .filter(|s| !s.is_empty())
            .collect();

        Ok(json_tools)
    }

    /// Phase 62: Get all tools for a skill.
    ///
    /// Args:
    ///   skill_name: Name of the skill (e.g., "git")
    ///
    /// Returns:
    ///   List of tool metadata JSON strings
    fn get_tools_by_skill(&self, skill_name: String) -> PyResult<Vec<String>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let tools = store
                .get_tools_by_skill(&skill_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let json_tools: Vec<String> = tools
                .into_iter()
                .map(|t| serde_json::to_string(&t).unwrap_or_default())
                .collect();
            Ok(json_tools)
        })
    }

    /// Phase 64: Get all file hashes from the database for incremental sync.
    ///
    /// Args:
    ///   table_name: Name of the table (default: "skills")
    ///
    /// Returns:
    ///   JSON string of path -> {hash, id} mapping
    fn get_all_file_hashes(&self, table_name: Option<String>) -> PyResult<String> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .get_all_file_hashes(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Phase 64: Delete documents by file path.
    ///
    /// Args:
    ///   file_paths: List of file paths to delete
    ///   table_name: Name of the table (default: "skills")
    ///
    /// Returns:
    ///   Ok(()) on success
    fn delete_by_file_path(
        &self,
        table_name: Option<String>,
        file_paths: Vec<String>,
    ) -> PyResult<()> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .delete_by_file_path(&table_name, file_paths)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }
}

/// Create a vector store (convenience function)
#[pyfunction]
#[pyo3(signature = (path, dimension = None))]
pub fn create_vector_store(path: String, dimension: Option<usize>) -> PyResult<PyVectorStore> {
    PyVectorStore::new(path, dimension)
}
