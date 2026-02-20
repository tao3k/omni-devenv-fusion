use std::path::Path;

#[allow(clippy::missing_errors_doc, clippy::doc_markdown)]
impl VectorStore {
    #[allow(clippy::unused_self)]
    fn scan_unique_skill_tools(
        &self,
        base_path: &str,
    ) -> Result<Vec<omni_scanner::ToolRecord>, VectorStoreError> {
        let skill_scanner = SkillScanner::new();
        let script_scanner = ToolsScanner::new();
        let resource_scanner = ResourceScanner::new();
        let skills_path = Path::new(base_path);
        if !skills_path.exists() {
            log::warn!("Skills path does not exist: {}", skills_path.display());
            return Ok(vec![]);
        }

        let metadatas = skill_scanner
            .scan_all(skills_path, None)
            .map_err(|e| VectorStoreError::General(e.to_string()))?;
        log::info!("Found {} skill manifests", metadatas.len());

        let mut tools_map = std::collections::HashMap::new();
        for metadata in &metadatas {
            let skill_path = skills_path.join(&metadata.skill_name);
            let mut tools = script_scanner
                .scan_scripts(
                    &skill_path.join("scripts"),
                    &metadata.skill_name,
                    &metadata.routing_keywords,
                    &metadata.intents,
                )
                .map_err(|e| VectorStoreError::General(e.to_string()))?;

            // Scan for @skill_resource decorated functions and convert to tools
            let resources: Vec<ResourceRecord> =
                match resource_scanner.scan(&skill_path.join("scripts"), &metadata.skill_name) {
                    Ok(r) => r,
                    Err(e) => return Err(VectorStoreError::General(e.to_string())),
                };

            // Convert resources to tools with resource_uri set
            for resource in resources {
                let resource_tool = ToolRecord {
                    tool_name: format!("{}.{}", resource.skill_name, resource.name),
                    description: resource.description.clone(),
                    skill_name: resource.skill_name.clone(),
                    file_path: resource.file_path.clone(),
                    function_name: resource.function_name.clone(),
                    execution_mode: "resource".to_string(),
                    keywords: vec![resource.skill_name.clone(), resource.name.clone()],
                    intents: metadata.intents.clone(),
                    file_hash: resource.file_hash.clone(),
                    input_schema: "{}".to_string(),
                    docstring: resource.description.clone(),
                    category: "resource".to_string(),
                    annotations: ToolAnnotations::default(),
                    parameters: vec![],
                    skill_tools_refers: vec![],
                    resource_uri: resource.resource_uri,
                };
                tools.push(resource_tool);
            }

            log::debug!(
                "Skill '{}': found {} tools (+ {} resources)",
                metadata.skill_name,
                tools.len(),
                tools.iter().filter(|t| !t.resource_uri.is_empty()).count()
            );

            // Fill skill_tools_refers from markdown front matter (references/*.md for_tools list), not from decorator
            let entry = skill_scanner.build_index_entry(metadata.clone(), &tools, &skill_path);
            for t in &mut tools {
                t.skill_tools_refers = entry
                    .references
                    .iter()
                    .filter(|r| r.applies_to_tool(&t.tool_name))
                    .map(|r| r.ref_name.clone())
                    .collect();
            }
            for tool in tools {
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
        log::info!("Indexing skills from: {base_path}");

        let tools = self.scan_unique_skill_tools(base_path)?;
        log::info!("Total tools to index: {}", tools.len());
        if tools.is_empty() {
            log::warn!(
                "index_skill_tools: scan returned 0 tools from {base_path}; keeping existing table"
            );
            return Ok(());
        }

        // Drop only when we have tools to write (avoids empty table on scan failure)
        let drop_result = self.drop_table(table_name).await;
        log::debug!("drop_table result: {drop_result:?}");
        if let Err(e) = self.enable_keyword_index() {
            log::warn!("Could not re-enable keyword index after drop: {e}");
        }

        self.add(table_name, tools).await?;
        if let Err(e) = self
            .create_scalar_index(table_name, SKILL_NAME_COLUMN, ScalarIndexType::BTree)
            .await
        {
            log::debug!("Scalar index skill_name skipped: {e}");
        }
        if let Err(e) = self
            .create_scalar_index(table_name, CATEGORY_COLUMN, ScalarIndexType::Bitmap)
            .await
        {
            log::debug!("Scalar index category skipped: {e}");
        }
        log::info!("Successfully indexed tools for table: {table_name}");
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
            // Do NOT drop: preserve existing data. Empty scan may mean wrong path, transient
            // failure, or no skills yet. Dropping would leave user with empty skill list.
            log::warn!(
                "index_skill_tools_dual: scan returned 0 tools from {base_path}; keeping existing table"
            );
            return Ok((0, 0));
        }

        self.drop_table(skills_table).await.ok();
        // Re-enable keyword index after drop_table cleared it
        if let Err(e) = self.enable_keyword_index() {
            log::warn!("Could not re-enable keyword index after drop: {e}");
        }
        self.add(skills_table, tools.clone()).await?;
        let _ = self
            .create_scalar_index(skills_table, SKILL_NAME_COLUMN, ScalarIndexType::BTree)
            .await;
        let _ = self
            .create_scalar_index(skills_table, CATEGORY_COLUMN, ScalarIndexType::Bitmap)
            .await;
        let skills_count = self.count(skills_table).await? as usize;

        if router_table == skills_table {
            return Ok((skills_count, skills_count));
        }

        self.drop_table(router_table).await.ok();
        // Re-enable keyword index after drop_table cleared it
        if let Err(e) = self.enable_keyword_index() {
            log::warn!("Could not re-enable keyword index after drop: {e}");
        }
        self.add(router_table, tools).await?;
        let _ = self
            .create_scalar_index(router_table, SKILL_NAME_COLUMN, ScalarIndexType::BTree)
            .await;
        let _ = self
            .create_scalar_index(router_table, CATEGORY_COLUMN, ScalarIndexType::Bitmap)
            .await;
        let router_count = self.count(router_table).await? as usize;

        Ok((skills_count, router_count))
    }

    /// Scan skill tools without indexing them.
    #[allow(clippy::unused_self)]
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

    /// List all tools that are also MCP resources (have non-empty `resource_uri` in metadata).
    pub async fn list_all_resources(&self, table_name: &str) -> Result<String, VectorStoreError> {
        use crate::ops::column_read::get_utf8_at;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok("[]".to_string());
        }
        let dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let schema = dataset.schema();
        if schema.field(METADATA_COLUMN).is_none() {
            return Ok("[]".to_string());
        }
        let mut scanner = dataset.scan();
        scanner.project(&["id", "content", METADATA_COLUMN, "skill_name", "tool_name"])?;
        let mut stream = scanner.try_into_stream().await?;
        let mut resources = Vec::new();
        while let Some(batch) = stream.try_next().await? {
            use lance::deps::arrow_array::Array;
            use lance::deps::arrow_array::StringArray;

            let id_col = batch.column_by_name("id");
            let content_col = batch.column_by_name("content");
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let skill_col = batch.column_by_name("skill_name");
            let tool_col = batch.column_by_name("tool_name");

            let m_arr =
                metadata_col.and_then(|c| c.as_any().downcast_ref::<StringArray>().cloned());

            if let (Some(ids), Some(contents)) = (id_col, content_col) {
                let id_arr = ids.as_any().downcast_ref::<StringArray>();
                let content_arr = contents.as_any().downcast_ref::<StringArray>();

                for i in 0..batch.num_rows() {
                    // Only include rows with non-empty resource_uri
                    let resource_uri = m_arr.as_ref().and_then(|ma| {
                        if ma.is_null(i) {
                            return None;
                        }
                        let meta_str = ma.value(i);
                        serde_json::from_str::<serde_json::Value>(meta_str)
                            .ok()
                            .and_then(|v| {
                                v.get("resource_uri")
                                    .and_then(|u| u.as_str())
                                    .filter(|s| !s.is_empty())
                                    .map(String::from)
                            })
                    });

                    let Some(uri) = resource_uri else {
                        continue;
                    };

                    let id = id_arr.map_or(String::new(), |arr| arr.value(i).to_string());
                    let content = content_arr.map_or(String::new(), |arr| arr.value(i).to_string());
                    let skill_name = skill_col.map_or(String::new(), |c| get_utf8_at(c, i));
                    let tool_name = tool_col.map_or(String::new(), |c| get_utf8_at(c, i));

                    resources.push(serde_json::json!({
                        "id": id,
                        "resource_uri": uri,
                        "description": content,
                        "skill_name": skill_name,
                        "tool_name": tool_name,
                    }));
                }
            }
        }
        serde_json::to_string(&resources).map_err(|e| VectorStoreError::General(e.to_string()))
    }

    /// Infer (skill_name, tool_name) from canonical id (e.g. "knowledge.ingest_document" -> ("knowledge", "ingest_document")).
    /// Ensures list_all_tools output always has valid skill_name/tool_name for discovery.
    fn infer_skill_tool_from_id(id: &str) -> (String, String) {
        let id = id.trim();
        if id.is_empty() {
            return (String::from("unknown"), String::from("unknown"));
        }
        if let Some(dot) = id.find('.') {
            let (skill, tool) = id.split_at(dot);
            let tool = tool.trim_start_matches('.');
            (
                skill.to_string(),
                if tool.is_empty() {
                    String::from("unknown")
                } else {
                    tool.to_string()
                },
            )
        } else {
            (id.to_string(), String::from("unknown"))
        }
    }

    /// List all tools in a specific table.
    /// When `source_filter` is set (e.g. "2601.03192.pdf"), applies predicate pushdown:
    /// `metadata LIKE '%{source}%'` so only matching rows are scanned (reduces I/O ~98% for full_document).
    #[allow(clippy::too_many_lines)]
    pub async fn list_all_tools(
        &self,
        table_name: &str,
        source_filter: Option<&str>,
    ) -> Result<String, VectorStoreError> {
        use crate::ops::column_read::get_utf8_at;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok("[]".to_string());
        }
        let dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let mut scanner = dataset.scan();
        // Predicate pushdown: filter by metadata.source when listing by document (full_document recall)
        if let Some(s) = source_filter.filter(|x| !x.is_empty()) {
            let arrow_schema = lance::deps::arrow_schema::Schema::from(dataset.schema());
            if arrow_schema.field_with_name("metadata").is_ok() {
                let escaped = s.replace('\'', "''");
                let filter_expr = format!("metadata LIKE '%{escaped}%'");
                if let Err(e) = scanner.filter(&filter_expr) {
                    log::debug!("list_all_tools source_filter failed (fallback to full scan): {e}");
                }
            }
        }
        // Include metadata column when present (e.g. knowledge_chunks with source, chunk_index)
        let arrow_schema = lance::deps::arrow_schema::Schema::from(dataset.schema());
        let has_metadata = arrow_schema.field_with_name("metadata").is_ok();
        let project_cols: Vec<&str> = if has_metadata {
            vec![
                "id",
                "content",
                "skill_name",
                "category",
                "tool_name",
                "file_path",
                "metadata",
            ]
        } else {
            vec![
                "id",
                "content",
                "skill_name",
                "category",
                "tool_name",
                "file_path",
            ]
        };
        scanner.project(&project_cols)?;
        let mut stream = scanner.try_into_stream().await?;
        let mut tools = Vec::new();
        while let Some(batch) = stream.try_next().await? {
            use lance::deps::arrow_array::Array;
            use lance::deps::arrow_array::StringArray;

            let id_col = batch.column_by_name("id");
            let content_col = batch.column_by_name("content");
            let skill_name_col = batch.column_by_name("skill_name");
            let category_col = batch.column_by_name("category");
            let tool_name_col = batch.column_by_name("tool_name");
            let file_path_col = batch.column_by_name("file_path");
            let metadata_col = batch.column_by_name("metadata");

            if let (Some(ids), Some(contents)) = (id_col, content_col) {
                let id_arr = ids.as_any().downcast_ref::<StringArray>();
                let content_arr = contents.as_any().downcast_ref::<StringArray>();

                for i in 0..batch.num_rows() {
                    let id = id_arr.map_or(String::new(), |arr| arr.value(i).to_string());
                    let content = content_arr.map_or(String::new(), |arr| arr.value(i).to_string());

                    // Use stored metadata when present (e.g. knowledge_chunks), else synthetic.
                    // Always prefer non-empty column values over stored JSON to avoid null propagation.
                    let sk = skill_name_col.map_or(String::new(), |c| get_utf8_at(c, i));
                    let cat = category_col.map_or(String::new(), |c| get_utf8_at(c, i));
                    let tn = tool_name_col.map_or(String::new(), |c| get_utf8_at(c, i));
                    let fp = file_path_col.map_or(String::new(), |c| get_utf8_at(c, i));
                    let mut metadata: serde_json::Value = if let Some(meta_col) = metadata_col {
                        let raw = get_utf8_at(meta_col.as_ref(), i);
                        if raw.is_empty() {
                            serde_json::json!({
                                "id": id,
                                "content": content,
                                "skill_name": sk,
                                "category": cat,
                                "tool_name": tn,
                                "file_path": fp,
                            })
                        } else {
                            serde_json::from_str(&raw).unwrap_or_else(
                                |_| serde_json::json!({ "id": id, "content": content }),
                            )
                        }
                    } else {
                        serde_json::json!({
                            "id": id,
                            "content": content,
                            "skill_name": sk,
                            "category": cat,
                            "tool_name": tn,
                            "file_path": fp,
                        })
                    };
                    // Override with column values when non-empty (stored JSON may have nulls).
                    // Only index when metadata is an object; knowledge_chunks may have metadata as string.
                    if let Some(obj) = metadata.as_object_mut() {
                        if !sk.is_empty() {
                            obj.insert("skill_name".to_string(), serde_json::json!(sk));
                        }
                        if !tn.is_empty() {
                            obj.insert("tool_name".to_string(), serde_json::json!(tn));
                        }
                        if !fp.is_empty() {
                            obj.insert("file_path".to_string(), serde_json::json!(fp));
                        }
                    }
                    // Infer from id when skill_name/tool_name still null or empty (contract guarantee)
                    let meta_obj = metadata.as_object_mut();
                    if let Some(obj) = meta_obj {
                        let sn = obj
                            .get("skill_name")
                            .and_then(|v| v.as_str())
                            .unwrap_or("")
                            .to_string();
                        let tool = obj
                            .get("tool_name")
                            .and_then(|v| v.as_str())
                            .unwrap_or("")
                            .to_string();
                        if sn.is_empty() || tool.is_empty() {
                            let (inferred_skill, inferred_tool) =
                                Self::infer_skill_tool_from_id(&id);
                            if sn.is_empty() {
                                obj.insert(
                                    "skill_name".to_string(),
                                    serde_json::json!(inferred_skill),
                                );
                            }
                            if tool.is_empty() {
                                obj.insert(
                                    "tool_name".to_string(),
                                    serde_json::json!(inferred_tool),
                                );
                            }
                        }
                    }
                    tools.push(
                        serde_json::json!({ "id": id, "content": content, "metadata": metadata }),
                    );
                }
            }
        }
        // Deduplicate by (source, chunk_index) when metadata has chunk_index (e.g. knowledge_chunks)
        let tools = dedup_by_source_chunk_index(tools);
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
            None,
        )
        .await
    }

    /// Search for tools with explicit ranking options.
    /// When `where_filter` is set (e.g. `skill_name = 'git'`), only rows matching the predicate are scanned.
    #[allow(
        clippy::too_many_arguments,
        clippy::too_many_lines,
        clippy::collapsible_if
    )]
    pub async fn search_tools_with_options(
        &self,
        table_name: &str,
        query_vector: &[f32],
        query_text: Option<&str>,
        limit: usize,
        threshold: f32,
        options: skill::ToolSearchOptions,
        where_filter: Option<&str>,
    ) -> Result<Vec<skill::ToolSearchResult>, VectorStoreError> {
        let mut results_map: std::collections::HashMap<String, skill::ToolSearchResult> =
            std::collections::HashMap::new();
        let table_path = self.table_path(table_name);
        if table_path.exists() {
            if let Ok(dataset) = self
                .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
                .await
            {
                let schema = dataset.schema();
                let has_metadata = schema.field(METADATA_COLUMN).is_some();
                let project_cols: Vec<&str> = if has_metadata {
                    vec![
                        VECTOR_COLUMN,
                        METADATA_COLUMN,
                        CONTENT_COLUMN,
                        "id",
                        crate::SKILL_NAME_COLUMN,
                        crate::CATEGORY_COLUMN,
                        crate::TOOL_NAME_COLUMN,
                        crate::FILE_PATH_COLUMN,
                        crate::ROUTING_KEYWORDS_COLUMN,
                        crate::INTENTS_COLUMN,
                    ]
                } else {
                    vec![
                        VECTOR_COLUMN,
                        CONTENT_COLUMN,
                        "id",
                        crate::SKILL_NAME_COLUMN,
                        crate::CATEGORY_COLUMN,
                        crate::TOOL_NAME_COLUMN,
                        crate::FILE_PATH_COLUMN,
                        crate::ROUTING_KEYWORDS_COLUMN,
                        crate::INTENTS_COLUMN,
                    ]
                };
                let mut scanner = dataset.scan();
                scanner.project(&project_cols).ok();
                let skill_filter_from_where =
                    where_filter.and_then(parse_skill_name_from_where_filter);
                if let Some(f) = where_filter {
                    if skill_filter_from_where.is_none() {
                        scanner.filter(f).map_err(|e| {
                            VectorStoreError::General(format!("Invalid where_filter: {e}"))
                        })?;
                    }
                }
                if let Ok(mut stream) = scanner.try_into_stream().await {
                    while let Ok(Some(batch)) = stream.try_next().await {
                        let v_col = batch.column_by_name(VECTOR_COLUMN);
                        let m_col = batch.column_by_name(METADATA_COLUMN);
                        let c_col = batch.column_by_name(CONTENT_COLUMN);
                        let id_col = batch.column_by_name("id");
                        let sk_col = batch.column_by_name(crate::SKILL_NAME_COLUMN);
                        let cat_col = batch.column_by_name(crate::CATEGORY_COLUMN);
                        let tn_col = batch.column_by_name(crate::TOOL_NAME_COLUMN);
                        let fp_col = batch.column_by_name(crate::FILE_PATH_COLUMN);
                        let rk_col = batch.column_by_name(crate::ROUTING_KEYWORDS_COLUMN);
                        let intent_col = batch.column_by_name(crate::INTENTS_COLUMN);
                        if let (Some(v_c), Some(c_c), Some(id_c)) = (v_col, c_col, id_col) {
                            use lance::deps::arrow_array::Array;
                            let vector_arr =
                                v_c.as_any()
                                    .downcast_ref::<lance::deps::arrow_array::FixedSizeListArray>();
                            let metadata_arr = m_col.and_then(|c| {
                                c.as_any()
                                    .downcast_ref::<lance::deps::arrow_array::StringArray>()
                            });
                            let content_arr = c_c
                                .as_any()
                                .downcast_ref::<lance::deps::arrow_array::StringArray>();
                            let id_arr = id_c
                                .as_any()
                                .downcast_ref::<lance::deps::arrow_array::StringArray>();
                            // Use get_utf8_at so Utf8 and Dictionary (e.g. TOOL_NAME) columns both work.
                            let str_at_col = |col: Option<
                                &std::sync::Arc<dyn lance::deps::arrow_array::Array>,
                            >,
                                              idx: usize|
                             -> String {
                                col.map(|c| crate::ops::get_utf8_at(c.as_ref(), idx))
                                    .unwrap_or_default()
                            };
                            if let (Some(v_arr), Some(c_arr), Some(i_arr)) =
                                (vector_arr, content_arr, id_arr)
                            {
                                let values = v_arr
                                    .values()
                                    .as_any()
                                    .downcast_ref::<lance::deps::arrow_array::Float32Array>(
                                );
                                if let Some(vals) = values {
                                    for i in 0..batch.num_rows() {
                                        let sk = sk_col
                                            .map(|c| crate::ops::get_utf8_at(c.as_ref(), i))
                                            .unwrap_or_default();
                                        if let Some(ref filter_skill) = skill_filter_from_where {
                                            if sk != filter_skill.as_str() {
                                                continue;
                                            }
                                        }
                                        let cat = cat_col
                                            .map(|c| crate::ops::get_utf8_at(c.as_ref(), i))
                                            .unwrap_or_default();
                                        let mut dist_sq = 0.0f32;
                                        let v_len = vals.len() / batch.num_rows();
                                        for (j, query_val) in
                                            query_vector.iter().copied().enumerate()
                                        {
                                            let db_val = if j < v_len {
                                                vals.value(i * v_len + j)
                                            } else {
                                                0.0
                                            };
                                            let diff = db_val - query_val;
                                            dist_sq += diff * diff;
                                        }
                                        let score = 1.0 / (1.0 + dist_sq.sqrt());
                                        let row_id = i_arr.value(i).to_string();
                                        let (
                                            canonical_tool_name,
                                            skill_name,
                                            file_path,
                                            routing_keywords,
                                            intents,
                                            category,
                                            input_schema,
                                        ) = if let Some(m_arr) = metadata_arr {
                                            if m_arr.is_null(i) {
                                                let tn = str_at_col(tn_col, i);
                                                let canon =
                                                    if tn.is_empty() { row_id.clone() } else { tn };
                                                let skill = if sk.is_empty() {
                                                    canon
                                                        .split('.')
                                                        .next()
                                                        .unwrap_or("")
                                                        .to_string()
                                                } else {
                                                    sk
                                                };
                                                let rk = rk_col
                                                    .map(|c| {
                                                        crate::ops::get_routing_keywords_at(
                                                            c.as_ref(),
                                                            i,
                                                        )
                                                    })
                                                    .unwrap_or_default();
                                                let inv = intent_col
                                                    .map(|c| {
                                                        crate::ops::get_intents_at(c.as_ref(), i)
                                                    })
                                                    .unwrap_or_default();
                                                let meta = serde_json::json!({ "routing_keywords": rk.iter().map(|s| serde_json::Value::String(s.clone())).collect::<Vec<_>>(), "intents": inv.iter().map(|s| serde_json::Value::String(s.clone())).collect::<Vec<_>>() });
                                                (
                                                    canon.clone(),
                                                    skill.clone(),
                                                    str_at_col(fp_col, i),
                                                    skill::resolve_routing_keywords(&meta),
                                                    skill::resolve_intents(&meta),
                                                    { if cat.is_empty() { skill } else { cat } },
                                                    serde_json::json!({}),
                                                )
                                            } else if let Ok(meta) =
                                                serde_json::from_str::<serde_json::Value>(
                                                    m_arr.value(i),
                                                )
                                            {
                                                if meta.get("type").and_then(|t| t.as_str())
                                                    != Some("command")
                                                {
                                                    continue;
                                                }
                                                let Some(canon) =
                                                    canonical_tool_name_from_result_meta(
                                                        &meta, &row_id,
                                                    )
                                                else {
                                                    continue;
                                                };
                                                let skill = meta
                                                    .get("skill_name")
                                                    .and_then(|s| s.as_str())
                                                    .map_or_else(
                                                        || {
                                                            canon
                                                                .split('.')
                                                                .next()
                                                                .unwrap_or("")
                                                                .to_string()
                                                        },
                                                        String::from,
                                                    );
                                                let file_path = meta
                                                    .get("file_path")
                                                    .and_then(|s| s.as_str())
                                                    .unwrap_or("")
                                                    .to_string();
                                                let rk = skill::resolve_routing_keywords(&meta);
                                                let inv = skill::resolve_intents(&meta);
                                                let cat = meta
                                                    .get("category")
                                                    .and_then(|c| c.as_str())
                                                    .or_else(|| {
                                                        meta.get("skill_name")
                                                            .and_then(|s| s.as_str())
                                                    })
                                                    .unwrap_or("")
                                                    .to_string();
                                                let schema = meta.get("input_schema").map_or_else(
                                                    || serde_json::json!({}),
                                                    skill::normalize_input_schema_value,
                                                );
                                                (canon, skill, file_path, rk, inv, cat, schema)
                                            } else {
                                                continue;
                                            }
                                        } else {
                                            let tn = str_at_col(tn_col, i);
                                            let canon =
                                                if tn.is_empty() { row_id.clone() } else { tn };
                                            let skill = if sk.is_empty() {
                                                canon.split('.').next().unwrap_or("").to_string()
                                            } else {
                                                sk
                                            };
                                            let rk = rk_col
                                                .map(|c| {
                                                    crate::ops::get_routing_keywords_at(
                                                        c.as_ref(),
                                                        i,
                                                    )
                                                })
                                                .unwrap_or_default();
                                            let inv = intent_col
                                                .map(|c| crate::ops::get_intents_at(c.as_ref(), i))
                                                .unwrap_or_default();
                                            let rk_json = serde_json::json!({ "routing_keywords": rk.iter().map(|s| serde_json::Value::String(s.clone())).collect::<Vec<_>>(), "intents": inv.iter().map(|s| serde_json::Value::String(s.clone())).collect::<Vec<_>>() });
                                            (
                                                canon.clone(),
                                                skill.clone(),
                                                str_at_col(fp_col, i),
                                                skill::resolve_routing_keywords(&rk_json),
                                                skill::resolve_intents(&rk_json),
                                                { if cat.is_empty() { skill } else { cat } },
                                                serde_json::json!({}),
                                            )
                                        };
                                        let full_name = if row_id.contains('.') {
                                            row_id.clone()
                                        } else {
                                            canonical_tool_name.clone()
                                        };
                                        if !skill::is_routable_tool_name(&full_name) {
                                            continue;
                                        }
                                        results_map.insert(
                                            canonical_tool_name.clone(),
                                            skill::ToolSearchResult {
                                                name: full_name.clone(),
                                                description: c_arr.value(i).to_string(),
                                                input_schema,
                                                score,
                                                vector_score: Some(score),
                                                keyword_score: None,
                                                skill_name,
                                                tool_name: full_name,
                                                file_path,
                                                routing_keywords,
                                                intents,
                                                category,
                                                parameters: vec![],
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
                options.semantic_weight.unwrap_or(keyword::SEMANTIC_WEIGHT),
                options.keyword_weight.unwrap_or(keyword::KEYWORD_WEIGHT),
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

    #[allow(clippy::too_many_lines, clippy::collapsible_if)]
    async fn get_tools_by_skill_internal(
        &self,
        table_name: &str,
        skill_filter: Option<&str>,
    ) -> Result<Vec<skill::ToolSearchResult>, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(Vec::new());
        }
        let dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let schema = dataset.schema();
        let has_metadata = schema.field(METADATA_COLUMN).is_some();
        let project_cols: Vec<&str> = if has_metadata {
            vec![
                METADATA_COLUMN,
                CONTENT_COLUMN,
                crate::SKILL_NAME_COLUMN,
                crate::TOOL_NAME_COLUMN,
                crate::FILE_PATH_COLUMN,
                crate::ROUTING_KEYWORDS_COLUMN,
                crate::INTENTS_COLUMN,
                crate::CATEGORY_COLUMN,
            ]
        } else {
            vec![
                CONTENT_COLUMN,
                crate::SKILL_NAME_COLUMN,
                crate::TOOL_NAME_COLUMN,
                crate::FILE_PATH_COLUMN,
                crate::ROUTING_KEYWORDS_COLUMN,
                crate::INTENTS_COLUMN,
                crate::CATEGORY_COLUMN,
            ]
        };
        let mut scanner = dataset.scan();
        scanner.project(&project_cols)?;

        if let Some(skill) = skill_filter {
            scanner.filter(&format!("skill_name = '{skill}'"))?;
        }

        let mut stream = scanner.try_into_stream().await?;
        let mut tools = Vec::new();
        while let Some(batch) = stream.try_next().await? {
            use lance::deps::arrow_array::Array;
            let c_col = batch.column_by_name(CONTENT_COLUMN);
            let m_col = batch.column_by_name(METADATA_COLUMN);
            let sk_col = batch.column_by_name(crate::SKILL_NAME_COLUMN);
            let tn_col = batch.column_by_name(crate::TOOL_NAME_COLUMN);
            let fp_col = batch.column_by_name(crate::FILE_PATH_COLUMN);
            let rk_col = batch.column_by_name(crate::ROUTING_KEYWORDS_COLUMN);
            let in_col = batch.column_by_name(crate::INTENTS_COLUMN);
            let cat_col = batch.column_by_name(crate::CATEGORY_COLUMN);
            let c_arr = c_col.and_then(|c| {
                c.as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>()
            });
            let m_arr = m_col.and_then(|c| {
                c.as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>()
            });
            let str_at_col = |col: Option<&std::sync::Arc<dyn lance::deps::arrow_array::Array>>,
                              idx: usize|
             -> String {
                col.map(|c| crate::ops::get_utf8_at(c.as_ref(), idx))
                    .unwrap_or_default()
            };
            if let Some(ca) = c_arr {
                for i in 0..batch.num_rows() {
                    let sk = sk_col
                        .map(|c| crate::ops::get_utf8_at(c.as_ref(), i))
                        .unwrap_or_default();
                    let cat = cat_col
                        .map(|c| crate::ops::get_utf8_at(c.as_ref(), i))
                        .unwrap_or_default();
                    let (
                        name,
                        skill_name,
                        tool_name,
                        file_path,
                        routing_keywords,
                        intents,
                        category,
                        input_schema,
                    ) = if let Some(ma) = m_arr {
                        if ma.is_null(i) {
                            let tn = str_at_col(tn_col, i);
                            let rk = rk_col
                                .map(|c| crate::ops::get_routing_keywords_at(c.as_ref(), i))
                                .unwrap_or_default();
                            let inv = in_col
                                .map(|c| crate::ops::get_intents_at(c.as_ref(), i))
                                .unwrap_or_default();
                            let rk_json = serde_json::json!({ "routing_keywords": rk.iter().map(|s| serde_json::Value::String(s.clone())).collect::<Vec<_>>(), "intents": inv.iter().map(|s| serde_json::Value::String(s.clone())).collect::<Vec<_>>() });
                            (
                                tn.clone(),
                                sk.clone(),
                                tn,
                                str_at_col(fp_col, i),
                                skill::resolve_routing_keywords(&rk_json),
                                skill::resolve_intents(&rk_json),
                                cat.clone(),
                                serde_json::json!({}),
                            )
                        } else if let Ok(meta) =
                            serde_json::from_str::<serde_json::Value>(ma.value(i))
                        {
                            if meta.get("type").and_then(|t| t.as_str()) != Some("command") {
                                continue;
                            }
                            if let Some(skill) = skill_filter {
                                if meta.get("skill_name").and_then(|s| s.as_str()) != Some(skill) {
                                    continue;
                                }
                            }
                            (
                                meta.get("command")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                meta.get("skill_name")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                meta.get("tool_name")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                meta.get("file_path")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                skill::resolve_routing_keywords(&meta),
                                skill::resolve_intents(&meta),
                                meta.get("category")
                                    .and_then(|c| c.as_str())
                                    .or_else(|| meta.get("skill_name").and_then(|s| s.as_str()))
                                    .unwrap_or("")
                                    .to_string(),
                                meta.get("input_schema").map_or_else(
                                    || serde_json::json!({}),
                                    skill::normalize_input_schema_value,
                                ),
                            )
                        } else {
                            continue;
                        }
                    } else {
                        let tn = str_at_col(tn_col, i);
                        if let Some(skill) = skill_filter {
                            if sk != skill {
                                continue;
                            }
                        }
                        let rk = rk_col
                            .map(|c| crate::ops::get_routing_keywords_at(c.as_ref(), i))
                            .unwrap_or_default();
                        let inv = in_col
                            .map(|c| crate::ops::get_intents_at(c.as_ref(), i))
                            .unwrap_or_default();
                        let rk_json = serde_json::json!({ "routing_keywords": rk.iter().map(|s| serde_json::Value::String(s.clone())).collect::<Vec<_>>(), "intents": inv.iter().map(|s| serde_json::Value::String(s.clone())).collect::<Vec<_>>() });
                        (
                            tn.clone(),
                            sk.clone(),
                            tn,
                            str_at_col(fp_col, i),
                            skill::resolve_routing_keywords(&rk_json),
                            skill::resolve_intents(&rk_json),
                            cat.clone(),
                            serde_json::json!({}),
                        )
                    };
                    tools.push(skill::ToolSearchResult {
                        name,
                        description: ca.value(i).to_string(),
                        input_schema,
                        score: 1.0,
                        vector_score: None,
                        keyword_score: None,
                        skill_name,
                        tool_name,
                        file_path,
                        routing_keywords,
                        intents,
                        category,
                        parameters: vec![],
                    });
                }
            }
        }
        Ok(tools)
    }
}

/// Deduplicate `list_all_tools` rows by (`metadata.source`, `metadata.chunk_index`).
/// Only applied when at least one row has numeric `metadata.chunk_index` (e.g. `knowledge_chunks`).
/// Keeps first occurrence per (`source`, `chunk_index`) and sorts by (`source`, `chunk_index`).
fn dedup_by_source_chunk_index(tools: Vec<serde_json::Value>) -> Vec<serde_json::Value> {
    use std::collections::HashSet;
    let has_chunk_index = tools.iter().any(|t| {
        t.get("metadata")
            .and_then(|m| m.get("chunk_index"))
            .and_then(serde_json::Value::as_i64)
            .is_some()
    });
    if !has_chunk_index {
        return tools;
    }
    let mut seen: HashSet<(String, i64)> = HashSet::new();
    let mut out: Vec<serde_json::Value> = Vec::new();
    for t in tools {
        let meta = t.get("metadata");
        let source = meta
            .and_then(|m| m.get("source"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or("")
            .to_string();
        let idx = meta
            .and_then(|m| m.get("chunk_index"))
            .and_then(serde_json::Value::as_i64)
            .unwrap_or(0);
        if seen.insert((source.clone(), idx)) {
            out.push(t);
        }
    }
    out.sort_by(|a, b| {
        let (sa, ia) = (
            a.get("metadata")
                .and_then(|m| m.get("source"))
                .and_then(serde_json::Value::as_str)
                .unwrap_or(""),
            a.get("metadata")
                .and_then(|m| m.get("chunk_index"))
                .and_then(serde_json::Value::as_i64)
                .unwrap_or(0),
        );
        let (sb, ib) = (
            b.get("metadata")
                .and_then(|m| m.get("source"))
                .and_then(serde_json::Value::as_str)
                .unwrap_or(""),
            b.get("metadata")
                .and_then(|m| m.get("chunk_index"))
                .and_then(serde_json::Value::as_i64)
                .unwrap_or(0),
        );
        (sa, ia).cmp(&(sb, ib))
    });
    out
}

/// Parse `skill_name = 'value'` from a `where_filter` string for Rust-side filtering
/// (Lance filter on dictionary columns can return no rows).
fn parse_skill_name_from_where_filter(where_filter: &str) -> Option<String> {
    let prefix = "skill_name = '";
    let f = where_filter.trim();
    if !f.starts_with(prefix) {
        return None;
    }
    let rest = f.get(prefix.len()..)?;
    let mut end = 0usize;
    let mut it = rest.char_indices();
    while let Some((i, c)) = it.next() {
        if c == '\'' {
            if rest.get(i + 1..)?.starts_with('\'') {
                it.next();
                end = i + 2;
                continue;
            }
            end = i;
            break;
        }
        end = i + c.len_utf8();
    }
    Some(rest[..end].replace("''", "'"))
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
        .map_or("", str::trim);
    let tool_name = meta
        .get("tool_name")
        .and_then(|s| s.as_str())
        .map_or("", str::trim);
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
        .map_or("", str::trim);
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
            .routing_keywords
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
            || tool
                .routing_keywords
                .iter()
                .any(|k| k.to_lowercase().contains(t))
            || tool.intents.iter().any(|i| i.to_lowercase().contains(t))
    })
}
