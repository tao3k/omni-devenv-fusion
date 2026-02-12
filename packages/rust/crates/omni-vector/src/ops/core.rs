impl VectorStore {
    /// Create a new VectorStore instance.
    pub async fn new(path: &str, dimension: Option<usize>) -> Result<Self, VectorStoreError> {
        let base_path = PathBuf::from(path);
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
            datasets: Arc::new(Mutex::new(DashMap::new())),
            dimension: dimension.unwrap_or(DEFAULT_DIMENSION),
            keyword_index: None,
            keyword_backend: KeywordSearchBackend::Tantivy,
        })
    }

    /// Create a new VectorStore instance with optional keyword index support.
    pub async fn new_with_keyword_index(
        path: &str,
        dimension: Option<usize>,
        enable_keyword_index: bool,
    ) -> Result<Self, VectorStoreError> {
        Self::new_with_keyword_backend(
            path,
            dimension,
            enable_keyword_index,
            KeywordSearchBackend::Tantivy,
        )
        .await
    }

    /// Create a new VectorStore with explicit keyword backend selection.
    pub async fn new_with_keyword_backend(
        path: &str,
        dimension: Option<usize>,
        enable_keyword_index: bool,
        keyword_backend: KeywordSearchBackend,
    ) -> Result<Self, VectorStoreError> {
        let mut store = Self::new(path, dimension).await?;
        store.keyword_backend = keyword_backend;
        if enable_keyword_index && path != ":memory:" {
            store.enable_keyword_index()?;
        }
        Ok(store)
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
    pub fn create_schema(&self) -> Arc<lance::deps::arrow_schema::Schema> {
        Arc::new(lance::deps::arrow_schema::Schema::new(vec![
            lance::deps::arrow_schema::Field::new(
                ID_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                false,
            ),
            lance::deps::arrow_schema::Field::new(
                VECTOR_COLUMN,
                lance::deps::arrow_schema::DataType::FixedSizeList(
                    Arc::new(lance::deps::arrow_schema::Field::new(
                        "item",
                        lance::deps::arrow_schema::DataType::Float32,
                        true,
                    )),
                    i32::try_from(self.dimension).unwrap_or(1536),
                ),
                false,
            ),
            lance::deps::arrow_schema::Field::new(
                CONTENT_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                false,
            ),
            lance::deps::arrow_schema::Field::new(
                METADATA_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                true,
            ),
        ]))
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
