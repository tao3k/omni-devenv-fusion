use super::*;

impl CheckpointStore {
    /// Save a checkpoint.
    ///
    /// # Errors
    ///
    /// Returns an error if schema conversion, dataset open, or append fails.
    #[allow(clippy::collapsible_if)]
    pub async fn save_checkpoint(
        &self,
        table_name: &str,
        record: &CheckpointRecord,
    ) -> Result<(), VectorStoreError> {
        let schema = self.create_schema();

        // Build metadata JSON (user metadata only; core fields are dedicated columns).
        let mut metadata_map = serde_json::Map::new();
        if let Some(ref user_meta) = record.metadata {
            if let Ok(user_obj) = serde_json::from_str::<serde_json::Value>(user_meta) {
                if let Some(obj) = user_obj.as_object() {
                    for (k, v) in obj {
                        metadata_map.insert(k.clone(), v.clone());
                    }
                }
            }
        }
        let checkpoint_step = metadata_map
            .get("step")
            .and_then(serde_json::Value::as_i64)
            .and_then(|step| i32::try_from(step).ok());
        let metadata = serde_json::Value::Object(metadata_map).to_string();

        // Build vector array (use zeros if no embedding)
        let embedding = record
            .embedding
            .clone()
            .unwrap_or_else(|| vec![0.0; self.dimension]);
        let flat_values: Vec<f32> = embedding;
        let vector_array = lance::deps::arrow_array::FixedSizeListArray::try_new(
            Arc::new(lance::deps::arrow_schema::Field::new(
                "item",
                lance::deps::arrow_schema::DataType::Float32,
                true,
            )),
            i32::try_from(self.dimension).unwrap_or(1536),
            Arc::new(lance::deps::arrow_array::Float32Array::from(flat_values)),
            None,
        )
        .map_err(VectorStoreError::Arrow)?;

        // Build record batch with core fields as first-class columns.
        let batch = RecordBatch::try_new(
            schema.clone(),
            vec![
                Arc::new(lance::deps::arrow_array::StringArray::from(vec![
                    record.checkpoint_id.clone(),
                ])),
                Arc::new(lance::deps::arrow_array::StringArray::from(vec![
                    record.thread_id.clone(),
                ])),
                Arc::new(lance::deps::arrow_array::Float64Array::from(vec![
                    record.timestamp,
                ])),
                Arc::new(lance::deps::arrow_array::StringArray::from(vec![
                    record.parent_id.clone(),
                ])),
                Arc::new(lance::deps::arrow_array::Int32Array::from(vec![
                    checkpoint_step,
                ])),
                Arc::new(vector_array),
                Arc::new(lance::deps::arrow_array::StringArray::from(vec![
                    record.content.clone(),
                ])),
                Arc::new(lance::deps::arrow_array::StringArray::from(vec![metadata])),
            ],
        )
        .map_err(VectorStoreError::Arrow)?;

        // Append to dataset
        let mut dataset = self.open_or_recover(table_name, false).await?;
        let batches: Vec<Result<_, ArrowError>> = vec![Ok(batch)];
        let iter = RecordBatchIterator::new(batches, schema);
        dataset
            .append(Box::new(iter), None)
            .await
            .map_err(VectorStoreError::LanceDB)?;
        self.refresh_dataset_cache(table_name, &dataset).await;
        self.maybe_auto_compact_dataset(&mut dataset, table_name, false)
            .await;

        log::debug!(
            "Saved checkpoint '{}' for thread '{}'",
            record.checkpoint_id,
            record.thread_id
        );

        Ok(())
    }
}
