//! `PyO3` bindings for `dual_core` recall boost.

use pyo3::prelude::*;
use pyo3::types::PyAny;
use std::collections::{HashMap, HashSet};

use crate::dual_core::{RecallResult, apply_link_graph_proximity_boost};

/// Apply LinkGraph link/tag proximity boost to recall results (Rust implementation).
///
/// Args:
///     results: List of dicts with keys: source, score, content, title
///     `stem_links`: Dict[str, List[str]] — stem -> linked stems
///     `stem_tags`: Dict[str, List[str]] — stem -> tags
///     `link_boost`: Score boost for bidirectional link
///     `tag_boost`: Score boost for shared tags
///
/// Returns:
///     List of dicts (same structure) with boosted scores, sorted by score desc.
///
/// # Errors
///
/// Returns an error if Python inputs cannot be converted to expected Rust types.
#[pyfunction]
#[pyo3(signature = (results, stem_links, stem_tags, link_boost, tag_boost))]
pub fn apply_link_graph_proximity_boost_py(
    py: Python<'_>,
    results: &Bound<'_, pyo3::types::PyList>,
    stem_links: &Bound<'_, pyo3::types::PyDict>,
    stem_tags: &Bound<'_, pyo3::types::PyDict>,
    link_boost: f64,
    tag_boost: f64,
) -> PyResult<Vec<Py<PyAny>>> {
    let mut rust_results: Vec<RecallResult> = Vec::with_capacity(results.len());
    for obj in results.iter() {
        let dict = obj.clone().cast_into::<pyo3::types::PyDict>()?;
        let source = dict
            .get_item("source")?
            .and_then(|v: Bound<'_, PyAny>| v.extract::<String>().ok())
            .unwrap_or_default();
        let score = dict
            .get_item("score")?
            .and_then(|v: Bound<'_, PyAny>| v.extract::<f64>().ok())
            .unwrap_or(0.0);
        let content = dict
            .get_item("content")?
            .and_then(|v: Bound<'_, PyAny>| v.extract::<String>().ok())
            .unwrap_or_default();
        let title = dict
            .get_item("title")?
            .and_then(|v: Bound<'_, PyAny>| v.extract::<String>().ok())
            .unwrap_or_default();
        rust_results.push(RecallResult::new(source, score, content, title));
    }

    let mut links_map: HashMap<String, HashSet<String>> = HashMap::new();
    for (k, v) in stem_links.iter() {
        let stem = k.extract::<String>()?;
        let list = v.cast::<pyo3::types::PyList>()?;
        let set: HashSet<String> = list
            .iter()
            .filter_map(|item: Bound<'_, PyAny>| item.extract::<String>().ok())
            .collect();
        links_map.insert(stem, set);
    }

    let mut tags_map: HashMap<String, HashSet<String>> = HashMap::new();
    for (k, v) in stem_tags.iter() {
        let stem = k.extract::<String>()?;
        let list = v.cast::<pyo3::types::PyList>()?;
        let set: HashSet<String> = list
            .iter()
            .filter_map(|item: Bound<'_, PyAny>| item.extract::<String>().ok())
            .collect();
        tags_map.insert(stem, set);
    }

    apply_link_graph_proximity_boost(
        &mut rust_results,
        &links_map,
        &tags_map,
        link_boost,
        tag_boost,
    );

    let mut out = Vec::with_capacity(rust_results.len());
    for r in rust_results {
        let dict = pyo3::types::PyDict::new(py);
        dict.set_item("source", r.source)?;
        dict.set_item("score", r.score)?;
        dict.set_item("content", r.content)?;
        dict.set_item("title", r.title)?;
        out.push(dict.into_pyobject(py)?.into());
    }
    Ok(out)
}
