use super::*;

impl CheckpointStore {
    /// Create the schema for checkpoint storage.
    pub(super) fn create_schema(&self) -> Arc<Schema> {
        Arc::new(Schema::new(vec![
            lance::deps::arrow_schema::Field::new(
                ID_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                false,
            ),
            // thread_id as first-class column for predicate push-down filtering
            lance::deps::arrow_schema::Field::new(
                THREAD_ID_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                false,
            ),
            lance::deps::arrow_schema::Field::new(
                CHECKPOINT_TIMESTAMP_COLUMN,
                lance::deps::arrow_schema::DataType::Float64,
                false,
            ),
            lance::deps::arrow_schema::Field::new(
                CHECKPOINT_PARENT_ID_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                true,
            ),
            lance::deps::arrow_schema::Field::new(
                CHECKPOINT_STEP_COLUMN,
                lance::deps::arrow_schema::DataType::Int32,
                true,
            ),
            lance::deps::arrow_schema::Field::new(
                VECTOR_COLUMN,
                lance::deps::arrow_schema::DataType::FixedSizeList(
                    Arc::new(lance::deps::arrow_schema::Field::new(
                        "item",
                        lance::deps::arrow_schema::DataType::Float32,
                        true,
                    )),
                    i32::try_from(self.dimension).unwrap_or(1536),
                ),
                true,
            ),
            lance::deps::arrow_schema::Field::new(
                CONTENT_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                false,
            ),
            lance::deps::arrow_schema::Field::new(
                METADATA_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                true,
            ),
        ]))
    }

    /// Create an empty record batch for initialization.
    pub(super) fn create_empty_batch(
        &self,
        schema: &Arc<Schema>,
    ) -> Result<RecordBatch, VectorStoreError> {
        let dimension = self.dimension;
        let arrays: Vec<Arc<dyn lance::deps::arrow_array::Array>> = vec![
            Arc::new(lance::deps::arrow_array::StringArray::from(
                Vec::<String>::new(),
            )) as _,
            // thread_id column
            Arc::new(lance::deps::arrow_array::StringArray::from(
                Vec::<String>::new(),
            )) as _,
            // checkpoint_timestamp column
            Arc::new(lance::deps::arrow_array::Float64Array::from(
                Vec::<f64>::new(),
            )) as _,
            // checkpoint_parent_id column
            Arc::new(lance::deps::arrow_array::StringArray::from(Vec::<
                Option<String>,
            >::new(
            ))) as _,
            // checkpoint_step column
            Arc::new(lance::deps::arrow_array::Int32Array::from(
                Vec::<Option<i32>>::new(),
            )) as _,
            Arc::new(lance::deps::arrow_array::FixedSizeListArray::new_null(
                Arc::new(lance::deps::arrow_schema::Field::new(
                    "item",
                    lance::deps::arrow_schema::DataType::Float32,
                    true,
                )),
                i32::try_from(dimension).unwrap_or(1536),
                0,
            )) as _,
            Arc::new(lance::deps::arrow_array::StringArray::from(
                Vec::<String>::new(),
            )) as _,
            Arc::new(lance::deps::arrow_array::StringArray::from(
                Vec::<String>::new(),
            )) as _,
        ];

        RecordBatch::try_new(schema.clone(), arrays).map_err(VectorStoreError::Arrow)
    }

    /// Validate checkpoint dataset schema against the current engine contract.
    pub(super) fn validate_dataset_schema(
        &self,
        dataset: &Dataset,
    ) -> Result<(), VectorStoreError> {
        use lance::deps::arrow_schema::DataType;

        let schema = lance::deps::arrow_schema::Schema::from(dataset.schema());
        let expected_dim = i32::try_from(self.dimension).unwrap_or(1536);

        let check_field = |name: &str,
                           expected_type: &DataType,
                           expected_nullable: bool|
         -> Result<(), VectorStoreError> {
            let field = schema.field_with_name(name).map_err(|_| {
                VectorStoreError::General(format!(
                    "Checkpoint schema mismatch: missing required column '{name}'"
                ))
            })?;
            if field.data_type() != expected_type {
                return Err(VectorStoreError::General(format!(
                    "Checkpoint schema mismatch on column '{name}': expected {expected_type:?}, got {:?}",
                    field.data_type()
                )));
            }
            if field.is_nullable() != expected_nullable {
                return Err(VectorStoreError::General(format!(
                    "Checkpoint schema mismatch on column '{name}': expected nullable={expected_nullable}, got {}",
                    field.is_nullable()
                )));
            }
            Ok(())
        };

        check_field(ID_COLUMN, &DataType::Utf8, false)?;
        check_field(THREAD_ID_COLUMN, &DataType::Utf8, false)?;
        check_field(CHECKPOINT_TIMESTAMP_COLUMN, &DataType::Float64, false)?;
        check_field(CHECKPOINT_PARENT_ID_COLUMN, &DataType::Utf8, true)?;
        check_field(CHECKPOINT_STEP_COLUMN, &DataType::Int32, true)?;
        check_field(CONTENT_COLUMN, &DataType::Utf8, false)?;
        check_field(METADATA_COLUMN, &DataType::Utf8, true)?;

        let vector_field = schema.field_with_name(VECTOR_COLUMN).map_err(|_| {
            VectorStoreError::General(format!(
                "Checkpoint schema mismatch: missing required column '{VECTOR_COLUMN}'"
            ))
        })?;
        match vector_field.data_type() {
            DataType::FixedSizeList(item, size)
                if *size == expected_dim && matches!(item.data_type(), DataType::Float32) => {}
            other => {
                return Err(VectorStoreError::General(format!(
                    "Checkpoint schema mismatch on column '{VECTOR_COLUMN}': expected FixedSizeList<Float32; {expected_dim}>, got {other:?}"
                )));
            }
        }
        if !vector_field.is_nullable() {
            return Err(VectorStoreError::General(format!(
                "Checkpoint schema mismatch on column '{VECTOR_COLUMN}': expected nullable=true"
            )));
        }

        Ok(())
    }
}
