use arrow::array::{Float32Array, Float64Array, ListBuilder, StringArray, StringBuilder};
use arrow::datatypes::{DataType, Field, Schema};
use arrow_ipc::writer::StreamWriter;
use lance_index::scalar::FullTextSearchQuery;
use omni_types::VectorSearchResult;
use serde::Deserialize;
use serde_json::Value;
use std::io::Cursor;

fn normalize_string_vec(v: Vec<String>) -> Vec<String> {
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();
    for s in v {
        let t = s.trim();
        if t.is_empty() {
            continue;
        }
        if seen.insert(t.to_string()) {
            out.push(t.to_string());
        }
    }
    out
}

/// Metadata fields needed for FTS result rows. Parsed once per row instead of full Value + .get().
#[derive(Deserialize, Default)]
struct FtsMetadataRow {
    #[serde(default)]
    tool_name: Option<String>,
    #[serde(default)]
    skill_name: Option<String>,
    #[serde(default)]
    category: Option<String>,
    #[serde(default)]
    file_path: Option<String>,
    #[serde(default)]
    input_schema: Option<Value>,
    #[serde(default)]
    routing_keywords: Vec<String>,
    #[serde(default)]
    intents: Vec<String>,
}

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

/// Allowed column names for IPC projection (vector search result batch).
const IPC_VECTOR_COLUMNS: &[&str] = &[
    "id",
    "content",
    "tool_name",
    "file_path",
    "routing_keywords",
    "intents",
    "_distance",
    "metadata",
];

/// Encode search results as Arrow IPC stream bytes (single RecordBatch).
/// If `projection` is Some and non-empty, only those columns are included (smaller payload).
/// Schema (full): id, content, tool_name, file_path, routing_keywords (List<Utf8>), intents (List<Utf8>), _distance, metadata (Utf8).
fn search_results_to_ipc(
    results: &[VectorSearchResult],
    projection: Option<&[String]>,
) -> Result<Vec<u8>, String> {
    use arrow::record_batch::RecordBatch;
    use std::sync::Arc;

    let ids: Vec<&str> = results.iter().map(|r| r.id.as_str()).collect();
    let contents: Vec<&str> = results.iter().map(|r| r.content.as_str()).collect();
    let tool_names: Vec<&str> = results.iter().map(|r| r.tool_name.as_str()).collect();
    let file_paths: Vec<&str> = results.iter().map(|r| r.file_path.as_str()).collect();
    let distances: Vec<f64> = results.iter().map(|r| r.distance).collect();
    let metadata_strs: Vec<String> = results
        .iter()
        .map(|r| serde_json::to_string(&r.metadata).unwrap_or_else(|_| "null".to_string()))
        .collect();
    let metadata_refs: Vec<&str> = metadata_strs.iter().map(String::as_str).collect();

    let mut rk_builder = ListBuilder::new(StringBuilder::new());
    for r in results {
        for s in r
            .routing_keywords
            .split_whitespace()
            .filter(|s| !s.is_empty())
        {
            rk_builder.values().append_value(s);
        }
        rk_builder.append(true);
    }
    let rk_array = Arc::new(rk_builder.finish());

    let mut intents_builder = ListBuilder::new(StringBuilder::new());
    for r in results {
        for s in r
            .intents
            .split(" | ")
            .map(str::trim)
            .filter(|s| !s.is_empty())
        {
            intents_builder.values().append_value(s);
        }
        intents_builder.append(true);
    }
    let intents_array = Arc::new(intents_builder.finish());

    let cols: Vec<&str> = match projection {
        Some(p) if !p.is_empty() => {
            for name in p {
                if !IPC_VECTOR_COLUMNS.contains(&name.as_str()) {
                    return Err(format!("invalid ipc_projection column: {}", name));
                }
            }
            p.iter().map(String::as_str).collect()
        }
        _ => IPC_VECTOR_COLUMNS.to_vec(),
    };

    let mut schema_fields = Vec::with_capacity(cols.len());
    let mut arrays: Vec<Arc<dyn arrow::array::Array>> = Vec::with_capacity(cols.len());
    for col in &cols {
        match *col {
            "id" => {
                schema_fields.push(Field::new("id", DataType::Utf8, true));
                arrays.push(Arc::new(StringArray::from(ids.clone())));
            }
            "content" => {
                schema_fields.push(Field::new("content", DataType::Utf8, true));
                arrays.push(Arc::new(StringArray::from(contents.clone())));
            }
            "tool_name" => {
                schema_fields.push(Field::new("tool_name", DataType::Utf8, true));
                arrays.push(Arc::new(StringArray::from(tool_names.clone())));
            }
            "file_path" => {
                schema_fields.push(Field::new("file_path", DataType::Utf8, true));
                arrays.push(Arc::new(StringArray::from(file_paths.clone())));
            }
            "routing_keywords" => {
                schema_fields.push(Field::new(
                    "routing_keywords",
                    DataType::List(Arc::new(Field::new("item", DataType::Utf8, true))),
                    true,
                ));
                arrays.push(rk_array.clone());
            }
            "intents" => {
                schema_fields.push(Field::new(
                    "intents",
                    DataType::List(Arc::new(Field::new("item", DataType::Utf8, true))),
                    true,
                ));
                arrays.push(intents_array.clone());
            }
            "_distance" => {
                schema_fields.push(Field::new("_distance", DataType::Float64, true));
                arrays.push(Arc::new(Float64Array::from(distances.clone())));
            }
            "metadata" => {
                schema_fields.push(Field::new("metadata", DataType::Utf8, true));
                arrays.push(Arc::new(StringArray::from(metadata_refs.clone())));
            }
            _ => {}
        }
    }

    let schema = Schema::new(schema_fields);
    let batch = RecordBatch::try_new(Arc::new(schema), arrays).map_err(|e| e.to_string())?;

    let mut buf = Cursor::new(Vec::new());
    let mut writer =
        StreamWriter::try_new(&mut buf, batch.schema().as_ref()).map_err(|e| e.to_string())?;
    writer.write(&batch).map_err(|e| e.to_string())?;
    writer.finish().map_err(|e| e.to_string())?;
    Ok(buf.into_inner())
}

/// Encode tool search results as Arrow IPC stream bytes (single RecordBatch).
/// Schema: name, description, score, skill_name, tool_name, file_path, routing_keywords (List<Utf8>), intents (List<Utf8>), category, metadata (Utf8 JSON), vector_score, keyword_score.
/// Python ToolSearchPayload.from_arrow_table consumes this (confidence/final_score default on Python side).
pub(crate) fn tool_search_results_to_ipc(
    results: &[crate::skill::ToolSearchResult],
) -> Result<Vec<u8>, String> {
    use arrow::record_batch::RecordBatch;
    use std::sync::Arc;

    if results.is_empty() {
        let schema = Schema::new(vec![
            Field::new("name", DataType::Utf8, true),
            Field::new("description", DataType::Utf8, true),
            Field::new("score", DataType::Float32, true),
        ]);
        let batch = RecordBatch::try_new(
            Arc::new(schema),
            vec![
                Arc::new(StringArray::from(Vec::<String>::new())),
                Arc::new(StringArray::from(Vec::<String>::new())),
                Arc::new(Float32Array::from(Vec::<f32>::new())),
            ],
        )
        .map_err(|e| e.to_string())?;
        let mut buf = Cursor::new(Vec::new());
        let mut writer =
            StreamWriter::try_new(&mut buf, batch.schema().as_ref()).map_err(|e| e.to_string())?;
        writer.write(&batch).map_err(|e| e.to_string())?;
        writer.finish().map_err(|e| e.to_string())?;
        return Ok(buf.into_inner());
    }

    let names: Vec<&str> = results.iter().map(|r| r.name.as_str()).collect();
    let descriptions: Vec<&str> = results.iter().map(|r| r.description.as_str()).collect();
    let scores: Vec<f32> = results.iter().map(|r| r.score).collect();
    let skill_names: Vec<&str> = results.iter().map(|r| r.skill_name.as_str()).collect();
    let tool_names: Vec<&str> = results.iter().map(|r| r.tool_name.as_str()).collect();
    let file_paths: Vec<&str> = results.iter().map(|r| r.file_path.as_str()).collect();
    let categories: Vec<&str> = results.iter().map(|r| r.category.as_str()).collect();
    let metadata_strs: Vec<String> = results
        .iter()
        .map(|r| serde_json::to_string(&r.input_schema).unwrap_or_else(|_| "{}".to_string()))
        .collect();
    let metadata_refs: Vec<&str> = metadata_strs.iter().map(String::as_str).collect();
    let vector_scores: Vec<Option<f32>> = results.iter().map(|r| r.vector_score).collect();
    let keyword_scores: Vec<Option<f32>> = results.iter().map(|r| r.keyword_score).collect();

    let vec_score_arr = Float32Array::from_iter(vector_scores.into_iter());
    let kw_score_arr = Float32Array::from_iter(keyword_scores.into_iter());

    let mut rk_builder = ListBuilder::new(StringBuilder::new());
    for r in results {
        for s in &r.routing_keywords {
            rk_builder.values().append_value(s.as_str());
        }
        rk_builder.append(true);
    }
    let rk_array = Arc::new(rk_builder.finish());

    let mut intents_builder = ListBuilder::new(StringBuilder::new());
    for r in results {
        for s in &r.intents {
            intents_builder.values().append_value(s.as_str());
        }
        intents_builder.append(true);
    }
    let intents_array = Arc::new(intents_builder.finish());

    let schema = Schema::new(vec![
        Field::new("name", DataType::Utf8, true),
        Field::new("description", DataType::Utf8, true),
        Field::new("score", DataType::Float32, true),
        Field::new("skill_name", DataType::Utf8, true),
        Field::new("tool_name", DataType::Utf8, true),
        Field::new("file_path", DataType::Utf8, true),
        Field::new(
            "routing_keywords",
            DataType::List(Arc::new(Field::new("item", DataType::Utf8, true))),
            true,
        ),
        Field::new(
            "intents",
            DataType::List(Arc::new(Field::new("item", DataType::Utf8, true))),
            true,
        ),
        Field::new("category", DataType::Utf8, true),
        Field::new("metadata", DataType::Utf8, true),
        Field::new("vector_score", DataType::Float32, true),
        Field::new("keyword_score", DataType::Float32, true),
    ]);

    let batch = RecordBatch::try_new(
        Arc::new(schema),
        vec![
            Arc::new(StringArray::from(names)),
            Arc::new(StringArray::from(descriptions)),
            Arc::new(Float32Array::from(scores)),
            Arc::new(StringArray::from(skill_names)),
            Arc::new(StringArray::from(tool_names)),
            Arc::new(StringArray::from(file_paths)),
            rk_array,
            intents_array,
            Arc::new(StringArray::from(categories)),
            Arc::new(StringArray::from(metadata_refs)),
            Arc::new(vec_score_arr),
            Arc::new(kw_score_arr),
        ],
    )
    .map_err(|e| e.to_string())?;

    let mut buf = Cursor::new(Vec::new());
    let mut writer =
        StreamWriter::try_new(&mut buf, batch.schema().as_ref()).map_err(|e| e.to_string())?;
    writer.write(&batch).map_err(|e| e.to_string())?;
    writer.finish().map_err(|e| e.to_string())?;
    Ok(buf.into_inner())
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

        let dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let query_arr = lance::deps::arrow_array::Float32Array::from(query);
        let (pushdown_filter, metadata_filter) =
            Self::build_filter_plan(options.where_filter.as_deref());

        let mut scanner = dataset.scan();
        // When a filter is pushed down, Lance may use scalar indices (e.g. skill_name/category);
        // if filtering happens after ANN we request more candidates so enough pass the filter.
        let fetch_count = if pushdown_filter.is_some() {
            limit.saturating_mul(4).max(limit + 50)
        } else {
            limit.saturating_mul(2).max(limit + 10)
        };
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
        let mut results = Vec::with_capacity(limit.min(1024));

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
            let tool_name_col = batch.column_by_name(crate::TOOL_NAME_COLUMN);
            let file_path_col = batch.column_by_name(crate::FILE_PATH_COLUMN);
            let routing_keywords_col = batch.column_by_name(crate::ROUTING_KEYWORDS_COLUMN);
            let intents_col = batch.column_by_name(crate::INTENTS_COLUMN);

            let ids = id_col.as_any().downcast_ref::<StringArray>().unwrap();
            let contents = content_col.as_any().downcast_ref::<StringArray>().unwrap();
            let distances = distance_col
                .as_any()
                .downcast_ref::<Float32Array>()
                .unwrap();

            let str_at = |col: Option<&std::sync::Arc<dyn Array>>, i: usize| -> String {
                col.map(|c| crate::ops::get_utf8_at(c.as_ref(), i))
                    .unwrap_or_default()
            };
            let rk_at = |col: Option<&std::sync::Arc<dyn Array>>, i: usize| -> Vec<String> {
                col.map(|c| crate::ops::get_routing_keywords_at(c.as_ref(), i))
                    .unwrap_or_default()
            };
            let intents_at = |col: Option<&std::sync::Arc<dyn Array>>, i: usize| -> Vec<String> {
                col.map(|c| crate::ops::get_intents_at(c.as_ref(), i))
                    .unwrap_or_default()
            };

            for i in 0..batch.num_rows() {
                let tool_name = str_at(tool_name_col, i);
                let file_path = str_at(file_path_col, i);
                let routing_keywords_vec = rk_at(routing_keywords_col, i);
                let intents_vec = intents_at(intents_col, i);
                let routing_keywords = routing_keywords_vec.join(" ");
                let intents = intents_vec.join(" | ");

                let (metadata, tool_name_out, file_path_out, routing_keywords_out, intents_out) =
                    if tool_name.is_empty()
                        && file_path.is_empty()
                        && routing_keywords_vec.is_empty()
                        && intents_vec.is_empty()
                    {
                        let metadata = if let Some(meta_col) = metadata_col {
                            if let Some(meta_arr) = meta_col.as_any().downcast_ref::<StringArray>()
                            {
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
                        let tool_name_out = metadata
                            .get("tool_name")
                            .and_then(|v| v.as_str())
                            .unwrap_or("")
                            .to_string();
                        let file_path_out = metadata
                            .get("file_path")
                            .and_then(|v| v.as_str())
                            .unwrap_or("")
                            .to_string();
                        let routing_keywords_out = metadata
                            .get("routing_keywords")
                            .and_then(|v| v.as_array())
                            .map(|arr| {
                                arr.iter()
                                    .filter_map(|v| v.as_str())
                                    .collect::<Vec<_>>()
                                    .join(" ")
                            })
                            .unwrap_or_default();
                        let intents_out = metadata
                            .get("intents")
                            .and_then(|v| v.as_array())
                            .map(|arr| {
                                arr.iter()
                                    .filter_map(|v| v.as_str())
                                    .collect::<Vec<_>>()
                                    .join(" | ")
                            })
                            .unwrap_or_default();
                        (
                            metadata,
                            tool_name_out,
                            file_path_out,
                            routing_keywords_out,
                            intents_out,
                        )
                    } else {
                        let kw_json: Vec<serde_json::Value> = routing_keywords_vec
                            .iter()
                            .map(|s| serde_json::Value::String(s.clone()))
                            .collect();
                        let inv_json: Vec<serde_json::Value> = intents_vec
                            .iter()
                            .map(|s| serde_json::Value::String(s.clone()))
                            .collect();
                        let metadata = serde_json::json!({
                            "tool_name": tool_name,
                            "file_path": file_path,
                            "routing_keywords": kw_json,
                            "intents": inv_json,
                        });
                        (
                            metadata,
                            tool_name.clone(),
                            file_path.clone(),
                            routing_keywords,
                            intents,
                        )
                    };

                if let Some(ref conditions) = metadata_filter {
                    if !VectorStore::matches_filter(&metadata, conditions) {
                        continue;
                    }
                }

                let id_val = ids.value(i).to_string();
                let (id, tool_name) = if tool_name_out.is_empty() {
                    (id_val.clone(), id_val)
                } else {
                    (id_val, tool_name_out)
                };
                results.push(VectorSearchResult {
                    id,
                    content: contents.value(i).to_string(),
                    tool_name,
                    file_path: file_path_out,
                    routing_keywords: routing_keywords_out,
                    intents: intents_out,
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

    /// Search with configurable options; returns Arrow IPC stream bytes for zero-copy consumption in Python.
    /// See [search result batch contract](docs/reference/search-result-batch-contract.md).
    pub async fn search_optimized_ipc(
        &self,
        table_name: &str,
        query: Vec<f32>,
        limit: usize,
        options: SearchOptions,
    ) -> Result<Vec<u8>, VectorStoreError> {
        let results = self
            .search_optimized(table_name, query, limit, options.clone())
            .await?;
        search_results_to_ipc(&results, options.ipc_projection.as_deref())
            .map_err(VectorStoreError::General)
    }

    /// Tool search; returns Arrow IPC stream bytes for zero-copy consumption in Python.
    /// Schema: name, description, score, skill_name, tool_name, file_path, routing_keywords, intents, category, metadata, vector_score, keyword_score.
    pub async fn search_tools_ipc(
        &self,
        table_name: &str,
        query_vector: &[f32],
        query_text: Option<&str>,
        limit: usize,
        threshold: f32,
        options: crate::skill::ToolSearchOptions,
        where_filter: Option<&str>,
    ) -> Result<Vec<u8>, VectorStoreError> {
        let results = self
            .search_tools_with_options(
                table_name,
                query_vector,
                query_text,
                limit,
                threshold,
                options,
                where_filter,
            )
            .await?;
        tool_search_results_to_ipc(&results).map_err(VectorStoreError::General)
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

        let dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let mut scanner = dataset.scan();
        scanner.project(&[
            ID_COLUMN,
            CONTENT_COLUMN,
            crate::SKILL_NAME_COLUMN,
            crate::CATEGORY_COLUMN,
            crate::TOOL_NAME_COLUMN,
            crate::FILE_PATH_COLUMN,
            crate::ROUTING_KEYWORDS_COLUMN,
            crate::INTENTS_COLUMN,
        ])?;
        scanner.full_text_search(FullTextSearchQuery::new(query.to_string()))?;
        if let Some(filter) = where_filter.map(str::trim).filter(|f| !f.is_empty()) {
            scanner.filter(filter)?;
        }
        scanner.limit(Some(i64::try_from(limit).unwrap_or(i64::MAX)), None)?;

        let mut stream = scanner.try_into_stream().await?;
        let mut results = Vec::with_capacity(limit.min(1024));

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
            let skill_name_col = batch.column_by_name(crate::SKILL_NAME_COLUMN);
            let category_col = batch.column_by_name(crate::CATEGORY_COLUMN);
            let tool_name_col = batch.column_by_name(crate::TOOL_NAME_COLUMN);
            let file_path_col = batch.column_by_name(crate::FILE_PATH_COLUMN);
            let routing_keywords_col = batch.column_by_name(crate::ROUTING_KEYWORDS_COLUMN);
            let intents_col = batch.column_by_name(crate::INTENTS_COLUMN);

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

            // Use get_utf8_at so Utf8 and Dictionary<Int32,Utf8> columns (e.g. TOOL_NAME) both work.
            let opt_utf8 = |col: Option<&Arc<dyn Array>>, i: usize| -> Option<String> {
                let s = col
                    .map(|c| crate::ops::get_utf8_at(c.as_ref(), i))
                    .unwrap_or_default();
                if s.is_empty() { None } else { Some(s) }
            };

            for i in 0..batch.num_rows() {
                let meta: FtsMetadataRow = if let Some(meta_col) = metadata_col {
                    if let Some(meta_arr) = meta_col.as_any().downcast_ref::<StringArray>() {
                        if meta_arr.is_null(i) {
                            FtsMetadataRow::default()
                        } else {
                            serde_json::from_str(meta_arr.value(i)).unwrap_or_default()
                        }
                    } else {
                        FtsMetadataRow::default()
                    }
                } else {
                    FtsMetadataRow::default()
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

                let id_str = ids.value(i).to_string();
                let tool_name = opt_utf8(tool_name_col, i)
                    .filter(|s| !s.is_empty())
                    .or_else(|| meta.tool_name.filter(|s| !s.is_empty()))
                    .unwrap_or_else(|| id_str.clone());
                let skill_name_raw = skill_name_col
                    .map(|c| crate::ops::get_utf8_at(c.as_ref(), i))
                    .unwrap_or_default();
                let skill_name = if !skill_name_raw.is_empty() {
                    skill_name_raw
                } else {
                    meta.skill_name
                        .clone()
                        .filter(|s| !s.is_empty())
                        .unwrap_or_else(|| tool_name.split('.').next().unwrap_or("").to_string())
                };
                let category_raw = category_col
                    .map(|c| crate::ops::get_utf8_at(c.as_ref(), i))
                    .unwrap_or_default();
                let category = if !category_raw.is_empty() {
                    category_raw
                } else {
                    meta.category
                        .clone()
                        .filter(|s| !s.is_empty())
                        .unwrap_or_else(|| skill_name.clone())
                };
                let keywords = opt_utf8(routing_keywords_col, i)
                    .map(|s| normalize_string_vec(s.split_whitespace().map(String::from).collect()))
                    .unwrap_or_else(|| normalize_string_vec(meta.routing_keywords));
                let intents = opt_utf8(intents_col, i)
                    .map(|s| normalize_string_vec(s.split(" | ").map(String::from).collect()))
                    .unwrap_or_else(|| normalize_string_vec(meta.intents));
                let file_path = opt_utf8(file_path_col, i)
                    .unwrap_or_else(|| meta.file_path.unwrap_or_default());
                let input_schema = meta
                    .input_schema
                    .as_ref()
                    .map(skill::normalize_input_schema_value)
                    .unwrap_or_else(|| serde_json::json!({}));

                results.push(skill::ToolSearchResult {
                    name: id_str,
                    description: contents.value(i).to_string(),
                    input_schema,
                    score,
                    vector_score: Some(score),
                    keyword_score: None,
                    skill_name,
                    tool_name,
                    file_path,
                    routing_keywords: keywords,
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
    /// Vector and keyword queries run in parallel via `try_join!` to reduce latency;
    /// vector failure fails fast, keyword failure falls back to empty.
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

        let vector_fut = self.search_optimized(
            table_name,
            query_vector,
            limit * 2,
            SearchOptions::default(),
        );
        let kw_fut = async {
            match self.keyword_search(table_name, query, limit * 2).await {
                Ok(v) => Ok(v),
                Err(e) => {
                    log::debug!("Keyword search failed, falling back to vector-only: {}", e);
                    Ok(Vec::new())
                }
            }
        };
        let (vector_results, kw_results) = tokio::try_join!(vector_fut, kw_fut)?;

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

            // 1. Boost from routing_keywords (Arrow-native or metadata fallback)
            let keywords_to_check: Vec<String> = if !result.routing_keywords.is_empty() {
                result
                    .routing_keywords
                    .split_whitespace()
                    .map(|s| s.to_lowercase())
                    .collect()
            } else if let Some(keywords_arr) = result
                .metadata
                .get("routing_keywords")
                .and_then(|v| v.as_array())
            {
                keywords_arr
                    .iter()
                    .filter_map(|k| k.as_str().map(|s| s.to_lowercase()))
                    .collect()
            } else {
                vec![]
            };
            for kw in &query_keywords {
                if keywords_to_check.iter().any(|k| k.contains(kw)) {
                    keyword_score += KEYWORD_BOOST;
                }
            }

            // 2. Boost from intents (Arrow-native or metadata fallback)
            let intents_to_check: Vec<String> = if !result.intents.is_empty() {
                result
                    .intents
                    .split(" | ")
                    .map(|s| s.trim().to_lowercase())
                    .collect()
            } else if let Some(intents_arr) =
                result.metadata.get("intents").and_then(|v| v.as_array())
            {
                intents_arr
                    .iter()
                    .filter_map(|k| k.as_str().map(|s| s.to_lowercase()))
                    .collect()
            } else {
                vec![]
            };
            for kw in &query_keywords {
                if intents_to_check.iter().any(|k| k.contains(kw)) {
                    keyword_score += KEYWORD_BOOST * 1.2; // Intents are higher signal
                }
            }

            let tool_name_lower = if result.tool_name.is_empty() {
                result.id.to_lowercase()
            } else {
                result.tool_name.to_lowercase()
            };
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

#[cfg(test)]
mod tests {
    use super::{search_results_to_ipc, tool_search_results_to_ipc};
    use crate::skill::ToolSearchResult;
    use omni_types::VectorSearchResult;

    #[test]
    fn test_search_results_to_ipc_empty() {
        let bytes = search_results_to_ipc(&[], None).unwrap();
        assert!(!bytes.is_empty(), "IPC stream should contain schema");
    }

    #[test]
    fn test_search_results_to_ipc_one_row() {
        let r = VectorSearchResult {
            id: "tool.a".to_string(),
            content: "Does something".to_string(),
            tool_name: "tool.a".to_string(),
            file_path: "/path/to/file".to_string(),
            routing_keywords: "kw1 kw2".to_string(),
            intents: "intent1 | intent2".to_string(),
            metadata: serde_json::json!({"x": 1}),
            distance: 0.5,
        };
        let bytes = search_results_to_ipc(&[r], None).unwrap();
        assert!(!bytes.is_empty());
    }

    #[test]
    fn test_search_results_to_ipc_projection() {
        let r = VectorSearchResult {
            id: "a".to_string(),
            content: "text".to_string(),
            tool_name: "t".to_string(),
            file_path: "p".to_string(),
            routing_keywords: String::new(),
            intents: String::new(),
            metadata: serde_json::json!({}),
            distance: 0.1,
        };
        let proj = vec![
            "id".to_string(),
            "content".to_string(),
            "_distance".to_string(),
        ];
        let bytes = search_results_to_ipc(&[r.clone()], Some(proj.as_slice())).unwrap();
        assert!(!bytes.is_empty());
        let full = search_results_to_ipc(&[r], None).unwrap();
        assert!(bytes.len() < full.len(), "projected IPC should be smaller");
    }

    #[test]
    fn test_search_results_to_ipc_invalid_projection() {
        let r = VectorSearchResult {
            id: "a".to_string(),
            content: "b".to_string(),
            tool_name: "t".to_string(),
            file_path: "p".to_string(),
            routing_keywords: String::new(),
            intents: String::new(),
            metadata: serde_json::json!({}),
            distance: 0.0,
        };
        let bad = vec!["id".to_string(), "no_such_column".to_string()];
        let err = search_results_to_ipc(&[r], Some(bad.as_slice())).unwrap_err();
        assert!(err.contains("invalid ipc_projection"));
    }

    #[test]
    fn test_tool_search_results_to_ipc_empty() {
        let bytes = tool_search_results_to_ipc(&[]).unwrap();
        assert!(!bytes.is_empty());
    }

    #[test]
    fn test_tool_search_results_to_ipc_one_row() {
        let r = ToolSearchResult {
            name: "git.commit".to_string(),
            description: "Commit changes".to_string(),
            input_schema: serde_json::json!({"type": "object"}),
            score: 0.85,
            vector_score: Some(0.8),
            keyword_score: Some(0.5),
            skill_name: "git".to_string(),
            tool_name: "commit".to_string(),
            file_path: "git/scripts/commit.py".to_string(),
            routing_keywords: vec!["git".to_string(), "commit".to_string()],
            intents: vec!["Save changes".to_string()],
            category: "vcs".to_string(),
        };
        let bytes = tool_search_results_to_ipc(&[r]).unwrap();
        assert!(!bytes.is_empty());
    }
}
