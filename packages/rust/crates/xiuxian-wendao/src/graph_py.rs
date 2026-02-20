//! PyO3 bindings for the KnowledgeGraph (entity, relation, graph, skill doc).
#![allow(clippy::doc_markdown)]

use pyo3::prelude::*;
use serde_json::{Value, json};

use crate::entity::{Entity, EntityType, RelationType};
use crate::graph::{KnowledgeGraph, QueryIntent, SkillDoc, extract_intent};
use crate::kg_cache;

/// Python wrapper for Entity type.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyEntityType;

/// Python wrapper for Entity.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyEntity {
    pub(crate) inner: Entity,
}

#[pymethods]
impl PyEntity {
    #[new]
    #[pyo3(signature = (name, entity_type, description))]
    fn new(name: &str, entity_type: &str, description: &str) -> Self {
        let etype = parse_entity_type(entity_type);
        let id = format!(
            "{}:{}",
            etype.to_string().to_lowercase(),
            name.to_lowercase().replace(' ', "_")
        );
        Self {
            inner: Entity::new(id, name.to_string(), etype, description.to_string()),
        }
    }

    #[getter]
    fn id(&self) -> String {
        self.inner.id.clone()
    }

    #[getter]
    fn name(&self) -> String {
        self.inner.name.clone()
    }

    #[getter]
    fn entity_type(&self) -> String {
        self.inner.entity_type.to_string()
    }

    #[getter]
    fn description(&self) -> String {
        self.inner.description.clone()
    }

    #[getter]
    fn source(&self) -> Option<String> {
        self.inner.source.clone()
    }

    #[getter]
    fn aliases(&self) -> Vec<String> {
        self.inner.aliases.clone()
    }

    #[getter]
    fn confidence(&self) -> f32 {
        self.inner.confidence
    }

    fn to_dict(&self) -> String {
        let value = json!({
            "id": self.inner.id,
            "name": self.inner.name,
            "entity_type": self.inner.entity_type.to_string(),
            "description": self.inner.description,
            "source": self.inner.source,
            "aliases": self.inner.aliases,
            "confidence": self.inner.confidence,
        });
        serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Python wrapper for Relation.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyRelation {
    inner: crate::entity::Relation,
}

#[pymethods]
impl PyRelation {
    #[new]
    #[pyo3(signature = (source, target, relation_type, description))]
    fn new(source: &str, target: &str, relation_type: &str, description: &str) -> Self {
        let rtype = parse_relation_type(relation_type);
        Self {
            inner: crate::entity::Relation::new(
                source.to_string(),
                target.to_string(),
                rtype,
                description.to_string(),
            ),
        }
    }

    #[getter]
    fn id(&self) -> String {
        self.inner.id.clone()
    }

    #[getter]
    fn source(&self) -> String {
        self.inner.source.clone()
    }

    #[getter]
    fn target(&self) -> String {
        self.inner.target.clone()
    }

    #[getter]
    fn relation_type(&self) -> String {
        self.inner.relation_type.to_string()
    }

    #[getter]
    fn description(&self) -> String {
        self.inner.description.clone()
    }

    #[getter]
    fn confidence(&self) -> f32 {
        self.inner.confidence
    }

    fn to_dict(&self) -> String {
        let value = json!({
            "id": self.inner.id,
            "source": self.inner.source,
            "target": self.inner.target,
            "relation_type": self.inner.relation_type.to_string(),
            "description": self.inner.description,
            "source_doc": self.inner.source_doc,
            "confidence": self.inner.confidence,
        });
        serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Python wrapper for KnowledgeGraph.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyKnowledgeGraph {
    inner: KnowledgeGraph,
}

#[pymethods]
impl PyKnowledgeGraph {
    #[new]
    fn new() -> Self {
        Self {
            inner: KnowledgeGraph::new(),
        }
    }

    fn add_entity(&self, entity: PyEntity) -> PyResult<()> {
        self.inner
            .add_entity(entity.inner)
            .map(|_| ())
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    fn add_relation(&self, relation: PyRelation) -> PyResult<()> {
        self.inner
            .add_relation(relation.inner)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    fn search_entities(&self, query: &str, limit: i32) -> Vec<PyEntity> {
        self.inner
            .search_entities(query, limit)
            .into_iter()
            .map(|e| PyEntity { inner: e })
            .collect()
    }

    fn get_entity(&self, entity_id: &str) -> Option<PyEntity> {
        self.inner
            .get_entity(entity_id)
            .map(|e| PyEntity { inner: e })
    }

    fn get_entity_by_name(&self, name: &str) -> Option<PyEntity> {
        self.inner
            .get_entity_by_name(name)
            .map(|e| PyEntity { inner: e })
    }

    fn get_relations(
        &self,
        entity_name: Option<&str>,
        relation_type: Option<&str>,
    ) -> Vec<PyRelation> {
        let rtype = relation_type.map(parse_relation_type);
        self.inner
            .get_relations(entity_name, rtype)
            .into_iter()
            .map(|r| PyRelation { inner: r })
            .collect()
    }

    fn multi_hop_search(&self, start_name: &str, max_hops: usize) -> Vec<PyEntity> {
        self.inner
            .multi_hop_search(start_name, max_hops)
            .into_iter()
            .map(|e| PyEntity { inner: e })
            .collect()
    }

    fn get_stats(&self) -> String {
        let stats = self.inner.get_stats();
        let value = json!({
            "total_entities": stats.total_entities,
            "total_relations": stats.total_relations,
            "entities_by_type": stats.entities_by_type,
            "relations_by_type": stats.relations_by_type,
        });
        serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }

    fn clear(&mut self) {
        self.inner.clear();
    }

    fn save_to_file(&self, path: &str) -> PyResult<()> {
        self.inner
            .save_to_file(path)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
    }

    fn load_from_file(&mut self, path: &str) -> PyResult<()> {
        self.inner
            .load_from_file(path)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
    }

    /// Save the graph to Lance tables inside the given knowledge.lance directory.
    ///
    /// Creates `kg_entities` and `kg_relations` Arrow tables alongside the
    /// knowledge chunks, sharing the same Lance ecosystem.
    /// Invalidates the KG cache for this path so subsequent loads see fresh data.
    #[pyo3(signature = (lance_dir, dimension=1024))]
    fn save_to_lance(&self, lance_dir: &str, dimension: usize) -> PyResult<()> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        runtime
            .block_on(self.inner.save_to_lance(lance_dir, dimension))
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
        kg_cache::invalidate(lance_dir);
        Ok(())
    }

    /// Load the graph from Lance tables inside the given knowledge.lance directory.
    ///
    /// Reads `kg_entities` and `kg_relations` tables. Falls back gracefully
    /// if tables don't exist yet.
    fn load_from_lance(&mut self, lance_dir: &str) -> PyResult<()> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        runtime
            .block_on(self.inner.load_from_lance(lance_dir))
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
    }

    fn export_as_json(&self) -> PyResult<String> {
        self.inner
            .export_as_json()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    fn get_all_entities_json(&self) -> PyResult<String> {
        let entities = self.inner.get_all_entities();
        let entities_json: Vec<Value> = entities
            .into_iter()
            .map(|e| {
                json!({
                    "id": e.id,
                    "name": e.name,
                    "entity_type": e.entity_type.to_string(),
                    "description": e.description,
                    "source": e.source,
                    "aliases": e.aliases,
                    "confidence": e.confidence,
                })
            })
            .collect();
        serde_json::to_string(&entities_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    /// Batch-register skill docs as entities and relations in the graph.
    fn register_skill_entities(&self, docs: Vec<PySkillDoc>) -> PyResult<String> {
        let skill_docs: Vec<SkillDoc> = docs.into_iter().map(|d| d.inner).collect();
        let result = self
            .inner
            .register_skill_entities(&skill_docs)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        let value = json!({
            "entities_added": result.entities_added,
            "relations_added": result.relations_added,
            "status": "success",
        });
        serde_json::to_string(&value)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    /// Register skill entities from a JSON string (convenience method).
    fn register_skill_entities_json(&self, json_str: &str) -> PyResult<String> {
        let parsed: Vec<serde_json::Value> = serde_json::from_str(json_str)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

        let mut skill_docs = Vec::with_capacity(parsed.len());
        for val in &parsed {
            let doc = SkillDoc {
                id: val
                    .get("id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
                doc_type: val
                    .get("type")
                    .or_else(|| val.get("doc_type"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
                skill_name: val
                    .get("skill_name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
                tool_name: val
                    .get("tool_name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
                content: val
                    .get("content")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
                routing_keywords: val
                    .get("routing_keywords")
                    .and_then(|v| v.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|x| x.as_str().map(str::to_string))
                            .collect()
                    })
                    .unwrap_or_default(),
            };
            skill_docs.push(doc);
        }

        let result = self
            .inner
            .register_skill_entities(&skill_docs)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        let value = json!({
            "entities_added": result.entities_added,
            "relations_added": result.relations_added,
            "status": "success",
        });
        serde_json::to_string(&value)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    /// Query-time tool relevance scoring via KnowledgeGraph traversal.
    #[pyo3(signature = (query_terms, max_hops = 2, limit = 10))]
    #[allow(clippy::needless_pass_by_value)]
    fn query_tool_relevance(
        &self,
        query_terms: Vec<String>,
        max_hops: usize,
        limit: usize,
    ) -> PyResult<String> {
        let results = self
            .inner
            .query_tool_relevance(&query_terms, max_hops, limit);
        let json_arr: Vec<Value> = results
            .iter()
            .map(|(name, score)| json!([name, score]))
            .collect();
        serde_json::to_string(&json_arr)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    fn get_all_relations_json(&self) -> PyResult<String> {
        let relations = self.inner.get_all_relations();
        let relations_json: Vec<Value> = relations
            .into_iter()
            .map(|r| {
                json!({
                    "id": r.id,
                    "source": r.source,
                    "target": r.target,
                    "relation_type": r.relation_type.to_string(),
                    "description": r.description,
                    "source_doc": r.source_doc,
                    "confidence": r.confidence,
                })
            })
            .collect();
        serde_json::to_string(&relations_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }
}

/// Python wrapper for SkillDoc (used by register_skill_entities).
#[pyclass]
#[derive(Debug, Clone)]
pub struct PySkillDoc {
    pub(crate) inner: SkillDoc,
}

#[pymethods]
impl PySkillDoc {
    #[new]
    #[pyo3(signature = (id, doc_type, skill_name, tool_name, content, routing_keywords))]
    fn new(
        id: &str,
        doc_type: &str,
        skill_name: &str,
        tool_name: &str,
        content: &str,
        routing_keywords: Vec<String>,
    ) -> Self {
        Self {
            inner: SkillDoc {
                id: id.to_string(),
                doc_type: doc_type.to_string(),
                skill_name: skill_name.to_string(),
                tool_name: tool_name.to_string(),
                content: content.to_string(),
                routing_keywords,
            },
        }
    }
}

// ---------------------------------------------------------------------------
// Query Intent (lightweight intent extraction)
// ---------------------------------------------------------------------------

/// Python wrapper for QueryIntent.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyQueryIntent {
    inner: QueryIntent,
}

#[pymethods]
impl PyQueryIntent {
    /// Primary action verb (e.g. "search", "commit", "create"). None if not detected.
    #[getter]
    fn action(&self) -> Option<String> {
        self.inner.action.clone()
    }

    /// Target domain or object (e.g. "git", "knowledge", "code"). None if not detected.
    #[getter]
    fn target(&self) -> Option<String> {
        self.inner.target.clone()
    }

    /// Context qualifiers (remaining significant tokens).
    #[getter]
    fn context(&self) -> Vec<String> {
        self.inner.context.clone()
    }

    /// All significant keywords (stop-words removed).
    #[getter]
    fn keywords(&self) -> Vec<String> {
        self.inner.keywords.clone()
    }

    /// Original query, lower-cased and trimmed.
    #[getter]
    fn normalized_query(&self) -> String {
        self.inner.normalized_query.clone()
    }

    fn to_dict(&self) -> String {
        let value = json!({
            "action": self.inner.action,
            "target": self.inner.target,
            "context": self.inner.context,
            "keywords": self.inner.keywords,
            "normalized_query": self.inner.normalized_query,
        });
        serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Extract structured query intent from a natural-language query string.
///
/// Returns a PyQueryIntent with action, target, context, and keywords.
#[pyfunction]
#[must_use]
pub fn extract_query_intent(query: &str) -> PyQueryIntent {
    PyQueryIntent {
        inner: extract_intent(query),
    }
}

/// Invalidate the in-process KG cache for the given Lance path.
///
/// Call after evicting the knowledge vector store so the long-lived process
/// does not retain the graph in memory. Safe to call when cache is empty.
#[pyfunction]
pub fn invalidate_kg_cache(lance_dir: &str) {
    kg_cache::invalidate(lance_dir);
}

/// Load KnowledgeGraph from Lance with caching.
///
/// Uses an in-process cache keyed by path. Avoids repeated disk reads
/// when the same knowledge.lance is accessed across multiple recalls.
/// Returns None if tables don't exist (graceful fallback).
///
/// # Errors
///
/// Returns `PyErr` when Lance loading fails.
#[pyfunction]
pub fn load_kg_from_lance_cached(lance_dir: &str) -> PyResult<Option<PyKnowledgeGraph>> {
    match kg_cache::load_from_lance_cached(lance_dir) {
        Ok(Some(graph)) => Ok(Some(PyKnowledgeGraph { inner: graph })),
        Ok(None) => Ok(None),
        Err(e) => Err(pyo3::exceptions::PyIOError::new_err(e.to_string())),
    }
}

// ---------------------------------------------------------------------------
// Type parsers (PyO3 input string → Rust enum)
// ---------------------------------------------------------------------------

/// Parse entity type from string.
pub(crate) fn parse_entity_type(s: &str) -> EntityType {
    match s.to_uppercase().as_str() {
        "PERSON" => EntityType::Person,
        "ORGANIZATION" => EntityType::Organization,
        "CONCEPT" => EntityType::Concept,
        "PROJECT" => EntityType::Project,
        "TOOL" => EntityType::Tool,
        "SKILL" => EntityType::Skill,
        "LOCATION" => EntityType::Location,
        "EVENT" => EntityType::Event,
        "DOCUMENT" => EntityType::Document,
        "CODE" => EntityType::Code,
        "API" => EntityType::Api,
        "ERROR" => EntityType::Error,
        "PATTERN" => EntityType::Pattern,
        _ => EntityType::Other(s.to_string()),
    }
}

/// Parse relation type from string.
pub(crate) fn parse_relation_type(s: &str) -> RelationType {
    match s.to_uppercase().as_str() {
        "WORKS_FOR" => RelationType::WorksFor,
        "PART_OF" => RelationType::PartOf,
        "USES" => RelationType::Uses,
        "DEPENDS_ON" => RelationType::DependsOn,
        "SIMILAR_TO" => RelationType::SimilarTo,
        "LOCATED_IN" => RelationType::LocatedIn,
        "CREATED_BY" => RelationType::CreatedBy,
        "DOCUMENTED_IN" => RelationType::DocumentedIn,
        "RELATED_TO" => RelationType::RelatedTo,
        "IMPLEMENTS" => RelationType::Implements,
        "EXTENDS" => RelationType::Extends,
        "CONTAINS" => RelationType::Contains,
        _ => RelationType::Other(s.to_string()),
    }
}
