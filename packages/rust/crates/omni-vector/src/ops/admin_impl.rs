use futures::TryStreamExt;
use lance::index::vector::VectorIndexParams;
use lance_index::IndexType;
use lance_index::traits::DatasetIndexExt;
use lance_linalg::distance::DistanceType;

impl VectorStore {
    /// Delete records by IDs.
    pub async fn delete(&self, table_name: &str, ids: Vec<String>) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }
        let mut dataset = Dataset::open(table_path.to_string_lossy().as_ref()).await?;
        for id in ids {
            dataset.delete(&format!("{ID_COLUMN} = '{id}'")).await?;
        }
        Ok(())
    }

    /// Delete records associated with specific file paths.
    pub async fn delete_by_file_path(
        &self,
        table_name: &str,
        file_paths: Vec<String>,
    ) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }
        if file_paths.is_empty() {
            return Ok(());
        }
        let mut dataset = Dataset::open(table_path.to_string_lossy().as_ref()).await?;
        let file_paths_set: std::collections::HashSet<String> =
            file_paths.iter().cloned().collect();
        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN, METADATA_COLUMN])?;
        let mut stream = scanner.try_into_stream().await?;
        let mut ids_to_delete = Vec::new();
        while let Some(batch) = stream.try_next().await? {
            use lance::deps::arrow_array::{Array, StringArray};
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let id_col = batch.column_by_name(ID_COLUMN);
            if let (Some(meta_col), Some(id_c)) = (metadata_col, id_col) {
                if let Some(metas) = meta_col.as_any().downcast_ref::<StringArray>() {
                    for i in 0..batch.num_rows() {
                        if metas.is_null(i) {
                            continue;
                        }
                        let id = id_c
                            .as_any()
                            .downcast_ref::<StringArray>()
                            .map(|arr| arr.value(i).to_string())
                            .unwrap_or_default();
                        if let Ok(meta) = serde_json::from_str::<serde_json::Value>(&metas.value(i))
                        {
                            if let Some(path) = meta.get("file_path").and_then(|v| v.as_str()) {
                                if file_paths_set.contains(path) {
                                    ids_to_delete.push(id);
                                }
                            }
                        }
                    }
                }
            }
        }
        if !ids_to_delete.is_empty() {
            dataset
                .delete(&format!("{ID_COLUMN} IN ('{}')", ids_to_delete.join("','")))
                .await?;
        }
        Ok(())
    }

    /// Drop a table and remove its data from disk.
    pub async fn drop_table(&self, table_name: &str) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);
        {
            let datasets = self.datasets.lock().await;
            datasets.remove(table_name);
        }
        if table_path.exists() {
            std::fs::remove_dir_all(&table_path)?;
        }
        Ok(())
    }

    /// Get the number of rows in a table.
    pub async fn count(&self, table_name: &str) -> Result<u32, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(0);
        }
        let dataset = Dataset::open(table_path.to_string_lossy().as_ref()).await?;
        Ok(u32::try_from(dataset.count_rows(None).await?).unwrap_or(0))
    }

    /// Retrieve all file paths and their hashes stored in the table.
    pub async fn get_all_file_hashes(&self, table_name: &str) -> Result<String, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok("{}".to_string());
        }
        let dataset = Dataset::open(table_path.to_string_lossy().as_ref()).await?;
        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN, METADATA_COLUMN])?;
        let mut stream = scanner.try_into_stream().await?;
        let mut hash_map = std::collections::HashMap::new();
        while let Some(batch) = stream.try_next().await? {
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let id_col = batch.column_by_name(ID_COLUMN);
            if let (Some(meta_col), Some(id_c)) = (metadata_col, id_col) {
                use lance::deps::arrow_array::{Array, StringArray};
                if let Some(metas) = meta_col.as_any().downcast_ref::<StringArray>() {
                    for i in 0..batch.num_rows() {
                        if metas.is_null(i) {
                            continue;
                        }
                        let metadata_str = metas.value(i);
                        let id = id_c
                            .as_any()
                            .downcast_ref::<StringArray>()
                            .map(|arr| arr.value(i).to_string())
                            .unwrap_or_default();
                        if let Ok(metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
                        {
                            if let (Some(path), Some(hash)) = (
                                metadata.get("file_path").and_then(|v| v.as_str()),
                                metadata.get("file_hash").and_then(|v| v.as_str()),
                            ) {
                                hash_map.insert(
                                    path.to_string(),
                                    serde_json::json!({ "hash": hash.to_string(), "id": id }),
                                );
                            }
                        }
                    }
                }
            }
        }
        serde_json::to_string(&hash_map).map_err(|e| VectorStoreError::General(format!("{}", e)))
    }

    /// Create a vector index for a table to optimize search performance.
    pub async fn create_index(&self, table_name: &str) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        let mut dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let num_rows = dataset
            .count_rows(None)
            .await
            .map_err(VectorStoreError::LanceDB)? as usize;

        // Skip indexing for very small datasets
        if num_rows < 100 {
            return Ok(());
        }

        let num_partitions = (num_rows / 256).clamp(32, 512);
        let params = VectorIndexParams::ivf_flat(num_partitions, DistanceType::L2);

        dataset
            .create_index(&[VECTOR_COLUMN], IndexType::Vector, None, &params, true)
            .await
            .map_err(VectorStoreError::LanceDB)?;
        Ok(())
    }
}
