use super::super::{
    LinkGraphHit, LinkGraphIndex, LinkGraphScope, LinkGraphSearchOptions, ScoredSearchRow,
    sort_hits,
};
use super::context::SearchExecutionContext;
use std::collections::HashSet;

impl LinkGraphIndex {
    #[allow(clippy::too_many_arguments)]
    pub(super) fn collect_search_rows(
        &self,
        options: &LinkGraphSearchOptions,
        context: &SearchExecutionContext,
        graph_candidates: Option<&HashSet<String>>,
        scope: LinkGraphScope,
        structural_edges_enabled: bool,
        semantic_edges_enabled: bool,
        collapse_to_doc: bool,
        per_doc_section_cap: usize,
        min_section_words: usize,
        max_heading_level: usize,
        max_tree_hops: Option<usize>,
    ) -> Vec<ScoredSearchRow> {
        self.docs_by_id
            .values()
            .flat_map(|doc| {
                self.evaluate_doc_rows(
                    doc,
                    options,
                    context,
                    graph_candidates,
                    scope,
                    structural_edges_enabled,
                    semantic_edges_enabled,
                    collapse_to_doc,
                    per_doc_section_cap,
                    min_section_words,
                    max_heading_level,
                    max_tree_hops,
                )
            })
            .collect()
    }

    pub(super) fn finalize_search_rows(
        &self,
        mut rows: Vec<ScoredSearchRow>,
        options: &LinkGraphSearchOptions,
        bounded: usize,
    ) -> Vec<LinkGraphHit> {
        sort_hits(&mut rows, &options.sort_terms);
        rows.truncate(bounded);
        rows.into_iter().map(|row| row.hit).collect()
    }
}
