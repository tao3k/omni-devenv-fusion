use super::*;

impl CheckpointStore {
    /// Check if a dataset is corrupted (missing files, etc.).
    ///
    /// Detects common corruption patterns from interrupted operations:
    /// - Missing _versions directory (partial transaction)
    /// - Empty data directories
    /// - Corrupt manifest files
    fn is_dataset_corrupted(&self, table_name: &str) -> bool {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return false;
        }
        // Check for common corruption indicators:
        // 1. Missing _versions directory (primary indicator of interrupted transaction)
        let versions_path = table_path.join("_versions");
        if !versions_path.exists() {
            log::warn!("Dataset corrupted: missing _versions directory for {table_name}");
            return true;
        }
        // 2. Check if _versions is empty (interrupted transaction)
        if let Ok(entries) = std::fs::read_dir(&versions_path) {
            let count = entries.count();
            if count == 0 {
                log::warn!("Dataset corrupted: empty _versions directory for {table_name}");
                return true;
            }
        }
        // 3. Check for data files (lance files)
        let data_files: Vec<_> = table_path
            .read_dir()
            .ok()
            .map(|dir| dir.filter_map(Result::ok).collect::<Vec<_>>())
            .unwrap_or_default();
        let has_lance_files = data_files
            .iter()
            .any(|e| e.file_name().to_string_lossy().ends_with(".lance"));
        if !has_lance_files {
            // No data files, but _versions exists - might be valid empty dataset
            return false;
        }
        false
    }

    /// Force recovery of a corrupted dataset, discarding all data.
    ///
    /// Use this when auto-recovery is insufficient and you want to
    /// completely reset the checkpoint store.
    ///
    /// # Errors
    ///
    /// Returns an error if corrupted data cannot be removed or dataset recreation fails.
    pub async fn force_recover(&self, table_name: &str) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);

        // Remove from cache
        {
            let datasets = self.datasets.lock().await;
            datasets.remove(table_name);
        }

        // Remove entire dataset directory
        if table_path.exists() {
            log::warn!(
                "Force recovering {table_name}: removing {}",
                table_path.display()
            );
            std::fs::remove_dir_all(&table_path).map_err(|e| {
                VectorStoreError::General(format!(
                    "Failed to remove corrupted dataset {table_name}: {e}"
                ))
            })?;
        }

        // Recreate empty dataset
        let mut dataset = self.get_or_create_dataset(table_name, true).await?;
        self.run_startup_repairs_once(table_name, &mut dataset)
            .await?;
        self.refresh_dataset_cache(table_name, &dataset).await;

        log::info!("Force recovery complete for {table_name}");
        Ok(())
    }

    /// Remove corrupted dataset and recreate it.
    pub(super) async fn recover_corrupted_dataset(
        &self,
        table_name: &str,
    ) -> Result<Dataset, VectorStoreError> {
        let table_path = self.table_path(table_name);

        // Remove from cache
        {
            let datasets = self.datasets.lock().await;
            datasets.remove(table_name);
        }

        // Remove corrupted dataset directory
        if table_path.exists() {
            log::warn!("Removing corrupted dataset: {}", table_path.display());
            std::fs::remove_dir_all(&table_path).map_err(|e| {
                VectorStoreError::General(format!(
                    "Failed to remove corrupted dataset {table_name}: {e}"
                ))
            })?;
        }

        // Recreate the dataset
        log::info!("Recreating dataset: {table_name}");
        let schema = self.create_schema();
        let empty_batch = self.create_empty_batch(&schema)?;
        let batches: Vec<Result<_, ArrowError>> = vec![Ok(empty_batch)];
        let iter = RecordBatchIterator::new(batches, schema);
        let table_uri = table_path.to_string_lossy().into_owned();
        let dataset = Dataset::write(
            Box::new(iter),
            table_uri.as_str(),
            Some(WriteParams::default()),
        )
        .await
        .map_err(VectorStoreError::LanceDB)?;

        // Add to cache
        self.refresh_dataset_cache(table_name, &dataset).await;

        Ok(dataset)
    }

    /// Try to open a dataset, recovering from corruption if needed.
    pub(super) async fn open_or_recover(
        &self,
        table_name: &str,
        force_create: bool,
    ) -> Result<Dataset, VectorStoreError> {
        if !force_create {
            let cached = {
                let datasets = self.datasets.lock().await;
                datasets.get(table_name).map(|entry| entry.clone())
            };
            if let Some(mut cached) = cached {
                if let Err(error) = self.validate_dataset_schema(&cached) {
                    log::warn!(
                        "Checkpoint schema mismatch for '{table_name}' from cache: {error}. Auto-repairing table."
                    );
                    return self.recover_corrupted_dataset(table_name).await;
                }
                self.run_startup_repairs_once(table_name, &mut cached)
                    .await?;
                self.refresh_dataset_cache(table_name, &cached).await;
                return Ok(cached);
            }
        }

        // First check if we need to recover
        if !force_create && self.is_dataset_corrupted(table_name) {
            return self.recover_corrupted_dataset(table_name).await;
        }

        // Try normal open
        let table_path = self.table_path(table_name);
        if !force_create && table_path.exists() {
            match Dataset::open(table_path.to_string_lossy().as_ref()).await {
                Ok(mut dataset) => {
                    if let Err(error) = self.validate_dataset_schema(&dataset) {
                        log::warn!(
                            "Checkpoint schema mismatch for '{table_name}': {error}. Auto-repairing table."
                        );
                        return self.recover_corrupted_dataset(table_name).await;
                    }
                    self.run_startup_repairs_once(table_name, &mut dataset)
                        .await?;
                    self.refresh_dataset_cache(table_name, &dataset).await;
                    return Ok(dataset);
                }
                Err(e) => {
                    log::warn!("Failed to open dataset {table_name}: {e}. Attempting recovery...");
                    return self.recover_corrupted_dataset(table_name).await;
                }
            }
        }

        // Create new dataset
        let mut dataset = self.get_or_create_dataset(table_name, force_create).await?;
        self.run_startup_repairs_once(table_name, &mut dataset)
            .await?;
        self.refresh_dataset_cache(table_name, &dataset).await;
        Ok(dataset)
    }

    /// Get or create a dataset for checkpoint storage.
    #[allow(clippy::collapsible_if)]
    pub(super) async fn get_or_create_dataset(
        &self,
        table_name: &str,
        force_create: bool,
    ) -> Result<Dataset, VectorStoreError> {
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

        let dataset = if table_path.exists() && !force_create {
            let dataset = Dataset::open(table_uri.as_str()).await?;
            if let Err(error) = self.validate_dataset_schema(&dataset) {
                log::warn!(
                    "Checkpoint schema mismatch for '{table_name}' during open: {error}. Auto-repairing table."
                );
                return self.recover_corrupted_dataset(table_name).await;
            }
            dataset
        } else {
            let schema = self.create_schema();
            let empty_batch = self.create_empty_batch(&schema)?;
            let batches: Vec<Result<_, ArrowError>> = vec![Ok(empty_batch)];
            let iter = RecordBatchIterator::new(batches, schema);
            Dataset::write(
                Box::new(iter),
                table_uri.as_str(),
                Some(WriteParams::default()),
            )
            .await
            .map_err(VectorStoreError::LanceDB)?
        };

        {
            let datasets = self.datasets.lock().await;
            datasets.insert(table_name.to_string(), dataset.clone());
        }

        Ok(dataset)
    }

    /// Refresh in-process dataset cache to the latest dataset handle.
    pub(super) async fn refresh_dataset_cache(&self, table_name: &str, dataset: &Dataset) {
        let datasets = self.datasets.lock().await;
        datasets.insert(table_name.to_string(), dataset.clone());
    }

    /// Best-effort auto-compaction to prevent fragment explosion from single-row appends.
    pub(super) async fn maybe_auto_compact_dataset(
        &self,
        dataset: &mut Dataset,
        table_name: &str,
        force: bool,
    ) {
        let fragment_count = dataset.get_fragments().len();
        if fragment_count <= AUTO_COMPACT_FRAGMENT_THRESHOLD {
            return;
        }
        if !force && fragment_count % AUTO_COMPACT_CHECK_INTERVAL != 0 {
            return;
        }

        let options = CompactionOptions {
            target_rows_per_fragment: AUTO_COMPACT_TARGET_ROWS_PER_FRAGMENT,
            max_rows_per_group: AUTO_COMPACT_MAX_ROWS_PER_GROUP,
            ..Default::default()
        };

        match compact_files(dataset, options, None).await {
            Ok(metrics) => {
                let after = dataset.get_fragments().len();
                self.refresh_dataset_cache(table_name, dataset).await;
                log::info!(
                    "Auto-compacted checkpoint table '{table_name}': fragments {} -> {} (removed={})",
                    fragment_count,
                    after,
                    metrics.fragments_removed
                );
            }
            Err(error) => {
                log::warn!("Auto-compaction skipped for checkpoint table '{table_name}': {error}");
            }
        }
    }
}
