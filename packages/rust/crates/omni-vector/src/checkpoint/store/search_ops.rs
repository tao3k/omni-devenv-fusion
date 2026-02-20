use super::*;

impl CheckpointStore {
    /// Search for similar checkpoints using vector similarity.
    ///
    /// Performs ANN-like scan over checkpoint vectors and returns nearest rows.
    /// Optionally filters by thread ID and/or metadata key-value conditions.
    ///
    /// # Returns
    /// Vector of tuples: `(content_json, metadata_json, distance_score)`.
    pub async fn search(
        &mut self,
        table_name: &str,
        query_vector: &[f32],
        limit: usize,
        thread_id: Option<&str>,
        filter_metadata: Option<serde_json::Value>,
    ) -> Result<Vec<(String, String, f32)>, VectorStoreError> {
        if limit == 0 || query_vector.is_empty() {
            return Ok(Vec::new());
        }

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(Vec::new());
        }

        let dataset = self.open_or_recover(table_name, false).await?;

        let mut scanner = dataset.scan();
        scanner.project(&[
            THREAD_ID_COLUMN,
            VECTOR_COLUMN,
            CONTENT_COLUMN,
            METADATA_COLUMN,
        ])?;
        if let Some(tid) = thread_id {
            let filter_expr = format!("{} = '{}'", THREAD_ID_COLUMN, tid.replace('\'', "''"));
            scanner.filter(&filter_expr)?;
        }

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let mut results: Vec<(String, String, f32)> = Vec::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let vector_col_opt = batch.column_by_name(VECTOR_COLUMN);
            let content_col_opt = batch.column_by_name(CONTENT_COLUMN);
            let metadata_col_opt = batch.column_by_name(METADATA_COLUMN);

            if let (Some(vector_col), Some(content_col), Some(metadata_col)) =
                (vector_col_opt, content_col_opt, metadata_col_opt)
            {
                let vector_arr = vector_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::FixedSizeListArray>();
                let content_strs = content_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let metadata_strs = metadata_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();

                if let (Some(vector_arr), Some(content_strs), Some(metadata_strs)) =
                    (vector_arr, content_strs, metadata_strs)
                {
                    let Some(values_arr) = vector_arr
                        .values()
                        .as_any()
                        .downcast_ref::<lance::deps::arrow_array::Float32Array>(
                    ) else {
                        continue;
                    };

                    let row_dim = usize::try_from(vector_arr.value_length()).unwrap_or_default();
                    if row_dim == 0 {
                        continue;
                    }
                    let values_slice = values_arr.values();
                    let compute_len = row_dim.min(query_vector.len());

                    for i in 0..batch.num_rows() {
                        if vector_arr.is_null(i)
                            || content_strs.is_null(i)
                            || metadata_strs.is_null(i)
                        {
                            continue;
                        }

                        let start = i.saturating_mul(row_dim);
                        let end = start.saturating_add(row_dim);
                        if end > values_slice.len() || compute_len == 0 {
                            continue;
                        }
                        let row_vector = &values_slice[start..end];
                        let distance: f32 = query_vector[..compute_len]
                            .iter()
                            .zip(&row_vector[..compute_len])
                            .map(|(q, d)| {
                                let diff = q - d;
                                diff * diff
                            })
                            .sum::<f32>()
                            .sqrt();

                        let metadata_str = metadata_strs.value(i);
                        if let Some(meta_filter) = &filter_metadata {
                            let Ok(metadata_json) =
                                serde_json::from_str::<serde_json::Value>(metadata_str)
                            else {
                                continue;
                            };
                            let Some(filter_obj) = meta_filter.as_object() else {
                                continue;
                            };
                            let matches = filter_obj
                                .iter()
                                .all(|(key, expected)| metadata_json.get(key) == Some(expected));
                            if !matches {
                                continue;
                            }
                        }

                        results.push((
                            content_strs.value(i).to_string(),
                            metadata_str.to_string(),
                            distance,
                        ));
                    }
                }
            }
        }

        results.sort_by(|a, b| a.2.partial_cmp(&b.2).unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(limit);
        Ok(results)
    }
}
