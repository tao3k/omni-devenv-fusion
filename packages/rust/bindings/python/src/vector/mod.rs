//! Vector Store - Python Bindings for omni-vector / LanceDB
//!
//! Provides semantic search and vector storage capabilities.
//!
//! ## Module Structure (by functionality)
//!
//! ```text
//! vector/
//!   ├── mod.rs           # Main module, all PyVectorStore methods
//!   ├── tool_record.rs   # PyToolRecord wrapper (reusable)
//!   ├── doc_ops.rs       # Document operation helpers (for internal use)
//!   ├── search_ops.rs    # Search operation helpers (for internal use)
//!   └── tool_ops.rs      # Tool indexing helpers (for internal use)
//! ```

use omni_vector::VectorStore;
use pyo3::prelude::*;
use std::path::Path;

mod doc_ops;
mod search_ops;
mod tool_ops;
pub mod tool_record;

pub use tool_record::PyToolRecord;

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
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        rt.block_on(async {
            VectorStore::new_with_keyword_index(&path, Some(dimension), enable_keyword_index)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })?;

        Ok(PyVectorStore {
            path,
            dimension,
            enable_keyword_index,
        })
    }

    fn count(&self, table_name: String) -> PyResult<u32> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
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
        let enable_kw = self.enable_keyword_index;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .drop_table(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
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
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .add_documents(&table_name, ids, vectors, contents, metadatas)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    fn add(
        &self,
        table_name: String,
        content: String,
        vector: Vec<f32>,
        metadata: String,
    ) -> PyResult<()> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let id = uuid::Uuid::new_v4().to_string();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
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
        let enable_kw = self.enable_keyword_index;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .delete(&table_name, ids)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    fn delete_by_file_path(
        &self,
        table_name: Option<String>,
        file_paths: Vec<String>,
    ) -> PyResult<()> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .delete_by_file_path(&table_name, file_paths)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    // -------------------------------------------------------------------------
    // Search Operations
    // -------------------------------------------------------------------------

    fn search(&self, table_name: String, query: Vec<f32>, limit: usize) -> PyResult<Vec<String>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let query = query.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let results = store
                .search(&table_name, query, limit)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let json_results: Vec<String> = results
                .into_iter()
                .map(|r| serde_json::to_string(&r).unwrap_or_default())
                .collect();
            Ok(json_results)
        })
    }

    fn search_filtered(
        &self,
        table_name: String,
        query: Vec<f32>,
        limit: usize,
        where_filter: Option<String>,
    ) -> PyResult<Vec<String>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let query = query.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let results = store
                .search_filtered(&table_name, query, limit, where_filter)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let json_results: Vec<String> = results
                .into_iter()
                .map(|r| serde_json::to_string(&r).unwrap_or_default())
                .collect();
            Ok(json_results)
        })
    }

    fn search_hybrid(
        &self,
        table_name: String,
        query: Vec<f32>,
        keywords: Vec<String>,
        limit: usize,
    ) -> PyResult<Vec<String>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let query = query.clone();
        let keywords = keywords.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let results = store
                .search_tools(
                    &table_name,
                    &query,
                    keywords.first().as_ref().map(|s| s.as_str()),
                    limit,
                    0.0,
                )
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
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
        let enable_kw = self.enable_keyword_index;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .create_index(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    // -------------------------------------------------------------------------
    // Tool Indexing Operations
    // -------------------------------------------------------------------------

    fn index_skill_tools(&self, base_path: String, table_name: Option<String>) -> PyResult<usize> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .index_skill_tools(&base_path, &table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let count = store
                .count(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            Ok(count as usize)
        })
    }

    fn scan_skill_tools_raw(&self, base_path: String) -> PyResult<Vec<String>> {
        use skills_scanner::{SkillScanner, ToolRecord, ToolsScanner};

        let skill_scanner = SkillScanner::new();
        let script_scanner = ToolsScanner::new();
        let skills_path = Path::new(&base_path);

        if !skills_path.exists() {
            return Ok(vec![]);
        }

        let metadatas = skill_scanner
            .scan_all(skills_path, None)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        let mut all_tools: Vec<ToolRecord> = Vec::new();
        let empty_intents: &[String] = &[];

        for metadata in &metadatas {
            let skill_scripts_path = skills_path.join(&metadata.skill_name).join("scripts");

            match script_scanner.scan_scripts(
                &skill_scripts_path,
                &metadata.skill_name,
                &metadata.routing_keywords,
                empty_intents,
            ) {
                Ok(tools) => all_tools.extend(tools),
                Err(e) => eprintln!(
                    "Warning: Failed to scan for '{}': {}",
                    metadata.skill_name, e
                ),
            }
        }

        let json_tools: Vec<String> = all_tools
            .into_iter()
            .map(|t| serde_json::to_string(&t).unwrap_or_default())
            .filter(|s| !s.is_empty())
            .collect();

        Ok(json_tools)
    }

    /// Get complete skill index with full metadata (routing_keywords, intents, authors, etc.)
    ///
    /// This scans the filesystem directly and returns all SkillIndexEntry data as JSON.
    /// Unlike list_all_tools which only returns tool records from LanceDB,
    /// this method returns full skill metadata from SKILL.md frontmatter.
    fn get_skill_index(&self, base_path: String) -> PyResult<String> {
        use skills_scanner::{
            DocsAvailable, IndexToolEntry, SkillIndexEntry, SkillScanner, ToolsScanner,
        };

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
        let mut skill_entries: Vec<SkillIndexEntry> = Vec::new();

        for metadata in &metadatas {
            let skill_scripts_path = skills_path.join(&metadata.skill_name).join("scripts");

            // Scan tools for this skill
            let tools: Vec<IndexToolEntry> = match script_scanner.scan_scripts(
                &skill_scripts_path,
                &metadata.skill_name,
                &metadata.routing_keywords,
                &metadata.intents,
            ) {
                Ok(tool_records) => tool_records
                    .into_iter()
                    .map(|tr| IndexToolEntry {
                        name: tr.tool_name,
                        description: tr.description,
                        category: tr.category,
                        input_schema: tr.input_schema,
                        file_hash: tr.file_hash,
                    })
                    .collect(),
                Err(e) => {
                    eprintln!(
                        "Warning: Failed to scan tools for '{}': {}",
                        metadata.skill_name, e
                    );
                    Vec::new()
                }
            };

            // Build the full skill index entry with all metadata
            let entry = SkillIndexEntry {
                name: metadata.skill_name.clone(),
                description: metadata.description.clone(),
                version: metadata.version.clone(),
                path: format!("assets/skills/{}", metadata.skill_name),
                tools,
                routing_keywords: metadata.routing_keywords.clone(),
                intents: metadata.intents.clone(),
                authors: metadata.authors.clone(),
                docs_available: DocsAvailable::default(),
                oss_compliant: Vec::new(),
                compliance_details: Vec::new(),
                require_refs: metadata.require_refs.clone(),
                sniffing_rules: Vec::new(),
                permissions: metadata.permissions.clone(),
            };

            skill_entries.push(entry);
        }

        serde_json::to_string(&skill_entries)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    }

    fn list_all_tools(&self, table_name: Option<String>) -> PyResult<String> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .list_all_tools(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    // -------------------------------------------------------------------------
    // Analytics Operations
    // -------------------------------------------------------------------------

    fn get_all_file_hashes(&self, table_name: Option<String>) -> PyResult<String> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .get_all_file_hashes(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    fn get_analytics_table(&self, table_name: Option<String>) -> PyResult<Py<PyAny>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        let json_tools = rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store
                .list_all_tools(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })?;

        pyo3::Python::attach(|py| -> PyResult<Py<PyAny>> {
            let json_mod = py.import("json")?;
            let loads_fn = json_mod.getattr("loads")?;
            let tools_py: pyo3::Bound<'_, pyo3::types::PyList> =
                loads_fn.call1((json_tools,))?.extract()?;

            let ids = pyo3::types::PyList::empty(py);
            let contents = pyo3::types::PyList::empty(py);
            let skill_names = pyo3::types::PyList::empty(py);
            let tool_names = pyo3::types::PyList::empty(py);
            let file_paths = pyo3::types::PyList::empty(py);
            let keywords = pyo3::types::PyList::empty(py);

            for item in tools_py.iter() {
                let tool_dict = item.cast::<pyo3::types::PyDict>()?;
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

    #[pyo3(signature = (table_name, query_vector, query_text=None, limit=5, threshold=0.0))]
    fn search_tools(
        &self,
        table_name: Option<String>,
        query_vector: Vec<f32>,
        query_text: Option<String>,
        limit: usize,
        threshold: f32,
    ) -> PyResult<Vec<Py<PyAny>>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

            let results = store
                .search_tools(
                    &table_name,
                    &query_vector,
                    query_text.as_deref(),
                    limit,
                    threshold,
                )
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

            let py_results = pyo3::Python::attach(|py| -> PyResult<Vec<Py<PyAny>>> {
                let mut dicts = Vec::with_capacity(results.len());
                for r in results {
                    let dict = pyo3::types::PyDict::new(py);
                    dict.set_item("name", r.name)?;
                    dict.set_item("description", r.description)?;
                    dict.set_item("input_schema", r.input_schema.to_string())?;
                    dict.set_item("score", r.score)?;
                    dict.set_item("skill_name", r.skill_name)?;
                    dict.set_item("tool_name", r.tool_name)?;
                    dict.set_item("file_path", r.file_path)?;
                    dict.set_item("keywords", r.keywords)?;
                    dicts.push(dict.into_pyobject(py)?.into());
                }
                Ok(dicts)
            });
            py_results
        })
    }

    fn load_tool_registry(&self, table_name: Option<String>) -> PyResult<Vec<Py<PyAny>>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let enable_kw = self.enable_keyword_index;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        rt.block_on(async {
            let store = VectorStore::new_with_keyword_index(&path, Some(dimension), enable_kw)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

            let results = store
                .load_tool_registry(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

            let py_results = pyo3::Python::attach(|py| -> PyResult<Vec<Py<PyAny>>> {
                let mut dicts = Vec::with_capacity(results.len());
                for r in results {
                    let dict = pyo3::types::PyDict::new(py);
                    dict.set_item("name", r.name)?;
                    dict.set_item("description", r.description)?;
                    dict.set_item("input_schema", r.input_schema.to_string())?;
                    dict.set_item("score", r.score)?;
                    dict.set_item("skill_name", r.skill_name)?;
                    dict.set_item("tool_name", r.tool_name)?;
                    dict.set_item("file_path", r.file_path)?;
                    dict.set_item("keywords", r.keywords)?;
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
#[pyo3(signature = (path, dimension = 1536, enable_keyword_index = false))]
pub fn create_vector_store(
    path: String,
    dimension: usize,
    enable_keyword_index: bool,
) -> PyResult<PyVectorStore> {
    PyVectorStore::new(path, dimension, enable_keyword_index)
}
