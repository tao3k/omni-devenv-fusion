//! `PyO3` bindings for knowledge types (category, entry).

use pyo3::prelude::*;
use serde_json::{json, to_string};

use crate::types::{KnowledgeCategory, KnowledgeEntry};

/// Knowledge category Python wrapper.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyKnowledgeCategory {
    pub(crate) inner: KnowledgeCategory,
}

#[pymethods]
impl PyKnowledgeCategory {
    #[classattr]
    const PATTERN: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Pattern,
    };

    #[classattr]
    const SOLUTION: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Solution,
    };

    #[classattr]
    const ERROR: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Error,
    };

    #[classattr]
    const TECHNIQUE: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Technique,
    };

    #[classattr]
    const NOTE: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Note,
    };

    #[classattr]
    const REFERENCE: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Reference,
    };

    #[classattr]
    const ARCHITECTURE: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Architecture,
    };

    #[classattr]
    const WORKFLOW: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Workflow,
    };

    #[new]
    fn new(category: &str) -> PyResult<Self> {
        match category {
            "patterns" | "pattern" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Pattern,
            }),
            "solutions" | "solution" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Solution,
            }),
            "errors" | "error" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Error,
            }),
            "techniques" | "technique" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Technique,
            }),
            "notes" | "note" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Note,
            }),
            "references" | "reference" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Reference,
            }),
            "architecture" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Architecture,
            }),
            "workflows" | "workflow" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Workflow,
            }),
            _ => Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Unknown category: {category}"
            ))),
        }
    }

    #[getter]
    fn value(&self) -> String {
        match self.inner {
            KnowledgeCategory::Pattern => "patterns".to_string(),
            KnowledgeCategory::Solution => "solutions".to_string(),
            KnowledgeCategory::Error => "errors".to_string(),
            KnowledgeCategory::Technique => "techniques".to_string(),
            KnowledgeCategory::Note => "notes".to_string(),
            KnowledgeCategory::Reference => "references".to_string(),
            KnowledgeCategory::Architecture => "architecture".to_string(),
            KnowledgeCategory::Workflow => "workflows".to_string(),
        }
    }

    fn __str__(&self) -> String {
        self.value()
    }
}

/// Knowledge entry Python wrapper.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyKnowledgeEntry {
    pub(crate) inner: KnowledgeEntry,
}

#[pymethods]
impl PyKnowledgeEntry {
    #[new]
    #[pyo3(signature = (id, title, content, category))]
    fn new(id: &str, title: &str, content: &str, category: PyKnowledgeCategory) -> Self {
        Self {
            inner: KnowledgeEntry::new(
                id.to_string(),
                title.to_string(),
                content.to_string(),
                category.inner,
            ),
        }
    }

    #[getter]
    fn id(&self) -> String {
        self.inner.id.clone()
    }

    #[getter]
    fn title(&self) -> String {
        self.inner.title.clone()
    }

    #[getter]
    fn content(&self) -> String {
        self.inner.content.clone()
    }

    #[getter]
    fn category(&self) -> PyKnowledgeCategory {
        PyKnowledgeCategory {
            inner: self.inner.category.clone(),
        }
    }

    #[getter]
    fn tags(&self) -> Vec<String> {
        self.inner.tags.clone()
    }

    #[getter]
    fn source(&self) -> Option<String> {
        self.inner.source.clone()
    }

    #[getter]
    fn version(&self) -> i32 {
        self.inner.version
    }

    #[setter]
    fn set_tags(&mut self, tags: Vec<String>) {
        self.inner.tags = tags;
    }

    #[setter]
    fn set_source(&mut self, source: Option<String>) {
        self.inner.source = source;
    }

    fn add_tag(&mut self, tag: String) {
        self.inner.add_tag(tag);
    }

    fn to_dict(&self) -> String {
        let value = json!({
            "id": self.inner.id,
            "title": self.inner.title,
            "content": self.inner.content,
            "category": self.category().value(),
            "tags": self.inner.tags,
            "source": self.inner.source,
            "version": self.inner.version,
        });
        to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Create a knowledge entry from Python.
#[pyfunction]
#[pyo3(signature = (title, content, category, tags, source))]
pub fn create_knowledge_entry(
    title: &str,
    content: &str,
    category: PyKnowledgeCategory,
    tags: Vec<String>,
    source: Option<&str>,
) -> PyKnowledgeEntry {
    let entry = KnowledgeEntry::new(
        uuid::Uuid::new_v4().to_string(),
        title.to_string(),
        content.to_string(),
        category.inner,
    )
    .with_tags(tags)
    .with_source(source.map(std::string::ToString::to_string));

    PyKnowledgeEntry { inner: entry }
}
