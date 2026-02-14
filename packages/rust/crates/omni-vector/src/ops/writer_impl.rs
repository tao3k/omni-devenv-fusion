use lance::dataset::WriteParams;
use lance::deps::arrow_array::types::Int32Type;

/// Write params for new tables and appends: V2_1 storage for better encoding/compression.
fn default_write_params() -> WriteParams {
    WriteParams {
        data_storage_version: Some(lance_file::version::LanceFileVersion::V2_1),
        ..WriteParams::default()
    }
}

/// Build dictionary-encoded columns for low-cardinality SKILL_NAME and CATEGORY.
fn build_dictionary_columns(
    skill_names: &[String],
    categories: &[String],
) -> (
    lance::deps::arrow_array::DictionaryArray<Int32Type>,
    lance::deps::arrow_array::DictionaryArray<Int32Type>,
) {
    use lance::deps::arrow_array::{DictionaryArray, Int32Array, StringArray};

    let mut uniq_skill: Vec<String> = Vec::new();
    let mut map_skill: std::collections::HashMap<String, i32> = std::collections::HashMap::new();
    for s in skill_names {
        if !map_skill.contains_key(s) {
            let idx = uniq_skill.len() as i32;
            map_skill.insert(s.clone(), idx);
            uniq_skill.push(s.clone());
        }
    }
    let keys_skill: Vec<i32> = skill_names
        .iter()
        .map(|s| *map_skill.get(s).unwrap_or(&0))
        .collect();
    let values_skill = StringArray::from(uniq_skill);
    let skill_name_array = DictionaryArray::<Int32Type>::try_new(
        Int32Array::from(keys_skill),
        std::sync::Arc::new(values_skill),
    )
    .expect("dictionary skill_name");

    let mut uniq_cat: Vec<String> = Vec::new();
    let mut map_cat: std::collections::HashMap<String, i32> = std::collections::HashMap::new();
    for c in categories {
        if !map_cat.contains_key(c) {
            let idx = uniq_cat.len() as i32;
            map_cat.insert(c.clone(), idx);
            uniq_cat.push(c.clone());
        }
    }
    let keys_cat: Vec<i32> = categories
        .iter()
        .map(|c| *map_cat.get(c).unwrap_or(&0))
        .collect();
    let values_cat = StringArray::from(uniq_cat);
    let category_array = DictionaryArray::<Int32Type>::try_new(
        Int32Array::from(keys_cat),
        std::sync::Arc::new(values_cat),
    )
    .expect("dictionary category");

    (skill_name_array, category_array)
}

/// Build a single dictionary-encoded column from string values (e.g. TOOL_NAME).
fn build_string_dictionary(
    values: &[String],
) -> lance::deps::arrow_array::DictionaryArray<Int32Type> {
    use lance::deps::arrow_array::{DictionaryArray, Int32Array, StringArray};

    let mut uniq: Vec<String> = Vec::new();
    let mut map: std::collections::HashMap<String, i32> = std::collections::HashMap::new();
    for s in values {
        if !map.contains_key(s) {
            let idx = uniq.len() as i32;
            map.insert(s.clone(), idx);
            uniq.push(s.clone());
        }
    }
    let keys: Vec<i32> = values.iter().map(|s| *map.get(s).unwrap_or(&0)).collect();
    let value_arr = StringArray::from(uniq);
    DictionaryArray::<Int32Type>::try_new(Int32Array::from(keys), std::sync::Arc::new(value_arr))
        .expect("dictionary tool_name")
}

/// Parse JSON with simd-json when possible; fallback to serde_json to preserve behavior.
#[inline]
fn parse_metadata_extract(s: &str) -> MetadataExtract {
    let mut bytes = s.as_bytes().to_vec();
    simd_json::serde::from_slice(&mut bytes)
        .unwrap_or_else(|_| serde_json::from_str(s).unwrap_or_default())
}

/// Parse JSON to Value with simd-json when possible; fallback to serde_json.
#[inline]
fn parse_metadata_value(s: &str) -> Option<serde_json::Value> {
    let mut bytes = s.as_bytes().to_vec();
    simd_json::serde::from_slice(&mut bytes)
        .ok()
        .or_else(|| serde_json::from_str(s).ok())
}

/// Single-pass metadata extraction for Arrow-native columns (avoids full Value tree).
#[derive(serde::Deserialize, Default)]
struct MetadataExtract {
    #[serde(default)]
    skill_name: Option<String>,
    #[serde(default)]
    category: Option<String>,
    #[serde(default)]
    tool_name: Option<String>,
    #[serde(default)]
    command: Option<String>,
    #[serde(default)]
    file_path: Option<String>,
    #[serde(default)]
    routing_keywords: Vec<String>,
    #[serde(default)]
    intents: Vec<String>,
}

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
        use lance::deps::arrow_array::builder::{ListBuilder, StringBuilder};
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

        let id_array = StringArray::from(ids.clone());
        let content_array = StringArray::from(contents);
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

        // Single-pass extraction for all Arrow-native columns (simd-json when possible).
        let extracts: Vec<MetadataExtract> = metadatas
            .iter()
            .map(|s| parse_metadata_extract(s))
            .collect();

        let skill_names: Vec<String> = extracts
            .iter()
            .map(|e| e.skill_name.clone().unwrap_or_default())
            .collect();
        let categories: Vec<String> = extracts
            .iter()
            .map(|e| e.category.clone().unwrap_or_default())
            .collect();

        let (skill_name_array, category_array) =
            build_dictionary_columns(&skill_names, &categories);
        let tool_names: Vec<String> = extracts
            .iter()
            .zip(ids.iter())
            .map(|(e, id)| {
                e.tool_name
                    .clone()
                    .or_else(|| e.command.clone())
                    .unwrap_or_else(|| id.clone())
            })
            .collect();
        let tool_name_array = build_string_dictionary(&tool_names);
        let file_path_array = StringArray::from(
            extracts
                .iter()
                .map(|e| e.file_path.clone().unwrap_or_default())
                .collect::<Vec<_>>(),
        );
        let mut rk_builder = ListBuilder::new(StringBuilder::new());
        for e in &extracts {
            for s in &e.routing_keywords {
                rk_builder.values().append_value(s.as_str());
            }
            rk_builder.append(true);
        }
        let routing_keywords_array = rk_builder.finish();
        let mut in_builder = ListBuilder::new(StringBuilder::new());
        for e in &extracts {
            for s in &e.intents {
                in_builder.values().append_value(s.as_str());
            }
            in_builder.append(true);
        }
        let intents_array = in_builder.finish();
        let metadata_array = StringArray::from(metadatas);

        let schema = self.create_schema();
        let batch = lance::deps::arrow_array::RecordBatch::try_new(
            schema.clone(),
            vec![
                Arc::new(id_array),
                Arc::new(vector_array),
                Arc::new(content_array),
                Arc::new(skill_name_array),
                Arc::new(category_array),
                Arc::new(tool_name_array),
                Arc::new(file_path_array),
                Arc::new(routing_keywords_array),
                Arc::new(intents_array),
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
                        routing_keywords: t.keywords.clone(),
                        intents: t.intents.clone(),
                        category: t.category.clone(),
                    }
                })
                .collect();
            if let Err(e) = kw_index.index_batch(&search_results) {
                log::error!(
                    "Keyword index batch failed for {} tools: {}",
                    search_results.len(),
                    e
                );
            } else {
                log::info!("Keyword index: indexed {} tools", search_results.len());
            }
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
                    "skill_tools_refers": t.skill_tools_refers,
                    "resource_uri": t.resource_uri,
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

        let (mut dataset, created) = self
            .get_or_create_dataset(table_name, false, Some((schema.clone(), batch.clone())))
            .await?;
        if !created {
            dataset
                .append(
                    Box::new(RecordBatchIterator::new(vec![Ok(batch)], schema)),
                    Some(default_write_params()),
                )
                .await?;
        }

        // DUAL WRITE: Also write to Keyword Index if enabled
        if let Some(ref kw_index) = self.keyword_index {
            let mut keyword_docs = Vec::new();
            for (i, meta_str) in metadatas_for_keyword.iter().enumerate() {
                if let Some(meta) = parse_metadata_value(meta_str) {
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

    /// Add documents with rows grouped by a partition column so fragments align by partition
    /// (enables partition pruning at read). Partition value is read from each row's metadata JSON.
    pub async fn add_documents_partitioned(
        &self,
        table_name: &str,
        partition_by: &str,
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
    ) -> Result<(), VectorStoreError> {
        use lance::deps::arrow_array::RecordBatchIterator;
        use std::collections::BTreeMap;

        if ids.is_empty() {
            return Ok(());
        }
        if ids.len() != vectors.len() || ids.len() != contents.len() || ids.len() != metadatas.len()
        {
            return Err(VectorStoreError::General(
                "Mismatched input lengths for ids/vectors/contents/metadatas".to_string(),
            ));
        }

        let partition_values: Vec<String> = metadatas
            .iter()
            .map(|s| {
                parse_metadata_value(s)
                    .and_then(|v| {
                        v.get(partition_by)
                            .and_then(|x| x.as_str())
                            .map(String::from)
                    })
                    .unwrap_or_else(|| "_unknown".to_string())
            })
            .collect();

        let mut groups: BTreeMap<String, Vec<usize>> = BTreeMap::new();
        for (i, pv) in partition_values.into_iter().enumerate() {
            groups.entry(pv).or_default().push(i);
        }

        let contents_for_keyword = contents.clone();
        let metadatas_for_keyword = metadatas.clone();

        let (mut dataset, _) = self.get_or_create_dataset(table_name, false, None).await?;
        let schema = self.create_schema();

        for (_partition_value, indices) in groups {
            let part_ids: Vec<String> = indices.iter().map(|&i| ids[i].clone()).collect();
            let part_vectors: Vec<Vec<f32>> = indices.iter().map(|&i| vectors[i].clone()).collect();
            let part_contents: Vec<String> = indices.iter().map(|&i| contents[i].clone()).collect();
            let part_metadatas: Vec<String> =
                indices.iter().map(|&i| metadatas[i].clone()).collect();

            let (_, batch) =
                self.build_document_batch(part_ids, part_vectors, part_contents, part_metadatas)?;
            let batches: Vec<Result<_, crate::error::ArrowError>> = vec![Ok(batch)];
            dataset
                .append(
                    Box::new(RecordBatchIterator::new(batches, schema.clone())),
                    Some(default_write_params()),
                )
                .await?;
        }

        if let Some(ref kw_index) = self.keyword_index {
            let mut keyword_docs = Vec::new();
            for (i, meta_str) in metadatas_for_keyword.iter().enumerate() {
                if let Some(meta) = parse_metadata_value(meta_str) {
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
        // Re-enable keyword index after drop_table cleared it
        if let Err(e) = self.enable_keyword_index() {
            log::warn!("Could not re-enable keyword index after drop: {}", e);
        }
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
            self.open_dataset_at_uri(table_path.to_string_lossy().as_ref())
                .await?
        } else {
            self.get_or_create_dataset(table_name, false, None).await?.0
        };
        let mut builder =
            MergeInsertBuilder::try_new(Arc::new(dataset), vec![match_on.to_string()])?;
        builder
            .when_matched(WhenMatched::UpdateAll)
            .when_not_matched(WhenNotMatched::InsertAll);
        let job = builder.try_build()?;
        let (updated_dataset, stats) = job.execute_reader(source).await?;

        {
            let mut cache = self.datasets.lock().await;
            cache.insert(table_name.to_string(), updated_dataset.as_ref().clone());
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

    /// Get or create a dataset. When `initial` is `Some((schema, batch))` and the table is
    /// created, that batch is written (full 10-column schema). Returns `(dataset, created)` so
    /// callers can skip appending when `created` is true.
    pub async fn get_or_create_dataset(
        &self,
        table_name: &str,
        force_create: bool,
        initial: Option<(
            Arc<lance::deps::arrow_schema::Schema>,
            lance::deps::arrow_array::RecordBatch,
        )>,
    ) -> Result<(Dataset, bool), VectorStoreError> {
        use lance::deps::arrow_array::RecordBatchIterator;

        let table_path = self.table_path(table_name);
        let is_memory_mode = self.base_path.as_os_str() == ":memory:";
        let write_uri = if is_memory_mode {
            let id = self
                .memory_mode_id
                .expect("memory_mode_id set when base_path is :memory:");
            std::env::temp_dir()
                .join("omni_lance")
                .join(format!("{:016x}", id))
                .join(table_name)
                .to_string_lossy()
                .into_owned()
        } else {
            table_path.to_string_lossy().into_owned()
        };
        let write_path = std::path::Path::new(&write_uri);

        {
            let mut cache = self.datasets.lock().await;
            if !force_create {
                if let Some(cached) = cache.get(table_name) {
                    if write_path.exists() {
                        return Ok((cached, false));
                    }
                }
            }
        }

        fn has_lance_data(path: &std::path::Path) -> bool {
            if !path.exists() {
                return false;
            }
            path.join("_versions").exists() || path.join("data").exists()
        }

        let (dataset, created) = if has_lance_data(write_path) && !force_create {
            (self.open_dataset_at_uri(&write_uri).await?, false)
        } else {
            if write_path.exists() {
                // When write_path == base_path (base_path ends with .lance),
                // selectively remove only LanceDB artifacts to preserve keyword_index/.
                if write_path == self.base_path.as_path() {
                    Self::remove_lance_artifacts(write_path)?;
                } else {
                    std::fs::remove_dir_all(write_path)?;
                }
            }
            let (schema, batches) = match initial {
                Some((s, batch)) => (s, vec![Ok(batch)]),
                None => {
                    let schema = self.create_schema();
                    let empty = lance::deps::arrow_array::RecordBatch::new_empty(schema.clone());
                    (schema, vec![Ok(empty)])
                }
            };
            log::info!(
                "Creating new LanceDB dataset at {} with dimension {}",
                write_uri,
                self.dimension
            );
            let ds = Dataset::write(
                Box::new(RecordBatchIterator::new(batches, schema)),
                &write_uri,
                Some(default_write_params()),
            )
            .await?;
            (ds, true)
        };

        {
            let mut cache = self.datasets.lock().await;
            cache.insert(table_name.to_string(), dataset.clone());
        }
        Ok((dataset, created))
    }
}
