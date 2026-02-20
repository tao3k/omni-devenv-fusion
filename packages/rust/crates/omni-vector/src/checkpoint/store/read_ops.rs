use super::*;

impl CheckpointStore {
    /// Get the latest checkpoint for a thread.
    ///
    /// # Errors
    ///
    /// Returns an error if dataset scan or row decoding fails.
    pub async fn get_latest(
        &mut self,
        table_name: &str,
        thread_id: &str,
    ) -> Result<Option<String>, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(None);
        }

        // Use open_or_recover to handle corruption
        let mut dataset = self.open_or_recover(table_name, false).await?;
        self.maybe_auto_compact_dataset(&mut dataset, table_name, true)
            .await;

        let mut scanner = dataset.scan();
        scanner.project(&[CONTENT_COLUMN, CHECKPOINT_TIMESTAMP_COLUMN])?;
        // PREDICATE PUSH-DOWN: Filter by thread_id column
        let filter_expr = format!("{} = '{}'", THREAD_ID_COLUMN, thread_id.replace('\'', "''"));
        scanner.filter(&filter_expr)?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut latest_content: Option<String> = None;
        let mut latest_timestamp = f64::NEG_INFINITY;

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let content_col_opt = batch.column_by_name(CONTENT_COLUMN);
            let timestamp_col_opt = batch.column_by_name(CHECKPOINT_TIMESTAMP_COLUMN);

            if let (Some(content_col), Some(timestamp_col)) = (content_col_opt, timestamp_col_opt) {
                let content_strs = content_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let timestamp_vals = timestamp_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::Float64Array>();

                if let (Some(content_strs), Some(timestamp_vals)) = (content_strs, timestamp_vals) {
                    for i in 0..batch.num_rows() {
                        if content_strs.is_null(i) || timestamp_vals.is_null(i) {
                            continue;
                        }

                        let timestamp = timestamp_vals.value(i);
                        if timestamp > latest_timestamp {
                            latest_timestamp = timestamp;
                            latest_content = Some(content_strs.value(i).to_string());
                        }
                    }
                }
            }
        }

        Ok(latest_content)
    }

    /// Get checkpoint history for a thread (newest first).
    ///
    /// # Errors
    ///
    /// Returns an error if dataset scan or row decoding fails.
    pub async fn get_history(
        &mut self,
        table_name: &str,
        thread_id: &str,
        limit: usize,
    ) -> Result<Vec<String>, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(Vec::new());
        }

        // Use open_or_recover to handle corruption
        let mut dataset = self.open_or_recover(table_name, false).await?;
        self.maybe_auto_compact_dataset(&mut dataset, table_name, true)
            .await;

        let mut scanner = dataset.scan();
        scanner.project(&[CONTENT_COLUMN, CHECKPOINT_TIMESTAMP_COLUMN])?;
        // PREDICATE PUSH-DOWN: Filter by thread_id column
        let filter_expr = format!("{} = '{}'", THREAD_ID_COLUMN, thread_id.replace('\'', "''"));
        scanner.filter(&filter_expr)?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut checkpoints: Vec<(f64, String)> = Vec::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let content_col_opt = batch.column_by_name(CONTENT_COLUMN);
            let timestamp_col_opt = batch.column_by_name(CHECKPOINT_TIMESTAMP_COLUMN);

            if let (Some(content_col), Some(timestamp_col)) = (content_col_opt, timestamp_col_opt) {
                let content_strs = content_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let timestamp_vals = timestamp_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::Float64Array>();

                if let (Some(content_strs), Some(timestamp_vals)) = (content_strs, timestamp_vals) {
                    for i in 0..batch.num_rows() {
                        if content_strs.is_null(i) || timestamp_vals.is_null(i) {
                            continue;
                        }

                        checkpoints
                            .push((timestamp_vals.value(i), content_strs.value(i).to_string()));
                    }
                }
            }
        }

        // Sort by timestamp descending and limit
        checkpoints.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        checkpoints.truncate(limit);

        Ok(checkpoints.into_iter().map(|(_, c)| c).collect())
    }

    /// Get checkpoint by ID.
    ///
    /// # Errors
    ///
    /// Returns an error if dataset scan fails.
    #[allow(clippy::collapsible_if)]
    pub async fn get_by_id(
        &mut self,
        table_name: &str,
        checkpoint_id: &str,
    ) -> Result<Option<String>, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(None);
        }

        // Use open_or_recover to handle corruption
        let mut dataset = self.open_or_recover(table_name, false).await?;
        self.maybe_auto_compact_dataset(&mut dataset, table_name, true)
            .await;

        let mut scanner = dataset.scan();
        let filter_str = format!("{} = '{}'", ID_COLUMN, checkpoint_id.replace('\'', "''"));
        scanner.filter(filter_str.as_str())?;
        scanner.project(&[CONTENT_COLUMN])?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        if let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            if let Some(col) = batch.column_by_name(CONTENT_COLUMN) {
                if let Some(arr) = col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>()
                {
                    if batch.num_rows() > 0 && !arr.is_null(0) {
                        return Ok(Some(arr.value(0).to_string()));
                    }
                }
            }
        }

        Ok(None)
    }

    /// Delete all checkpoints for a thread.
    ///
    /// # Errors
    ///
    /// Returns an error if dataset scan or deletion fails.
    pub async fn delete_thread(
        &mut self,
        table_name: &str,
        thread_id: &str,
    ) -> Result<u32, VectorStoreError> {
        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Ok(0);
        }

        let deleted_count = self.count(table_name, thread_id).await?;
        if deleted_count == 0 {
            return Ok(0);
        }

        // Use open_or_recover to handle corruption
        let mut dataset = self.open_or_recover(table_name, false).await?;

        // Single predicate delete is substantially faster than per-row deletes.
        let filter_expr = format!("{} = '{}'", THREAD_ID_COLUMN, thread_id.replace('\'', "''"));
        dataset.delete(&filter_expr).await?;
        self.refresh_dataset_cache(table_name, &dataset).await;

        Ok(deleted_count)
    }

    /// Count checkpoints for a thread.
    ///
    /// # Errors
    ///
    /// Returns an error if dataset scan fails.
    pub async fn count(
        &mut self,
        table_name: &str,
        thread_id: &str,
    ) -> Result<u32, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(0);
        }

        // Use open_or_recover to handle corruption
        let dataset = self.open_or_recover(table_name, false).await?;

        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN])?;
        // PREDICATE PUSH-DOWN: Filter by thread_id column
        let filter_expr = format!("{} = '{}'", THREAD_ID_COLUMN, thread_id.replace('\'', "''"));
        scanner.filter(&filter_expr)?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let mut count = 0u32;

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            // thread_id already filtered, just count rows
            let batch_rows = u32::try_from(batch.num_rows()).unwrap_or(u32::MAX);
            count = count.saturating_add(batch_rows);
        }

        Ok(count)
    }
}
