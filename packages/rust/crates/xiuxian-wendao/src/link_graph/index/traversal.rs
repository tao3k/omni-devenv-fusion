use super::{
    LinkGraphDirection, LinkGraphDocument, LinkGraphIndex, LinkGraphMetadata, LinkGraphNeighbor,
    LinkGraphRelatedPprDiagnostics, LinkGraphRelatedPprOptions, LinkGraphStats, doc_sort_key,
};
use std::collections::{HashMap, HashSet, VecDeque};

fn merge_direction(
    existing: LinkGraphDirection,
    new_dir: LinkGraphDirection,
) -> LinkGraphDirection {
    if existing == new_dir {
        existing
    } else {
        LinkGraphDirection::Both
    }
}

impl LinkGraphIndex {
    fn build_related_neighbors_from_ranked(
        &self,
        ranked: Vec<(String, usize, f64)>,
        limit: usize,
    ) -> Vec<LinkGraphNeighbor> {
        let bounded_limit = limit.max(1);
        ranked
            .into_iter()
            .filter_map(|(doc_id, distance, _score)| {
                self.docs_by_id.get(&doc_id).map(|doc| LinkGraphNeighbor {
                    stem: doc.stem.clone(),
                    direction: LinkGraphDirection::Both,
                    distance,
                    title: doc.title.clone(),
                    path: doc.path.clone(),
                })
            })
            .take(bounded_limit)
            .collect()
    }

    /// Traverse neighbors for a note stem/id/path.
    #[must_use]
    pub fn neighbors(
        &self,
        stem_or_id: &str,
        direction: LinkGraphDirection,
        hops: usize,
        limit: usize,
    ) -> Vec<LinkGraphNeighbor> {
        let Some(start_id) = self.resolve_doc_id(stem_or_id).map(str::to_string) else {
            return Vec::new();
        };

        let max_hops = hops.max(1);
        let max_items = limit.max(1);

        let mut queue: VecDeque<(String, usize, LinkGraphDirection)> = VecDeque::new();
        queue.push_back((start_id.clone(), 0, LinkGraphDirection::Both));
        let mut visited: HashSet<String> = HashSet::new();
        visited.insert(start_id.clone());

        let mut neighbors: HashMap<String, LinkGraphNeighbor> = HashMap::new();

        while let Some((current_id, depth, root_direction)) = queue.pop_front() {
            if depth >= max_hops {
                continue;
            }

            let mut next_nodes: Vec<(String, LinkGraphDirection)> = Vec::new();
            if matches!(
                direction,
                LinkGraphDirection::Both | LinkGraphDirection::Outgoing
            ) && let Some(targets) = self.outgoing.get(&current_id)
            {
                for target in targets {
                    let effective = if depth == 0 {
                        LinkGraphDirection::Outgoing
                    } else {
                        root_direction
                    };
                    next_nodes.push((target.clone(), effective));
                }
            }
            if matches!(
                direction,
                LinkGraphDirection::Both | LinkGraphDirection::Incoming
            ) && let Some(sources) = self.incoming.get(&current_id)
            {
                for source in sources {
                    let effective = if depth == 0 {
                        LinkGraphDirection::Incoming
                    } else {
                        root_direction
                    };
                    next_nodes.push((source.clone(), effective));
                }
            }

            for (next_id, next_direction) in next_nodes {
                if next_id == start_id {
                    continue;
                }
                let Some(doc) = self.docs_by_id.get(&next_id) else {
                    continue;
                };
                let distance = depth + 1;
                if let Some(existing) = neighbors.get_mut(&next_id) {
                    existing.distance = existing.distance.min(distance);
                    existing.direction = merge_direction(existing.direction, next_direction);
                } else {
                    neighbors.insert(
                        next_id.clone(),
                        LinkGraphNeighbor {
                            stem: doc.stem.clone(),
                            direction: next_direction,
                            distance,
                            title: doc.title.clone(),
                            path: doc.path.clone(),
                        },
                    );
                }
                if distance < max_hops && !visited.contains(&next_id) {
                    visited.insert(next_id.clone());
                    queue.push_back((next_id, distance, next_direction));
                }
            }
        }

        let mut out: Vec<LinkGraphNeighbor> = neighbors.into_values().collect();
        out.sort_by(|a, b| a.distance.cmp(&b.distance).then(a.path.cmp(&b.path)));
        out.truncate(max_items);
        out
    }

    /// Find related notes through bidirectional traversal.
    #[must_use]
    pub fn related(
        &self,
        stem_or_id: &str,
        max_distance: usize,
        limit: usize,
    ) -> Vec<LinkGraphNeighbor> {
        self.related_with_options(stem_or_id, max_distance, limit, None)
    }

    /// Find related notes through bidirectional traversal with explicit PPR options.
    #[must_use]
    pub fn related_with_options(
        &self,
        stem_or_id: &str,
        max_distance: usize,
        limit: usize,
        ppr: Option<&LinkGraphRelatedPprOptions>,
    ) -> Vec<LinkGraphNeighbor> {
        let seeds = vec![stem_or_id.to_string()];
        self.related_from_seeds_with_diagnostics(&seeds, max_distance, limit, ppr)
            .0
    }

    /// Find related notes and return extra PPR diagnostics for debug/observability.
    #[must_use]
    pub fn related_with_diagnostics(
        &self,
        stem_or_id: &str,
        max_distance: usize,
        limit: usize,
        ppr: Option<&LinkGraphRelatedPprOptions>,
    ) -> (
        Vec<LinkGraphNeighbor>,
        Option<LinkGraphRelatedPprDiagnostics>,
    ) {
        let seeds = vec![stem_or_id.to_string()];
        self.related_from_seeds_with_diagnostics(&seeds, max_distance, limit, ppr)
    }

    /// Find related notes from explicit seed notes and return PPR diagnostics.
    #[must_use]
    pub fn related_from_seeds_with_diagnostics(
        &self,
        seeds: &[String],
        max_distance: usize,
        limit: usize,
        ppr: Option<&LinkGraphRelatedPprOptions>,
    ) -> (
        Vec<LinkGraphNeighbor>,
        Option<LinkGraphRelatedPprDiagnostics>,
    ) {
        let seed_ids = self.resolve_doc_ids(seeds);
        if seed_ids.is_empty() {
            return (Vec::new(), None);
        }
        let Some(computation) = self.related_ppr_compute(&seed_ids, max_distance.max(1), ppr)
        else {
            return (Vec::new(), None);
        };
        (
            self.build_related_neighbors_from_ranked(computation.ranked_doc_ids, limit),
            Some(computation.diagnostics),
        )
    }

    /// Get per-note metadata.
    #[must_use]
    pub fn metadata(&self, stem_or_id: &str) -> Option<LinkGraphMetadata> {
        let doc_id = self.resolve_doc_id(stem_or_id)?;
        let doc = self.docs_by_id.get(doc_id)?;
        Some(LinkGraphMetadata {
            stem: doc.stem.clone(),
            title: doc.title.clone(),
            path: doc.path.clone(),
            tags: doc.tags.clone(),
        })
    }

    /// Return table-of-contents rows.
    #[must_use]
    pub fn toc(&self, limit: usize) -> Vec<LinkGraphDocument> {
        let mut docs: Vec<LinkGraphDocument> = self.docs_by_id.values().cloned().collect();
        docs.sort_by(|a, b| doc_sort_key(a).cmp(&doc_sort_key(b)));
        docs.truncate(limit.max(1));
        docs
    }

    /// Return normalized stats payload.
    #[must_use]
    pub fn stats(&self) -> LinkGraphStats {
        let total_notes = self.docs_by_id.len();
        let orphans = self
            .docs_by_id
            .keys()
            .filter(|doc_id| {
                let out_empty = self
                    .outgoing
                    .get(*doc_id)
                    .map(|v| v.is_empty())
                    .unwrap_or(true);
                let in_empty = self
                    .incoming
                    .get(*doc_id)
                    .map(|v| v.is_empty())
                    .unwrap_or(true);
                out_empty && in_empty
            })
            .count();
        LinkGraphStats {
            total_notes,
            orphans,
            links_in_graph: self.edge_count,
            nodes_in_graph: total_notes,
        }
    }
}
