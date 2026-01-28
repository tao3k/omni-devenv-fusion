//! Search Operations - Vector and hybrid search helper functions

#![allow(dead_code)]

use omni_vector::VectorStore;
use std::path::Path;

/// Vector search helper
pub async fn search_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
    query: Vec<f32>,
    limit: usize,
) -> pyo3::PyResult<Vec<String>> {
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
}

/// Filtered search helper
pub async fn search_filtered_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
    query: Vec<f32>,
    limit: usize,
    where_filter: Option<String>,
) -> pyo3::PyResult<Vec<String>> {
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
}

/// Hybrid search helper using Weighted RRF + Field Boosting
pub async fn search_hybrid_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
    query: Vec<f32>,
    query_text: String,
    limit: usize,
) -> pyo3::PyResult<Vec<String>> {
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
}

/// Create index helper
pub async fn create_index_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
) -> pyo3::PyResult<()> {
    let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    store
        .create_index(table_name)
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

/// Scan skill tools helper (sync)
pub fn scan_skill_tools_raw(base_path: &str) -> pyo3::PyResult<Vec<String>> {
    let skill_scanner = omni_vector::SkillScanner::new();
    let script_scanner = omni_vector::ToolsScanner::new();
    let skills_path = Path::new(base_path);

    if !skills_path.exists() {
        return Ok(vec![]);
    }

    let metadatas = skill_scanner
        .scan_all(skills_path, None)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

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
