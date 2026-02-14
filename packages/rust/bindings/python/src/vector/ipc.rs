//! Arrow IPC encoding for analytics (TableHealthReport → bytes).
//!
//! Produces a single RecordBatch with one row: row_count, fragment_count,
//! fragmentation_ratio, index_names (List<Utf8>), index_types (List<Utf8>),
//! recommendations (List<Utf8>). Python can read with pyarrow.ipc.open_stream.

use arrow::array::{Array, Float64Array, ListArray, StringArray, UInt32Array, UInt64Array};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use arrow_ipc::writer::StreamWriter;
use std::io::Cursor;
use std::sync::Arc;

use omni_vector::{Recommendation, TableHealthReport};

fn recommendation_to_str(r: &Recommendation) -> String {
    match r {
        Recommendation::RunCompaction => "run_compaction".to_string(),
        Recommendation::CreateIndices => "create_indices".to_string(),
        Recommendation::RebuildIndices => "rebuild_indices".to_string(),
        Recommendation::Partition { column } => format!("partition:{}", column),
        Recommendation::None => "none".to_string(),
    }
}

/// Encode TableHealthReport as Arrow IPC stream bytes (single RecordBatch).
pub fn table_health_report_to_ipc(report: &TableHealthReport) -> Result<Vec<u8>, String> {
    let index_names: Vec<&str> = report
        .indices_status
        .iter()
        .map(|s| s.name.as_str())
        .collect();
    let index_types: Vec<&str> = report
        .indices_status
        .iter()
        .map(|s| s.index_type.as_str())
        .collect();
    let rec_strs: Vec<String> = report
        .recommendations
        .iter()
        .map(recommendation_to_str)
        .collect();
    let rec_refs: Vec<&str> = rec_strs.iter().map(String::as_str).collect();

    let row_count_arr = Arc::new(UInt32Array::from(vec![report.row_count]));
    let fragment_count_arr = Arc::new(UInt64Array::from(vec![report.fragment_count as u64]));
    let frag_ratio_arr = Arc::new(Float64Array::from(vec![report.fragmentation_ratio]));

    let index_names_child = StringArray::from(index_names);
    let index_names_offsets =
        arrow::buffer::OffsetBuffer::new(vec![0, index_names_child.len() as i32].into());
    let index_names_list = Arc::new(ListArray::new(
        Arc::new(Field::new("item", DataType::Utf8, true)),
        index_names_offsets,
        Arc::new(index_names_child),
        None,
    ));

    let index_types_child = StringArray::from(index_types);
    let index_types_offsets =
        arrow::buffer::OffsetBuffer::new(vec![0, index_types_child.len() as i32].into());
    let index_types_list = Arc::new(ListArray::new(
        Arc::new(Field::new("item", DataType::Utf8, true)),
        index_types_offsets,
        Arc::new(index_types_child),
        None,
    ));

    let rec_child = StringArray::from(rec_refs);
    let rec_offsets = arrow::buffer::OffsetBuffer::new(vec![0, rec_child.len() as i32].into());
    let rec_list = Arc::new(ListArray::new(
        Arc::new(Field::new("item", DataType::Utf8, true)),
        rec_offsets,
        Arc::new(rec_child),
        None,
    ));

    let schema = Schema::new(vec![
        Field::new("row_count", DataType::UInt32, false),
        Field::new("fragment_count", DataType::UInt64, false),
        Field::new("fragmentation_ratio", DataType::Float64, false),
        Field::new(
            "index_names",
            DataType::List(Arc::new(Field::new("item", DataType::Utf8, true))),
            true,
        ),
        Field::new(
            "index_types",
            DataType::List(Arc::new(Field::new("item", DataType::Utf8, true))),
            true,
        ),
        Field::new(
            "recommendations",
            DataType::List(Arc::new(Field::new("item", DataType::Utf8, true))),
            true,
        ),
    ]);

    let batch = RecordBatch::try_new(
        Arc::new(schema.clone()),
        vec![
            row_count_arr,
            fragment_count_arr,
            frag_ratio_arr,
            index_names_list,
            index_types_list,
            rec_list,
        ],
    )
    .map_err(|e| e.to_string())?;

    let mut buf = Cursor::new(Vec::new());
    {
        let mut writer =
            StreamWriter::try_new(&mut buf, &batch.schema()).map_err(|e| e.to_string())?;
        writer.write(&batch).map_err(|e| e.to_string())?;
        writer.finish().map_err(|e| e.to_string())?;
    }
    Ok(buf.into_inner())
}

// Roundtrip test lives in Python: agent/tests/integration/test_db_health_compact.py
// (Rust tests here would load the Python extension and fail without a Python runtime.)
