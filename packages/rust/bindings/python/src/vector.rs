//! Vector Store - Python Bindings for omni-vector / LanceDB
//!
//! Provides semantic search and vector storage capabilities.

use omni_vector::{ToolRecord, VectorStore};
use pyo3::prelude::*;
use std::path::Path;

/// Python wrapper for ToolRecord
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
    #[pyo3(get)]
    file_hash: String,
    #[pyo3(get)]
    category: String,
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
            file_hash: record.file_hash.clone(),
            category: record.category.clone(),
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

    /// Hybrid search with keyword boosting.
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

    /// Add a single document to the vector store.
    ///
    /// This is a convenience wrapper around add_documents for single-item additions.
    /// Matches the Python interface: add(collection, content, vector, metadata_json)
    ///
    /// Args:
    ///   table_name: Name of the table (called "collection" in Python)
    ///   content: Text content to store
    ///   vector: Pre-computed embedding vector
    ///   metadata: JSON string of metadata
    ///
    /// Returns:
    ///   Ok(()) on success
    fn add(
        &self,
        table_name: String,
        content: String,
        vector: Vec<f32>,
        metadata: String,
    ) -> PyResult<()> {
        let path = self.path.clone();
        let dimension = self.dimension;
        // Generate a UUID for the document
        let id = uuid::Uuid::new_v4().to_string();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .add_documents(
                    &table_name,
                    vec![id],
                    vec![vector],
                    vec![content],
                    vec![metadata],
                )
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

    /// Index all tools from skills scripts directory.
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

    /// Scan for skill tools without indexing (sync version).
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
        // Use SkillScanner for metadata and ToolsScanner for tools
        let skill_scanner = omni_vector::SkillScanner::new();
        let script_scanner = omni_vector::ToolsScanner::new();
        let skills_path = Path::new(&base_path);

        if !skills_path.exists() {
            return Ok(vec![]);
        }

        // Step 1: Scan SKILL.md files to get routing_keywords
        let metadatas = skill_scanner
            .scan_all(skills_path, None)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        // Step 2: For each skill, scan scripts with routing_keywords
        let mut all_tools: Vec<omni_vector::ToolRecord> = Vec::new();

        for metadata in &metadatas {
            let skill_scripts_path = skills_path.join(&metadata.skill_name).join("scripts");

            match script_scanner.scan_scripts(
                &skill_scripts_path,
                &metadata.skill_name,
                &metadata.routing_keywords,
            ) {
                Ok(tools) => all_tools.extend(tools),
                Err(e) => eprintln!(
                    "Warning: Failed to scan scripts for '{}': {}",
                    metadata.skill_name, e
                ),
            }
        }

        // Convert to JSON strings
        let json_tools: Vec<String> = all_tools
            .into_iter()
            .map(|t| serde_json::to_string(&t).unwrap_or_default())
            .filter(|s| !s.is_empty())
            .collect();

        Ok(json_tools)
    }

    /// Get all tools for a skill.
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

    /// Get all file hashes from the database for incremental sync.
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

    /// Delete documents by file path.
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

    /// List all tools from LanceDB as JSON.
    ///
    /// Enables using LanceDB as the Single Source of Truth instead of skill_index.json.
    /// Returns tools with: name, description, skill_name, category, input_schema, file_path, keywords.
    ///
    /// Args:
    ///   table_name: Name of the table (default: "skills")
    ///
    /// Returns:
    ///   JSON string of tool array
    fn list_all_tools(&self, table_name: Option<String>) -> PyResult<String> {
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
                .list_all_tools(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Get all tools as a PyArrow Table for analytics.
    ///
    /// This is optimized for high-performance operations using Arrow's columnar format.
    /// The metadata JSON column is parsed into separate columns for easier querying.
    ///
    /// Args:
    ///   table_name: Name of the table (default: "skills")
    ///
    /// Returns:
    ///   PyArrow Table with columns: id, content, skill_name, tool_name, file_path, keywords, etc.
    fn get_analytics_table(&self, table_name: Option<String>) -> PyResult<Py<PyAny>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        let json_tools = rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .list_all_tools(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })?;

        // Convert JSON to PyArrow Table in Python
        pyo3::Python::attach(|py| -> PyResult<Py<PyAny>> {
            // Parse JSON
            let json_mod = py.import("json")?;
            let loads_fn = json_mod.getattr("loads")?;
            let tools_py: pyo3::Bound<'_, pyo3::types::PyList> =
                loads_fn.call1((json_tools,))?.extract()?;

            // Create empty Python lists using PyList::empty
            let ids = pyo3::types::PyList::empty(py);
            let contents = pyo3::types::PyList::empty(py);
            let skill_names = pyo3::types::PyList::empty(py);
            let tool_names = pyo3::types::PyList::empty(py);
            let file_paths = pyo3::types::PyList::empty(py);
            let keywords = pyo3::types::PyList::empty(py);

            for item in tools_py.iter() {
                let tool_dict = item.cast::<pyo3::types::PyDict>()?;

                // get_item returns Result<Option<Bound<PyAny>>, PyErr>
                if let Ok(Some(id_any)) = tool_dict.get_item("id") {
                    let id_: String = id_any.extract()?;
                    ids.append(id_)?;
                }
                if let Ok(Some(content_any)) = tool_dict.get_item("content") {
                    let content: String = content_any.extract()?;
                    contents.append(content)?;
                }
                if let Ok(Some(skill_any)) = tool_dict.get_item("skill_name") {
                    let skill: String = skill_any.extract()?;
                    skill_names.append(skill)?;
                }
                if let Ok(Some(tool_any)) = tool_dict.get_item("tool_name") {
                    let tool_: String = tool_any.extract()?;
                    tool_names.append(tool_)?;
                }
                if let Ok(Some(fp_any)) = tool_dict.get_item("file_path") {
                    let fp: String = fp_any.extract()?;
                    file_paths.append(fp)?;
                }
                if let Ok(Some(kw_any)) = tool_dict.get_item("keywords") {
                    let kw_list: pyo3::Bound<'_, pyo3::types::PyList> = kw_any.extract()?;
                    let mut kw_strings: Vec<String> = Vec::new();
                    for kw in kw_list.iter() {
                        if let Ok(kw_str) = kw.extract() {
                            kw_strings.push(kw_str);
                        }
                    }
                    keywords.append(kw_strings)?;
                }
            }

            // Create PyArrow table from dict of columns
            let pyarrow = py.import("pyarrow")?;
            let table_fn = pyarrow.getattr("table")?;

            let columns_dict = pyo3::types::PyDict::new(py);

            columns_dict.set_item("id", ids.as_any())?;
            columns_dict.set_item("content", contents.as_any())?;
            columns_dict.set_item("skill_name", skill_names.as_any())?;
            columns_dict.set_item("tool_name", tool_names.as_any())?;
            columns_dict.set_item("file_path", file_paths.as_any())?;
            columns_dict.set_item("keywords", keywords.as_any())?;

            let table = table_fn.call1((columns_dict,))?;

            Ok(table.unbind())
        })
    }

    /// High-performance tool search with integrated filtering and scoring.
    ///
    /// Performs the entire search pipeline in Rust:
    /// - Vector similarity computation (L2 distance)
    /// - Score threshold filtering
    /// - Metadata parsing and validation
    /// - Returns pre-formatted dicts
    ///
    /// Args:
    ///   table_name: Table containing tool records (default: "skills")
    ///   query_vector: Query embedding vector
    ///   limit: Maximum number of results to return
    ///   threshold: Minimum score threshold (0.0 to 1.0, default: 0.0)
    ///
    /// Returns:
    ///   List of dicts with: name, description, input_schema (JSON), score, skill_name, tool_name, file_path, keywords
    #[allow(deprecated)]
    fn search_tools(
        &self,
        table_name: Option<String>,
        query_vector: Vec<f32>,
        limit: usize,
        threshold: Option<f32>,
    ) -> PyResult<Vec<PyObject>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        let threshold = threshold.unwrap_or(0.0);

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

            let results = store
                .search_tools(&table_name, &query_vector, limit, threshold)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

            // Convert to Python dicts
            let py_results = pyo3::Python::with_gil(|py| -> PyResult<Vec<PyObject>> {
                let mut dicts = Vec::with_capacity(results.len());
                for r in results {
                    let dict = pyo3::types::PyDict::new(py);
                    dict.set_item("name", r.name)?;
                    dict.set_item("description", r.description)?;
                    // Convert input_schema Value to JSON string for Python to parse
                    dict.set_item("input_schema", r.input_schema.to_string())?;
                    dict.set_item("score", r.score)?;
                    dict.set_item("skill_name", r.skill_name)?;
                    dict.set_item("tool_name", r.tool_name)?;
                    dict.set_item("file_path", r.file_path)?;
                    dict.set_item("keywords", r.keywords)?;
                    // Convert Bound<PyDict> to PyObject using into_pyobject and into()
                    dicts.push(dict.into_pyobject(py)?.into());
                }
                Ok(dicts)
            });
            py_results
        })
    }

    /// Fast registry loading for MCP initialization.
    ///
    /// Loads all tools from the database with minimal IO:
    /// - Only reads METADATA and CONTENT columns
    /// - Returns pre-formatted dicts
    /// - No vector computation needed (score = 1.0 for all)
    ///
    /// This is used during MCP server startup to build the tool registry.
    ///
    /// Args:
    ///   table_name: Table containing tool records (default: "skills")
    ///
    /// Returns:
    ///   List of dicts with: name, description, input_schema (JSON), score=1.0, skill_name, tool_name, file_path, keywords
    #[allow(deprecated)]
    fn load_tool_registry(&self, table_name: Option<String>) -> PyResult<Vec<PyObject>> {
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

            let results = store
                .load_tool_registry(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

            // Convert to Python dicts
            let py_results = pyo3::Python::with_gil(|py| -> PyResult<Vec<PyObject>> {
                let mut dicts = Vec::with_capacity(results.len());
                for r in results {
                    let dict = pyo3::types::PyDict::new(py);
                    dict.set_item("name", r.name)?;
                    dict.set_item("description", r.description)?;
                    // Convert input_schema Value to JSON string for Python to parse
                    dict.set_item("input_schema", r.input_schema.to_string())?;
                    dict.set_item("score", r.score)?;
                    dict.set_item("skill_name", r.skill_name)?;
                    dict.set_item("tool_name", r.tool_name)?;
                    dict.set_item("file_path", r.file_path)?;
                    dict.set_item("keywords", r.keywords)?;
                    // Convert Bound<PyDict> to PyObject using into_pyobject and into()
                    dicts.push(dict.into_pyobject(py)?.into());
                }
                Ok(dicts)
            });
            py_results
        })
    }
}

/// Create a vector store (convenience function)
#[pyfunction]
#[pyo3(signature = (path, dimension = None))]
pub fn create_vector_store(path: String, dimension: Option<usize>) -> PyResult<PyVectorStore> {
    PyVectorStore::new(path, dimension)
}
