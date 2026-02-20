use super::super::{
    LinkGraphDirection, LinkGraphEdgeType, LinkGraphIndex, LinkGraphLinkFilter,
    LinkGraphRelatedFilter, LinkGraphSearchFilters, LinkGraphSearchOptions,
};
use std::collections::HashSet;

impl LinkGraphIndex {
    pub(super) fn has_link_filter(filter: &Option<LinkGraphLinkFilter>) -> bool {
        filter.as_ref().is_some_and(|row| !row.seeds.is_empty())
    }

    pub(super) fn has_related_filter(filter: &Option<LinkGraphRelatedFilter>) -> bool {
        filter.as_ref().is_some_and(|row| !row.seeds.is_empty())
    }

    fn allows_edge_type(filters: &LinkGraphSearchFilters, edge_type: LinkGraphEdgeType) -> bool {
        filters.edge_types.is_empty() || filters.edge_types.contains(&edge_type)
    }

    pub(super) fn allows_structural_edges(filters: &LinkGraphSearchFilters) -> bool {
        Self::allows_edge_type(filters, LinkGraphEdgeType::Structural)
    }

    pub(super) fn allows_semantic_edges(filters: &LinkGraphSearchFilters) -> bool {
        Self::allows_edge_type(filters, LinkGraphEdgeType::Semantic)
    }

    pub(super) fn graph_filter_candidates(
        &self,
        options: &LinkGraphSearchOptions,
    ) -> Option<HashSet<String>> {
        let filters = &options.filters;
        let has_semantic_filters = Self::has_link_filter(&filters.link_to)
            || Self::has_link_filter(&filters.linked_by)
            || Self::has_related_filter(&filters.related)
            || !filters.mentioned_by_notes.is_empty();
        if has_semantic_filters && !Self::allows_semantic_edges(filters) {
            return Some(HashSet::new());
        }

        let mut selected: Option<HashSet<String>> = None;
        let universe = self.all_doc_ids();

        if let Some(link_to_filter) = filters.link_to.as_ref()
            && !link_to_filter.seeds.is_empty()
        {
            let matches = self.collect_link_filter_candidates(
                link_to_filter,
                LinkGraphDirection::Incoming,
                &universe,
            );
            selected = Self::combine_candidates(selected, matches);
        }

        if let Some(linked_by_filter) = filters.linked_by.as_ref()
            && !linked_by_filter.seeds.is_empty()
        {
            let matches = self.collect_link_filter_candidates(
                linked_by_filter,
                LinkGraphDirection::Outgoing,
                &universe,
            );
            selected = Self::combine_candidates(selected, matches);
        }

        if let Some(related_filter) = filters.related.as_ref()
            && !related_filter.seeds.is_empty()
        {
            let matches = self.collect_related_filter_candidates(related_filter);
            selected = Self::combine_candidates(selected, matches);
        }

        if !filters.mentioned_by_notes.is_empty() {
            let matches = self.collect_mentioned_by_note_candidates(&filters.mentioned_by_notes);
            selected = Self::combine_candidates(selected, matches);
        }

        selected
    }
}
