use super::super::{
    LinkGraphDocument, LinkGraphIndex, LinkGraphScope, LinkGraphSearchOptions, ScoredSearchRow,
    score_path_fields,
};
use super::context::SearchExecutionContext;
use std::collections::HashSet;

impl LinkGraphIndex {
    #[allow(clippy::too_many_arguments)]
    pub(super) fn evaluate_doc_rows(
        &self,
        doc: &LinkGraphDocument,
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
        let mut out: Vec<ScoredSearchRow> = Vec::new();
        let raw_query = context.raw_query.as_str();

        if let Some(allowed_ids) = graph_candidates
            && !allowed_ids.contains(&doc.id)
        {
            return out;
        }
        if !Self::matches_temporal_filters(doc, options) {
            return out;
        }
        if !self.matches_structured_filters(
            doc,
            options,
            &context.include_paths,
            &context.exclude_paths,
            &context.tag_all,
            &context.tag_any,
            &context.tag_not,
            &context.mention_filters,
        ) {
            return out;
        }

        let mut section_candidates = if structural_edges_enabled {
            self.section_candidates(
                &doc.id,
                &context.clean_query,
                &context.query_tokens,
                context.case_sensitive,
                max_heading_level,
                min_section_words,
                max_tree_hops,
            )
        } else {
            Vec::new()
        };
        if matches!(scope, LinkGraphScope::SectionOnly | LinkGraphScope::Mixed) {
            section_candidates.retain(|row| !row.heading_path.trim().is_empty());
        }
        if section_candidates.len() > per_doc_section_cap {
            section_candidates.truncate(per_doc_section_cap);
        }
        let section_match = Self::best_section_match(&section_candidates);
        let section_score = section_match.as_ref().map_or(0.0, |row| row.score);

        let path_score = if raw_query.is_empty() {
            0.0
        } else {
            score_path_fields(
                doc,
                &context.clean_query,
                &context.query_tokens,
                context.case_sensitive,
            )
        };

        let (doc_score, doc_reason) = self.score_doc_for_strategy(
            doc,
            options,
            raw_query,
            &context.clean_query,
            &context.query_tokens,
            scope,
            collapse_to_doc,
            &section_candidates,
            section_match.as_ref(),
            section_score,
            path_score,
            semantic_edges_enabled,
            context.regex.as_ref(),
        );

        if !matches!(scope, LinkGraphScope::SectionOnly) {
            Self::emit_doc_row(&mut out, doc, doc_score, doc_reason, section_match.as_ref());
        }

        let emit_section_rows = structural_edges_enabled
            && (matches!(scope, LinkGraphScope::SectionOnly)
                || (matches!(scope, LinkGraphScope::Mixed) && !collapse_to_doc));
        if emit_section_rows {
            self.emit_section_rows(
                &mut out,
                doc,
                &section_candidates,
                options,
                raw_query,
                semantic_edges_enabled,
            );
        }

        out
    }
}
