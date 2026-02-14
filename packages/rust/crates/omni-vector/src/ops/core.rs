/// Unique id for each :memory: store so temp paths don't collide (e.g. across tests).
static NEXT_MEMORY_MODE_ID: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);

impl VectorStore {
    /// Create a new VectorStore instance.
    pub async fn new(path: &str, dimension: Option<usize>) -> Result<Self, VectorStoreError> {
        let base_path = PathBuf::from(path);
        let memory_mode_id = if path == ":memory:" {
            Some(NEXT_MEMORY_MODE_ID.fetch_add(1, std::sync::atomic::Ordering::Relaxed))
        } else {
            None
        };
        if path != ":memory:" {
            // Only create the parent directory, not the table directory itself
            // The table directory will be created when we actually write data
            if let Some(parent) = base_path.parent() {
                if !parent.exists() {
                    std::fs::create_dir_all(parent)?;
                }
            }
        }

        Ok(Self {
            base_path,
            datasets: Arc::new(Mutex::new(DatasetCache::new(DatasetCacheConfig::default()))),
            dimension: dimension.unwrap_or(DEFAULT_DIMENSION),
            keyword_index: None,
            keyword_backend: KeywordSearchBackend::Tantivy,
            index_cache_size_bytes: None,
            query_metrics: Arc::new(DashMap::new()),
            index_progress_callback: None,
            memory_mode_id,
        })
    }

    /// Create a new VectorStore with optional dataset cache limit (LRU eviction when exceeded).
    pub async fn new_with_cache_options(
        path: &str,
        dimension: Option<usize>,
        cache_config: DatasetCacheConfig,
    ) -> Result<Self, VectorStoreError> {
        let mut store = Self::new(path, dimension).await?;
        store.datasets = Arc::new(Mutex::new(DatasetCache::new(cache_config)));
        Ok(store)
    }

    /// Create a new VectorStore instance with optional keyword index and optional dataset cache.
    pub async fn new_with_keyword_index(
        path: &str,
        dimension: Option<usize>,
        enable_keyword_index: bool,
        index_cache_size_bytes: Option<usize>,
        cache_config: Option<DatasetCacheConfig>,
    ) -> Result<Self, VectorStoreError> {
        Self::new_with_keyword_backend(
            path,
            dimension,
            enable_keyword_index,
            KeywordSearchBackend::Tantivy,
            index_cache_size_bytes,
            cache_config,
        )
        .await
    }

    /// Create a new VectorStore with explicit keyword backend and optional dataset cache.
    pub async fn new_with_keyword_backend(
        path: &str,
        dimension: Option<usize>,
        enable_keyword_index: bool,
        keyword_backend: KeywordSearchBackend,
        index_cache_size_bytes: Option<usize>,
        cache_config: Option<DatasetCacheConfig>,
    ) -> Result<Self, VectorStoreError> {
        let mut store = Self::new(path, dimension).await?;
        if let Some(c) = cache_config {
            store.datasets = Arc::new(Mutex::new(DatasetCache::new(c)));
        }
        store.keyword_backend = keyword_backend;
        store.index_cache_size_bytes = index_cache_size_bytes;
        if enable_keyword_index && path != ":memory:" {
            store.enable_keyword_index()?;
        }
        Ok(store)
    }

    /// Set an optional callback for index build progress (Started/Done; Progress when Lance exposes API).
    pub fn with_index_progress_callback(mut self, cb: crate::IndexProgressCallback) -> Self {
        self.index_progress_callback = Some(cb);
        self
    }

    /// Open an existing dataset at the given URI, using optional index cache size when set.
    pub async fn open_dataset_at_uri(&self, uri: &str) -> Result<Dataset, VectorStoreError> {
        match self.index_cache_size_bytes {
            None => Dataset::open(uri).await.map_err(Into::into),
            Some(n) => lance::dataset::builder::DatasetBuilder::from_uri(uri)
                .with_index_cache_size_bytes(n)
                .load()
                .await
                .map_err(Into::into),
        }
    }

    /// Get the filesystem path for a specific table.
    pub fn table_path(&self, table_name: &str) -> PathBuf {
        if self.base_path.as_os_str() == ":memory:" {
            PathBuf::from(format!(":memory:_{}", table_name))
        } else {
            // Check if base_path already ends with .lance (any table directory)
            // This handles cases where the storage path is passed as "xxx.lance"
            // instead of the parent directory
            if self.base_path.to_string_lossy().ends_with(".lance") {
                // base_path is already a table directory, use it directly
                self.base_path.clone()
            } else {
                // Append table_name.lance to base_path
                self.base_path.join(format!("{table_name}.lance"))
            }
        }
    }

    /// Create the Arrow schema for the vector store tables.
    ///
    /// Uses Dictionary encoding for low-cardinality columns (SKILL_NAME, CATEGORY, TOOL_NAME)
    /// and field metadata for self-documentation and index hints.
    pub fn create_schema(&self) -> Arc<lance::deps::arrow_schema::Schema> {
        use lance::deps::arrow_schema::{DataType, Field};
        use std::collections::HashMap;

        let doc = |desc: &str| {
            let mut m = HashMap::new();
            m.insert("description".to_string(), desc.to_string());
            m
        };

        let fields = vec![
            Field::new(ID_COLUMN, DataType::Utf8, false)
                .with_metadata(doc("Unique document/tool id")),
            Field::new(
                VECTOR_COLUMN,
                DataType::FixedSizeList(
                    Arc::new(Field::new("item", DataType::Float32, true)),
                    i32::try_from(self.dimension).unwrap_or(1536),
                ),
                false,
            )
            .with_metadata(doc("Embedding vector (L2 index)")),
            Field::new(CONTENT_COLUMN, DataType::Utf8, false)
                .with_metadata(doc("Indexed text content")),
            Field::new_dictionary(
                crate::SKILL_NAME_COLUMN,
                DataType::Int32,
                DataType::Utf8,
                true,
            )
            .with_metadata({
                let mut m = doc("Skill name (low cardinality, dictionary encoded)");
                m.insert("index_hint".to_string(), "bitmap".to_string());
                m.insert("cardinality".to_string(), "low".to_string());
                m
            }),
            Field::new_dictionary(
                crate::CATEGORY_COLUMN,
                DataType::Int32,
                DataType::Utf8,
                true,
            )
            .with_metadata({
                let mut m =
                    doc("Skill category for filtering (low cardinality, dictionary encoded)");
                m.insert("index_hint".to_string(), "bitmap".to_string());
                m.insert("cardinality".to_string(), "low".to_string());
                m
            }),
            Field::new_dictionary(
                crate::TOOL_NAME_COLUMN,
                DataType::Int32,
                DataType::Utf8,
                true,
            )
            .with_metadata({
                let mut m = doc("Tool command name (e.g. skill.command), dictionary encoded");
                m.insert("index_hint".to_string(), "bitmap".to_string());
                m.insert("cardinality".to_string(), "low".to_string());
                m
            }),
            Field::new(crate::FILE_PATH_COLUMN, DataType::Utf8, true)
                .with_metadata(doc("Source file path")),
            Field::new(
                crate::ROUTING_KEYWORDS_COLUMN,
                DataType::List(Arc::new(Field::new("item", DataType::Utf8, true))),
                true,
            )
            .with_metadata(doc("Routing keywords for hybrid search (list)")),
            Field::new(
                crate::INTENTS_COLUMN,
                DataType::List(Arc::new(Field::new("item", DataType::Utf8, true))),
                true,
            )
            .with_metadata(doc("Intent tags (list)")),
            Field::new(crate::METADATA_COLUMN, DataType::Utf8, true)
                .with_metadata(doc("Full tool/resource metadata JSON")),
        ];

        Arc::new(lance::deps::arrow_schema::Schema::new(fields))
    }

    /// Enable keyword support for hybrid search.
    pub fn enable_keyword_index(&mut self) -> Result<(), VectorStoreError> {
        if self.keyword_backend == KeywordSearchBackend::LanceFts {
            // Lance FTS path does not require in-memory Tantivy index object.
            return Ok(());
        }
        if self.keyword_index.is_some() {
            return Ok(());
        }
        if self.base_path.as_os_str() == ":memory:" {
            return Err(VectorStoreError::General(
                "Cannot enable keyword index in memory mode".to_string(),
            ));
        }
        self.keyword_index = Some(Arc::new(KeywordIndex::new(&self.base_path)?));
        Ok(())
    }

    /// Switch keyword backend at runtime.
    pub fn set_keyword_backend(
        &mut self,
        backend: KeywordSearchBackend,
    ) -> Result<(), VectorStoreError> {
        self.keyword_backend = backend;
        if backend == KeywordSearchBackend::Tantivy {
            self.enable_keyword_index()?;
        }
        Ok(())
    }
}
