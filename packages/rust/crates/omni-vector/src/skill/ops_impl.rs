use std::path::Path;

impl VectorStore {
    /// Index all tools found in a skill directory.
    pub async fn index_skill_tools(
        &self,
        base_path: &str,
        table_name: &str,
    ) -> Result<(), VectorStoreError> {
        let skill_scanner = SkillScanner::new();
        let script_scanner = ToolsScanner::new();
        let skills_path = Path::new(base_path);
        if !skills_path.exists() {
            return Ok(());
        }
        let metadatas = skill_scanner
            .scan_all(skills_path, None)
            .map_err(|e| VectorStoreError::General(e.to_string()))?;
        let mut tools_map = std::collections::HashMap::new();
        for metadata in &metadatas {
            let tools = script_scanner
                .scan_scripts(
                    &skills_path.join(&metadata.skill_name).join("scripts"),
                    &metadata.skill_name,
                    &metadata.routing_keywords,
                    &metadata.intents,
                )
                .map_err(|e| VectorStoreError::General(e.to_string()))?;
            for tool in tools {
                tools_map.insert(format!("{}.{}", tool.skill_name, tool.tool_name), tool);
            }
        }
        self.add(table_name, tools_map.into_values().collect())
            .await?;
        Ok(())
    }

    /// Scan skill tools without indexing them.
    pub fn scan_skill_tools_raw(&self, base_path: &str) -> Result<Vec<String>, VectorStoreError> {
        let skill_scanner = SkillScanner::new();
        let script_scanner = ToolsScanner::new();
        let skills_path = Path::new(base_path);
        if !skills_path.exists() {
            return Ok(vec![]);
        }
        let metadatas = skill_scanner
            .scan_all(skills_path, None)
            .map_err(|e| VectorStoreError::General(e.to_string()))?;
        let mut all_tools = Vec::new();
        for metadata in &metadatas {
            let tools = script_scanner
                .scan_scripts(
                    &skills_path.join(&metadata.skill_name).join("scripts"),
                    &metadata.skill_name,
                    &metadata.routing_keywords,
                    &[],
                )
                .map_err(|e| VectorStoreError::General(e.to_string()))?;
            all_tools.extend(tools);
        }
        Ok(all_tools
            .into_iter()
            .map(|t| serde_json::to_string(&t).unwrap_or_default())
            .filter(|s| !s.is_empty())
            .collect())
    }

    /// List all tools in a specific table.
    pub async fn list_all_tools(&self, table_name: &str) -> Result<String, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok("[]".to_string());
        }
        let dataset = Dataset::open(table_path.to_string_lossy().as_ref()).await?;
        let mut scanner = dataset.scan();
        scanner.project(&["id", "content", "metadata"])?;
        let mut stream = scanner.try_into_stream().await?;
        let mut tools = Vec::new();
        while let Some(batch) = stream.try_next().await? {
            use lance::deps::arrow_array::Array;
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
        serde_json::to_string(&tools).map_err(|e| VectorStoreError::General(e.to_string()))
    }

    /// Search for tools using hybrid search (vector + keyword).
    pub async fn search_tools(
        &self,
        table_name: &str,
        query_vector: &[f32],
        query_text: Option<&str>,
        limit: usize,
        threshold: f32,
    ) -> Result<Vec<skill::ToolSearchResult>, VectorStoreError> {
        let mut results_map: std::collections::HashMap<String, skill::ToolSearchResult> =
            std::collections::HashMap::new();
        let table_path = self.table_path(table_name);
        if table_path.exists() {
            if let Ok(dataset) = Dataset::open(table_path.to_string_lossy().as_ref()).await {
                let mut scanner = dataset.scan();
                scanner
                    .project(&[VECTOR_COLUMN, METADATA_COLUMN, CONTENT_COLUMN])
                    .ok();
                if let Ok(mut stream) = scanner.try_into_stream().await {
                    let query_len = query_vector.len();
                    while let Ok(Some(batch)) = stream.try_next().await {
                        let v_col = batch.column_by_name(VECTOR_COLUMN);
                        let m_col = batch.column_by_name(METADATA_COLUMN);
                        let c_col = batch.column_by_name(CONTENT_COLUMN);
                        if let (Some(v_c), Some(m_c), Some(c_c)) = (v_col, m_col, c_col) {
                            use lance::deps::arrow_array::Array;
                            let vector_arr =
                                v_c.as_any()
                                    .downcast_ref::<lance::deps::arrow_array::FixedSizeListArray>();
                            let metadata_arr = m_c
                                .as_any()
                                .downcast_ref::<lance::deps::arrow_array::StringArray>();
                            let content_arr = c_c
                                .as_any()
                                .downcast_ref::<lance::deps::arrow_array::StringArray>();
                            if let (Some(v_arr), Some(m_arr), Some(c_arr)) =
                                (vector_arr, metadata_arr, content_arr)
                            {
                                let values = v_arr
                                    .values()
                                    .as_any()
                                    .downcast_ref::<lance::deps::arrow_array::Float32Array>(
                                );
                                if let Some(vals) = values {
                                    for i in 0..batch.num_rows() {
                                        let mut dist_sq = 0.0f32;
                                        let v_len = vals.len();
                                        for j in 0..query_len {
                                            let db_val = if j < v_len {
                                                vals.value(i * v_len / batch.num_rows() + j)
                                            } else {
                                                0.0
                                            };
                                            let diff = db_val - query_vector[j];
                                            dist_sq += diff * diff;
                                        }
                                        let score = 1.0 / (1.0 + dist_sq.sqrt());
                                        if m_arr.is_null(i) {
                                            continue;
                                        }
                                        if let Ok(meta) = serde_json::from_str::<serde_json::Value>(
                                            &m_arr.value(i),
                                        ) {
                                            if meta.get("type").and_then(|t| t.as_str())
                                                != Some("command")
                                            {
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
                                            results_map.insert(
                                                name.clone(),
                                                skill::ToolSearchResult {
                                                    name,
                                                    description: c_arr.value(i).to_string(),
                                                    input_schema: meta
                                                        .get("input_schema")
                                                        .cloned()
                                                        .unwrap_or(serde_json::Value::Object(
                                                            serde_json::Map::new(),
                                                        )),
                                                    score,
                                                    skill_name: meta
                                                        .get("skill_name")
                                                        .and_then(|s| s.as_str())
                                                        .unwrap_or("")
                                                        .to_string(),
                                                    tool_name: meta
                                                        .get("tool_name")
                                                        .and_then(|s| s.as_str())
                                                        .unwrap_or("")
                                                        .to_string(),
                                                    file_path: meta
                                                        .get("file_path")
                                                        .and_then(|s| s.as_str())
                                                        .unwrap_or("")
                                                        .to_string(),
                                                    keywords: meta
                                                        .get("keywords")
                                                        .and_then(|k| k.as_array())
                                                        .map(|arr| {
                                                            arr.iter()
                                                                .filter_map(|k| {
                                                                    k.as_str()
                                                                        .map(|s| s.to_string())
                                                                })
                                                                .collect()
                                                        })
                                                        .unwrap_or_default(),
                                                    intents: meta
                                                        .get("intents")
                                                        .and_then(|k| k.as_array())
                                                        .map(|arr| {
                                                            arr.iter()
                                                                .filter_map(|k| {
                                                                    k.as_str()
                                                                        .map(|s| s.to_string())
                                                                })
                                                                .collect()
                                                        })
                                                        .unwrap_or_default(),
                                                },
                                            );
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        if let Some(text) = query_text {
            if let Some(kw_index) = self.keyword_index.as_ref() {
                let vector_scores: Vec<(String, f32)> = results_map
                    .iter()
                    .map(|(n, r)| (n.clone(), r.score))
                    .collect();
                if let Ok(kw_hits) = kw_index.search(text, limit * 2) {
                    let fused = apply_weighted_rrf(
                        vector_scores,
                        kw_hits.clone(),
                        keyword::RRF_K,
                        keyword::SEMANTIC_WEIGHT,
                        keyword::KEYWORD_WEIGHT,
                        text,
                    );
                    let mut new_map = std::collections::HashMap::new();
                    let kw_lookup: std::collections::HashMap<String, skill::ToolSearchResult> =
                        kw_hits
                            .into_iter()
                            .map(|r| (r.tool_name.clone(), r))
                            .collect();
                    for f in fused {
                        if let Some(mut tool) = results_map
                            .get(&f.tool_name)
                            .cloned()
                            .or_else(|| kw_lookup.get(&f.tool_name).cloned())
                        {
                            tool.score = f.rrf_score;
                            new_map.insert(f.tool_name, tool);
                        }
                    }
                    results_map = new_map;
                }
            }
        }
        let mut res: Vec<_> = results_map.into_values().collect();
        if threshold > 0.0 {
            res.retain(|r| r.score >= threshold);
        }
        res.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap());
        res.truncate(limit);
        Ok(res)
    }

    /// Load the tool registry from a table.
    pub async fn load_tool_registry(
        &self,
        table_name: &str,
    ) -> Result<Vec<skill::ToolSearchResult>, VectorStoreError> {
        // ... (existing implementation)
        self.get_tools_by_skill_internal(table_name, None).await
    }

    /// Get all tools belonging to a specific skill.
    pub async fn get_tools_by_skill(
        &self,
        skill_name: &str,
    ) -> Result<Vec<skill::ToolSearchResult>, VectorStoreError> {
        self.get_tools_by_skill_internal("tools", Some(skill_name))
            .await
    }

    async fn get_tools_by_skill_internal(
        &self,
        table_name: &str,
        skill_filter: Option<&str>,
    ) -> Result<Vec<skill::ToolSearchResult>, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(Vec::new());
        }
        let dataset = Dataset::open(table_path.to_string_lossy().as_ref()).await?;
        let mut scanner = dataset.scan();
        scanner.project(&[METADATA_COLUMN, CONTENT_COLUMN])?;

        if let Some(skill) = skill_filter {
            scanner.filter(&format!("skill_name = '{}'", skill))?;
        }

        let mut stream = scanner.try_into_stream().await?;
        let mut tools = Vec::new();
        while let Some(batch) = stream.try_next().await? {
            use lance::deps::arrow_array::Array;
            if let (Some(m_col), Some(c_col)) = (
                batch.column_by_name(METADATA_COLUMN),
                batch.column_by_name(CONTENT_COLUMN),
            ) {
                let m_arr = m_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let c_arr = c_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                if let (Some(ma), Some(ca)) = (m_arr, c_arr) {
                    for i in 0..batch.num_rows() {
                        if ma.is_null(i) {
                            continue;
                        }
                        if let Ok(meta) = serde_json::from_str::<serde_json::Value>(&ma.value(i)) {
                            if meta.get("type").and_then(|t| t.as_str()) != Some("command") {
                                continue;
                            }

                            // Extra safety check if scanner filter wasn't used or supported
                            if let Some(skill) = skill_filter {
                                if meta.get("skill_name").and_then(|s| s.as_str()) != Some(skill) {
                                    continue;
                                }
                            }

                            tools.push(skill::ToolSearchResult {
                                name: meta
                                    .get("command")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                description: ca.value(i).to_string(),
                                input_schema: meta
                                    .get("input_schema")
                                    .cloned()
                                    .unwrap_or(serde_json::Value::Object(serde_json::Map::new())),
                                score: 1.0,
                                skill_name: meta
                                    .get("skill_name")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                tool_name: meta
                                    .get("tool_name")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                file_path: meta
                                    .get("file_path")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                keywords: meta
                                    .get("keywords")
                                    .and_then(|k| k.as_array())
                                    .map(|arr| {
                                        arr.iter()
                                            .filter_map(|k| k.as_str().map(|s| s.to_string()))
                                            .collect()
                                    })
                                    .unwrap_or_default(),
                                intents: meta
                                    .get("intents")
                                    .and_then(|k| k.as_array())
                                    .map(|arr| {
                                        arr.iter()
                                            .filter_map(|k| k.as_str().map(|s| s.to_string()))
                                            .collect()
                                    })
                                    .unwrap_or_default(),
                            });
                        }
                    }
                }
            }
        }
        Ok(tools)
    }
}
