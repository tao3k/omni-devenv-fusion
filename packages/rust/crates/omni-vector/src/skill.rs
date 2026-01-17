//! Skill Tool Indexing - Discover and index @skill_command decorated functions
//!
//! This module provides methods for scanning skill directories and indexing
//! tool functions discovered via the `ScriptScanner`.

use std::path::Path;

use crate::{ScriptScanner, ToolRecord, VectorStoreError};

impl crate::VectorStore {
    /// Index all tools from skills scripts directory.
    ///
    /// Scans `base_path/skills/*/scripts/*.py` for `@skill_command` decorated
    /// functions and indexes them for discovery.
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
        let scanner = ScriptScanner::new();
        let skills_path = Path::new(base_path);

        if !skills_path.exists() {
            log::warn!("Skills directory not found: {}", base_path);
            return Ok(());
        }

        let tools = scanner
            .scan_all(skills_path)
            .map_err(|e| VectorStoreError::from(anyhow::anyhow!("Failed to scan skills: {}", e)))?;

        if tools.is_empty() {
            log::info!("No tools found in scripts");
            return Ok(());
        }

        // Convert tools to record format
        let ids: Vec<String> = tools
            .iter()
            .map(|t| format!("{}.{}", t.skill_name, t.tool_name))
            .collect();

        // Use description as content for embedding
        let contents: Vec<String> = tools.iter().map(|t| t.description.clone()).collect();

        // Create metadata JSON with file_hash (input_schema will be added by Python if needed)
        let metadatas: Vec<String> = tools
            .iter()
            .map(|t| {
                serde_json::json!({
                    "skill_name": t.skill_name,
                    "tool_name": t.tool_name,
                    "file_path": t.file_path,
                    "function_name": t.function_name,
                    "keywords": t.keywords,
                    "file_hash": t.file_hash,
                    "input_schema": "{}",  // Placeholder - Python can update this
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

        self.add_documents(table_name, ids, vectors, contents, metadatas)
            .await?;

        log::info!("Indexed {} tools from scripts", tools.len());
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
        let scanner = ScriptScanner::new();
        let skills_path = Path::new(base_path);

        if !skills_path.exists() {
            log::warn!("Skills directory not found: {}", base_path);
            return Ok(vec![]);
        }

        let tools = scanner
            .scan_all(skills_path)
            .map_err(|e| VectorStoreError::from(anyhow::anyhow!("Failed to scan skills: {}", e)))?;

        // Convert to JSON strings
        let json_tools: Vec<String> = tools
            .into_iter()
            .map(|t| serde_json::to_string(&t).unwrap_or_default())
            .filter(|s| !s.is_empty())
            .collect();

        log::info!("Scanned {} skill tools", json_tools.len());
        Ok(json_tools)
    }
}
