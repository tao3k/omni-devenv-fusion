//! Analytics Operations - Data analytics and aggregation helpers.
//!
//! Contains: get_all_file_hashes, get_analytics_table

use omni_vector::VectorStore;
use pyo3::{prelude::*, types::PyAny};

pub(crate) fn get_all_file_hashes_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
) -> PyResult<String> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(
            path,
            Some(dimension),
            enable_kw,
            index_cache_size_bytes,
            super::store::cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .get_all_file_hashes(table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

/// Get analytics table for Arrow-native operations.
/// Returns a PyArrow Table with columns: id, content, skill_name, tool_name, file_path, routing_keywords.
pub(crate) fn get_analytics_table_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
) -> PyResult<Py<PyAny>> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    let json_tools = rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(
            path,
            Some(dimension),
            enable_kw,
            index_cache_size_bytes,
            super::store::cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .list_all_tools(table_name)
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
        let routing_keywords = pyo3::types::PyList::empty(py);

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
            if let Ok(Some(kw_any)) = tool_dict.get_item("routing_keywords") {
                let kw_list: pyo3::Bound<'_, pyo3::types::PyList> = kw_any.extract()?;
                let mut kw_strings: Vec<String> = Vec::new();
                for kw in kw_list.iter() {
                    if let Ok(kw_str) = kw.extract() {
                        kw_strings.push(kw_str);
                    }
                }
                routing_keywords.append(kw_strings)?;
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
        columns_dict.set_item("routing_keywords", routing_keywords.as_any())?;

        let table = table_fn.call1((columns_dict,))?;
        Ok(table.unbind())
    })
}
