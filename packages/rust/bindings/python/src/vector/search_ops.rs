//! Search Operations - Vector and hybrid search helper functions
//!
//! Contains: search_optimized, search_hybrid, create_index,
//!           search_tools, load_tool_registry, scan_skill_tools_raw

use omni_vector::{
    AgenticSearchConfig, QueryIntent, SearchOptions, ToolSearchOptions, VectorStore,
};
use pyo3::{
    prelude::*,
    types::{PyAny, PyDict, PyList},
};
use serde::Deserialize;
use std::collections::HashMap;
use std::path::Path;
use std::str::FromStr;

fn json_value_to_py(py: pyo3::Python<'_>, value: &serde_json::Value) -> PyResult<Py<PyAny>> {
    match value {
        serde_json::Value::Null => Ok(py.None()),
        serde_json::Value::Bool(v) => Ok(v.into_pyobject(py)?.to_owned().into_any().unbind()),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.into_pyobject(py)?.into_any().unbind())
            } else if let Some(u) = n.as_u64() {
                Ok(u.into_pyobject(py)?.into_any().unbind())
            } else if let Some(f) = n.as_f64() {
                Ok(f.into_pyobject(py)?.into_any().unbind())
            } else {
                Ok(py.None())
            }
        }
        serde_json::Value::String(s) => Ok(s.into_pyobject(py)?.into_any().unbind()),
        serde_json::Value::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(json_value_to_py(py, item)?)?;
            }
            Ok(list.into_any().unbind())
        }
        serde_json::Value::Object(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                dict.set_item(k, json_value_to_py(py, v)?)?;
            }
            Ok(dict.into_any().unbind())
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
struct ConfidenceProfile {
    high_threshold: f32,
    medium_threshold: f32,
    high_base: f32,
    high_scale: f32,
    high_cap: f32,
    medium_base: f32,
    medium_scale: f32,
    medium_cap: f32,
    low_floor: f32,
}

impl Default for ConfidenceProfile {
    fn default() -> Self {
        Self {
            high_threshold: 0.75,
            medium_threshold: 0.5,
            high_base: 0.90,
            high_scale: 0.05,
            high_cap: 0.99,
            medium_base: 0.60,
            medium_scale: 0.30,
            medium_cap: 0.89,
            low_floor: 0.10,
        }
    }
}

impl ConfidenceProfile {
    fn sanitize(mut self) -> Self {
        if self.high_threshold < self.medium_threshold {
            std::mem::swap(&mut self.high_threshold, &mut self.medium_threshold);
        }
        if self.high_cap < self.high_base {
            self.high_cap = self.high_base;
        }
        if self.medium_cap < self.medium_base {
            self.medium_cap = self.medium_base;
        }
        self.low_floor = self.low_floor.clamp(0.0, 1.0);
        self
    }
}

/// Minimum score gap between top and second result to treat top as "clear winner" and promote to high.
const CLEAR_WINNER_GAP: f32 = 0.15;
/// Minimum keyword (BM25) score to treat match as attribute-driven and allow high confidence when score >= medium.
const MIN_KEYWORD_SCORE_ATTRIBUTE_HIGH: f32 = 0.2;
/// Minimum vector (similarity) score to treat as "tool description match" — primary signal for LLM tool-calling.
const MIN_VECTOR_SCORE_TOOL_DESCRIPTION_HIGH: f32 = 0.55;

fn calibrate_confidence(score: f32, profile: &ConfidenceProfile) -> (&'static str, f32) {
    if score >= profile.high_threshold {
        (
            "high",
            (profile.high_base + score * profile.high_scale).min(profile.high_cap),
        )
    } else if score >= profile.medium_threshold {
        (
            "medium",
            (profile.medium_base + score * profile.medium_scale).min(profile.medium_cap),
        )
    } else {
        ("low", score.max(profile.low_floor))
    }
}

/// Calibrate confidence using score, clear-winner gap, and attribute signals (vector_score, keyword_score).
/// Aligns with route-test-schema doc: (1) tool description = vector path = primary for LLM tool-calling;
/// (2) keyword path = routing_keywords, intents, tool_name, skill_name, command.
fn calibrate_confidence_with_attributes(
    score: f32,
    second_score: Option<f32>,
    vector_score: Option<f32>,
    keyword_score: Option<f32>,
    profile: &ConfidenceProfile,
) -> (&'static str, f32) {
    let (mut conf, mut final_score) = calibrate_confidence(score, profile);

    // Clear winner: top is far ahead of second
    if let Some(s2) = second_score {
        if score >= profile.medium_threshold && (score - s2) >= CLEAR_WINNER_GAP {
            conf = "high";
            final_score = (profile.high_base + score * profile.high_scale).min(profile.high_cap);
        }
    }

    let kw = keyword_score.unwrap_or(0.0);
    let vec = vector_score.unwrap_or(0.0);

    // Tool-description match (vector path): primary signal for "model can call this tool correctly".
    if conf != "high"
        && score >= profile.medium_threshold
        && vec >= MIN_VECTOR_SCORE_TOOL_DESCRIPTION_HIGH
    {
        conf = "high";
        final_score = (profile.high_base + score * profile.high_scale).min(profile.high_cap);
    }

    // Keyword path: strong match on routing_keywords / intents / tool_name / category
    if conf != "high" && score >= profile.medium_threshold {
        if kw >= MIN_KEYWORD_SCORE_ATTRIBUTE_HIGH {
            conf = "high";
            final_score = (profile.high_base + score * profile.high_scale).min(profile.high_cap);
        } else if kw > 0.0 && vec < 0.5 && kw > vec {
            // Keyword-dominated (keyword contributed more than vector)
            conf = "high";
            final_score = (profile.high_base + score * profile.high_scale).min(profile.high_cap);
        }
    }

    (conf, final_score)
}

#[derive(Debug, Deserialize, Default)]
struct PySearchOptions {
    where_filter: Option<String>,
    batch_size: Option<usize>,
    fragment_readahead: Option<usize>,
    batch_readahead: Option<usize>,
    scan_limit: Option<usize>,
    /// Columns to include in IPC output (e.g. ["id", "content", "_distance"]). Reduces payload for batch search.
    #[serde(default)]
    projection: Option<Vec<String>>,
}

pub(crate) fn search_optimized_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    query: Vec<f32>,
    limit: usize,
    options_json: Option<String>,
) -> PyResult<Vec<String>> {
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
        let py_options = options_json
            .as_deref()
            .map(serde_json::from_str::<PySearchOptions>)
            .transpose()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?
            .unwrap_or_default();

        let options = SearchOptions {
            where_filter: py_options.where_filter,
            batch_size: py_options.batch_size,
            fragment_readahead: py_options.fragment_readahead,
            batch_readahead: py_options.batch_readahead,
            scan_limit: py_options.scan_limit,
            ..SearchOptions::default()
        };

        let results = store
            .search_optimized(table_name, query, limit, options)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(results
            .into_iter()
            .map(|r| {
                let score = 1.0f64 / (1.0f64 + r.distance.max(0.0));
                serde_json::json!({
                    "schema": "omni.vector.search.v1",
                    "id": r.id,
                    "content": r.content,
                    "metadata": r.metadata,
                    "distance": r.distance,
                    "score": score,
                })
                .to_string()
            })
            .collect())
    })
}

/// Run search and return Arrow IPC stream bytes (single RecordBatch) for zero-copy consumption.
/// See docs/reference/search-result-batch-contract.md.
pub(crate) fn search_optimized_ipc_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    query: Vec<f32>,
    limit: usize,
    options_json: Option<String>,
) -> PyResult<Vec<u8>> {
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

        let py_options = options_json
            .as_deref()
            .map(serde_json::from_str::<PySearchOptions>)
            .transpose()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?
            .unwrap_or_default();

        let options = SearchOptions {
            where_filter: py_options.where_filter,
            batch_size: py_options.batch_size,
            fragment_readahead: py_options.fragment_readahead,
            batch_readahead: py_options.batch_readahead,
            scan_limit: py_options.scan_limit,
            ipc_projection: py_options.projection,
            ..SearchOptions::default()
        };

        store
            .search_optimized_ipc(table_name, query, limit, options)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn search_hybrid_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
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
        let store = VectorStore::new_with_keyword_index(
            path,
            Some(dimension),
            enable_kw,
            index_cache_size_bytes,
            super::store::cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let vector_rows = store
            .search_optimized(
                table_name,
                query.clone(),
                limit.saturating_mul(2).max(limit),
                SearchOptions::default(),
            )
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let mut by_id: HashMap<String, (String, serde_json::Value)> = HashMap::new();
        for row in vector_rows {
            by_id.insert(row.id, (row.content, row.metadata));
        }

        let results = store
            .hybrid_search(table_name, &query_text, query, limit)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(results
            .into_iter()
            .map(|r| {
                let (content, metadata) = by_id
                    .get(&r.tool_name)
                    .cloned()
                    .unwrap_or_else(|| (String::new(), serde_json::json!({})));
                serde_json::json!({
                    "schema": "omni.vector.hybrid.v1",
                    "id": r.tool_name,
                    "content": content,
                    "metadata": metadata,
                    "source": "hybrid",
                    "score": r.rrf_score,
                    "vector_score": r.vector_score,
                    "keyword_score": r.keyword_score,
                })
                .to_string()
            })
            .collect())
    })
}

pub(crate) fn create_index_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
) -> PyResult<()> {
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
            .create_index(table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn search_tools_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    query_vector: Vec<f32>,
    query_text: Option<String>,
    limit: usize,
    threshold: f32,
    confidence_profile_json: Option<String>,
    rerank: bool,
) -> PyResult<Vec<Py<PyAny>>> {
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

        let results = store
            .search_tools_with_options(
                table_name,
                &query_vector,
                query_text.as_deref(),
                limit,
                threshold,
                ToolSearchOptions {
                    rerank,
                    semantic_weight: None,
                    keyword_weight: None,
                },
                None,
            )
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        let confidence_profile = confidence_profile_json
            .as_deref()
            .map(serde_json::from_str::<ConfidenceProfile>)
            .transpose()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?
            .unwrap_or_default()
            .sanitize();

        let py_results = pyo3::Python::attach(|py| -> PyResult<Vec<Py<PyAny>>> {
            let mut dicts = Vec::with_capacity(results.len());
            for (idx, r) in results.iter().enumerate() {
                let second_score = results.get(idx + 1).map(|s| s.score);
                let (confidence, final_score) = calibrate_confidence_with_attributes(
                    r.score,
                    second_score,
                    r.vector_score,
                    r.keyword_score,
                    &confidence_profile,
                );
                let dict = pyo3::types::PyDict::new(py);
                dict.set_item("schema", "omni.vector.tool_search.v1")?;
                dict.set_item("name", r.name.clone())?;
                dict.set_item("description", r.description.clone())?;
                dict.set_item("input_schema", json_value_to_py(py, &r.input_schema)?)?;
                dict.set_item("score", r.score)?;
                if let Some(v) = r.vector_score {
                    dict.set_item("vector_score", v)?;
                }
                if let Some(v) = r.keyword_score {
                    dict.set_item("keyword_score", v)?;
                }
                dict.set_item("final_score", final_score)?;
                dict.set_item("confidence", confidence)?;
                dict.set_item("skill_name", r.skill_name.clone())?;
                dict.set_item("tool_name", r.tool_name.clone())?;
                dict.set_item("file_path", r.file_path.clone())?;
                dict.set_item("routing_keywords", r.routing_keywords.clone())?;
                dict.set_item("intents", r.intents.clone())?;
                dict.set_item("category", r.category.clone())?;
                dicts.push(dict.into_pyobject(py)?.into());
            }
            Ok(dicts)
        });
        py_results
    })
}

/// Tool search returning Arrow IPC stream bytes for zero-copy consumption in Python.
pub(crate) fn search_tools_ipc_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    query_vector: Vec<f32>,
    query_text: Option<String>,
    limit: usize,
    threshold: f32,
    rerank: bool,
) -> PyResult<Vec<u8>> {
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

        let bytes = store
            .search_tools_ipc(
                table_name,
                &query_vector,
                query_text.as_deref(),
                limit,
                threshold,
                ToolSearchOptions {
                    rerank,
                    semantic_weight: None,
                    keyword_weight: None,
                },
                None,
            )
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(bytes)
    })
}

/// Agentic tool search with intent-based strategy (exact / semantic / hybrid).
pub(crate) fn agentic_search_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    query_vector: Vec<f32>,
    query_text: Option<String>,
    limit: usize,
    threshold: f32,
    intent: Option<String>,
    confidence_profile_json: Option<String>,
    rerank: bool,
    skill_name_filter: Option<String>,
    category_filter: Option<String>,
    semantic_weight: Option<f32>,
    keyword_weight: Option<f32>,
) -> PyResult<Vec<Py<PyAny>>> {
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

        let intent_parsed = intent
            .as_deref()
            .and_then(|s| QueryIntent::from_str(s).ok());
        let config = AgenticSearchConfig {
            limit,
            threshold,
            intent: intent_parsed,
            tool_options: ToolSearchOptions {
                rerank,
                semantic_weight,
                keyword_weight,
            },
            skill_name_filter,
            category_filter,
        };

        let results = store
            .agentic_search(table_name, &query_vector, query_text.as_deref(), config)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        let confidence_profile = confidence_profile_json
            .as_deref()
            .map(serde_json::from_str::<ConfidenceProfile>)
            .transpose()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?
            .unwrap_or_default()
            .sanitize();

        let py_results = pyo3::Python::attach(|py| -> PyResult<Vec<Py<PyAny>>> {
            let mut dicts = Vec::with_capacity(results.len());
            for (idx, r) in results.iter().enumerate() {
                let second_score = results.get(idx + 1).map(|s| s.score);
                let (confidence, final_score) = calibrate_confidence_with_attributes(
                    r.score,
                    second_score,
                    r.vector_score,
                    r.keyword_score,
                    &confidence_profile,
                );
                let dict = pyo3::types::PyDict::new(py);
                dict.set_item("schema", "omni.vector.tool_search.v1")?;
                dict.set_item("name", r.name.clone())?;
                dict.set_item("description", r.description.clone())?;
                dict.set_item("input_schema", json_value_to_py(py, &r.input_schema)?)?;
                dict.set_item("score", r.score)?;
                if let Some(v) = r.vector_score {
                    dict.set_item("vector_score", v)?;
                }
                if let Some(v) = r.keyword_score {
                    dict.set_item("keyword_score", v)?;
                }
                dict.set_item("final_score", final_score)?;
                dict.set_item("confidence", confidence)?;
                dict.set_item("skill_name", r.skill_name.clone())?;
                dict.set_item("tool_name", r.tool_name.clone())?;
                dict.set_item("file_path", r.file_path.clone())?;
                dict.set_item("routing_keywords", r.routing_keywords.clone())?;
                dict.set_item("intents", r.intents.clone())?;
                dict.set_item("category", r.category.clone())?;
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
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    confidence_profile_json: Option<String>,
) -> PyResult<Vec<Py<PyAny>>> {
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

        let results = store
            .load_tool_registry(table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        let confidence_profile = confidence_profile_json
            .as_deref()
            .map(serde_json::from_str::<ConfidenceProfile>)
            .transpose()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?
            .unwrap_or_default()
            .sanitize();

        let py_results = pyo3::Python::attach(|py| -> PyResult<Vec<Py<PyAny>>> {
            let mut dicts = Vec::with_capacity(results.len());
            for r in results {
                let (confidence, final_score) = calibrate_confidence(r.score, &confidence_profile);
                let dict = pyo3::types::PyDict::new(py);
                dict.set_item("schema", "omni.vector.tool_search.v1")?;
                dict.set_item("name", r.name)?;
                dict.set_item("description", r.description)?;
                dict.set_item("input_schema", json_value_to_py(py, &r.input_schema)?)?;
                dict.set_item("score", r.score)?;
                if let Some(v) = r.vector_score {
                    dict.set_item("vector_score", v)?;
                }
                if let Some(v) = r.keyword_score {
                    dict.set_item("keyword_score", v)?;
                }
                dict.set_item("final_score", final_score)?;
                dict.set_item("confidence", confidence)?;
                dict.set_item("skill_name", r.skill_name)?;
                dict.set_item("tool_name", r.tool_name)?;
                dict.set_item("file_path", r.file_path)?;
                dict.set_item("routing_keywords", r.routing_keywords)?;
                dict.set_item("intents", r.intents)?;
                dict.set_item("category", r.category)?;
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
