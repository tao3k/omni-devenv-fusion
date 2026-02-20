use super::*;

impl CheckpointStore {
    /// Get timeline records for time-travel visualization.
    ///
    /// Returns structured timeline events with previews, suitable for UI display.
    pub async fn get_timeline_records(
        &mut self,
        table_name: &str,
        thread_id: &str,
        limit: usize,
    ) -> Result<Vec<crate::checkpoint::TimelineRecord>, VectorStoreError> {
        if limit == 0 {
            return Ok(Vec::new());
        }

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(Vec::new());
        }

        let dataset = self.open_or_recover(table_name, false).await?;

        let mut scanner = dataset.scan();
        scanner.project(&[
            ID_COLUMN,
            CONTENT_COLUMN,
            METADATA_COLUMN,
            CHECKPOINT_TIMESTAMP_COLUMN,
            CHECKPOINT_PARENT_ID_COLUMN,
            CHECKPOINT_STEP_COLUMN,
        ])?;
        let filter_expr = format!("{} = '{}'", THREAD_ID_COLUMN, thread_id.replace('\'', "''"));
        scanner.filter(&filter_expr)?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let mut checkpoints: Vec<(f64, Option<i32>, crate::checkpoint::TimelineRecord)> =
            Vec::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let id_col_opt = batch.column_by_name(ID_COLUMN);
            let content_col_opt = batch.column_by_name(CONTENT_COLUMN);
            let metadata_col_opt = batch.column_by_name(METADATA_COLUMN);
            let ts_col_opt = batch.column_by_name(CHECKPOINT_TIMESTAMP_COLUMN);
            let parent_col_opt = batch.column_by_name(CHECKPOINT_PARENT_ID_COLUMN);
            let step_col_opt = batch.column_by_name(CHECKPOINT_STEP_COLUMN);

            if let (
                Some(id_col),
                Some(content_col),
                Some(metadata_col),
                Some(ts_col),
                Some(parent_col),
                Some(step_col),
            ) = (
                id_col_opt,
                content_col_opt,
                metadata_col_opt,
                ts_col_opt,
                parent_col_opt,
                step_col_opt,
            ) {
                let id_strs = id_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let content_strs = content_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let metadata_strs = metadata_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let ts_vals = ts_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::Float64Array>();
                let parent_vals = parent_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let step_vals = step_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::Int32Array>();

                if let (
                    Some(id_strs),
                    Some(content_strs),
                    Some(metadata_strs),
                    Some(ts_vals),
                    Some(parent_vals),
                    Some(step_vals),
                ) = (
                    id_strs,
                    content_strs,
                    metadata_strs,
                    ts_vals,
                    parent_vals,
                    step_vals,
                ) {
                    for i in 0..batch.num_rows() {
                        if id_strs.is_null(i) || content_strs.is_null(i) || ts_vals.is_null(i) {
                            continue;
                        }

                        let id = id_strs.value(i).to_string();
                        let content = content_strs.value(i);
                        let timestamp = ts_vals.value(i);
                        let parent_checkpoint_id = if parent_vals.is_null(i) {
                            None
                        } else {
                            Some(parent_vals.value(i).to_string())
                        };
                        let explicit_step = if step_vals.is_null(i) {
                            None
                        } else {
                            Some(step_vals.value(i))
                        };

                        let reason = if metadata_strs.is_null(i) {
                            None
                        } else {
                            serde_json::from_str::<serde_json::Value>(metadata_strs.value(i))
                                .ok()
                                .and_then(|meta| {
                                    meta.get("reason")
                                        .and_then(serde_json::Value::as_str)
                                        .map(ToString::to_string)
                                })
                        };

                        let preview = if content.chars().count() > PREVIEW_MAX_LEN {
                            let truncated: String = content.chars().take(PREVIEW_MAX_LEN).collect();
                            format!("{truncated}...")
                        } else {
                            content.to_string()
                        };

                        let record = crate::checkpoint::TimelineRecord {
                            checkpoint_id: id,
                            thread_id: thread_id.to_string(),
                            step: explicit_step.unwrap_or(0),
                            timestamp,
                            preview,
                            parent_checkpoint_id,
                            reason,
                        };
                        checkpoints.push((timestamp, explicit_step, record));
                    }
                }
            }
        }

        checkpoints.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        checkpoints.truncate(limit);

        let timeline = checkpoints
            .into_iter()
            .enumerate()
            .map(|(index, (_, explicit_step, mut record))| {
                if explicit_step.is_none() {
                    record.step = i32::try_from(index).unwrap_or(i32::MAX);
                }
                record
            })
            .collect();
        Ok(timeline)
    }
}
