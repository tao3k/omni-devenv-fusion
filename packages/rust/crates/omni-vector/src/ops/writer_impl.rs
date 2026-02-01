impl VectorStore {
    /// Add tool records to the vector store.
    pub async fn add(
        &self,
        table_name: &str,
        tools: Vec<ToolRecord>,
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
                        skill_name: t.skill_name.clone(),
                        tool_name: t.tool_name.clone(),
                        file_path: t.file_path.clone(),
                        keywords: t.keywords.clone(),
                        intents: t.intents.clone(),
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
        let metadatas: Vec<String> = tools.iter().map(|t| {
            let command_name = t.tool_name.split('.').skip(1).collect::<Vec<_>>().join(".");
            serde_json::json!({
                "type": "command", "skill_name": t.skill_name, "command": command_name, "tool_name": t.tool_name,
                "file_path": t.file_path, "function_name": t.function_name, "keywords": t.keywords, "intents": t.intents,
                "file_hash": t.file_hash, "input_schema": t.input_schema, "docstring": t.docstring,
            }).to_string()
        }).collect();

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
        use lance::deps::arrow_array::{
            FixedSizeListArray, Float32Array, RecordBatchIterator, StringArray,
        };

        if ids.is_empty() {
            return Ok(());
        }

        let dimension = vectors[0].len();
        let id_array = StringArray::from(ids.clone());
        let content_array = StringArray::from(contents.clone());
        let metadata_array = StringArray::from(metadatas.clone());
        let flat_values: Vec<f32> = vectors.into_iter().flatten().collect();
        let vector_array = FixedSizeListArray::try_new(
            Arc::new(lance::deps::arrow_schema::Field::new(
                "item",
                lance::deps::arrow_schema::DataType::Float32,
                true,
            )),
            i32::try_from(dimension).unwrap_or(1536),
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

        let mut dataset = self.get_or_create_dataset(table_name, false).await?;
        let batches: Vec<Result<_, crate::error::ArrowError>> = vec![Ok(batch)];
        dataset
            .append(Box::new(RecordBatchIterator::new(batches, schema)), None)
            .await?;

        // DUAL WRITE: Also write to Keyword Index if enabled
        if let Some(ref kw_index) = self.keyword_index {
            let mut keyword_docs = Vec::new();
            for (i, meta_str) in metadatas.iter().enumerate() {
                if let Ok(meta) = serde_json::from_str::<serde_json::Value>(meta_str) {
                    let name = meta
                        .get("tool_name")
                        .and_then(|s| s.as_str())
                        .or_else(|| meta.get("command").and_then(|s| s.as_str()))
                        .unwrap_or(&ids[i])
                        .to_string();
                    let category = meta
                        .get("skill_name")
                        .and_then(|s| s.as_str())
                        .unwrap_or("unknown")
                        .to_string();
                    let kws: Vec<String> = meta
                        .get("keywords")
                        .and_then(|v| v.as_array())
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|v| v.as_str().map(|s| s.to_string()))
                                .collect()
                        })
                        .unwrap_or_default();
                    let intents: Vec<String> = meta
                        .get("intents")
                        .and_then(|v| v.as_array())
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|v| v.as_str().map(|s| s.to_string()))
                                .collect()
                        })
                        .unwrap_or_default();
                    keyword_docs.push((name, contents[i].clone(), category, kws, intents));
                }
            }
            if !keyword_docs.is_empty() {
                let _ = kw_index.bulk_upsert(keyword_docs);
            }
        }
        Ok(())
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
        let table_uri = table_path.to_string_lossy().into_owned();

        {
            let datasets = self.datasets.lock().await;
            if !force_create {
                if let Some(cached) = datasets.get(table_name) {
                    return Ok(cached.clone());
                }
            }
        }

        let is_memory_mode = self.base_path.as_os_str() == ":memory:";
        let dataset = if !is_memory_mode && table_path.exists() && !force_create {
            Dataset::open(&table_uri).await?
        } else {
            let schema = self.create_schema();
            let batches: Vec<Result<_, crate::error::ArrowError>> = vec![Ok(
                lance::deps::arrow_array::RecordBatch::new_empty(schema.clone()),
            )];
            let write_uri = if is_memory_mode {
                std::env::temp_dir()
                    .join(format!("omni_lance_{}", table_name))
                    .to_string_lossy()
                    .into_owned()
            } else {
                table_uri
            };
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
