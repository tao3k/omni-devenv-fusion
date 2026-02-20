use super::super::{
    LinkGraphDirection, LinkGraphIndex, LinkGraphLinkFilter, LinkGraphRelatedFilter,
};
use std::collections::{HashSet, VecDeque};

impl LinkGraphIndex {
    fn collect_directional_ids(
        &self,
        seed_id: &str,
        direction: LinkGraphDirection,
        max_distance: usize,
    ) -> HashSet<String> {
        let bounded_distance = max_distance.max(1);
        let mut out: HashSet<String> = HashSet::new();
        let mut visited: HashSet<String> = HashSet::new();
        let mut queue: VecDeque<(String, usize)> = VecDeque::new();

        visited.insert(seed_id.to_string());
        queue.push_back((seed_id.to_string(), 0));

        while let Some((current, depth)) = queue.pop_front() {
            if depth >= bounded_distance {
                continue;
            }
            let next_depth = depth + 1;

            if matches!(
                direction,
                LinkGraphDirection::Outgoing | LinkGraphDirection::Both
            ) && let Some(targets) = self.outgoing.get(&current)
            {
                for target in targets {
                    if target == seed_id {
                        continue;
                    }
                    if visited.insert(target.clone()) {
                        out.insert(target.clone());
                        queue.push_back((target.clone(), next_depth));
                    }
                }
            }

            if matches!(
                direction,
                LinkGraphDirection::Incoming | LinkGraphDirection::Both
            ) && let Some(sources) = self.incoming.get(&current)
            {
                for source in sources {
                    if source == seed_id {
                        continue;
                    }
                    if visited.insert(source.clone()) {
                        out.insert(source.clone());
                        queue.push_back((source.clone(), next_depth));
                    }
                }
            }
        }

        out
    }

    pub(super) fn combine_candidates(
        current: Option<HashSet<String>>,
        incoming: HashSet<String>,
    ) -> Option<HashSet<String>> {
        match current {
            None => Some(incoming),
            Some(existing) => Some(existing.intersection(&incoming).cloned().collect()),
        }
    }

    pub(super) fn collect_link_filter_candidates(
        &self,
        filter: &LinkGraphLinkFilter,
        direction: LinkGraphDirection,
        universe: &HashSet<String>,
    ) -> HashSet<String> {
        let seed_ids = self.resolve_doc_ids(&filter.seeds);
        let max_distance = if filter.recursive {
            filter.max_distance.unwrap_or(2).max(1)
        } else {
            1
        };
        let mut matches: HashSet<String> = HashSet::new();
        for seed_id in seed_ids {
            matches.extend(self.collect_directional_ids(&seed_id, direction, max_distance));
        }
        if filter.negate {
            universe.difference(&matches).cloned().collect()
        } else {
            matches
        }
    }

    pub(super) fn collect_related_filter_candidates(
        &self,
        filter: &LinkGraphRelatedFilter,
    ) -> HashSet<String> {
        let seed_ids = self.resolve_doc_ids(&filter.seeds);
        if seed_ids.is_empty() {
            return HashSet::new();
        }
        let max_distance = filter.max_distance.unwrap_or(2).max(1);
        self.related_ppr_ranked_doc_ids(&seed_ids, max_distance, filter.ppr.as_ref())
            .into_iter()
            .map(|(doc_id, _distance, _score)| doc_id)
            .collect()
    }

    pub(super) fn collect_mentioned_by_note_candidates(&self, seeds: &[String]) -> HashSet<String> {
        let seed_ids = self.resolve_doc_ids(seeds);
        let mut matches: HashSet<String> = HashSet::new();
        for seed_id in seed_ids {
            matches.extend(self.collect_directional_ids(&seed_id, LinkGraphDirection::Outgoing, 1));
        }
        matches
    }
}
