//! Python bindings for omni-memory.

#[cfg(feature = "pybindings")]
#[allow(
    missing_docs,
    clippy::doc_markdown,
    clippy::module_inception,
    clippy::needless_pass_by_value,
    clippy::must_use_candidate,
    clippy::semicolon_if_nothing_returned
)]
mod pymodule_impl {
    use crate::encoder::IntentEncoder;
    use crate::episode::Episode;
    use crate::q_table::QTable;
    use crate::store::{EpisodeStore, StoreConfig};
    use crate::two_phase::{TwoPhaseConfig, TwoPhaseSearch, calculate_score as calc_score};
    use pyo3::prelude::*;
    use std::sync::Arc;

    // ============================================================================
    // PyO3 Wrappers
    // ============================================================================

    /// Python wrapper for Episode.
    #[pyclass]
    #[derive(Clone)]
    pub struct PyEpisode {
        inner: Episode,
    }

    #[pymethods]
    impl PyEpisode {
        #[new]
        fn new(id: String, intent: String, experience: String, outcome: String) -> Self {
            let encoder = IntentEncoder::new(384);
            let embedding = encoder.encode(&intent);
            Self {
                inner: Episode::new(id, intent, embedding, experience, outcome),
            }
        }

        #[getter]
        fn id(&self) -> String {
            self.inner.id.clone()
        }

        #[getter]
        fn intent(&self) -> String {
            self.inner.intent.clone()
        }

        #[getter]
        fn experience(&self) -> String {
            self.inner.experience.clone()
        }

        #[getter]
        fn outcome(&self) -> String {
            self.inner.outcome.clone()
        }

        #[getter]
        fn q_value(&self) -> f32 {
            self.inner.q_value
        }

        #[getter]
        fn success_count(&self) -> u32 {
            self.inner.success_count
        }

        #[getter]
        fn failure_count(&self) -> u32 {
            self.inner.failure_count
        }

        fn utility(&self) -> f32 {
            self.inner.utility()
        }

        fn mark_success(&mut self) {
            self.inner.mark_success();
        }

        fn mark_failure(&mut self) {
            self.inner.mark_failure();
        }

        fn intent_embedding(&self) -> Vec<f32> {
            self.inner.intent_embedding.clone()
        }
    }

    /// Python wrapper for QTable.
    #[pyclass]
    #[derive(Clone)]
    pub struct PyQTable {
        inner: QTable,
    }

    #[pymethods]
    impl PyQTable {
        #[new]
        fn new(learning_rate: Option<f32>, discount_factor: Option<f32>) -> Self {
            let inner = match (learning_rate, discount_factor) {
                (Some(lr), Some(df)) => QTable::with_params(lr, df),
                _ => QTable::new(),
            };
            Self { inner }
        }

        fn update(&self, episode_id: &str, reward: f32) -> f32 {
            self.inner.update(episode_id, reward)
        }

        fn get_q(&self, episode_id: &str) -> f32 {
            self.inner.get_q(episode_id)
        }

        fn len(&self) -> usize {
            self.inner.len()
        }

        fn is_empty(&self) -> bool {
            self.inner.is_empty()
        }

        fn learning_rate(&self) -> f32 {
            self.inner.learning_rate()
        }

        fn discount_factor(&self) -> f32 {
            self.inner.discount_factor()
        }
    }

    /// Python wrapper for IntentEncoder.
    #[pyclass]
    #[derive(Clone)]
    pub struct PyIntentEncoder {
        inner: IntentEncoder,
    }

    #[pymethods]
    impl PyIntentEncoder {
        #[new]
        fn new(dimension: Option<usize>) -> Self {
            Self {
                inner: IntentEncoder::new(dimension.unwrap_or(384)),
            }
        }

        fn encode(&self, intent: &str) -> Vec<f32> {
            self.inner.encode(intent)
        }

        fn cosine_similarity(&self, a: Vec<f32>, b: Vec<f32>) -> f32 {
            self.inner.cosine_similarity(&a, &b)
        }

        fn dimension(&self) -> usize {
            self.inner.dimension()
        }
    }

    /// Python wrapper for StoreConfig.
    #[pyclass]
    #[derive(Clone)]
    pub struct PyStoreConfig {
        #[pyo3(get, set)]
        pub path: String,
        #[pyo3(get, set)]
        pub embedding_dim: usize,
        #[pyo3(get, set)]
        pub table_name: String,
    }

    #[pymethods]
    impl PyStoreConfig {
        #[new]
        fn new(
            path: Option<String>,
            embedding_dim: Option<usize>,
            table_name: Option<String>,
        ) -> Self {
            Self {
                path: path.unwrap_or_else(|| "memory".to_string()),
                embedding_dim: embedding_dim.unwrap_or(384),
                table_name: table_name.unwrap_or_else(|| "episodes".to_string()),
            }
        }
    }

    /// Python wrapper for EpisodeStore.
    #[pyclass]
    pub struct PyEpisodeStore {
        inner: EpisodeStore,
    }

    #[pymethods]
    impl PyEpisodeStore {
        #[new]
        fn new(config: Option<PyStoreConfig>) -> Self {
            let config = config.map(|c| StoreConfig {
                path: c.path,
                embedding_dim: c.embedding_dim,
                table_name: c.table_name,
            });
            let config = config.unwrap_or_default();
            Self {
                inner: EpisodeStore::new(config),
            }
        }

        fn store(&self, episode: PyEpisode) -> PyResult<String> {
            self.inner
                .store(episode.inner.clone())
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        }

        fn get(&self, id: &str) -> Option<PyEpisode> {
            self.inner.get(id).map(|e| PyEpisode { inner: e })
        }

        fn get_all(&self) -> Vec<PyEpisode> {
            self.inner
                .get_all()
                .into_iter()
                .map(|e| PyEpisode { inner: e })
                .collect()
        }

        fn update_q(&self, episode_id: &str, reward: f32) -> f32 {
            self.inner.update_q(episode_id, reward)
        }

        fn recall(&self, intent: &str, top_k: usize) -> Vec<(PyEpisode, f32)> {
            self.inner
                .recall(intent, top_k)
                .into_iter()
                .map(|(e, s)| (PyEpisode { inner: e }, s))
                .collect()
        }

        /// Recall with pre-computed embedding (for real embeddings from Python)
        fn recall_with_embedding(
            &self,
            embedding: Vec<f32>,
            top_k: usize,
        ) -> Vec<(PyEpisode, f32)> {
            self.inner
                .recall_with_embedding(&embedding, top_k)
                .into_iter()
                .map(|(e, s)| (PyEpisode { inner: e }, s))
                .collect()
        }

        fn two_phase_recall(
            &self,
            intent: &str,
            k1: usize,
            k2: usize,
            lambda: f32,
        ) -> Vec<(PyEpisode, f32)> {
            self.inner
                .two_phase_recall(intent, k1, k2, lambda)
                .into_iter()
                .map(|(e, s)| (PyEpisode { inner: e }, s))
                .collect()
        }

        /// Two-phase recall with pre-computed embedding (for real embeddings from Python)
        fn two_phase_recall_with_embedding(
            &self,
            embedding: Vec<f32>,
            k1: usize,
            k2: usize,
            lambda: f32,
        ) -> Vec<(PyEpisode, f32)> {
            self.inner
                .two_phase_recall_with_embedding(&embedding, k1, k2, lambda)
                .into_iter()
                .map(|(e, s)| (PyEpisode { inner: e }, s))
                .collect()
        }

        /// Multi-hop reasoning: chain multiple queries together.
        fn multi_hop_recall(
            &self,
            queries: Vec<String>,
            k: usize,
            lambda: f32,
        ) -> Vec<(PyEpisode, f32)> {
            self.inner
                .multi_hop_recall(&queries, k, lambda)
                .into_iter()
                .map(|(e, s)| (PyEpisode { inner: e }, s))
                .collect()
        }

        /// Multi-hop reasoning with pre-computed embeddings.
        fn multi_hop_recall_with_embeddings(
            &self,
            embeddings: Vec<Vec<f32>>,
            k: usize,
            lambda: f32,
        ) -> Vec<(PyEpisode, f32)> {
            self.inner
                .multi_hop_recall_with_embeddings(&embeddings, k, lambda)
                .into_iter()
                .map(|(e, s)| (PyEpisode { inner: e }, s))
                .collect()
        }

        fn len(&self) -> usize {
            self.inner.len()
        }

        fn is_empty(&self) -> bool {
            self.inner.is_empty()
        }

        /// Save episodes to JSON file.
        fn save(&self, path: &str) -> PyResult<()> {
            self.inner
                .save(path)
                .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
        }

        /// Load episodes from JSON file.
        fn load(&mut self, path: &str) -> PyResult<()> {
            self.inner
                .load(path)
                .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
        }

        /// Save Q-table to JSON file.
        fn save_q_table(&self, path: &str) -> PyResult<()> {
            self.inner
                .save_q_table(path)
                .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
        }

        /// Load Q-table from JSON file.
        fn load_q_table(&mut self, path: &str) -> PyResult<()> {
            self.inner
                .load_q_table(path)
                .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
        }

        /// Apply time-based decay to all episodes.
        ///
        /// Args:
        /// - decay_factor: Decay per hour (e.g., 0.95 = 5% decay per hour)
        fn apply_decay(&self, decay_factor: f32) {
            self.inner.apply_decay(decay_factor);
        }

        /// Update an existing episode.
        fn update_episode(&self, episode_id: &str, experience: &str, outcome: &str) -> bool {
            self.inner.update_episode(episode_id, experience, outcome)
        }

        /// Delete an episode by ID.
        fn delete_episode(&self, episode_id: &str) -> bool {
            self.inner.delete_episode(episode_id)
        }

        /// Mark an episode as accessed (for frequency tracking).
        fn mark_accessed(&self, episode_id: &str) {
            self.inner.mark_accessed(episode_id);
        }

        /// Get memory statistics.
        fn stats(&self) -> PyMemoryStats {
            let inner_stats = self.inner.stats();
            PyMemoryStats {
                total_episodes: inner_stats.total_episodes,
                validated_episodes: inner_stats.validated_episodes,
                avg_age_hours: inner_stats.avg_age_hours,
                q_table_size: inner_stats.q_table_size,
            }
        }

        fn encoder(&self) -> PyIntentEncoder {
            PyIntentEncoder {
                inner: self.inner.encoder_clone(),
            }
        }
    }

    /// Python wrapper for memory statistics.
    #[pyclass]
    #[derive(Clone)]
    pub struct PyMemoryStats {
        #[pyo3(get, set)]
        pub total_episodes: usize,
        #[pyo3(get, set)]
        pub validated_episodes: usize,
        #[pyo3(get, set)]
        pub avg_age_hours: f32,
        #[pyo3(get, set)]
        pub q_table_size: usize,
    }

    /// Python wrapper for TwoPhaseConfig.
    #[pyclass]
    #[derive(Clone)]
    pub struct PyTwoPhaseConfig {
        #[pyo3(get, set)]
        pub k1: usize,
        #[pyo3(get, set)]
        pub k2: usize,
        #[pyo3(get, set)]
        pub lambda: f32,
    }

    #[pymethods]
    impl PyTwoPhaseConfig {
        #[new]
        fn new(k1: Option<usize>, k2: Option<usize>, lambda: Option<f32>) -> Self {
            Self {
                k1: k1.unwrap_or(20),
                k2: k2.unwrap_or(5),
                lambda: lambda.unwrap_or(0.3),
            }
        }
    }

    /// Python wrapper for TwoPhaseSearch.
    #[pyclass]
    pub struct PyTwoPhaseSearch {
        inner: TwoPhaseSearch,
    }

    #[pymethods]
    impl PyTwoPhaseSearch {
        #[new]
        fn new(
            q_table: &PyQTable,
            encoder: &PyIntentEncoder,
            config: Option<PyTwoPhaseConfig>,
        ) -> Self {
            let q_table = Arc::new(q_table.inner.clone());
            let encoder = Arc::new(encoder.inner.clone());
            let config = config.map(|c| TwoPhaseConfig {
                k1: c.k1,
                k2: c.k2,
                lambda: c.lambda,
            });
            let config = config.unwrap_or_default();
            Self {
                inner: TwoPhaseSearch::new(q_table, encoder, config),
            }
        }

        fn search(
            &self,
            episodes: Vec<PyEpisode>,
            intent: &str,
            k1: Option<usize>,
            k2: Option<usize>,
            lambda: Option<f32>,
        ) -> Vec<(PyEpisode, f32)> {
            let episodes: Vec<Episode> = episodes.into_iter().map(|e| e.inner).collect();
            self.inner
                .search(&episodes, intent, k1, k2, lambda)
                .into_iter()
                .map(|(e, s)| (PyEpisode { inner: e }, s))
                .collect()
        }

        fn quick_search(&self, episodes: Vec<PyEpisode>, intent: &str) -> Vec<(PyEpisode, f32)> {
            let episodes: Vec<Episode> = episodes.into_iter().map(|e| e.inner).collect();
            self.inner
                .quick_search(&episodes, intent)
                .into_iter()
                .map(|(e, s)| (PyEpisode { inner: e }, s))
                .collect()
        }
    }

    // ============================================================================
    // PyO3 Functions
    // ============================================================================

    #[pyfunction]
    pub fn create_episode(
        id: String,
        intent: String,
        experience: String,
        outcome: String,
    ) -> PyEpisode {
        let encoder = IntentEncoder::new(384);
        let embedding = encoder.encode(&intent);
        PyEpisode {
            inner: Episode::new(id, intent, embedding, experience, outcome),
        }
    }

    /// Create an episode with pre-computed embedding (for real embeddings from Python)
    #[pyfunction]
    pub fn create_episode_with_embedding(
        id: String,
        intent: String,
        experience: String,
        outcome: String,
        embedding: Vec<f32>,
    ) -> PyEpisode {
        PyEpisode {
            inner: Episode::new(id, intent, embedding, experience, outcome),
        }
    }

    #[pyfunction]
    pub fn create_q_table(learning_rate: Option<f32>, discount_factor: Option<f32>) -> PyQTable {
        let inner = match (learning_rate, discount_factor) {
            (Some(lr), Some(df)) => QTable::with_params(lr, df),
            _ => QTable::new(),
        };
        PyQTable { inner }
    }

    #[pyfunction]
    pub fn create_intent_encoder(dimension: Option<usize>) -> PyIntentEncoder {
        PyIntentEncoder {
            inner: IntentEncoder::new(dimension.unwrap_or(384)),
        }
    }

    #[pyfunction]
    pub fn create_episode_store(config: Option<PyStoreConfig>) -> PyEpisodeStore {
        let config = config.map(|c| StoreConfig {
            path: c.path,
            embedding_dim: c.embedding_dim,
            table_name: c.table_name,
        });
        let config = config.unwrap_or_default();
        PyEpisodeStore {
            inner: EpisodeStore::new(config),
        }
    }

    #[pyfunction]
    pub fn create_two_phase_search(
        q_table: &PyQTable,
        encoder: &PyIntentEncoder,
        config: Option<PyTwoPhaseConfig>,
    ) -> PyTwoPhaseSearch {
        let q_table = Arc::new(q_table.inner.clone());
        let encoder = Arc::new(encoder.inner.clone());
        let config = config.map(|c| TwoPhaseConfig {
            k1: c.k1,
            k2: c.k2,
            lambda: c.lambda,
        });
        let config = config.unwrap_or_default();
        PyTwoPhaseSearch {
            inner: TwoPhaseSearch::new(q_table, encoder, config),
        }
    }

    #[pyfunction]
    pub fn calculate_score(similarity: f32, q_value: f32, lambda: f32) -> f32 {
        calc_score(similarity, q_value, lambda)
    }

    // ============================================================================
    // Python Module Registration
    // ============================================================================

    /// Register the memory module with a Python module.
    ///
    /// # Errors
    ///
    /// Returns an error if any class or function cannot be registered.
    pub fn register_memory_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
        // Episode
        m.add_class::<PyEpisode>()?;

        // Q-Table
        m.add_class::<PyQTable>()?;
        m.add_function(wrap_pyfunction!(create_q_table, m)?)?;

        // Intent Encoder
        m.add_class::<PyIntentEncoder>()?;
        m.add_function(wrap_pyfunction!(create_intent_encoder, m)?)?;

        // Store Config
        m.add_class::<PyStoreConfig>()?;

        // Episode Store
        m.add_class::<PyEpisodeStore>()?;
        m.add_function(wrap_pyfunction!(create_episode_store, m)?)?;

        // Memory Stats
        m.add_class::<PyMemoryStats>()?;

        // Two-Phase Config
        m.add_class::<PyTwoPhaseConfig>()?;

        // Two-Phase Search
        m.add_class::<PyTwoPhaseSearch>()?;
        m.add_function(wrap_pyfunction!(create_two_phase_search, m)?)?;

        // Utility functions
        m.add_function(wrap_pyfunction!(create_episode, m)?)?;
        m.add_function(wrap_pyfunction!(calculate_score, m)?)?;

        Ok(())
    }
}

#[cfg(feature = "pybindings")]
pub use pymodule_impl::*;

#[cfg(not(feature = "pybindings"))]
pub mod pymodule_impl {
    // Empty module when pybindings not enabled
}
