use super::super::{
    LinkGraphHit, LinkGraphIndex, LinkGraphScope, LinkGraphSearchOptions, ParsedLinkGraphQuery,
    parse_search_query,
};
use crate::link_graph::{LinkGraphDisplayHit, LinkGraphPlannedSearchPayload};

impl LinkGraphIndex {
    /// Parse query directives/options once and execute the resulting search plan.
    #[must_use]
    pub fn search_planned(
        &self,
        query: &str,
        limit: usize,
        base_options: LinkGraphSearchOptions,
    ) -> (ParsedLinkGraphQuery, Vec<LinkGraphHit>) {
        let parsed = parse_search_query(query, base_options);
        let rows = self.execute_search(&parsed.query, limit, parsed.options.clone());
        (parsed, rows)
    }

    /// Parse/execute search and return canonical external payload shape.
    #[must_use]
    pub fn search_planned_payload(
        &self,
        query: &str,
        limit: usize,
        base_options: LinkGraphSearchOptions,
    ) -> LinkGraphPlannedSearchPayload {
        let (parsed, rows) = self.search_planned(query, limit, base_options);
        let hit_count = rows.len();
        let section_hit_count = rows
            .iter()
            .filter(|row| {
                row.best_section
                    .as_deref()
                    .map(str::trim)
                    .is_some_and(|value| !value.is_empty())
            })
            .count();
        let hits = rows
            .iter()
            .map(LinkGraphDisplayHit::from)
            .collect::<Vec<_>>();
        LinkGraphPlannedSearchPayload {
            query: parsed.query,
            options: parsed.options,
            hits,
            hit_count,
            section_hit_count,
            results: rows,
        }
    }

    /// Execute query plan with explicit matching and sorting options.
    #[must_use]
    fn execute_search(
        &self,
        query: &str,
        limit: usize,
        options: LinkGraphSearchOptions,
    ) -> Vec<LinkGraphHit> {
        let Some(context) = self.prepare_execution_context(query, limit, &options) else {
            return Vec::new();
        };
        let raw_query = context.raw_query.as_str();
        let graph_candidates = self.graph_filter_candidates(&options);
        if raw_query.is_empty()
            && graph_candidates.is_none()
            && !Self::has_non_query_filters(&options)
        {
            return Vec::new();
        }

        let scope = Self::effective_scope(&options.filters);
        let structural_edges_enabled = Self::allows_structural_edges(&options.filters);
        let semantic_edges_enabled = Self::allows_semantic_edges(&options.filters);
        if matches!(scope, LinkGraphScope::SectionOnly) && !structural_edges_enabled {
            return Vec::new();
        }
        let collapse_to_doc = options.filters.collapse_to_doc.unwrap_or(true);
        let per_doc_section_cap = Self::effective_per_doc_section_cap(&options.filters, scope);
        let min_section_words = Self::effective_min_section_words(&options.filters, scope);
        let max_heading_level = Self::effective_max_heading_level(&options.filters);
        let max_tree_hops = options.filters.max_tree_hops;

        let rows = self.collect_search_rows(
            &options,
            &context,
            graph_candidates.as_ref(),
            scope,
            structural_edges_enabled,
            semantic_edges_enabled,
            collapse_to_doc,
            per_doc_section_cap,
            min_section_words,
            max_heading_level,
            max_tree_hops,
        );
        self.finalize_search_rows(rows, &options, context.bounded)
    }
}
