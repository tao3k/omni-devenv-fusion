use futures::TryStreamExt;
use lance::index::vector::VectorIndexParams;
use lance_index::IndexType;
use lance_index::scalar::inverted::tokenizer::InvertedIndexParams;
use lance_index::scalar::{BuiltinIndexType, ScalarIndexParams};
use lance_index::traits::DatasetIndexExt;
use lance_linalg::distance::DistanceType;

/// Open a dataset by URI for background tasks (Send-safe; no store state).
async fn open_uri_for_background(
    uri: &str,
    index_cache_size_bytes: Option<usize>,
) -> Result<Dataset, crate::error::VectorStoreError> {
    match index_cache_size_bytes {
        None => Dataset::open(uri).await.map_err(Into::into),
        Some(n) => lance::dataset::builder::DatasetBuilder::from_uri(uri)
            .with_index_cache_size_bytes(n)
            .load()
            .await
            .map_err(Into::into),
    }
}

/// True if the error indicates the dataset path exists but is not a valid Lance dataset
/// (e.g. after drop_table removed _versions/data).
fn is_dataset_not_found_or_invalid(e: &crate::error::VectorStoreError) -> bool {
    match e {
        crate::error::VectorStoreError::LanceDB(inner) => {
            let s = inner.to_string();
            s.contains("DatasetNotFound") || s.contains("NotFound") || s.contains("_versions")
        }
        _ => false,
    }
}

/// Scalar index type for exact / categorical / full-text filtering.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ScalarIndexType {
    /// BTree: exact match, range queries (e.g. skill_name = 'git').
    BTree,
    /// Bitmap: low-cardinality enums (e.g. category = 'git').
    Bitmap,
    /// Inverted: FTS / array contains (e.g. tags, content).
    Inverted,
}

fn index_type_name(t: ScalarIndexType) -> &'static str {
    match t {
        ScalarIndexType::BTree => "btree",
        ScalarIndexType::Bitmap => "bitmap",
        ScalarIndexType::Inverted => "inverted",
    }
}

impl VectorStore {
    /// Delete records by IDs.
    pub async fn delete(&self, table_name: &str, ids: Vec<String>) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);
        // If table doesn't exist, nothing to delete
        if !table_path.exists() {
            return Ok(());
        }
        let mut dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
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
        // If table doesn't exist, nothing to delete
        if !table_path.exists() {
            return Ok(());
        }
        if file_paths.is_empty() {
            return Ok(());
        }
        let mut dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let file_paths_set: std::collections::HashSet<String> =
            file_paths.iter().cloned().collect();
        let schema = dataset.schema();
        let has_metadata = schema.field(METADATA_COLUMN).is_some();
        let project_cols: Vec<&str> = if has_metadata {
            vec![ID_COLUMN, crate::FILE_PATH_COLUMN, METADATA_COLUMN]
        } else {
            vec![ID_COLUMN, crate::FILE_PATH_COLUMN]
        };
        let mut scanner = dataset.scan();
        scanner.project(&project_cols)?;
        let mut stream = scanner.try_into_stream().await?;
        let mut ids_to_delete = Vec::new();
        while let Some(batch) = stream.try_next().await? {
            use lance::deps::arrow_array::{Array, StringArray};
            let id_col = batch.column_by_name(ID_COLUMN);
            let file_path_col = batch.column_by_name(crate::FILE_PATH_COLUMN);
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let id_arr = id_col.and_then(|c| c.as_any().downcast_ref::<StringArray>());
            let file_path_arr =
                file_path_col.and_then(|c| c.as_any().downcast_ref::<StringArray>());
            let meta_arr = metadata_col.and_then(|c| c.as_any().downcast_ref::<StringArray>());
            if let Some(ids) = id_arr {
                for i in 0..batch.num_rows() {
                    let id = ids.value(i).to_string();
                    let path_from_col = file_path_arr
                        .filter(|arr| !arr.is_null(i))
                        .map(|arr| arr.value(i).to_string())
                        .filter(|s| !s.is_empty());
                    let path = path_from_col.or_else(|| {
                        meta_arr.and_then(|ma| {
                            if ma.is_null(i) {
                                None
                            } else {
                                serde_json::from_str::<serde_json::Value>(ma.value(i))
                                    .ok()
                                    .and_then(|m| {
                                        m.get("file_path")
                                            .and_then(|v| v.as_str())
                                            .map(String::from)
                                    })
                            }
                        })
                    });
                    if let Some(path) = path {
                        if file_paths_set.contains(&path) {
                            ids_to_delete.push(id);
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

    /// Clear the keyword index (useful when re-indexing tools).
    /// This removes the old index directory and recreates a fresh empty index.
    pub fn clear_keyword_index(&mut self) -> Result<(), VectorStoreError> {
        // Remove the old keyword index directory if it exists
        let keyword_path = self.base_path.join("keyword_index");
        if keyword_path.exists() {
            std::fs::remove_dir_all(&keyword_path).map_err(|e| {
                VectorStoreError::General(format!("Failed to clear keyword index: {}", e))
            })?;
        }
        // Clear our reference so enable_keyword_index will recreate
        self.keyword_index = None;
        // Recreate the keyword index
        self.enable_keyword_index()?;
        Ok(())
    }

    /// Check if keyword index contains a given tool name (for testing).
    /// Returns true if the tool exists in the keyword index.
    pub fn keyword_index_contains(&self, tool_name: &str) -> bool {
        if self.keyword_backend != KeywordSearchBackend::Tantivy {
            return false;
        }
        if let Some(ref kw_index) = self.keyword_index {
            let results = kw_index.search(tool_name, 10);
            if let Ok(hits) = results {
                return !hits.is_empty();
            }
        }
        false
    }

    /// Check if keyword index is empty (for testing).
    /// Returns true if keyword index is empty or not available.
    pub fn keyword_index_is_empty(&self) -> bool {
        if self.keyword_backend != KeywordSearchBackend::Tantivy {
            return true;
        }
        if let Some(ref kw_index) = self.keyword_index {
            // Search for a unique character that won't match anything
            let results = kw_index.search("___UNIQUE_NONEXISTENT___", 10);
            if let Ok(hits) = results {
                return hits.is_empty();
            }
        }
        true // If no keyword index, consider it empty
    }

    /// Drop a table and remove its data from disk.
    /// Also clears the keyword index when dropping skills/router tables.
    ///
    /// When `table_path` equals `base_path` (i.e. base_path ends with `.lance`),
    /// we selectively remove only LanceDB artifacts (`_versions`, `data`, `_indices`,
    /// `_transactions`, `_deletions`) so that the `keyword_index/` subdirectory
    /// is preserved.  This prevents the Tantivy keyword index from being destroyed
    /// every time the skills table is rebuilt.
    pub async fn drop_table(&mut self, table_name: &str) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);
        let is_memory_mode = self.base_path.as_os_str() == ":memory:";
        let drop_path = if is_memory_mode {
            let id = self
                .memory_mode_id
                .expect("memory_mode_id set when base_path is :memory:");
            std::env::temp_dir()
                .join("omni_lance")
                .join(format!("{:016x}", id))
                .join(table_name)
        } else {
            table_path.clone()
        };
        {
            let mut cache = self.datasets.lock().await;
            cache.remove(table_name);
        }
        if drop_path.exists() {
            // When table_path == base_path (base_path ends with .lance),
            // selectively remove only LanceDB directories to preserve keyword_index.
            if drop_path == self.base_path {
                Self::remove_lance_artifacts(&drop_path)?;
            } else {
                std::fs::remove_dir_all(&drop_path)?;
            }
        }
        // Clear the keyword index when dropping skills/router tables
        // This ensures stale data doesn't persist across reindex operations
        if table_name == "skills" || table_name == "router" {
            // Delete the keyword index directory to clear stale data
            let keyword_index_path = self.base_path.join("keyword_index");
            if keyword_index_path.exists() {
                std::fs::remove_dir_all(&keyword_index_path)?;
            }
            // Clear our reference so enable_keyword_index will recreate on next use
            self.keyword_index = None;
        }
        Ok(())
    }

    /// Remove only LanceDB-specific artifacts from a directory, preserving other
    /// subdirectories such as `keyword_index/`.
    fn remove_lance_artifacts(dir: &std::path::Path) -> Result<(), VectorStoreError> {
        static LANCE_DIRS: &[&str] = &[
            "_versions",
            "data",
            "_indices",
            "_transactions",
            "_deletions",
        ];
        for entry in std::fs::read_dir(dir)? {
            let entry = entry?;
            let name = entry.file_name();
            let name_str = name.to_string_lossy();
            // Remove known LanceDB directories
            if LANCE_DIRS.contains(&name_str.as_ref()) {
                std::fs::remove_dir_all(entry.path())?;
            }
            // Remove .lance subdirectories (nested table dirs)
            else if name_str.ends_with(".lance") {
                std::fs::remove_dir_all(entry.path())?;
            }
            // Remove loose files (e.g. *.manifest)
            else if entry.file_type()?.is_file() {
                std::fs::remove_file(entry.path())?;
            }
            // Preserve keyword_index/ and other non-lance directories
        }
        Ok(())
    }

    /// Get the number of rows in a table.
    /// Returns 0 if the table path does not exist or the dataset was dropped (e.g. after
    /// `drop_table` when base_path ends with `.lance`, the directory may remain but Lance
    /// artifacts like `_versions` are removed).
    pub async fn count(&self, table_name: &str) -> Result<u32, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(0);
        }
        let dataset = match self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await
        {
            Ok(d) => d,
            Err(e) if is_dataset_not_found_or_invalid(&e) => return Ok(0),
            Err(e) => return Err(e),
        };
        Ok(u32::try_from(dataset.count_rows(None).await?).unwrap_or(0))
    }

    /// Get the latest table version id.
    pub async fn get_dataset_version(&self, table_name: &str) -> Result<u64, VectorStoreError> {
        let dataset = self.open_table_or_err(table_name).await?;
        dataset.latest_version_id().await.map_err(Into::into)
    }

    /// Open a historical snapshot by version (time travel).
    pub async fn checkout_version(
        &self,
        table_name: &str,
        version: u64,
    ) -> Result<Dataset, VectorStoreError> {
        let dataset = self.open_table_or_err(table_name).await?;
        dataset.checkout_version(version).await.map_err(Into::into)
    }

    /// List all historical versions of a table.
    pub async fn list_versions(
        &self,
        table_name: &str,
    ) -> Result<Vec<TableVersionInfo>, VectorStoreError> {
        let dataset = self.open_table_or_err(table_name).await?;
        let versions = dataset.versions().await?;

        Ok(versions
            .into_iter()
            .map(|version| TableVersionInfo {
                version_id: version.version,
                timestamp: version.timestamp.to_rfc3339(),
                metadata: version.metadata,
            })
            .collect())
    }

    /// Get basic table observability info for dashboard/admin usage.
    pub async fn get_table_info(&self, table_name: &str) -> Result<TableInfo, VectorStoreError> {
        let dataset = self.open_table_or_err(table_name).await?;
        let version = dataset.version();
        let num_rows = dataset.count_rows(None).await?;

        Ok(TableInfo {
            version_id: version.version,
            commit_timestamp: version.timestamp.to_rfc3339(),
            num_rows: num_rows as u64,
            schema: format!("{:?}", dataset.schema()),
            fragment_count: dataset.count_fragments(),
        })
    }

    /// Get fragment-level row/file stats to support query tuning and diagnostics.
    pub async fn get_fragment_stats(
        &self,
        table_name: &str,
    ) -> Result<Vec<FragmentInfo>, VectorStoreError> {
        let dataset = self.open_table_or_err(table_name).await?;
        let mut stats = Vec::new();

        for fragment in dataset.get_fragments() {
            let num_rows = fragment.count_rows(None).await?;
            let metadata = fragment.metadata();
            stats.push(FragmentInfo {
                id: fragment.id(),
                num_rows,
                physical_rows: metadata.physical_rows,
                num_data_files: metadata.files.len(),
            });
        }

        Ok(stats)
    }

    /// Add new columns to a table as schema evolution.
    pub async fn add_columns(
        &self,
        table_name: &str,
        columns: Vec<TableNewColumn>,
    ) -> Result<(), VectorStoreError> {
        use lance::dataset::NewColumnTransform;
        use lance::deps::arrow_schema::{DataType, Field, Schema};

        if columns.is_empty() {
            return Ok(());
        }

        let mut dataset = self.open_table_or_err(table_name).await?;
        let fields = columns
            .into_iter()
            .map(|column| {
                self.ensure_non_reserved_column(&column.name)?;
                let data_type = match column.data_type {
                    TableColumnType::Utf8 => DataType::Utf8,
                    TableColumnType::Int64 => DataType::Int64,
                    TableColumnType::Float64 => DataType::Float64,
                    TableColumnType::Boolean => DataType::Boolean,
                };
                Ok(Field::new(&column.name, data_type, column.nullable))
            })
            .collect::<Result<Vec<_>, VectorStoreError>>()?;

        let schema = Arc::new(Schema::new(fields));
        dataset
            .add_columns(NewColumnTransform::AllNulls(schema), None, None)
            .await?;
        {
            let mut cache = self.datasets.lock().await;
            cache.insert(table_name.to_string(), dataset.clone());
        }
        Ok(())
    }

    /// Apply schema alterations such as rename and nullability changes.
    pub async fn alter_columns(
        &self,
        table_name: &str,
        alterations: Vec<TableColumnAlteration>,
    ) -> Result<(), VectorStoreError> {
        use lance::dataset::ColumnAlteration as LanceColumnAlteration;

        if alterations.is_empty() {
            return Ok(());
        }

        let mut dataset = self.open_table_or_err(table_name).await?;
        let mut lance_alterations = Vec::with_capacity(alterations.len());

        for alteration in alterations {
            match alteration {
                TableColumnAlteration::Rename { path, new_name } => {
                    self.ensure_non_reserved_column(&path)?;
                    lance_alterations.push(LanceColumnAlteration::new(path).rename(new_name));
                }
                TableColumnAlteration::SetNullable { path, nullable } => {
                    self.ensure_non_reserved_column(&path)?;
                    lance_alterations.push(LanceColumnAlteration::new(path).set_nullable(nullable));
                }
            }
        }

        dataset.alter_columns(&lance_alterations).await?;
        {
            let mut cache = self.datasets.lock().await;
            cache.insert(table_name.to_string(), dataset.clone());
        }
        Ok(())
    }

    /// Drop non-reserved columns from a table.
    pub async fn drop_columns(
        &self,
        table_name: &str,
        columns: Vec<String>,
    ) -> Result<(), VectorStoreError> {
        if columns.is_empty() {
            return Ok(());
        }
        for column in &columns {
            self.ensure_non_reserved_column(column)?;
        }

        let mut dataset = self.open_table_or_err(table_name).await?;
        let refs: Vec<&str> = columns.iter().map(String::as_str).collect();
        dataset.drop_columns(&refs).await?;
        {
            let mut cache = self.datasets.lock().await;
            cache.insert(table_name.to_string(), dataset.clone());
        }
        Ok(())
    }

    /// Retrieve all file paths and their hashes stored in the table.
    pub async fn get_all_file_hashes(&self, table_name: &str) -> Result<String, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok("{}".to_string());
        }
        let dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let schema = dataset.schema();
        let has_metadata = schema.field(METADATA_COLUMN).is_some();
        let project_cols: Vec<&str> = if has_metadata {
            vec![ID_COLUMN, crate::FILE_PATH_COLUMN, METADATA_COLUMN]
        } else {
            vec![ID_COLUMN, crate::FILE_PATH_COLUMN]
        };
        let mut scanner = dataset.scan();
        scanner.project(&project_cols)?;
        let mut stream = scanner.try_into_stream().await?;
        let mut hash_map = std::collections::HashMap::new();
        while let Some(batch) = stream.try_next().await? {
            use lance::deps::arrow_array::{Array, StringArray};
            let id_col = batch.column_by_name(ID_COLUMN);
            let file_path_col = batch.column_by_name(crate::FILE_PATH_COLUMN);
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let id_arr = id_col.and_then(|c| c.as_any().downcast_ref::<StringArray>());
            let file_path_arr =
                file_path_col.and_then(|c| c.as_any().downcast_ref::<StringArray>());
            let meta_arr = metadata_col.and_then(|c| c.as_any().downcast_ref::<StringArray>());
            if let Some(ids) = id_arr {
                for i in 0..batch.num_rows() {
                    let id = ids.value(i).to_string();
                    let path_from_col = file_path_arr
                        .filter(|arr| !arr.is_null(i))
                        .map(|arr| arr.value(i).to_string())
                        .filter(|s| !s.is_empty());
                    let meta = meta_arr.and_then(|ma| {
                        if ma.is_null(i) {
                            None
                        } else {
                            serde_json::from_str::<serde_json::Value>(ma.value(i)).ok()
                        }
                    });
                    let path = path_from_col.or_else(|| {
                        meta.as_ref().and_then(|m| {
                            m.get("file_path")
                                .and_then(|v| v.as_str())
                                .map(String::from)
                        })
                    });
                    let hash = meta.and_then(|m| {
                        m.get("file_hash")
                            .and_then(|v| v.as_str())
                            .map(String::from)
                    });
                    if let Some(path) = path {
                        hash_map.insert(
                            path,
                            serde_json::json!({ "hash": hash.unwrap_or_default(), "id": id }),
                        );
                    }
                }
            }
        }
        serde_json::to_string(&hash_map).map_err(|e| VectorStoreError::General(format!("{}", e)))
    }

    /// Create a vector index for a table to optimize search performance.
    pub async fn create_index(&self, table_name: &str) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);
        // If table doesn't exist yet, this is a no-op (table will be created when first adding data)
        if !table_path.exists() {
            return Ok(());
        }

        let mut dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
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

    /// Start building the vector index in a background task. Returns immediately; the index
    /// will be built asynchronously. Errors are logged; use `create_index` if you need to await.
    /// Uses only Lance Dataset in the task (Send-safe; no VectorStore/RefCell across threads).
    pub fn create_index_background(&self, table_name: &str) {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return;
        }
        let uri = table_path.to_string_lossy().into_owned();
        let index_cache_size_bytes = self.index_cache_size_bytes;
        tokio::spawn(async move {
            let mut dataset = match open_uri_for_background(&uri, index_cache_size_bytes).await {
                Ok(ds) => ds,
                Err(e) => {
                    log::warn!("create_index_background: open dataset failed: {}", e);
                    return;
                }
            };
            let num_rows = match dataset.count_rows(None).await {
                Ok(n) => n as usize,
                Err(e) => {
                    log::warn!("create_index_background: count_rows failed: {}", e);
                    return;
                }
            };
            if num_rows < 100 {
                return;
            }
            let num_partitions = (num_rows / 256).clamp(32, 512);
            let params = VectorIndexParams::ivf_flat(num_partitions, DistanceType::L2);
            if let Err(e) = dataset
                .create_index(
                    &[crate::VECTOR_COLUMN],
                    IndexType::Vector,
                    None,
                    &params,
                    true,
                )
                .await
            {
                log::warn!("create_index_background failed: {}", e);
            }
        });
    }

    /// Create a native Lance inverted index for full-text search on content.
    pub async fn create_fts_index(&self, table_name: &str) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(());
        }

        let mut dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let params = InvertedIndexParams::default();
        dataset
            .create_index(
                &[CONTENT_COLUMN],
                IndexType::Inverted,
                Some("content_fts".to_string()),
                &params,
                true,
            )
            .await
            .map_err(VectorStoreError::LanceDB)?;
        Ok(())
    }

    /// Create a scalar index on a column for fast exact/categorical filtering.
    /// Use BTree for equality/range (e.g. skill_name), Bitmap for low-cardinality (e.g. category),
    /// Inverted for FTS/array (e.g. tags). The table must already have the column.
    pub async fn create_scalar_index(
        &self,
        table_name: &str,
        column: &str,
        index_type: ScalarIndexType,
    ) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(());
        }
        let mut dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let index_name = format!("scalar_{}_{}", column, index_type_name(index_type));
        match index_type {
            ScalarIndexType::BTree => {
                let params = ScalarIndexParams::for_builtin(BuiltinIndexType::BTree);
                dataset
                    .create_index(&[column], IndexType::BTree, Some(index_name), &params, true)
                    .await
            }
            ScalarIndexType::Bitmap => {
                let params = ScalarIndexParams::for_builtin(BuiltinIndexType::Bitmap);
                dataset
                    .create_index(
                        &[column],
                        IndexType::Bitmap,
                        Some(index_name),
                        &params,
                        true,
                    )
                    .await
            }
            ScalarIndexType::Inverted => {
                let params = InvertedIndexParams::default();
                dataset
                    .create_index(
                        &[column],
                        IndexType::Inverted,
                        Some(index_name),
                        &params,
                        true,
                    )
                    .await
            }
        }
        .map_err(VectorStoreError::LanceDB)?;
        Ok(())
    }

    async fn open_table_or_err(&self, table_name: &str) -> Result<Dataset, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }
        let uri = table_path.to_string_lossy();
        self.open_dataset_at_uri(uri.as_ref()).await
    }

    fn ensure_non_reserved_column(&self, column: &str) -> Result<(), VectorStoreError> {
        if Self::is_reserved_column(column) {
            return Err(VectorStoreError::General(format!(
                "Column '{}' is reserved and cannot be altered or dropped",
                column
            )));
        }
        Ok(())
    }

    fn is_reserved_column(column: &str) -> bool {
        matches!(
            column,
            ID_COLUMN
                | VECTOR_COLUMN
                | CONTENT_COLUMN
                | METADATA_COLUMN
                | THREAD_ID_COLUMN
                | SKILL_NAME_COLUMN
                | CATEGORY_COLUMN
                | crate::TOOL_NAME_COLUMN
                | crate::FILE_PATH_COLUMN
                | crate::ROUTING_KEYWORDS_COLUMN
                | crate::INTENTS_COLUMN
        )
    }
}
