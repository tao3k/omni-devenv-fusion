//! ZK Entity Reference PyO3 Bindings
//!
//! Provides Python bindings for zk entity reference extraction.
//! This file is kept separate from zk.rs to keep lib.rs modular.

use pyo3::prelude::*;
use serde_json::to_string;
use std::collections::HashSet;

use crate::zk::{ZkEntityRef, ZkRefStats, get_ref_stats, is_valid_entity_ref, parse_entity_ref};

/// Python wrapper for ZkEntityRef
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyZkEntityRef {
    inner: ZkEntityRef,
}

#[pymethods]
impl PyZkEntityRef {
    #[new]
    fn new(name: String, entity_type: Option<String>, original: String) -> Self {
        Self {
            inner: ZkEntityRef::new(name, entity_type, original),
        }
    }

    #[getter]
    fn name(&self) -> String {
        self.inner.name.clone()
    }

    #[getter]
    fn entity_type(&self) -> Option<String> {
        self.inner.entity_type.clone()
    }

    #[getter]
    fn original(&self) -> String {
        self.inner.original.clone()
    }

    fn to_wikilink(&self) -> String {
        self.inner.to_wikilink()
    }

    fn to_tag(&self) -> String {
        self.inner.to_tag()
    }

    fn to_dict(&self) -> PyResult<String> {
        let value = serde_json::json!({
            "name": self.inner.name,
            "entity_type": self.inner.entity_type,
            "original": self.inner.original,
        });
        Ok(to_string(&value).unwrap_or_else(|_| "{}".to_string()))
    }
}

/// Python wrapper for ZkRefStats
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyZkRefStats {
    inner: ZkRefStats,
}

#[pymethods]
impl PyZkRefStats {
    #[new]
    fn new(total_refs: usize, unique_entities: usize, by_type: Vec<(String, usize)>) -> Self {
        Self {
            inner: ZkRefStats {
                total_refs,
                unique_entities,
                by_type,
            },
        }
    }

    #[getter]
    fn total_refs(&self) -> usize {
        self.inner.total_refs
    }

    #[getter]
    fn unique_entities(&self) -> usize {
        self.inner.unique_entities
    }

    #[getter]
    fn by_type(&self) -> Vec<(String, usize)> {
        self.inner.by_type.clone()
    }

    fn to_dict(&self) -> PyResult<String> {
        let value = serde_json::json!({
            "total_refs": self.inner.total_refs,
            "unique_entities": self.inner.unique_entities,
            "by_type": self.inner.by_type,
        });
        Ok(to_string(&value).unwrap_or_else(|_| "{}".to_string()))
    }
}

/// Extract entity references from note content (Rust-accelerated).
///
/// # Arguments
///
/// * `content` - The note body content to search
///
/// # Returns
///
/// List of extracted entity references
#[pyfunction]
#[pyo3(signature = (content))]
pub fn zk_extract_entity_refs(content: &str) -> Vec<PyZkEntityRef> {
    extract_entity_refs(content)
        .into_iter()
        .map(|e| PyZkEntityRef { inner: e })
        .collect()
}

/// Get entity reference statistics for content.
#[pyfunction]
#[pyo3(signature = (content))]
pub fn zk_get_ref_stats(content: &str) -> PyZkRefStats {
    let stats = get_ref_stats(content);
    PyZkRefStats { inner: stats }
}

/// Parse a single entity reference string.
#[pyfunction]
#[pyo3(signature = (text))]
pub fn zk_parse_entity_ref(text: &str) -> Option<PyZkEntityRef> {
    parse_entity_ref(text).map(|e| PyZkEntityRef { inner: e })
}

/// Check if text is a valid entity reference.
#[pyfunction]
#[pyo3(signature = (text))]
pub fn zk_is_valid_ref(text: &str) -> bool {
    is_valid_entity_ref(text)
}

/// Count entity references in content.
#[pyfunction]
#[pyo3(signature = (content))]
pub fn zk_count_refs(content: &str) -> usize {
    count_entity_refs(content)
}

/// Find notes referencing an entity (Python-friendly API).
#[pyfunction]
#[pyo3(signature = (entity_name, contents))]
pub fn zk_find_referencing_notes(entity_name: &str, contents: Vec<String>) -> Vec<usize> {
    // Return indices of matching notes
    let lower_name = entity_name.to_lowercase();
    let wikilink_pattern = format!("[[{}]]", entity_name);
    let wikilink_pattern_typed = format!("[[{}#", entity_name);

    contents
        .iter()
        .enumerate()
        .filter_map(|(idx, content)| {
            let lower = content.to_lowercase();
            if lower.contains(&lower_name)
                || lower.contains(&wikilink_pattern.to_lowercase())
                || lower.contains(&wikilink_pattern_typed.to_lowercase())
            {
                Some(idx)
            } else {
                None
            }
        })
        .collect()
}

/// Extract all entity references from note content.
fn extract_entity_refs(content: &str) -> Vec<ZkEntityRef> {
    static WIKILINK_REGEX: once_cell::sync::Lazy<regex::Regex> = once_cell::sync::Lazy::new(|| {
        regex::Regex::new(r"\[\[([^\]#\|]+)(?:#([^\]#\|]+))?(?:\|[^\]]+)?\]\]")
            .expect("Failed to compile wikilink regex")
    });

    let mut seen: HashSet<String> = HashSet::new();
    let mut refs: Vec<ZkEntityRef> = Vec::new();

    for caps in WIKILINK_REGEX.captures_iter(content) {
        let name = caps.get(1).unwrap().as_str().trim().to_string();
        let entity_type = caps.get(2).map(|m| m.as_str().trim().to_string());
        let original = caps.get(0).unwrap().as_str().to_string();

        if !seen.contains(&name) {
            seen.insert(name.clone());
            refs.push(ZkEntityRef::new(name, entity_type, original));
        }
    }

    refs
}

/// Count entity references in content.
fn count_entity_refs(content: &str) -> usize {
    static WIKILINK_REGEX: once_cell::sync::Lazy<regex::Regex> = once_cell::sync::Lazy::new(|| {
        regex::Regex::new(r"\[\[([^\]#\|]+)(?:#([^\]#\|]+))?(?:\|[^\]]+)?\]\]")
            .expect("Failed to compile wikilink regex")
    });
    WIKILINK_REGEX.captures_iter(content).count()
}
