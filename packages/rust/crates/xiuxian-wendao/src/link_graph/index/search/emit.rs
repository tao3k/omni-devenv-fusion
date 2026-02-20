use super::super::{
    LinkGraphDocument, LinkGraphHit, LinkGraphIndex, LinkGraphMatchStrategy,
    LinkGraphSearchOptions, ScoredSearchRow, SectionCandidate, SectionMatch,
    deterministic_random_key,
};

impl LinkGraphIndex {
    pub(super) fn emit_doc_row(
        out: &mut Vec<ScoredSearchRow>,
        doc: &LinkGraphDocument,
        score: f64,
        reason: String,
        section_match: Option<&SectionMatch>,
    ) {
        if score <= 0.0 {
            return;
        }
        out.push(ScoredSearchRow {
            hit: LinkGraphHit {
                stem: doc.stem.clone(),
                title: doc.title.clone(),
                path: doc.path.clone(),
                score,
                best_section: section_match.and_then(|row| row.heading_path.clone()),
                match_reason: Some(reason),
            },
            created_ts: doc.created_ts,
            modified_ts: doc.modified_ts,
            word_count: doc.word_count,
            random_key: deterministic_random_key(&doc.stem, &doc.path),
        });
    }

    pub(super) fn emit_section_rows(
        &self,
        out: &mut Vec<ScoredSearchRow>,
        doc: &LinkGraphDocument,
        section_candidates: &[SectionCandidate],
        options: &LinkGraphSearchOptions,
        raw_query: &str,
        semantic_edges_enabled: bool,
    ) {
        for section in section_candidates {
            let mut section_score = section.score;
            let mut section_reason = format!("section+{}", section.reason);
            if semantic_edges_enabled
                && !raw_query.is_empty()
                && matches!(
                    options.match_strategy,
                    LinkGraphMatchStrategy::Fts | LinkGraphMatchStrategy::PathFuzzy
                )
                && section_score > 0.0
            {
                let boosted = self.apply_graph_rank_boost(&doc.id, section_score);
                if boosted > section_score {
                    section_reason.push_str("+graph_rank");
                }
                section_score = boosted;
            }
            out.push(ScoredSearchRow {
                hit: LinkGraphHit {
                    stem: doc.stem.clone(),
                    title: doc.title.clone(),
                    path: doc.path.clone(),
                    score: section_score,
                    best_section: Some(section.heading_path.clone()),
                    match_reason: Some(section_reason),
                },
                created_ts: doc.created_ts,
                modified_ts: doc.modified_ts,
                word_count: doc.word_count,
                random_key: deterministic_random_key(
                    &doc.stem,
                    &format!("{}#{}", doc.path, section.heading_path),
                ),
            });
        }
    }
}
