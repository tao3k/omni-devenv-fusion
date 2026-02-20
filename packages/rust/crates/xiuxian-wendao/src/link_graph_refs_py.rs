//! LinkGraph Entity Reference PyO3 Bindings
#![allow(clippy::doc_markdown)]
//!
//! Provides Python bindings for link-graph entity reference extraction.
//! This file is kept separate from link_graph_refs.rs to keep lib.rs modular.

use pyo3::prelude::*;
use regex::Regex;
use serde_json::to_string;
use std::collections::HashSet;
use std::sync::LazyLock;

use crate::link_graph_refs::{
    LinkGraphEntityRef, LinkGraphRefStats, get_ref_stats, is_valid_entity_ref, parse_entity_ref,
};

fn compile_regex(pattern: &str) -> Regex {
    match Regex::new(pattern) {
        Ok(regex) => regex,
        Err(_compile_err) => match Regex::new(r"$^") {
            Ok(fallback) => fallback,
            Err(fallback_err) => panic!("hardcoded fallback regex must compile: {fallback_err}"),
        },
    }
}

static WIKILINK_REGEX: LazyLock<Regex> =
    LazyLock::new(|| compile_regex(r"\[\[([^\]#\|]+)(?:#([^\]#\|]+))?(?:\|[^\]]+)?\]\]"));

/// Python wrapper for `LinkGraphEntityRef`.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyLinkGraphEntityRef {
    inner: LinkGraphEntityRef,
}

#[pymethods]
impl PyLinkGraphEntityRef {
    #[new]
    fn new(name: String, entity_type: Option<String>, original: String) -> Self {
        Self {
            inner: LinkGraphEntityRef::new(name, entity_type, original),
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

    fn to_dict(&self) -> String {
        let value = serde_json::json!({
            "name": self.inner.name,
            "entity_type": self.inner.entity_type,
            "original": self.inner.original,
        });
        to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Python wrapper for `LinkGraphRefStats`.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyLinkGraphRefStats {
    inner: LinkGraphRefStats,
}

#[pymethods]
impl PyLinkGraphRefStats {
    #[new]
    fn new(total_refs: usize, unique_entities: usize, by_type: Vec<(String, usize)>) -> Self {
        Self {
            inner: LinkGraphRefStats {
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

    fn to_dict(&self) -> String {
        let value = serde_json::json!({
            "total_refs": self.inner.total_refs,
            "unique_entities": self.inner.unique_entities,
            "by_type": self.inner.by_type,
        });
        to_string(&value).unwrap_or_else(|_| "{}".to_string())
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
#[must_use]
pub fn link_graph_extract_entity_refs(content: &str) -> Vec<PyLinkGraphEntityRef> {
    extract_entity_refs(content)
        .into_iter()
        .map(|e| PyLinkGraphEntityRef { inner: e })
        .collect()
}

/// Get entity reference statistics for content.
#[pyfunction]
#[pyo3(signature = (content))]
#[must_use]
pub fn link_graph_get_ref_stats(content: &str) -> PyLinkGraphRefStats {
    let stats = get_ref_stats(content);
    PyLinkGraphRefStats { inner: stats }
}

/// Parse a single entity reference string.
#[pyfunction]
#[pyo3(signature = (text))]
#[must_use]
pub fn link_graph_parse_entity_ref(text: &str) -> Option<PyLinkGraphEntityRef> {
    parse_entity_ref(text).map(|e| PyLinkGraphEntityRef { inner: e })
}

/// Check if text is a valid entity reference.
#[pyfunction]
#[pyo3(signature = (text))]
#[must_use]
pub fn link_graph_is_valid_ref(text: &str) -> bool {
    is_valid_entity_ref(text)
}

/// Count entity references in content.
#[pyfunction]
#[pyo3(signature = (content))]
#[must_use]
pub fn link_graph_count_refs(content: &str) -> usize {
    count_entity_refs(content)
}

/// Find notes referencing an entity (Python-friendly API).
#[pyfunction]
#[pyo3(signature = (entity_name, contents))]
#[allow(clippy::needless_pass_by_value)]
#[must_use]
pub fn link_graph_find_referencing_notes(entity_name: &str, contents: Vec<String>) -> Vec<usize> {
    // Return indices of matching notes
    let lower_name = entity_name.to_lowercase();
    let wikilink_pattern = format!("[[{entity_name}]]");
    let wikilink_pattern_typed = format!("[[{entity_name}#");

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
fn extract_entity_refs(content: &str) -> Vec<LinkGraphEntityRef> {
    let mut seen: HashSet<String> = HashSet::new();
    let mut refs: Vec<LinkGraphEntityRef> = Vec::new();

    for caps in WIKILINK_REGEX.captures_iter(content) {
        let Some(name_match) = caps.get(1) else {
            continue;
        };
        let name = name_match.as_str().trim().to_string();
        let entity_type = caps.get(2).map(|m| m.as_str().trim().to_string());
        let Some(original_match) = caps.get(0) else {
            continue;
        };
        let original = original_match.as_str().to_string();

        if !seen.contains(&name) {
            seen.insert(name.clone());
            refs.push(LinkGraphEntityRef::new(name, entity_type, original));
        }
    }

    refs
}

/// Count entity references in content.
fn count_entity_refs(content: &str) -> usize {
    WIKILINK_REGEX.captures_iter(content).count()
}
