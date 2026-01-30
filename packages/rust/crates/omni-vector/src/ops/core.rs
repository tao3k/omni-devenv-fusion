impl VectorStore {
    /// Create a new VectorStore instance.
    pub async fn new(path: &str, dimension: Option<usize>) -> Result<Self, VectorStoreError> {
        let base_path = PathBuf::from(path);
        if path != ":memory:" {
            if let Some(parent) = base_path.parent() {
                if !parent.exists() {
                    std::fs::create_dir_all(parent)?;
                }
            }
            if !base_path.exists() {
                std::fs::create_dir_all(&base_path)?;
            }
        }

        Ok(Self {
            base_path,
            datasets: Arc::new(Mutex::new(DashMap::new())),
            dimension: dimension.unwrap_or(DEFAULT_DIMENSION),
            keyword_index: None,
        })
    }

    /// Create a new VectorStore instance with optional keyword index support.
    pub async fn new_with_keyword_index(
        path: &str,
        dimension: Option<usize>,
        enable_keyword_index: bool,
    ) -> Result<Self, VectorStoreError> {
        let mut store = Self::new(path, dimension).await?;
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
            self.base_path.join(format!("{table_name}.lance"))
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

    /// Enable the Tantivy-based keyword index for hybrid search.
    pub fn enable_keyword_index(&mut self) -> Result<(), VectorStoreError> {
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
}
