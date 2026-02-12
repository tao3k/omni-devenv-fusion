use lance_index::scalar::FullTextSearchQuery;
use omni_types::VectorSearchResult;
use serde_json::Value;

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
    /// Backward-compatible search wrapper.
    pub async fn search(
        &self,
        table_name: &str,
        query: Vec<f32>,
        limit: usize,
    ) -> Result<Vec<VectorSearchResult>, VectorStoreError> {
        self.search_optimized(table_name, query, limit, SearchOptions::default())
            .await
    }

    /// Search with configurable scanner tuning for projection / read-ahead.
    pub async fn search_optimized(
        &self,
        table_name: &str,
        query: Vec<f32>,
        limit: usize,
        options: SearchOptions,
    ) -> Result<Vec<VectorSearchResult>, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref()).await?;
        let query_arr = lance::deps::arrow_array::Float32Array::from(query);
        let (pushdown_filter, metadata_filter) =
            Self::build_filter_plan(options.where_filter.as_deref());

        let mut scanner = dataset.scan();
        let fetch_count = limit.saturating_mul(2).max(limit + 10);
        if !options.projected_columns.is_empty() {
            scanner.project(&options.projected_columns)?;
        }
        scanner.nearest(VECTOR_COLUMN, &query_arr, fetch_count)?;
        if let Some(batch_size) = options.batch_size {
            scanner.batch_size(batch_size);
        }
        if let Some(fragment_readahead) = options.fragment_readahead {
            scanner.fragment_readahead(fragment_readahead);
        }
        if let Some(batch_readahead) = options.batch_readahead {
            scanner.batch_readahead(batch_readahead);
        }
        if let Some(filter) = pushdown_filter {
            scanner.filter(&filter)?;
        }
        let scan_limit = options.scan_limit.unwrap_or(fetch_count);
        scanner.limit(Some(i64::try_from(scan_limit).unwrap_or(i64::MAX)), None)?;

        let mut stream = scanner.try_into_stream().await?;
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

                if let Some(ref conditions) = metadata_filter {
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

    /// Run native Lance full-text search over the content column.
    pub async fn search_fts(
        &self,
        table_name: &str,
        query: &str,
        limit: usize,
        where_filter: Option<&str>,
    ) -> Result<Vec<skill::ToolSearchResult>, VectorStoreError> {
        if query.trim().is_empty() || limit == 0 {
            return Ok(Vec::new());
        }

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref()).await?;
        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN, CONTENT_COLUMN, METADATA_COLUMN])?;
        scanner.full_text_search(FullTextSearchQuery::new(query.to_string()))?;
        if let Some(filter) = where_filter.map(str::trim).filter(|f| !f.is_empty()) {
            scanner.filter(filter)?;
        }
        scanner.limit(Some(i64::try_from(limit).unwrap_or(i64::MAX)), None)?;

        let mut stream = scanner.try_into_stream().await?;
        let mut results = Vec::new();

        while let Some(batch) = stream.try_next().await? {
            use lance::deps::arrow_array::{Array, Float32Array, Float64Array, StringArray};
            let id_col = batch
                .column_by_name(ID_COLUMN)
                .ok_or_else(|| VectorStoreError::General("id column not found".to_string()))?;
            let content_col = batch
                .column_by_name(CONTENT_COLUMN)
                .ok_or_else(|| VectorStoreError::General("content column not found".to_string()))?;
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let score_col = batch.column_by_name("_score");

            let ids = id_col
                .as_any()
                .downcast_ref::<StringArray>()
                .ok_or_else(|| {
                    VectorStoreError::General("id column type mismatch for fts".to_string())
                })?;
            let contents = content_col
                .as_any()
                .downcast_ref::<StringArray>()
                .ok_or_else(|| {
                    VectorStoreError::General("content column type mismatch for fts".to_string())
                })?;

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

                let score = if let Some(col) = score_col {
                    if let Some(arr) = col.as_any().downcast_ref::<Float32Array>() {
                        arr.value(i)
                    } else if let Some(arr) = col.as_any().downcast_ref::<Float64Array>() {
                        arr.value(i) as f32
                    } else {
                        0.0
                    }
                } else {
                    0.0
                };

                let keywords = skill::resolve_routing_keywords(&metadata);
                let intents = skill::resolve_intents(&metadata);

                let tool_name = metadata
                    .get("tool_name")
                    .and_then(|v| v.as_str())
                    .map(ToString::to_string)
                    .unwrap_or_else(|| ids.value(i).to_string());
                let skill_name = metadata
                    .get("skill_name")
                    .and_then(|v| v.as_str())
                    .map(ToString::to_string)
                    .unwrap_or_else(|| tool_name.split('.').next().unwrap_or("").to_string());
                let category = metadata
                    .get("category")
                    .and_then(|v| v.as_str())
                    .map(ToString::to_string)
                    .unwrap_or_else(|| skill_name.clone());

                results.push(skill::ToolSearchResult {
                    name: ids.value(i).to_string(),
                    description: contents.value(i).to_string(),
                    input_schema: metadata
                        .get("input_schema")
                        .map(skill::normalize_input_schema_value)
                        .unwrap_or_else(|| serde_json::json!({})),
                    score,
                    vector_score: Some(score),
                    keyword_score: None,
                    skill_name,
                    tool_name,
                    file_path: metadata
                        .get("file_path")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string(),
                    keywords,
                    intents,
                    category,
                });
            }
        }

        results.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        results.truncate(limit);
        Ok(results)
    }

    /// Unified keyword search entrypoint for configured backend.
    pub async fn keyword_search(
        &self,
        table_name: &str,
        query: &str,
        limit: usize,
    ) -> Result<Vec<skill::ToolSearchResult>, VectorStoreError> {
        match self.keyword_backend {
            KeywordSearchBackend::Tantivy => {
                let index = self.keyword_index.as_ref().ok_or_else(|| {
                    VectorStoreError::General("Keyword index not enabled.".to_string())
                })?;
                index.search(query, limit)
            }
            KeywordSearchBackend::LanceFts => self.search_fts(table_name, query, limit, None).await,
        }
    }

    fn build_filter_plan(where_filter: Option<&str>) -> (Option<String>, Option<Value>) {
        let Some(filter) = where_filter.map(str::trim).filter(|f| !f.is_empty()) else {
            return (None, None);
        };

        if let Ok(json_filter) = serde_json::from_str::<Value>(filter) {
            let pushdown = if Self::is_pushdown_eligible_json(&json_filter) {
                let candidate = json_to_lance_where(&json_filter);
                if candidate.is_empty() {
                    None
                } else {
                    Some(candidate)
                }
            } else {
                None
            };
            return (pushdown, Some(json_filter));
        }

        (Some(filter.to_string()), None)
    }

    fn is_pushdown_eligible_json(expr: &Value) -> bool {
        let Some(obj) = expr.as_object() else {
            return false;
        };
        obj.keys().all(|key| {
            key == ID_COLUMN
                || key == CONTENT_COLUMN
                || key == METADATA_COLUMN
                || key == "_distance"
        })
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

        let vector_future = self.search_optimized(
            table_name,
            query_vector.clone(),
            limit * 2,
            SearchOptions::default(),
        );

        let vector_results = vector_future.await?;
        let kw_results: Vec<skill::ToolSearchResult> =
            match self.keyword_search(table_name, query, limit * 2).await {
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
        if self.keyword_backend != KeywordSearchBackend::Tantivy {
            return Ok(());
        }
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
        if self.keyword_backend != KeywordSearchBackend::Tantivy {
            return Ok(());
        }
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
            if let Some(keywords_arr) = result
                .metadata
                .get("routing_keywords")
                .and_then(|v| v.as_array())
            {
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
