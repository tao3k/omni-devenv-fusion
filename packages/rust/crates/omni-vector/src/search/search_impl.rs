use omni_types::VectorSearchResult;

/// Multiplier for keyword match boost
const KEYWORD_BOOST: f32 = 0.1;

/// Convert JSON filter expression to LanceDB WHERE clause.
pub fn json_to_lance_where(expr: &serde_json::Value) -> String {
    match expr {
        serde_json::Value::Object(obj) => {
            if obj.is_empty() {
                return String::new();
            }
            let mut clauses = Vec::new();
            for (key, value) in obj {
                let clause = match value {
                    serde_json::Value::Object(comp) => {
                        if let Some(op) = comp.keys().next() {
                            match op.as_str() {
                                "$gt" | ">" => {
                                    if let Some(val) = comp.get("$gt").or(comp.get(">")) {
                                        match val {
                                            serde_json::Value::String(s) => {
                                                format!("{} > '{}'", key, s)
                                            }
                                            _ => format!("{} > {}", key, val),
                                        }
                                    } else {
                                        continue;
                                    }
                                }
                                "$gte" | ">=" => {
                                    if let Some(val) = comp.get("$gte").or(comp.get(">=")) {
                                        match val {
                                            serde_json::Value::String(s) => {
                                                format!("{} >= '{}'", key, s)
                                            }
                                            _ => format!("{} >= {}", key, val),
                                        }
                                    } else {
                                        continue;
                                    }
                                }
                                "$lt" | "<" => {
                                    if let Some(val) = comp.get("$lt").or(comp.get("<")) {
                                        match val {
                                            serde_json::Value::String(s) => {
                                                format!("{} < '{}'", key, s)
                                            }
                                            _ => format!("{} < {}", key, val),
                                        }
                                    } else {
                                        continue;
                                    }
                                }
                                "$lte" | "<=" => {
                                    if let Some(val) = comp.get("$lte").or(comp.get("<=")) {
                                        match val {
                                            serde_json::Value::String(s) => {
                                                format!("{} <= '{}'", key, s)
                                            }
                                            _ => format!("{} <= {}", key, val),
                                        }
                                    } else {
                                        continue;
                                    }
                                }
                                "$ne" | "!=" => {
                                    if let Some(val) = comp.get("$ne").or(comp.get("!=")) {
                                        match val {
                                            serde_json::Value::String(s) => {
                                                format!("{} != '{}'", key, s)
                                            }
                                            _ => format!("{} != {}", key, val),
                                        }
                                    } else {
                                        continue;
                                    }
                                }
                                _ => continue,
                            }
                        } else {
                            continue;
                        }
                    }
                    serde_json::Value::String(s) => format!("{} = '{}'", key, s),
                    serde_json::Value::Number(n) => format!("{} = {}", key, n),
                    serde_json::Value::Bool(b) => format!("{} = {}", key, b),
                    _ => continue,
                };
                clauses.push(clause);
            }
            if clauses.is_empty() {
                String::new()
            } else {
                clauses.join(" AND ")
            }
        }
        _ => String::new(),
    }
}

impl VectorStore {
    /// Search for similar documents in a table.
    pub async fn search(
        &self,
        table_name: &str,
        query: Vec<f32>,
        limit: usize,
    ) -> Result<Vec<VectorSearchResult>, VectorStoreError> {
        self.search_with_keywords(table_name, query, Vec::new(), limit, None)
            .await
    }

    /// Search with metadata filtering.
    pub async fn search_filtered(
        &self,
        table_name: &str,
        query: Vec<f32>,
        limit: usize,
        where_filter: Option<String>,
    ) -> Result<Vec<VectorSearchResult>, VectorStoreError> {
        self.search_with_keywords(table_name, query, Vec::new(), limit, where_filter)
            .await
    }

    /// Internal search implementation with optional keyword boosting and metadata filtering.
    pub async fn search_with_keywords(
        &self,
        table_name: &str,
        query: Vec<f32>,
        _keywords: Vec<String>,
        limit: usize,
        where_filter: Option<String>,
    ) -> Result<Vec<VectorSearchResult>, VectorStoreError> {
        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref()).await?;
        let query_arr = lance::deps::arrow_array::Float32Array::from(query);

        let mut scanner = dataset.scan();
        let fetch_count = limit.saturating_mul(2).max(limit + 10);
        scanner.nearest(VECTOR_COLUMN, &query_arr, fetch_count)?;

        let mut stream = scanner.try_into_stream().await?;
        let filter_conditions = where_filter
            .as_ref()
            .map(|f| serde_json::from_str::<serde_json::Value>(f).ok())
            .flatten();

        let mut results = Vec::new();

        while let Some(batch) = stream.try_next().await? {
            use lance::deps::arrow_array::{Array, Float32Array, StringArray};
            let id_col = batch
                .column_by_name(ID_COLUMN)
                .ok_or_else(|| VectorStoreError::General("id column not found".to_string()))?;
            let content_col = batch
                .column_by_name(CONTENT_COLUMN)
                .ok_or_else(|| VectorStoreError::General("content column not found".to_string()))?;
            let distance_col = batch.column_by_name("_distance").ok_or_else(|| {
                VectorStoreError::General("_distance column not found".to_string())
            })?;
            let metadata_col = batch.column_by_name(METADATA_COLUMN);

            let ids = id_col.as_any().downcast_ref::<StringArray>().unwrap();
            let contents = content_col.as_any().downcast_ref::<StringArray>().unwrap();
            let distances = distance_col
                .as_any()
                .downcast_ref::<Float32Array>()
                .unwrap();

            for i in 0..batch.num_rows() {
                let metadata = if let Some(meta_col) = metadata_col {
                    if let Some(meta_arr) = meta_col.as_any().downcast_ref::<StringArray>() {
                        if meta_arr.is_null(i) {
                            serde_json::Value::Null
                        } else {
                            serde_json::from_str(meta_arr.value(i)).unwrap_or_default()
                        }
                    } else {
                        serde_json::Value::Null
                    }
                } else {
                    serde_json::Value::Null
                };

                if let Some(ref conditions) = filter_conditions {
                    if !VectorStore::matches_filter(&metadata, conditions) {
                        continue;
                    }
                }

                results.push(VectorSearchResult {
                    id: ids.value(i).to_string(),
                    content: contents.value(i).to_string(),
                    metadata,
                    distance: f64::from(distances.value(i)),
                });
            }
        }

        results.sort_by(|a, b| {
            a.distance
                .partial_cmp(&b.distance)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        results.truncate(limit);
        Ok(results)
    }

    /// Hybrid search combining vector similarity and keyword (BM25) search.
    pub async fn hybrid_search(
        &self,
        table_name: &str,
        query: &str,
        query_vector: Vec<f32>,
        limit: usize,
    ) -> Result<Vec<HybridSearchResult>, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        let keyword_index = self
            .keyword_index
            .as_ref()
            .ok_or_else(|| VectorStoreError::General("Keyword index not enabled.".to_string()))?;

        let vector_future = self.search(table_name, query_vector.clone(), limit * 2);

        let kw_query = query.to_string();
        let kw_index = keyword_index.clone();
        let kw_future = tokio::task::spawn_blocking(move || kw_index.search(&kw_query, limit * 2));

        let vector_results = vector_future.await?;
        let kw_results: Vec<skill::ToolSearchResult> = match kw_future
            .await
            .map_err(|e| VectorStoreError::General(format!("Keyword search task failed: {}", e)))?
        {
            Ok(results) => results,
            Err(e) => {
                log::debug!("Keyword search failed, falling back to vector-only: {}", e);
                Vec::new()
            }
        };

        let vector_scores: Vec<(String, f32)> = vector_results
            .iter()
            .map(|r| (r.id.clone(), 1.0 - r.distance as f32))
            .collect();

        let fused_results = apply_weighted_rrf(
            vector_scores,
            kw_results,
            RRF_K,
            SEMANTIC_WEIGHT,
            KEYWORD_WEIGHT,
            query,
        );

        Ok(fused_results.into_iter().take(limit).collect())
    }

    /// Index a document in the keyword index.
    pub fn index_keyword(
        &self,
        name: &str,
        description: &str,
        category: &str,
        keywords: &[String],
        intents: &[String],
    ) -> Result<(), VectorStoreError> {
        if let Some(index) = &self.keyword_index {
            index.upsert_document(name, description, category, keywords, intents)?;
        }
        Ok(())
    }

    /// Bulk index documents in the keyword index.
    pub fn bulk_index_keywords<I>(&self, docs: I) -> Result<(), VectorStoreError>
    where
        I: IntoIterator<Item = (String, String, String, Vec<String>, Vec<String>)>,
    {
        if let Some(index) = &self.keyword_index {
            index.bulk_upsert(docs)?;
        }
        Ok(())
    }

    /// Apply keyword boosting to search results.
    pub fn apply_keyword_boost(results: &mut [VectorSearchResult], keywords: &[String]) {
        if keywords.is_empty() {
            return;
        }
        let mut query_keywords: Vec<String> = Vec::new();
        for s in keywords {
            let lowered = s.to_lowercase();
            for w in lowered.split_whitespace() {
                query_keywords.push(w.to_string());
            }
        }

        for result in results {
            let mut keyword_score = 0.0;

            // 1. Boost from metadata keywords
            if let Some(keywords_arr) = result.metadata.get("keywords").and_then(|v| v.as_array()) {
                for kw in &query_keywords {
                    if keywords_arr
                        .iter()
                        .any(|k| k.as_str().map_or(false, |s| s.to_lowercase().contains(kw)))
                    {
                        keyword_score += KEYWORD_BOOST;
                    }
                }
            }

            // 2. Boost from metadata intents
            if let Some(intents_arr) = result.metadata.get("intents").and_then(|v| v.as_array()) {
                for kw in &query_keywords {
                    if intents_arr
                        .iter()
                        .any(|k| k.as_str().map_or(false, |s| s.to_lowercase().contains(kw)))
                    {
                        keyword_score += KEYWORD_BOOST * 1.2; // Intents are higher signal
                    }
                }
            }

            let tool_name_lower = result.id.to_lowercase();
            let content_lower = result.content.to_lowercase();
            for kw in &query_keywords {
                if tool_name_lower.contains(kw) {
                    keyword_score += KEYWORD_BOOST * 0.5;
                }
                if content_lower.contains(kw) {
                    keyword_score += KEYWORD_BOOST * 0.3;
                }
            }
            let keyword_bonus = keyword_score * 0.3f32;
            result.distance = (result.distance - keyword_bonus as f64).max(0.0);
        }
    }
}
