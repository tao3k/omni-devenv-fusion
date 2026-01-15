//! omni-core-rs - Python bindings for Omni DevEnv Rust core.
//!
//! Provides high-performance Rust implementations for:
//! - Environment sniffing (OmniSniffer)
//! - File I/O (read_file_safe)
//! - Token counting (count_tokens)
//! - Secret scanning (scan_secrets)
//! - Code navigation (get_file_outline, search_code, search_directory)
//! - Structural refactoring (structural_replace, structural_preview)
//!
//! Phase 53 Vector Store moved to omni-vector-rs package for faster builds.

use pyo3::prelude::*;
use omni_sniffer::OmniSniffer;
use omni_io;
use omni_tokenizer;
use omni_security::SecretScanner;
use omni_tags::TagExtractor;
use omni_edit::StructuralEditor;
use omni_vector::VectorStore;
use anyhow;
use std::path::Path;

/// Python wrapper for EnvironmentSnapshot.
/// Uses omni_types::EnvironmentSnapshot for type unification.
#[pyclass]
#[derive(serde::Serialize)]
struct PyEnvironmentSnapshot {
    git_branch: String,
    git_modified: usize,
    git_staged: usize,
    active_context_lines: usize,
    dirty_files: Vec<String>,
    timestamp: f64,
}

#[pymethods]
impl PyEnvironmentSnapshot {
    #[getter]
    fn git_branch(&self) -> String {
        self.git_branch.clone()
    }

    #[getter]
    fn git_modified(&self) -> usize {
        self.git_modified
    }

    #[getter]
    fn git_staged(&self) -> usize {
        self.git_staged
    }

    #[getter]
    fn active_context_lines(&self) -> usize {
        self.active_context_lines
    }

    #[getter]
    fn dirty_files(&self) -> Vec<String> {
        self.dirty_files.clone()
    }

    #[getter]
    fn timestamp(&self) -> f64 {
        self.timestamp
    }

    fn to_prompt_string(&self) -> String {
        let dirty_desc = if self.dirty_files.is_empty() {
            "Clean".to_string()
        } else {
            let count = self.dirty_files.len();
            let preview = self.dirty_files.iter().take(3).cloned().collect::<Vec<_>>().join(", ");
            if count > 3 {
                format!("{count} files ({preview}, ...)")
            } else {
                format!("{count} files ({preview})")
            }
        };

        format!(
            "[LIVE ENVIRONMENT STATE]\n\
            - Git: Branch: {} | Modified: {} | Staged: {} | Status: {}\n\
            - Active Context: {} lines in SCRATCHPAD.md",
            self.git_branch,
            self.git_modified,
            self.git_staged,
            dirty_desc,
            self.active_context_lines
        )
    }

    fn to_json(&self) -> String {
        serde_json::to_string(&self).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Python wrapper for OmniSniffer.
#[pyclass]
struct PyOmniSniffer {
    sniffer: OmniSniffer,
}

#[pymethods]
impl PyOmniSniffer {
    #[new]
    fn new(project_root: &str) -> Self {
        Self {
            sniffer: OmniSniffer::new(project_root),
        }
    }

    /// Get environment snapshot (high-performance Rust implementation)
    fn get_snapshot(&self) -> PyEnvironmentSnapshot {
        let snapshot = self.sniffer.get_snapshot();
        PyEnvironmentSnapshot {
            git_branch: snapshot.git_branch,
            git_modified: snapshot.git_modified,
            git_staged: snapshot.git_staged,
            active_context_lines: snapshot.active_context_lines,
            dirty_files: snapshot.dirty_files,
            timestamp: snapshot.timestamp,
        }
    }

    /// Quick git status check (lightweight)
    fn git_status(&self) -> PyResult<(String, usize, usize)> {
        let (branch, modified, staged, _) = self.sniffer.scan_git()
            .map_err(|e| pyo3::PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Git error: {e}")))?;
        Ok((branch, modified, staged))
    }
}

/// Python module initialization
#[pymodule]
fn omni_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyOmniSniffer>()?;
    m.add_class::<PyEnvironmentSnapshot>()?;
    m.add_class::<PyBatchRefactorStats>()?;
    m.add_class::<PyToolRecord>()?;
    m.add_class::<PyVectorStore>()?;
    m.add_function(pyo3::wrap_pyfunction!(py_get_sniffer, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(get_environment_snapshot, m)?)?;
    // Phase 47: Iron Lung functions
    m.add_function(pyo3::wrap_pyfunction!(read_file_safe, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(count_tokens, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(truncate_tokens, m)?)?;
    // Phase 49: Hyper-Immune System
    m.add_function(pyo3::wrap_pyfunction!(scan_secrets, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(contains_secrets, m)?)?;
    // Phase 50: The Cartographer
    m.add_function(pyo3::wrap_pyfunction!(get_file_outline, m)?)?;
    // Phase 51: The Hunter - Structural Code Search
    m.add_function(pyo3::wrap_pyfunction!(search_code, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(search_directory, m)?)?;
    // Phase 52: The Surgeon - Structural Refactoring
    m.add_function(pyo3::wrap_pyfunction!(structural_replace, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(structural_preview, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(structural_apply, m)?)?;
    // Phase 58: The Ouroboros - Heavy-Duty Batch Refactoring
    m.add_function(pyo3::wrap_pyfunction!(batch_structural_replace, m)?)?;
    // Phase 53/57: Vector Store - omni-vector bindings
    m.add_function(pyo3::wrap_pyfunction!(create_vector_store, m)?)?;
    // Phase 62: Script Scanner bindings
    m.add_function(pyo3::wrap_pyfunction!(scan_skill_tools, m)?)?;
    m.add("VERSION", "0.5.0")?;
    Ok(())
}

#[pyfunction]
#[pyo3(signature = (project_root=None))]
/// Convenience function to get a sniffer for the current directory
fn py_get_sniffer(project_root: Option<&str>) -> PyOmniSniffer {
    let root = project_root.unwrap_or(".");
    PyOmniSniffer::new(root)
}

/// Get environment snapshot as a formatted prompt string.
/// This is the primary interface for Phase 43 Holographic Agent.
#[pyfunction]
#[pyo3(signature = (root_path="."))]
fn get_environment_snapshot(root_path: &str) -> String {
    let sniffer = OmniSniffer::new(root_path);
    let snapshot = sniffer.get_snapshot();
    snapshot.to_prompt_string()
}

// ============================================================================
// Phase 47: The Iron Lung - Safe I/O and Tokenization
// ============================================================================

/// Safely read a text file with size and binary checks.
/// Releases GIL for CPU-intensive file operations.
#[pyfunction]
#[pyo3(signature = (path, max_bytes = 1048576))]
fn read_file_safe(path: String, max_bytes: u64) -> PyResult<String> {
    Python::attach(|py| {
        py.detach(|| {
            omni_io::read_text_safe(path, max_bytes)
                .map_err(|e| anyhow::anyhow!(e))
        })
    }).map_err(|e| pyo3::PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
}

/// Count tokens in text using cl100k_base (GPT-4/3.5 standard).
/// Uses cached BPE instance for optimal performance.
#[pyfunction]
fn count_tokens(text: &str) -> usize {
    omni_tokenizer::count_tokens(text)
}

/// Truncate text to fit within a maximum token count.
/// Uses cached BPE instance for optimal performance.
#[pyfunction]
#[pyo3(signature = (text, max_tokens))]
fn truncate_tokens(text: &str, max_tokens: usize) -> String {
    omni_tokenizer::truncate(text, max_tokens)
}

// ============================================================================
// Phase 49: The Hyper-Immune System - Secret Scanning
// ============================================================================

/// Scan content for secrets (AWS keys, Stripe keys, Slack tokens, etc.)
/// Returns a violation message if secrets are found, None if clean.
/// Releases GIL for CPU-intensive regex scanning.
#[pyfunction]
fn scan_secrets(content: &str) -> Option<String> {
    Python::attach(|py| {
        py.detach(|| {
            SecretScanner::scan(content).map(|v| {
                format!("[SECURITY VIOLATION] Found {}: {}", v.rule_id, v.description)
            })
        })
    })
}

/// Check if content contains any secrets (boolean check only).
/// More efficient than scan_secrets when you only need a boolean result.
/// Releases GIL for CPU-intensive regex scanning.
#[pyfunction]
fn contains_secrets(content: &str) -> bool {
    Python::attach(|py| {
        py.detach(|| {
            SecretScanner::contains_secrets(content)
        })
    })
}

// ============================================================================
// Phase 50: The Cartographer - AST-based Code Navigation
// ============================================================================

/// Generate a symbolic outline for a file using AST patterns.
/// Returns formatted string showing only definitions (classes, functions, etc.)
/// This is the primary interface for CCA-aligned code navigation.
#[pyfunction]
#[pyo3(signature = (path, language = None))]
fn get_file_outline(path: String, language: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            TagExtractor::outline_file(&path, language)
                .unwrap_or_else(|e| format!("[Error generating outline: {}]", e))
        })
    })
}

// ============================================================================
// Phase 51: The Hunter - Structural Code Search
// ============================================================================

/// Search for AST patterns in a single file using ast-grep syntax.
///
/// Examples:
/// - Find all function calls: "connect($ARGS)"
/// - Find class definitions: "class $NAME"
/// - Find method definitions: "def $NAME($PARAMS)"
///
/// Returns formatted string with match locations and captured variables.
#[pyfunction]
#[pyo3(signature = (path, pattern, language = None))]
fn search_code(path: String, pattern: String, language: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            TagExtractor::search_file(&path, &pattern, language)
                .unwrap_or_else(|e| format!("[Search error: {}]", e))
        })
    })
}

/// Search for AST patterns recursively in a directory.
///
/// Args:
///   path: Directory to search in
///   pattern: ast-grep pattern (e.g., "connect($ARGS)", "class $NAME")
///   file_pattern: Optional glob pattern for files (e.g., "**/*.py")
#[pyfunction]
#[pyo3(signature = (path, pattern, file_pattern = None))]
fn search_directory(path: String, pattern: String, file_pattern: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            let config = omni_tags::SearchConfig {
                file_pattern: file_pattern.unwrap_or("**/*").to_string(),
                ..Default::default()
            };
            TagExtractor::search_directory(&path, &pattern, config)
                .unwrap_or_else(|e| format!("[Search error: {}]", e))
        })
    })
}

// ============================================================================
// Phase 52: The Surgeon - Structural Refactoring
// ============================================================================

/// Perform structural replace on content using ast-grep patterns.
///
/// This is the pure function that operates on content strings.
/// Use structural_preview or structural_apply for file operations.
///
/// Args:
///   content: Source code content
///   pattern: ast-grep pattern to match (e.g., "connect($ARGS)")
///   replacement: Replacement pattern (e.g., "async_connect($ARGS)")
///   language: Programming language (python, rust, javascript, typescript)
///
/// Returns:
///   Formatted string showing diff and edit locations, or error message.
///
/// Examples:
///   structural_replace("x = connect(a, b)", "connect($ARGS)", "safe_connect($ARGS)", "python")
///   # Returns diff showing "x = safe_connect(a, b)"
#[pyfunction]
fn structural_replace(content: &str, pattern: &str, replacement: &str, language: &str) -> String {
    Python::attach(|py| {
        py.detach(|| {
            match StructuralEditor::replace(content, pattern, replacement, language) {
                Ok(result) => StructuralEditor::format_result(&result, None),
                Err(e) => format!("[Structural replace error: {}]", e),
            }
        })
    })
}

/// Preview structural replace on a file (no modification).
///
/// Returns diff showing what changes would be made without modifying the file.
///
/// Args:
///   path: Path to the source file
///   pattern: ast-grep pattern to match
///   replacement: Replacement pattern
///   language: Optional language hint (auto-detected if None)
///
/// Returns:
///   Formatted string showing diff and edit locations.
#[pyfunction]
#[pyo3(signature = (path, pattern, replacement, language = None))]
fn structural_preview(path: String, pattern: &str, replacement: &str, language: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            match StructuralEditor::preview(&path, pattern, replacement, language) {
                Ok(result) => StructuralEditor::format_result(&result, Some(&path)),
                Err(e) => format!("[Structural preview error: {}]", e),
            }
        })
    })
}

/// Apply structural replace to a file (modifies the file).
///
/// **CAUTION**: This modifies the file in place. Use structural_preview first to verify changes.
///
/// Args:
///   path: Path to the source file
///   pattern: ast-grep pattern to match
///   replacement: Replacement pattern
///   language: Optional language hint (auto-detected if None)
///
/// Returns:
///   Formatted string showing applied changes and diff.
#[pyfunction]
#[pyo3(signature = (path, pattern, replacement, language = None))]
fn structural_apply(path: String, pattern: &str, replacement: &str, language: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            match StructuralEditor::apply(&path, pattern, replacement, language) {
                Ok(result) => {
                    let mut output = StructuralEditor::format_result(&result, Some(&path));
                    if result.count > 0 {
                        output.push_str("\n[FILE MODIFIED]\n");
                    }
                    output
                }
                Err(e) => format!("[Structural apply error: {}]", e),
            }
        })
    })
}

// ============================================================================
// Phase 58: The Ouroboros - Heavy-Duty Batch Refactoring
// ============================================================================

/// Result of batch structural refactoring.
#[pyclass]
struct PyBatchRefactorStats {
    #[pyo3(get)]
    files_scanned: usize,
    #[pyo3(get)]
    files_changed: usize,
    #[pyo3(get)]
    replacements: usize,
    #[pyo3(get)]
    modified_files: Vec<String>,
    #[pyo3(get)]
    errors: Vec<String>,
}

impl From<omni_edit::BatchRefactorStats> for PyBatchRefactorStats {
    fn from(stats: omni_edit::BatchRefactorStats) -> Self {
        Self {
            files_scanned: stats.files_scanned,
            files_changed: stats.files_changed,
            replacements: stats.replacements,
            modified_files: stats.modified_files,
            errors: stats.errors.into_iter().map(|(k, v)| format!("{}: {}", k, v)).collect(),
        }
    }
}

/// Perform batch structural refactoring across a directory.
///
/// This is the "heavy equipment" function that processes thousands of files
/// in parallel using Rust's rayon thread pool.
///
/// Args:
///   root_path: Root directory to start searching
///   search_pattern: ast-grep pattern to match (e.g., `print($ARGS)`)
///   rewrite_pattern: Replacement pattern (e.g., `logger.info($ARGS)`)
///   file_pattern: Glob pattern for files (e.g., `**/*.py`)
///   dry_run: If true, only preview changes (default: true)
///
/// Returns:
///   PyBatchRefactorStats with statistics about the operation.
#[pyfunction]
#[pyo3(signature = (root_path, search_pattern, rewrite_pattern, file_pattern = "**/*.py", dry_run = true))]
fn batch_structural_replace(
    root_path: String,
    search_pattern: String,
    rewrite_pattern: String,
    file_pattern: &str,
    dry_run: bool,
) -> PyResult<PyBatchRefactorStats> {
    Python::attach(|py| {
        py.detach(|| {
            let config = omni_edit::BatchConfig {
                file_pattern: file_pattern.to_string(),
                dry_run,
                ..Default::default()
            };

            let stats = StructuralEditor::batch_replace(
                Path::new(&root_path),
                &search_pattern,
                &rewrite_pattern,
                &config,
            );

            Ok(PyBatchRefactorStats::from(stats))
        })
    })
}

// ============================================================================
// Phase 53/57: Vector Store - Python Bindings for omni-vector
// ============================================================================

/// Python wrapper for ToolRecord (Phase 62)
/// Represents a discovered tool from script scanning.
#[pyclass]
#[derive(Debug, Clone)]
struct PyToolRecord {
    #[pyo3(get)]
    tool_name: String,
    #[pyo3(get)]
    description: String,
    #[pyo3(get)]
    skill_name: String,
    #[pyo3(get)]
    file_path: String,
    #[pyo3(get)]
    function_name: String,
    #[pyo3(get)]
    execution_mode: String,
    #[pyo3(get)]
    keywords: Vec<String>,
    #[pyo3(get)]
    input_schema: String,
    #[pyo3(get)]
    docstring: String,
}

impl From<&omni_vector::ToolRecord> for PyToolRecord {
    fn from(record: &omni_vector::ToolRecord) -> Self {
        Self {
            tool_name: record.tool_name.clone(),
            description: record.description.clone(),
            skill_name: record.skill_name.clone(),
            file_path: record.file_path.clone(),
            function_name: record.function_name.clone(),
            execution_mode: record.execution_mode.clone(),
            keywords: record.keywords.clone(),
            input_schema: record.input_schema.clone(),
            docstring: record.docstring.clone(),
        }
    }
}

impl From<omni_vector::ToolRecord> for PyToolRecord {
    fn from(record: omni_vector::ToolRecord) -> Self {
        Self::from(&record)
    }
}

/// Python wrapper for VectorStore (omni-vector / LanceDB)
#[pyclass]
struct PyVectorStore {
    path: String,
    dimension: usize,
}

#[pymethods]
impl PyVectorStore {
    #[new]
    fn new(path: String, dimension: Option<usize>) -> PyResult<Self> {
        let dimension = dimension.unwrap_or(1536);

        // Verify we can create the store
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        rt.block_on(async {
            VectorStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })?;

        Ok(PyVectorStore { path, dimension })
    }

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
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension)).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store.add_documents(&table_name, ids, vectors, contents, metadatas).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    fn search(
        &self,
        table_name: String,
        query: Vec<f32>,
        limit: usize,
    ) -> PyResult<Vec<String>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let query = query.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension)).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let results = store.search(&table_name, query, limit).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            // Return JSON strings for easier Python processing
            let json_results: Vec<String> = results
                .into_iter()
                .map(|r| serde_json::to_string(&r).unwrap_or_default())
                .collect();
            Ok(json_results)
        })
    }

    /// Search with metadata filtering.
    ///
    /// Args:
    ///   table_name: Name of the table
    ///   query: Query vector for semantic search
    ///   limit: Maximum number of results
    ///   where_filter: Optional JSON filter (e.g., {"domain": "python"})
    ///
    /// Returns:
    ///   List of JSON strings representing search results
    fn search_filtered(
        &self,
        table_name: String,
        query: Vec<f32>,
        limit: usize,
        where_filter: Option<String>,
    ) -> PyResult<Vec<String>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let query = query.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension)).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let results = store.search_filtered(&table_name, query, limit, where_filter).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            // Return JSON strings for easier Python processing
            let json_results: Vec<String> = results
                .into_iter()
                .map(|r| serde_json::to_string(&r).unwrap_or_default())
                .collect();
            Ok(json_results)
        })
    }

    /// Phase 67: Hybrid search with keyword boosting.
    ///
    /// Combines vector similarity with keyword matching for better relevance.
    /// Formula: Score = Vector_Score * 0.7 + Keyword_Match * 0.3
    ///
    /// Args:
    ///   table_name: Name of the table
    ///   query: Query vector for semantic search
    ///   keywords: Keywords to boost (matched against metadata.keywords)
    ///   limit: Maximum number of results
    ///
    /// Returns:
    ///   List of JSON strings representing search results
    fn search_hybrid(
        &self,
        table_name: String,
        query: Vec<f32>,
        keywords: Vec<String>,
        limit: usize,
    ) -> PyResult<Vec<String>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let query = query.clone();
        let keywords = keywords.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension)).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let results = store.search_hybrid(&table_name, query, keywords, limit).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            // Return JSON strings for easier Python processing
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
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension)).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store.create_index(&table_name).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    fn delete(&self, table_name: String, ids: Vec<String>) -> PyResult<()> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension)).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store.delete(&table_name, ids).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    fn count(&self, table_name: String) -> PyResult<u32> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension)).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store.count(&table_name).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    fn drop_table(&self, table_name: String) -> PyResult<()> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension)).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store.drop_table(&table_name).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Phase 62: Index all tools from skills scripts directory.
    ///
    /// Scans `base_path/skills/*/scripts/*.py` for `@skill_script` decorated
    /// functions and indexes them for discovery.
    ///
    /// Args:
    ///   base_path: Base directory containing skills (e.g., "assets/skills")
    ///   table_name: Table to store tool records (default: "skills")
    ///
    /// Returns:
    ///   Number of tools indexed
    fn index_skill_tools(&self, base_path: String, table_name: Option<String>) -> PyResult<usize> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension)).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store.index_skill_tools(&base_path, &table_name).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            // Return count of indexed tools (we can count from table)
            let count = store.count(&table_name).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            Ok(count as usize)
        })
    }

    /// Phase 64: Scan for skill tools without indexing (sync version).
    ///
    /// This method discovers @skill_script decorated functions without
    /// attempting schema extraction. Returns raw tool records as JSON strings
    /// that can be processed by Python for schema extraction.
    ///
    /// Args:
    ///   base_path: Base directory containing skills (e.g., "assets/skills")
    ///
    /// Returns:
    ///   List of JSON strings representing tool records
    fn scan_skill_tools_raw(&self, base_path: String) -> PyResult<Vec<String>> {
        use std::path::Path;

        // Use the omni-vector scanner directly
        let scanner = omni_vector::ScriptScanner::new();
        let skills_path = Path::new(&base_path);

        if !skills_path.exists() {
            return Ok(vec![]);
        }

        let tools = scanner.scan_all(skills_path)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        // Convert to JSON strings
        let json_tools: Vec<String> = tools
            .into_iter()
            .map(|t| serde_json::to_string(&t).unwrap_or_default())
            .filter(|s| !s.is_empty())
            .collect();

        Ok(json_tools)
    }

    /// Phase 62: Get all tools for a skill.
    ///
    /// Args:
    ///   skill_name: Name of the skill (e.g., "git")
    ///
    /// Returns:
    ///   List of tool metadata JSON strings
    fn get_tools_by_skill(&self, skill_name: String) -> PyResult<Vec<String>> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension)).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let tools = store.get_tools_by_skill(&skill_name).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let json_tools: Vec<String> = tools
                .into_iter()
                .map(|t| serde_json::to_string(&t).unwrap_or_default())
                .collect();
            Ok(json_tools)
        })
    }

    /// Phase 64: Get all file hashes from the database for incremental sync.
    ///
    /// Args:
    ///   table_name: Name of the table (default: "skills")
    ///
    /// Returns:
    ///   JSON string of path -> {hash, id} mapping
    fn get_all_file_hashes(&self, table_name: Option<String>) -> PyResult<String> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension)).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store.get_all_file_hashes(&table_name)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Phase 64: Delete documents by file path.
    ///
    /// Args:
    ///   file_paths: List of file paths to delete
    ///   table_name: Name of the table (default: "skills")
    ///
    /// Returns:
    ///   Ok(()) on success
    fn delete_by_file_path(&self, file_paths: Vec<String>, table_name: Option<String>) -> PyResult<()> {
        let path = self.path.clone();
        let dimension = self.dimension;
        let table_name = table_name.unwrap_or_else(|| "skills".to_string());
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        rt.block_on(async {
            let store = VectorStore::new(&path, Some(dimension)).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            store.delete_by_file_path(&table_name, file_paths)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }
}

/// Create a vector store (convenience function)
#[pyfunction]
#[pyo3(signature = (path, dimension = None))]
fn create_vector_store(path: String, dimension: Option<usize>) -> PyResult<PyVectorStore> {
    PyVectorStore::new(path, dimension)
}

// ============================================================================
// Phase 62: Script Scanner - Direct Python Bindings
// ============================================================================

/// Scan a skills directory and return discovered tools.
///
/// This function uses the Rust ast-grep scanner to find all Python functions
/// decorated with @skill_script in the skill scripts directory.
///
/// Args:
///   base_path: Base directory containing skills (e.g., "assets/skills")
///
/// Returns:
///   List of PyToolRecord objects with discovered tools
#[pyfunction]
#[pyo3(signature = (base_path))]
fn scan_skill_tools(base_path: String) -> Vec<PyToolRecord> {
    use std::path::Path;

    let scanner = omni_vector::ScriptScanner::new();
    let skills_path = Path::new(&base_path);

    if !skills_path.exists() {
        return Vec::new();
    }

    match scanner.scan_all(skills_path) {
        Ok(tools) => tools.into_iter().map(|t| t.into()).collect(),
        Err(_) => Vec::new(),
    }
}
