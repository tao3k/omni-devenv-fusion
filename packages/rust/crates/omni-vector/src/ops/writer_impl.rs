impl VectorStore {
    fn derive_routing_keywords(tool: &OmniToolRecord) -> Vec<String> {
        let skill_token = tool.skill_name.trim();
        let tool_token = tool
            .tool_name
            .split('.')
            .next_back()
            .map(str::trim)
            .unwrap_or("");
        let full_tool = tool.tool_name.trim();
        let mut out = Vec::new();
        let mut seen = std::collections::HashSet::new();
        for kw in &tool.keywords {
            let token = kw.trim();
            if token.is_empty() {
                continue;
            }
            if token == skill_token || token == tool_token || token == full_tool {
                continue;
            }
            if seen.insert(token.to_string()) {
                out.push(token.to_string());
            }
        }
        out
    }

    fn canonical_tool_name_from_metadata(meta: &serde_json::Value) -> Option<String> {
        let skill_name = meta
            .get("skill_name")
            .and_then(|s| s.as_str())
            .map(str::trim)
            .unwrap_or("");
        let tool_name = meta
            .get("tool_name")
            .and_then(|s| s.as_str())
            .map(str::trim)
            .unwrap_or("");
        if crate::skill::is_routable_tool_name(tool_name) && tool_name.contains('.') {
            return Some(tool_name.to_string());
        }
        if !skill_name.is_empty() && crate::skill::is_routable_tool_name(tool_name) {
            let candidate = format!("{skill_name}.{tool_name}");
            if crate::skill::is_routable_tool_name(&candidate) {
                return Some(candidate);
            }
        }

        let command = meta
            .get("command")
            .and_then(|s| s.as_str())
            .map(str::trim)
            .unwrap_or("");

        if !skill_name.is_empty() && !command.is_empty() {
            let candidate = format!("{skill_name}.{command}");
            if crate::skill::is_routable_tool_name(&candidate) {
                return Some(candidate);
            }
        }

        if crate::skill::is_routable_tool_name(command) {
            return Some(command.to_string());
        }
        None
    }

    fn build_document_batch(
        &self,
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
    ) -> Result<
        (
            Arc<lance::deps::arrow_schema::Schema>,
            lance::deps::arrow_array::RecordBatch,
        ),
        VectorStoreError,
    > {
        use lance::deps::arrow_array::{FixedSizeListArray, Float32Array, StringArray};

        if ids.is_empty() {
            return Err(VectorStoreError::General(
                "Cannot build record batch from empty ids".to_string(),
            ));
        }
        if ids.len() != vectors.len() || ids.len() != contents.len() || ids.len() != metadatas.len()
        {
            return Err(VectorStoreError::General(
                "Mismatched input lengths for ids/vectors/contents/metadatas".to_string(),
            ));
        }
        if vectors[0].len() != self.dimension {
            return Err(VectorStoreError::InvalidDimension {
                expected: self.dimension,
                actual: vectors[0].len(),
            });
        }
        if vectors.iter().any(|v| v.len() != self.dimension) {
            return Err(VectorStoreError::General(
                "All vectors must match store dimension".to_string(),
            ));
        }

        let id_array = StringArray::from(ids);
        let content_array = StringArray::from(contents);
        let metadata_array = StringArray::from(metadatas);
        let flat_values: Vec<f32> = vectors.into_iter().flatten().collect();
        let vector_array = FixedSizeListArray::try_new(
            Arc::new(lance::deps::arrow_schema::Field::new(
                "item",
                lance::deps::arrow_schema::DataType::Float32,
                true,
            )),
            i32::try_from(self.dimension).unwrap_or(1536),
            Arc::new(Float32Array::from(flat_values)),
            None,
        )
        .map_err(VectorStoreError::Arrow)?;

        let schema = self.create_schema();
        let batch = lance::deps::arrow_array::RecordBatch::try_new(
            schema.clone(),
            vec![
                Arc::new(id_array),
                Arc::new(vector_array),
                Arc::new(content_array),
                Arc::new(metadata_array),
            ],
        )
        .map_err(VectorStoreError::Arrow)?;
        Ok((schema, batch))
    }

    /// Add tool records to the vector store.
    pub async fn add(
        &self,
        table_name: &str,
        tools: Vec<OmniToolRecord>,
    ) -> Result<(), VectorStoreError> {
        if tools.is_empty() {
            return Ok(());
        }

        // 1. Write to Keyword Index if enabled
        if let Some(kw_index) = &self.keyword_index {
            let search_results: Vec<skill::ToolSearchResult> = tools
                .iter()
                .map(|t| {
                    let full_name = format!(
                        "{}.{}",
                        t.skill_name,
                        t.tool_name.split('.').skip(1).collect::<Vec<_>>().join(".")
                    );
                    skill::ToolSearchResult {
                        name: full_name.clone(),
                        description: t.description.clone(),
                        input_schema: serde_json::json!({}),
                        score: 1.0,
                        vector_score: None,
                        keyword_score: Some(1.0),
                        skill_name: t.skill_name.clone(),
                        tool_name: t.tool_name.clone(),
                        file_path: t.file_path.clone(),
                        keywords: t.keywords.clone(),
                        intents: t.intents.clone(),
                        category: t.category.clone(),
                    }
                })
                .collect();
            let _ = kw_index.index_batch(&search_results);
        }

        // 2. Prepare metadata and IDs for LanceDB
        let ids: Vec<String> = tools
            .iter()
            .map(|t| {
                format!(
                    "{}.{}",
                    t.skill_name,
                    t.tool_name.split('.').skip(1).collect::<Vec<_>>().join(".")
                )
            })
            .collect();
        let contents: Vec<String> = tools.iter().map(|t| t.description.clone()).collect();
        let metadatas: Vec<String> = tools
            .iter()
            .map(|t| {
                let routing_keywords = Self::derive_routing_keywords(t);
                let command_name = t.tool_name.split('.').skip(1).collect::<Vec<_>>().join(".");
                serde_json::json!({
                    "type": "command", "skill_name": t.skill_name, "command": command_name, "tool_name": t.tool_name,
                    "file_path": t.file_path, "function_name": t.function_name, "intents": t.intents,
                    "routing_keywords": routing_keywords,
                    "file_hash": t.file_hash, "input_schema": t.input_schema, "docstring": t.docstring,
                    "category": t.category, "annotations": t.annotations, "parameters": t.parameters,
                })
                .to_string()
            })
            .collect();

        // Standard vectors (dummy for now as SkillIndexer provides actual vectors via add_documents)
        let vectors: Vec<Vec<f32>> = (0..ids.len()).map(|_| vec![0.0; self.dimension]).collect();

        self.add_documents(table_name, ids, vectors, contents, metadatas)
            .await?;
        Ok(())
    }

    /// Batch add documents with vectors to a table.
    pub async fn add_documents(
        &self,
        table_name: &str,
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
    ) -> Result<(), VectorStoreError> {
        use lance::deps::arrow_array::RecordBatchIterator;

        if ids.is_empty() {
            return Ok(());
        }

        let contents_for_keyword = contents.clone();
        let metadatas_for_keyword = metadatas.clone();
        let (schema, batch) = self.build_document_batch(ids, vectors, contents, metadatas)?;

        let mut dataset = self.get_or_create_dataset(table_name, false).await?;
        let batches: Vec<Result<_, crate::error::ArrowError>> = vec![Ok(batch)];
        dataset
            .append(Box::new(RecordBatchIterator::new(batches, schema)), None)
            .await?;

        // DUAL WRITE: Also write to Keyword Index if enabled
        if let Some(ref kw_index) = self.keyword_index {
            let mut keyword_docs = Vec::new();
            for (i, meta_str) in metadatas_for_keyword.iter().enumerate() {
                if let Ok(meta) = serde_json::from_str::<serde_json::Value>(meta_str) {
                    if meta.get("type").and_then(|s| s.as_str()) != Some("command") {
                        continue;
                    }
                    let Some(name) = Self::canonical_tool_name_from_metadata(&meta) else {
                        continue;
                    };
                    let category = meta
                        .get("category")
                        .and_then(|s| s.as_str())
                        .or_else(|| meta.get("skill_name").and_then(|s| s.as_str()))
                        .unwrap_or("unknown")
                        .to_string();
                    let kws = crate::skill::resolve_routing_keywords(&meta);
                    let intents = crate::skill::resolve_intents(&meta);
                    keyword_docs.push((
                        name,
                        contents_for_keyword[i].clone(),
                        category,
                        kws,
                        intents,
                    ));
                }
            }
            if !keyword_docs.is_empty() {
                let _ = kw_index.bulk_upsert(keyword_docs);
            }
        }
        Ok(())
    }

    /// Replace all documents in a table with the provided batch atomically
    /// from the caller perspective (drop then write fresh snapshot).
    pub async fn replace_documents(
        &mut self,
        table_name: &str,
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
    ) -> Result<(), VectorStoreError> {
        self.drop_table(table_name).await?;
        self.add_documents(table_name, ids, vectors, contents, metadatas)
            .await
    }

    /// Merge-insert (upsert) documents using a key column (default use-case: `id`).
    pub async fn merge_insert_documents(
        &self,
        table_name: &str,
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
        match_on: &str,
    ) -> Result<MergeInsertStats, VectorStoreError> {
        use lance::dataset::{MergeInsertBuilder, WhenMatched, WhenNotMatched};
        use lance::deps::arrow_array::RecordBatchIterator;

        if ids.is_empty() {
            return Ok(MergeInsertStats::default());
        }

        let (schema, batch) = self.build_document_batch(ids, vectors, contents, metadatas)?;
        let source_batches: Vec<Result<_, crate::error::ArrowError>> = vec![Ok(batch)];
        let source = Box::new(RecordBatchIterator::new(source_batches, schema));

        let table_path = self.table_path(table_name);
        let dataset = if table_path.exists() {
            Dataset::open(table_path.to_string_lossy().as_ref()).await?
        } else {
            self.get_or_create_dataset(table_name, false).await?
        };
        let mut builder =
            MergeInsertBuilder::try_new(Arc::new(dataset), vec![match_on.to_string()])?;
        builder
            .when_matched(WhenMatched::UpdateAll)
            .when_not_matched(WhenNotMatched::InsertAll);
        let job = builder.try_build()?;
        let (updated_dataset, stats) = job.execute_reader(source).await?;

        {
            let datasets = self.datasets.lock().await;
            datasets.insert(table_name.to_string(), updated_dataset.as_ref().clone());
        }

        Ok(MergeInsertStats {
            inserted: stats.num_inserted_rows,
            updated: stats.num_updated_rows,
            deleted: stats.num_deleted_rows,
            attempts: stats.num_attempts,
            bytes_written: stats.bytes_written,
            files_written: stats.num_files_written,
        })
    }

    /// Helper to get a dataset handle or create it if it doesn't exist.
    pub async fn get_or_create_dataset(
        &self,
        table_name: &str,
        force_create: bool,
    ) -> Result<Dataset, VectorStoreError> {
        use lance::dataset::WriteParams;
        use lance::deps::arrow_array::RecordBatchIterator;

        let table_path = self.table_path(table_name);
        let is_memory_mode = self.base_path.as_os_str() == ":memory:";
        let write_uri = if is_memory_mode {
            std::env::temp_dir()
                .join(format!("omni_lance_{}", table_name))
                .to_string_lossy()
                .into_owned()
        } else {
            table_path.to_string_lossy().into_owned()
        };
        let write_path = std::path::Path::new(&write_uri);

        {
            let datasets = self.datasets.lock().await;
            if !force_create {
                if let Some(cached) = datasets.get(table_name) {
                    // Check if the cached dataset is still valid (path exists with data).
                    if write_path.exists() {
                        return Ok(cached.clone());
                    }
                }
            }
        }

        // Helper to check if directory has valid LanceDB data (not just empty directory)
        fn has_lance_data(path: &std::path::Path) -> bool {
            if !path.exists() {
                return false;
            }
            // Check for LanceDB version directory or data directory
            path.join("_versions").exists() || path.join("data").exists()
        }

        let dataset = if has_lance_data(write_path) && !force_create {
            Dataset::open(&write_uri).await?
        } else {
            // Remove existing directory if it exists (clean slate for new data).
            if write_path.exists() {
                std::fs::remove_dir_all(write_path)?;
            }
            let schema = self.create_schema();
            log::info!(
                "Creating new LanceDB dataset at {} with dimension {}",
                write_uri,
                self.dimension
            );
            let batches: Vec<Result<_, crate::error::ArrowError>> = vec![Ok(
                lance::deps::arrow_array::RecordBatch::new_empty(schema.clone()),
            )];
            Dataset::write(
                Box::new(RecordBatchIterator::new(batches, schema)),
                &write_uri,
                Some(WriteParams::default()),
            )
            .await?
        };

        {
            let datasets = self.datasets.lock().await;
            datasets.insert(table_name.to_string(), dataset.clone());
        }
        Ok(dataset)
    }
}
