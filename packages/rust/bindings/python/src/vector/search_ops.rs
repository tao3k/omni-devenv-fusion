//! Search Operations - Vector and hybrid search helper functions
//!
//! Contains: search, search_filtered, search_hybrid, create_index,
//!           search_tools, load_tool_registry, scan_skill_tools_raw

#![allow(dead_code)]

use omni_vector::VectorStore;
use pyo3::{prelude::*, types::PyAny};
use std::path::Path;

pub(crate) fn search_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
    query: Vec<f32>,
    limit: usize,
) -> PyResult<Vec<String>> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let results = store
            .search(table_name, query, limit)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(results
            .into_iter()
            .map(|r| serde_json::to_string(&r).unwrap_or_default())
            .collect())
    })
}

pub(crate) fn search_filtered_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
    query: Vec<f32>,
    limit: usize,
    where_filter: Option<String>,
) -> PyResult<Vec<String>> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let results = store
            .search_filtered(table_name, query, limit, where_filter)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(results
            .into_iter()
            .map(|r| serde_json::to_string(&r).unwrap_or_default())
            .collect())
    })
}

pub(crate) fn search_hybrid_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
    query: Vec<f32>,
    query_text: String,
    limit: usize,
) -> PyResult<Vec<String>> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let results = store
            .search_tools(table_name, &query, Some(&query_text), limit, 0.0)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(results
            .into_iter()
            .map(|r| serde_json::to_string(&r).unwrap_or_default())
            .collect())
    })
}

pub(crate) fn create_index_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
) -> PyResult<()> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .create_index(table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn search_tools_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
    query_vector: Vec<f32>,
    query_text: Option<String>,
    limit: usize,
    threshold: f32,
) -> PyResult<Vec<Py<PyAny>>> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        let results = store
            .search_tools(
                table_name,
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

pub(crate) fn load_tool_registry_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
) -> PyResult<Vec<Py<PyAny>>> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        let results = store
            .load_tool_registry(table_name)
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

pub(crate) fn scan_skill_tools_raw(base_path: &str) -> PyResult<Vec<String>> {
    use omni_scanner::{SkillScanner, ToolRecord, ToolsScanner};

    let skill_scanner = SkillScanner::new();
    let script_scanner = ToolsScanner::new();
    let skills_path = Path::new(base_path);

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
