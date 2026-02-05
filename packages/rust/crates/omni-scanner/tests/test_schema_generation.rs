//! Tests for JSON Schema generation.
//!
//! Verifies that schema generation produces valid JSON and
//! writes to the correct location.

use omni_scanner::SkillMetadata;
use std::fs;
use std::path::PathBuf;

/// Test that skill_index_schema produces valid JSON.
#[test]
fn test_skill_index_schema_produces_json() {
    let schema_json = omni_scanner::skill_index_schema();
    assert!(!schema_json.is_empty());

    // Verify it's valid JSON
    let parsed: serde_json::Value =
        serde_json::from_str(&schema_json).expect("skill_index_schema should produce valid JSON");

    // Verify it has expected fields
    assert_eq!(parsed["title"], "SkillIndexEntry");
    assert_eq!(
        parsed["$schema"],
        "https://json-schema.org/draft/2020-12/schema"
    );
}

/// Test that SkillMetadata derives JsonSchema.
#[test]
fn test_skill_metadata_schema_derives() {
    // This test verifies that SkillMetadata can be used with schemars
    let schema = schemars::schema_for!(SkillMetadata);
    let schema_json =
        serde_json::to_string_pretty(&schema).expect("Should serialize schema to JSON");

    assert!(!schema_json.is_empty());
    assert!(schema_json.contains("SkillMetadata"));
}

/// Generate JSON Schema for SkillMetadata and write to packages/shared/schemas.
///
/// Run with: cargo test -p skills-scanner generate_skill_metadata_schema
#[test]
fn generate_skill_metadata_schema() {
    // 1. Generate Schema object for SkillMetadata
    let schema = schemars::schema_for!(SkillMetadata);

    // 2. Serialize to JSON string
    let schema_json =
        serde_json::to_string_pretty(&schema).expect("Failed to serialize schema to JSON");

    // 3. Resolve output path using PRJ_ROOT or CARGO_MANIFEST_DIR
    let output_path = resolve_output_path("skill_metadata.schema.json");

    // 4. Create parent directory if needed and write
    if let Some(parent) = output_path.parent() {
        fs::create_dir_all(parent).expect("Failed to create schema directory");
    }

    fs::write(&output_path, schema_json).expect("Failed to write skill_metadata.schema.json");

    println!(
        "Schema generated at: {:?}",
        output_path.canonicalize().unwrap_or(output_path)
    );
}

/// Resolve output path for schema files.
///
/// Uses PRJ_ROOT environment variable if set, otherwise falls back to
/// CARGO_MANIFEST_DIR + "../../../packages/shared/schemas/"
fn resolve_output_path(filename: &str) -> PathBuf {
    // Try PRJ_ROOT first
    if let Ok(prj_root) = std::env::var("PRJ_ROOT") {
        let path = PathBuf::from(prj_root)
            .join("packages/shared/schemas")
            .join(filename);
        if path.parent().map(|p| p.exists()).unwrap_or(false) {
            return path;
        }
    }

    // Fall back to CARGO_MANIFEST_DIR
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."));

    manifest_dir
        .join("../../../packages/shared/schemas")
        .join(filename)
}
