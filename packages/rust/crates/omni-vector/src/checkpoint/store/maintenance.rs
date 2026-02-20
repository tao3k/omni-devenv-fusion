use super::*;

impl CheckpointStore {
    /// Run one-time startup repairs for a table in the current process.
    pub(super) async fn run_startup_repairs_once(
        &self,
        table_name: &str,
        dataset: &mut Dataset,
    ) -> Result<(), VectorStoreError> {
        let should_run = {
            let mut repaired = self.repaired_tables.lock().await;
            repaired.insert(table_name.to_string())
        };
        if !should_run {
            return Ok(());
        }

        let removed = self
            .cleanup_orphan_checkpoints_in_dataset(dataset, table_name, false)
            .await?;
        if removed > 0 {
            self.refresh_dataset_cache(table_name, dataset).await;
            log::info!(
                "Checkpoint auto-repair removed {removed} interrupted/orphan checkpoints in '{table_name}'"
            );
        }
        Ok(())
    }

    /// Check and clean up orphan checkpoints from interrupted graph tasks.
    ///
    /// Orphan checkpoints are checkpoints that exist but don't form a valid chain
    /// (e.g., due to interrupted task leaving partial state). This method:
    /// 1. Finds checkpoints without valid parent references
    /// 2. Finds checkpoints whose parent no longer exists
    /// 3. Optionally removes invalid chains
    ///
    /// Returns the number of orphan checkpoints found/removed.
    ///
    /// # Errors
    ///
    /// Returns an error if the checkpoint table cannot be opened, scanned, or mutated.
    pub async fn cleanup_orphan_checkpoints(
        &mut self,
        table_name: &str,
        dry_run: bool,
    ) -> Result<u32, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(0);
        }

        let mut dataset = self.open_or_recover(table_name, false).await?;
        let orphan_count = self
            .cleanup_orphan_checkpoints_in_dataset(&mut dataset, table_name, dry_run)
            .await?;
        if orphan_count > 0 && !dry_run {
            self.refresh_dataset_cache(table_name, &dataset).await;
        }
        Ok(orphan_count)
    }

    async fn cleanup_orphan_checkpoints_in_dataset(
        &self,
        dataset: &mut Dataset,
        table_name: &str,
        dry_run: bool,
    ) -> Result<u32, VectorStoreError> {
        let orphan_ids = self.collect_orphan_ids(dataset).await?;
        let orphan_count = u32::try_from(orphan_ids.len()).unwrap_or(u32::MAX);
        if orphan_count == 0 {
            return Ok(0);
        }

        log::info!("Found {orphan_count} orphan checkpoints in {table_name} (dry_run={dry_run})");
        if !dry_run {
            self.delete_checkpoints_by_id(dataset, &orphan_ids).await?;
        }
        Ok(orphan_count)
    }

    async fn collect_orphan_ids(
        &self,
        dataset: &mut Dataset,
    ) -> Result<Vec<String>, VectorStoreError> {
        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN, CHECKPOINT_PARENT_ID_COLUMN])?;
        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut records: Vec<(String, Option<String>)> = Vec::new();
        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let id_col = batch.column_by_name(ID_COLUMN);
            let parent_col = batch.column_by_name(CHECKPOINT_PARENT_ID_COLUMN);
            if let (Some(id_c), Some(parent_c)) = (id_col, parent_col) {
                let ids = id_c
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let parents = parent_c
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                if let (Some(ids), Some(parents)) = (ids, parents) {
                    for i in 0..batch.num_rows() {
                        if ids.is_null(i) {
                            continue;
                        }
                        let id = ids.value(i).to_string();
                        let parent = if parents.is_null(i) {
                            None
                        } else {
                            Some(parents.value(i).to_string())
                        };
                        records.push((id, parent));
                    }
                }
            }
        }

        let all_ids: std::collections::HashSet<String> =
            records.iter().map(|(id, _)| id.clone()).collect();
        let parent_refs: std::collections::HashSet<String> = records
            .iter()
            .filter_map(|(_, parent)| parent.clone())
            .collect();
        let mut orphan_ids: std::collections::HashSet<String> = std::collections::HashSet::new();

        for (id, parent) in records {
            let has_dangling_parent = parent.as_ref().is_some_and(|p| !all_ids.contains(p));
            let is_unreferenced_ephemeral = !parent_refs.contains(&id)
                && (self.looks_like_ephemeral_checkpoint_id(&id) || id.len() > 50);

            if has_dangling_parent || is_unreferenced_ephemeral {
                orphan_ids.insert(id);
            }
        }

        let mut out: Vec<String> = orphan_ids.into_iter().collect();
        out.sort();
        Ok(out)
    }

    async fn delete_checkpoints_by_id(
        &self,
        dataset: &mut Dataset,
        ids: &[String],
    ) -> Result<(), VectorStoreError> {
        const DELETE_BATCH_SIZE: usize = 256;
        for chunk in ids.chunks(DELETE_BATCH_SIZE) {
            let predicate = chunk
                .iter()
                .map(|id| format!("{} = '{}'", ID_COLUMN, id.replace('\'', "''")))
                .collect::<Vec<_>>()
                .join(" OR ");
            dataset.delete(&predicate).await?;
        }
        Ok(())
    }

    fn looks_like_ephemeral_checkpoint_id(&self, id: &str) -> bool {
        id.len() >= 36
            && id.chars().all(|c| c.is_ascii_hexdigit() || c == '-')
            && id.matches('-').count() == 4
    }
}
