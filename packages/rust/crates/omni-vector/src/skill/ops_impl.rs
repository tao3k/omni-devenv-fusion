use std::path::Path;

impl VectorStore {
    fn scan_unique_skill_tools(
        &self,
        base_path: &str,
    ) -> Result<Vec<omni_scanner::ToolRecord>, VectorStoreError> {
        let skill_scanner = SkillScanner::new();
        let script_scanner = ToolsScanner::new();
        let skills_path = Path::new(base_path);
        if !skills_path.exists() {
            log::warn!("Skills path does not exist: {:?}", skills_path);
            return Ok(vec![]);
        }

        let metadatas = skill_scanner
            .scan_all(skills_path, None)
            .map_err(|e| VectorStoreError::General(e.to_string()))?;
        log::info!("Found {} skill manifests", metadatas.len());

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
            log::debug!(
                "Skill '{}': found {} tools",
                metadata.skill_name,
                tools.len()
            );
            for tool in tools {
                // tool.tool_name already includes skill_name prefix from tools_scanner
                tools_map.insert(tool.tool_name.clone(), tool);
            }
        }

        Ok(tools_map.into_values().collect())
    }

    /// Index all tools found in a skill directory.
    /// This drops and recreates the table to ensure sync with filesystem.
    pub async fn index_skill_tools(
        &mut self,
        base_path: &str,
        table_name: &str,
    ) -> Result<(), VectorStoreError> {
        log::info!("Indexing skills from: {:?}", base_path);

        // Drop existing table to ensure clean sync (removes deleted skills)
        let drop_result = self.drop_table(table_name).await;
        log::debug!("drop_table result: {:?}", drop_result);

        let tools = self.scan_unique_skill_tools(base_path)?;
        log::info!("Total tools to index: {}", tools.len());
        if tools.is_empty() {
            log::warn!("No tools found to index!");
            return Ok(());
        }

        self.add(table_name, tools).await?;
        log::info!("Successfully indexed tools for table: {}", table_name);
        Ok(())
    }

    /// Atomically rebuild two tool tables from a single filesystem scan.
    ///
    /// This guarantees skills/router are indexed from the same snapshot.
    pub async fn index_skill_tools_dual(
        &mut self,
        base_path: &str,
        skills_table: &str,
        router_table: &str,
    ) -> Result<(usize, usize), VectorStoreError> {
        let tools = self.scan_unique_skill_tools(base_path)?;
        if tools.is_empty() {
            self.drop_table(skills_table).await.ok();
            if router_table != skills_table {
                self.drop_table(router_table).await.ok();
            }
            return Ok((0, 0));
        }

        self.drop_table(skills_table).await.ok();
        self.add(skills_table, tools.clone()).await?;
        let skills_count = self.count(skills_table).await? as usize;

        if router_table == skills_table {
            return Ok((skills_count, skills_count));
        }

        self.drop_table(router_table).await.ok();
        self.add(router_table, tools).await?;
        let router_count = self.count(router_table).await? as usize;

        Ok((skills_count, router_count))
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
        self.search_tools_with_options(
            table_name,
            query_vector,
            query_text,
            limit,
            threshold,
            skill::ToolSearchOptions::default(),
        )
        .await
    }

    /// Search for tools with explicit ranking options.
    pub async fn search_tools_with_options(
        &self,
        table_name: &str,
        query_vector: &[f32],
        query_text: Option<&str>,
        limit: usize,
        threshold: f32,
        options: skill::ToolSearchOptions,
    ) -> Result<Vec<skill::ToolSearchResult>, VectorStoreError> {
        let mut results_map: std::collections::HashMap<String, skill::ToolSearchResult> =
            std::collections::HashMap::new();
        let table_path = self.table_path(table_name);
        if table_path.exists() {
            if let Ok(dataset) = Dataset::open(table_path.to_string_lossy().as_ref()).await {
                let mut scanner = dataset.scan();
                scanner
                    .project(&[VECTOR_COLUMN, METADATA_COLUMN, CONTENT_COLUMN, "id"])
                    .ok();
                if let Ok(mut stream) = scanner.try_into_stream().await {
                    let query_len = query_vector.len();
                    while let Ok(Some(batch)) = stream.try_next().await {
                        let v_col = batch.column_by_name(VECTOR_COLUMN);
                        let m_col = batch.column_by_name(METADATA_COLUMN);
                        let c_col = batch.column_by_name(CONTENT_COLUMN);
                        let i_col = batch.column_by_name("id");
                        if let (Some(v_c), Some(m_c), Some(c_c), Some(id_c)) =
                            (v_col, m_col, c_col, i_col)
                        {
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
                            let id_arr = id_c
                                .as_any()
                                .downcast_ref::<lance::deps::arrow_array::StringArray>();
                            if let (Some(v_arr), Some(m_arr), Some(c_arr), Some(i_arr)) =
                                (vector_arr, metadata_arr, content_arr, id_arr)
                            {
                                let values = v_arr
                                    .values()
                                    .as_any()
                                    .downcast_ref::<lance::deps::arrow_array::Float32Array>(
                                );
                                if let Some(vals) = values {
                                    for i in 0..batch.num_rows() {
                                        let mut dist_sq = 0.0f32;
                                        let v_len = vals.len() / batch.num_rows();
                                        for j in 0..query_len {
                                            let db_val = if j < v_len {
                                                vals.value(i * v_len + j)
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
                                            let row_id = i_arr.value(i).to_string();
                                            let Some(canonical_tool_name) =
                                                canonical_tool_name_from_result_meta(
                                                    &meta, &row_id,
                                                )
                                            else {
                                                continue;
                                            };
                                            let skill_name = meta
                                                .get("skill_name")
                                                .and_then(|s| s.as_str())
                                                .map(ToString::to_string)
                                                .unwrap_or_else(|| {
                                                    canonical_tool_name
                                                        .split('.')
                                                        .next()
                                                        .unwrap_or("")
                                                        .to_string()
                                                });
                                            results_map.insert(
                                                canonical_tool_name.clone(),
                                                skill::ToolSearchResult {
                                                    name: canonical_tool_name.clone(),
                                                    description: c_arr.value(i).to_string(),
                                                    input_schema: meta
                                                        .get("input_schema")
                                                        .map(skill::normalize_input_schema_value)
                                                        .unwrap_or_else(|| serde_json::json!({})),
                                                    score,
                                                    vector_score: Some(score),
                                                    keyword_score: None,
                                                    skill_name,
                                                    tool_name: canonical_tool_name,
                                                    file_path: meta
                                                        .get("file_path")
                                                        .and_then(|s| s.as_str())
                                                        .unwrap_or("")
                                                        .to_string(),
                                                    keywords: skill::resolve_routing_keywords(
                                                        &meta,
                                                    ),
                                                    intents: skill::resolve_intents(&meta),
                                                    category: meta
                                                        .get("category")
                                                        .and_then(|c| c.as_str())
                                                        .or_else(|| {
                                                            meta.get("skill_name")
                                                                .and_then(|s| s.as_str())
                                                        })
                                                        .unwrap_or("")
                                                        .to_string(),
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
            let mut vector_scores: Vec<(String, f32)> = results_map
                .iter()
                .map(|(n, r)| (n.clone(), r.score))
                .collect();
            vector_scores.sort_by(|a, b| b.1.total_cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
            let kw_hits = self
                .keyword_search(table_name, text, limit * 2)
                .await
                .unwrap_or_default();
            let fused = apply_weighted_rrf(
                vector_scores,
                kw_hits.clone(),
                keyword::RRF_K,
                keyword::SEMANTIC_WEIGHT,
                keyword::KEYWORD_WEIGHT,
                text,
            );
            let mut new_map = std::collections::HashMap::new();
            let kw_lookup: std::collections::HashMap<String, skill::ToolSearchResult> = kw_hits
                .into_iter()
                .map(|r| (r.tool_name.clone(), r))
                .collect();
            let query_parts = normalize_query_terms(text);
            let file_discovery_intent = query_parts.iter().any(|part| {
                matches!(
                    part.as_str(),
                    "find" | "list" | "file" | "files" | "directory" | "folder" | "path" | "glob"
                ) || part.starts_with("*.")
            });

            for f in fused {
                if let Some(mut tool) = results_map
                    .get(&f.tool_name)
                    .cloned()
                    .or_else(|| kw_lookup.get(&f.tool_name).cloned())
                {
                    tool.score = f.rrf_score;
                    if options.rerank {
                        let mut rerank_bonus = tool_metadata_alignment_boost(&tool, &query_parts);
                        if file_discovery_intent {
                            if tool.tool_name == "advanced_tools.smart_find" {
                                rerank_bonus += 0.70;
                            } else if tool_file_discovery_match(&tool) {
                                rerank_bonus += 0.30;
                            }
                        }
                        tool.score += rerank_bonus;
                    }
                    tool.vector_score = Some(f.vector_score);
                    tool.keyword_score = Some(f.keyword_score);
                    new_map.insert(f.tool_name, tool);
                }
            }
            results_map = new_map;
        }
        let mut res: Vec<_> = results_map.into_values().collect();
        if threshold > 0.0 {
            res.retain(|r| r.score >= threshold);
        }
        res.sort_by(|a, b| {
            b.score
                .total_cmp(&a.score)
                .then_with(|| a.tool_name.cmp(&b.tool_name))
        });
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
                                    .map(skill::normalize_input_schema_value)
                                    .unwrap_or_else(|| serde_json::json!({})),
                                score: 1.0,
                                vector_score: None,
                                keyword_score: None,
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
                                keywords: skill::resolve_routing_keywords(&meta),
                                intents: skill::resolve_intents(&meta),
                                category: meta
                                    .get("category")
                                    .and_then(|c| c.as_str())
                                    .or_else(|| meta.get("skill_name").and_then(|s| s.as_str()))
                                    .unwrap_or("")
                                    .to_string(),
                            });
                        }
                    }
                }
            }
        }
        Ok(tools)
    }
}

fn normalize_query_terms(query: &str) -> Vec<String> {
    query
        .to_lowercase()
        .split(|c: char| !(c.is_ascii_alphanumeric() || c == '*' || c == '.' || c == '_'))
        .filter(|t| !t.is_empty())
        .map(ToString::to_string)
        .collect()
}

fn canonical_tool_name_from_result_meta(meta: &serde_json::Value, row_id: &str) -> Option<String> {
    let skill_name = meta
        .get("skill_name")
        .and_then(|s| s.as_str())
        .map(str::trim)
        .unwrap_or("");
    let tool_name = meta
        .get("tool_name")
        .and_then(|s| s.as_str())
        .map(str::trim)
        .unwrap_or("");
    if skill::is_routable_tool_name(tool_name) && tool_name.contains('.') {
        return Some(tool_name.to_string());
    }
    if !skill_name.is_empty() && skill::is_routable_tool_name(tool_name) {
        let candidate = format!("{skill_name}.{tool_name}");
        if skill::is_routable_tool_name(&candidate) {
            return Some(candidate);
        }
    }

    let command = meta
        .get("command")
        .and_then(|s| s.as_str())
        .map(str::trim)
        .unwrap_or("");
    if !skill_name.is_empty() && !command.is_empty() {
        let candidate = format!("{skill_name}.{command}");
        if skill::is_routable_tool_name(&candidate) {
            return Some(candidate);
        }
    }

    if skill::is_routable_tool_name(command) {
        return Some(command.to_string());
    }
    if skill::is_routable_tool_name(row_id) {
        return Some(row_id.to_string());
    }
    None
}

fn tool_metadata_alignment_boost(tool: &skill::ToolSearchResult, query_parts: &[String]) -> f32 {
    if query_parts.is_empty() {
        return 0.0;
    }

    let mut boost = 0.0f32;
    let category = tool.category.to_lowercase();
    let description = tool.description.to_lowercase();

    for term in query_parts {
        if term.len() <= 2 {
            continue;
        }
        if !category.is_empty() && category.contains(term) {
            boost += 0.05;
        }
        if description.contains(term) {
            boost += 0.03;
        }
        if tool
            .keywords
            .iter()
            .any(|k| k.to_lowercase().contains(term))
        {
            boost += 0.07;
        }
        if tool.intents.iter().any(|i| i.to_lowercase().contains(term)) {
            boost += 0.08;
        }
    }

    boost.min(0.50)
}

fn tool_file_discovery_match(tool: &skill::ToolSearchResult) -> bool {
    let tool_name = tool.tool_name.to_lowercase();
    if tool_name == "advanced_tools.smart_find" {
        return true;
    }

    let category = tool.category.to_lowercase();
    let description = tool.description.to_lowercase();
    let terms = [
        "find",
        "file",
        "files",
        "directory",
        "folder",
        "path",
        "glob",
    ];
    terms.iter().any(|t| {
        category.contains(t)
            || description.contains(t)
            || tool.keywords.iter().any(|k| k.to_lowercase().contains(t))
            || tool.intents.iter().any(|i| i.to_lowercase().contains(t))
    })
}
