//! Skill Tool Indexing - Discover and index @skill_command decorated functions
//!
//! This module provides methods for scanning skill directories and indexing
//! tool functions discovered via `skills-scanner` crate.
//!
//! Uses both `SkillScanner` (for SKILL.md) and `ToolsScanner` (for scripts/)
//! to properly enrich tool records with routing_keywords from SKILL.md.

use std::path::Path;

use anyhow::Result;
use futures::TryStreamExt;
use lance::dataset::Dataset;
use serde::Serialize;
use serde_json::Value;

use crate::{
    CONTENT_COLUMN, METADATA_COLUMN, SkillScanner, ToolRecord, ToolsScanner, VECTOR_COLUMN,
    VectorStoreError,
};

/// Tool Search Result - Ready-to-use struct returned to Python
/// Optimized for zero-copy passing through FFI boundary
#[derive(Debug, Clone, Serialize)]
pub struct ToolSearchResult {
    /// Full tool name (e.g., "git.commit")
    pub name: String,
    /// Tool description from content
    pub description: String,
    /// JSON schema for tool inputs
    pub input_schema: Value,
    /// Relevance score (0.0 to 1.0)
    pub score: f32,
    /// Parent skill name (e.g., "git")
    pub skill_name: String,
    /// Tool function name (e.g., "commit")
    pub tool_name: String,
    /// Source file path
    pub file_path: String,
    /// Routing keywords for hybrid search
    pub keywords: Vec<String>,
}

impl crate::VectorStore {
    /// Index all tools from skills scripts directory.
    ///
    /// This method:
    /// 1. Scans SKILL.md files to extract `routing_keywords`
    /// 2. Scans scripts/ for `@skill_command` decorated functions
    /// 3. Enriches tool records with routing_keywords for hybrid search
    ///
    /// # Arguments
    ///
    /// * `base_path` - Base directory containing skills (e.g., "assets/skills")
    /// * `table_name` - Table to store tool records (default: "skills")
    ///
    /// # Errors
    ///
    /// Returns an error if scanning or indexing fails.
    pub async fn index_skill_tools(
        &self,
        base_path: &str,
        table_name: &str,
    ) -> Result<(), VectorStoreError> {
        let skill_scanner = SkillScanner::new();
        let script_scanner = ToolsScanner::new();
        let skills_path = Path::new(base_path);

        if !skills_path.exists() {
            log::warn!("Skills directory not found: {}", base_path);
            return Ok(());
        }

        // Step 1: Scan SKILL.md files to get routing_keywords
        let metadatas = skill_scanner.scan_all(skills_path, None).map_err(|e| {
            VectorStoreError::General(format!("Failed to scan skill metadata: {}", e))
        })?;

        if metadatas.is_empty() {
            log::info!("No skills with SKILL.md found");
            return Ok(());
        }

        // Step 2: For each skill, scan scripts with routing_keywords
        // Use HashMap to deduplicate by tool name (skill.tool_name)
        let mut tools_map: std::collections::HashMap<String, ToolRecord> =
            std::collections::HashMap::new();

        for metadata in &metadatas {
            let skill_scripts_path = skills_path.join(&metadata.skill_name).join("scripts");

            let tools = script_scanner
                .scan_scripts(
                    &skill_scripts_path,
                    &metadata.skill_name,
                    &metadata.routing_keywords,
                )
                .map_err(|e| {
                    VectorStoreError::General(format!(
                        "Failed to scan scripts for skill '{}': {}",
                        metadata.skill_name, e
                    ))
                })?;

            // Deduplicate by tool name (keep first occurrence)
            for tool in tools {
                let tool_key = format!("{}.{}", tool.skill_name, tool.tool_name);
                if !tools_map.contains_key(&tool_key) {
                    tools_map.insert(tool_key, tool);
                }
            }
        }

        let all_tools: Vec<ToolRecord> = tools_map.into_values().collect();

        if all_tools.is_empty() {
            log::info!("No tools found in scripts");
            return Ok(());
        }

        // Step 3: Convert tools to record format for indexing
        let ids: Vec<String> = all_tools
            .iter()
            .map(|t| {
                format!(
                    "{}.{}",
                    t.skill_name,
                    t.tool_name.split('.').skip(1).collect::<Vec<_>>().join(".")
                )
            })
            .collect();

        // Use description as content for embedding
        let contents: Vec<String> = all_tools.iter().map(|t| t.description.clone()).collect();

        // Create metadata JSON with routing_keywords for hybrid search
        let metadatas_json: Vec<String> = all_tools
            .iter()
            .map(|t| {
                serde_json::json!({
                    "skill_name": t.skill_name,
                    "tool_name": t.tool_name,
                    "file_path": t.file_path,
                    "function_name": t.function_name,
                    "keywords": t.keywords,  // Includes routing_keywords from SKILL.md
                    "file_hash": t.file_hash,
                    "input_schema": t.input_schema,
                    "docstring": t.docstring,
                })
                .to_string()
            })
            .collect();

        // Generate placeholder embeddings (in production, use actual embeddings)
        let dimension = self.dimension;
        let vectors: Vec<Vec<f32>> = ids
            .iter()
            .map(|id| {
                // Simple hash-based embedding for demonstration
                // In production, use: embedding_model.encode(content)
                let mut vec = vec![0.0; dimension];
                // Use wrapping_mul to avoid overflow panic on long IDs
                let hash = id
                    .bytes()
                    .fold(0u64, |acc, b| acc.wrapping_mul(31).wrapping_add(b as u64));
                for (i, v) in vec.iter_mut().enumerate() {
                    *v = ((hash >> (i % 64)) as f32 / u64::MAX as f32) * 0.1;
                }
                vec
            })
            .collect();

        self.add_documents(table_name, ids, vectors, contents, metadatas_json)
            .await?;

        log::info!(
            "Indexed {} tools from {} skills",
            all_tools.len(),
            metadatas.len()
        );
        Ok(())
    }

    /// Get tool records by skill name.
    ///
    /// # Arguments
    ///
    /// * `skill_name` - Name of the skill to query
    ///
    /// # Returns
    ///
    /// Vector of tool records for the skill.
    ///
    /// # Errors
    ///
    /// Returns an error if the table doesn't exist.
    pub async fn get_tools_by_skill(
        &self,
        _skill_name: &str,
    ) -> Result<Vec<ToolRecord>, VectorStoreError> {
        // Simplified implementation
        // Full implementation requires additional LanceDB table scanning API
        // For now, return empty list as placeholder
        //
        // To implement fully:
        // 1. Open the "skills" table
        // 2. Scan all records
        // 3. Filter by skill_name in metadata
        // 4. Deserialize and return ToolRecords
        Ok(vec![])
    }

    /// Scan for skill tools without indexing (returns raw tool records as JSON).
    ///
    /// This method discovers @skill_command decorated functions without
    /// attempting schema extraction. Use this when you want to do schema
    /// extraction in Python with proper import context.
    ///
    /// # Arguments
    ///
    /// * `base_path` - Base directory containing skills (e.g., "assets/skills")
    ///
    /// # Returns
    ///
    /// Vector of JSON strings representing tool records
    ///
    /// # Errors
    ///
    /// Returns an error if scanning fails.
    pub fn scan_skill_tools_raw(&self, base_path: &str) -> Result<Vec<String>, VectorStoreError> {
        let skill_scanner = SkillScanner::new();
        let script_scanner = ToolsScanner::new();
        let skills_path = Path::new(base_path);

        if !skills_path.exists() {
            log::warn!("Skills directory not found: {}", base_path);
            return Ok(vec![]);
        }

        // Get metadatas for routing_keywords
        let metadatas = skill_scanner.scan_all(skills_path, None).map_err(|e| {
            VectorStoreError::General(format!("Failed to scan skill metadata: {}", e))
        })?;

        // Collect tools with routing_keywords
        let mut all_tools: Vec<ToolRecord> = Vec::new();

        for metadata in &metadatas {
            let skill_scripts_path = skills_path.join(&metadata.skill_name).join("scripts");

            let tools = script_scanner
                .scan_scripts(
                    &skill_scripts_path,
                    &metadata.skill_name,
                    &metadata.routing_keywords,
                )
                .map_err(|e| {
                    VectorStoreError::General(format!(
                        "Failed to scan scripts for skill '{}': {}",
                        metadata.skill_name, e
                    ))
                })?;

            all_tools.extend(tools);
        }

        // Convert to JSON strings
        let json_tools: Vec<String> = all_tools
            .into_iter()
            .map(|t| serde_json::to_string(&t).unwrap_or_default())
            .filter(|s| !s.is_empty())
            .collect();

        log::info!("Scanned {} skill tools", json_tools.len());
        Ok(json_tools)
    }

    /// List all tools from LanceDB as JSON.
    ///
    /// Enables using LanceDB as the Single Source of Truth instead of skill_index.json.
    /// Returns tools with: id, content, metadata (skill_name, tool_name, file_path, keywords, etc.)
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table (default: "skills")
    ///
    /// # Returns
    ///
    /// JSON string of tool array
    ///
    /// # Errors
    ///
    /// Returns an error if the table doesn't exist.
    pub async fn list_all_tools(&self, table_name: &str) -> Result<String, VectorStoreError> {
        use futures::TryStreamExt;
        use lance::deps::arrow_array::Array;

        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Ok("[]".to_string());
        }

        let dataset = lance::dataset::Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        // Create scanner to read all columns
        let mut scanner = dataset.scan();
        scanner.project(&["id", "content", "metadata"])?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut tools: Vec<serde_json::Value> = Vec::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            use lance::deps::arrow_array::StringArray;

            let id_col = batch.column_by_name("id");
            let content_col = batch.column_by_name("content");
            let metadata_col = batch.column_by_name("metadata");

            if let (Some(ids), Some(contents), Some(metas)) = (id_col, content_col, metadata_col) {
                if let (Some(id_arr), Some(content_arr), Some(meta_arr)) = (
                    ids.as_any().downcast_ref::<StringArray>(),
                    contents.as_any().downcast_ref::<StringArray>(),
                    metas.as_any().downcast_ref::<StringArray>(),
                ) {
                    for i in 0..batch.num_rows() {
                        let id = id_arr.value(i).to_string();
                        let content = content_arr.value(i).to_string();
                        let metadata_str = if meta_arr.is_null(i) {
                            "{}".to_string()
                        } else {
                            meta_arr.value(i).to_string()
                        };

                        // Parse metadata and add id/content
                        if let Ok(mut metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
                        {
                            metadata["id"] = serde_json::json!(id);
                            metadata["content"] = serde_json::json!(content);
                            tools.push(metadata);
                        }
                    }
                }
            }
        }

        serde_json::to_string(&tools).map_err(|e| VectorStoreError::General(format!("{}", e)))
    }

    // ============================================================================
    // Rust-Native Tool Search (Zero-Copy, Predicate Push-down)
    // ============================================================================

    /// High-performance tool search with integrated filtering and scoring.
    ///
    /// This method performs the entire search pipeline in Rust:
    /// 1. Vector similarity computation (L2 distance)
    /// 2. Score threshold filtering
    /// 3. Metadata parsing and validation
    /// 4. Result formatting for Python consumption
    ///
    /// Benefits:
    /// - No Python-side DataFrame operations
    /// - No intermediate JSON parsing for filtered-out results
    /// - Returns pre-formatted ToolSearchResult structs
    ///
    /// # Arguments
    ///
    /// * `table_name` - Table containing tool records (default: "skills")
    /// * `query_vector` - Query embedding vector
    /// * `limit` - Maximum number of results to return
    /// * `threshold` - Minimum score threshold (0.0 to 1.0)
    ///
    /// # Returns
    ///
    /// Vector of `ToolSearchResult` ready for Python consumption
    ///
    /// # Errors
    ///
    /// Returns an error if the table doesn't exist or search fails.
    pub async fn search_tools(
        &self,
        table_name: &str,
        query_vector: &[f32],
        limit: usize,
        threshold: f32,
    ) -> Result<Vec<ToolSearchResult>, VectorStoreError> {
        use lance::deps::arrow_array::Array;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(Vec::new());
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut scanner = dataset.scan();
        scanner.project(&[VECTOR_COLUMN, METADATA_COLUMN, CONTENT_COLUMN])?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut results: Vec<ToolSearchResult> = Vec::new();
        let query_len = query_vector.len();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let vector_col = batch.column_by_name(VECTOR_COLUMN);
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let content_col = batch.column_by_name(CONTENT_COLUMN);

            if let (Some(v_col), Some(m_col), Some(c_col)) = (vector_col, metadata_col, content_col)
            {
                let vector_arr = v_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::FixedSizeListArray>();
                let metadata_arr = m_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let content_arr = c_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();

                if let (Some(vector_arr), Some(metadata_arr), Some(content_arr)) =
                    (vector_arr, metadata_arr, content_arr)
                {
                    let values = vector_arr
                        .values()
                        .as_any()
                        .downcast_ref::<lance::deps::arrow_array::Float32Array>();

                    if let Some(values) = values {
                        for i in 0..batch.num_rows() {
                            // Compute L2 distance
                            let mut distance_sq = 0.0f32;
                            let values_len = values.len();
                            for j in 0..query_len {
                                let db_val = if j < values_len {
                                    values.value(i * values_len / batch.num_rows() + j)
                                } else {
                                    0.0
                                };
                                let diff = db_val - query_vector[j];
                                distance_sq += diff * diff;
                            }
                            let distance = distance_sq.sqrt();

                            // Convert distance to score: 1 / (1 + distance)
                            let score = 1.0 / (1.0 + distance);

                            if score < threshold {
                                continue;
                            }

                            if metadata_arr.is_null(i) {
                                continue;
                            }

                            // Parse metadata for tool info
                            let metadata_str = metadata_arr.value(i);
                            if let Ok(meta) = serde_json::from_str::<Value>(&metadata_str) {
                                // Only process command-type tools
                                if meta.get("type").and_then(|t| t.as_str()) != Some("command") {
                                    continue;
                                }

                                let name = meta
                                    .get("command")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("")
                                    .to_string();
                                if name.is_empty() {
                                    continue;
                                }

                                let skill_name = meta
                                    .get("skill_name")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("")
                                    .to_string();
                                let tool_name = meta
                                    .get("tool_name")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("")
                                    .to_string();
                                let file_path = meta
                                    .get("file_path")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("")
                                    .to_string();
                                let keywords: Vec<String> = meta
                                    .get("keywords")
                                    .and_then(|k| k.as_array())
                                    .map(|arr| {
                                        arr.iter()
                                            .filter_map(|k| k.as_str().map(|s| s.to_string()))
                                            .collect()
                                    })
                                    .unwrap_or_default();
                                let input_schema = meta
                                    .get("input_schema")
                                    .cloned()
                                    .unwrap_or(Value::Object(serde_json::Map::new()));
                                let description = content_arr.value(i).to_string();

                                results.push(ToolSearchResult {
                                    name,
                                    description,
                                    input_schema,
                                    score,
                                    skill_name,
                                    tool_name,
                                    file_path,
                                    keywords,
                                });
                            }
                        }
                    }
                }
            }
        }

        // Sort by score descending and limit
        results.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        results.truncate(limit);

        Ok(results)
    }

    /// Fast registry loading for MCP initialization.
    ///
    /// Loads all tools from the database with minimal IO:
    /// - Only reads METADATA and CONTENT columns
    /// - Returns pre-formatted ToolSearchResult structs
    /// - No vector computation needed (score = 1.0 for all)
    ///
    /// This is used during MCP server startup to build the tool registry.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Table containing tool records (default: "skills")
    ///
    /// # Returns
    ///
    /// Vector of `ToolSearchResult` for all tools
    ///
    /// # Errors
    ///
    /// Returns an error if the table doesn't exist or loading fails.
    pub async fn load_tool_registry(
        &self,
        table_name: &str,
    ) -> Result<Vec<ToolSearchResult>, VectorStoreError> {
        use lance::deps::arrow_array::Array;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(Vec::new());
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut scanner = dataset.scan();
        // Only need metadata and content columns for registry
        scanner.project(&[METADATA_COLUMN, CONTENT_COLUMN])?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut tools: Vec<ToolSearchResult> = Vec::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let content_col = batch.column_by_name(CONTENT_COLUMN);

            if let (Some(m_col), Some(c_col)) = (metadata_col, content_col) {
                let metadata_arr = m_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let content_arr = c_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();

                if let (Some(metadata_arr), Some(content_arr)) = (metadata_arr, content_arr) {
                    for i in 0..batch.num_rows() {
                        if metadata_arr.is_null(i) {
                            continue;
                        }

                        let metadata_str = metadata_arr.value(i);
                        if let Ok(meta) = serde_json::from_str::<Value>(&metadata_str) {
                            // Only process command-type tools
                            if meta.get("type").and_then(|t| t.as_str()) != Some("command") {
                                continue;
                            }

                            let name = meta
                                .get("command")
                                .and_then(|s| s.as_str())
                                .unwrap_or("")
                                .to_string();
                            if name.is_empty() {
                                continue;
                            }

                            let skill_name = meta
                                .get("skill_name")
                                .and_then(|s| s.as_str())
                                .unwrap_or("")
                                .to_string();
                            let tool_name = meta
                                .get("tool_name")
                                .and_then(|s| s.as_str())
                                .unwrap_or("")
                                .to_string();
                            let file_path = meta
                                .get("file_path")
                                .and_then(|s| s.as_str())
                                .unwrap_or("")
                                .to_string();
                            let keywords: Vec<String> = meta
                                .get("keywords")
                                .and_then(|k| k.as_array())
                                .map(|arr| {
                                    arr.iter()
                                        .filter_map(|k| k.as_str().map(|s| s.to_string()))
                                        .collect()
                                })
                                .unwrap_or_default();
                            let input_schema = meta
                                .get("input_schema")
                                .cloned()
                                .unwrap_or(Value::Object(serde_json::Map::new()));
                            let description = content_arr.value(i).to_string();

                            tools.push(ToolSearchResult {
                                name,
                                description,
                                input_schema,
                                score: 1.0, // Registry load doesn't need scoring
                                skill_name,
                                tool_name,
                                file_path,
                                keywords,
                            });
                        }
                    }
                }
            }
        }

        Ok(tools)
    }
}
