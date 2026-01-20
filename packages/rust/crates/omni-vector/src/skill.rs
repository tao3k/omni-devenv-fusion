//! Skill Tool Indexing - Discover and index @skill_command decorated functions
//!
//! This module provides methods for scanning skill directories and indexing
//! tool functions discovered via `skills-scanner` crate.
//!
//! Uses both `SkillScanner` (for SKILL.md) and `ScriptScanner` (for scripts/)
//! to properly enrich tool records with routing_keywords from SKILL.md.

use std::path::Path;

use crate::{ScriptScanner, SkillScanner, ToolRecord, VectorStoreError};

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
        let script_scanner = ScriptScanner::new();
        let skills_path = Path::new(base_path);

        if !skills_path.exists() {
            log::warn!("Skills directory not found: {}", base_path);
            return Ok(());
        }

        // Step 1: Scan SKILL.md files to get routing_keywords
        let metadatas = skill_scanner.scan_all(skills_path, None).map_err(|e| {
            VectorStoreError::from(anyhow::anyhow!("Failed to scan skill metadata: {}", e))
        })?;

        if metadatas.is_empty() {
            log::info!("No skills with SKILL.md found");
            return Ok(());
        }

        // Step 2: For each skill, scan scripts with routing_keywords
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
                    VectorStoreError::from(anyhow::anyhow!(
                        "Failed to scan scripts for skill '{}': {}",
                        metadata.skill_name,
                        e
                    ))
                })?;

            all_tools.extend(tools);
        }

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
        let script_scanner = ScriptScanner::new();
        let skills_path = Path::new(base_path);

        if !skills_path.exists() {
            log::warn!("Skills directory not found: {}", base_path);
            return Ok(vec![]);
        }

        // Get metadatas for routing_keywords
        let metadatas = skill_scanner.scan_all(skills_path, None).map_err(|e| {
            VectorStoreError::from(anyhow::anyhow!("Failed to scan skill metadata: {}", e))
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
                    VectorStoreError::from(anyhow::anyhow!(
                        "Failed to scan scripts for skill '{}': {}",
                        metadata.skill_name,
                        e
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
}
