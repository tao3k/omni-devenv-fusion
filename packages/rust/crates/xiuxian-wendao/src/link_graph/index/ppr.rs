use super::{
    LinkGraphIndex, LinkGraphPprSubgraphMode, LinkGraphRelatedPprDiagnostics,
    LinkGraphRelatedPprOptions, doc_sort_key,
};
use rayon::prelude::*;
use std::cmp::Ordering;
use std::collections::{HashMap, HashSet, VecDeque};
use std::time::Instant;

const RELATED_PPR_DEFAULT_ALPHA: f64 = 0.85;
const RELATED_PPR_DEFAULT_MAX_ITER: usize = 48;
const RELATED_PPR_DEFAULT_TOL: f64 = 1e-6;
const RELATED_PPR_PARTITION_TRIGGER_NODES: usize = 256;
const RELATED_PPR_MAX_PARTITIONS: usize = 8;

#[derive(Debug, Clone)]
pub(super) struct RelatedPprComputation {
    pub(super) ranked_doc_ids: Vec<(String, usize, f64)>,
    pub(super) diagnostics: LinkGraphRelatedPprDiagnostics,
}

#[derive(Debug, Clone)]
struct RelatedPprKernelResult {
    scores_by_doc_id: HashMap<String, f64>,
    iteration_count: usize,
    final_residual: f64,
}

impl LinkGraphIndex {
    fn resolve_related_ppr_runtime(
        options: Option<&LinkGraphRelatedPprOptions>,
    ) -> (f64, usize, f64, LinkGraphPprSubgraphMode) {
        let alpha = options
            .and_then(|row| row.alpha)
            .unwrap_or(RELATED_PPR_DEFAULT_ALPHA);
        let max_iter = options
            .and_then(|row| row.max_iter)
            .unwrap_or(RELATED_PPR_DEFAULT_MAX_ITER)
            .max(1);
        let tol = options
            .and_then(|row| row.tol)
            .unwrap_or(RELATED_PPR_DEFAULT_TOL);
        let subgraph_mode = options
            .and_then(|row| row.subgraph_mode)
            .unwrap_or(LinkGraphPprSubgraphMode::Auto);
        (alpha, max_iter, tol, subgraph_mode)
    }

    fn collect_bidirectional_distance_map(
        &self,
        seed_ids: &HashSet<String>,
        max_distance: usize,
    ) -> HashMap<String, usize> {
        let bounded_distance = max_distance.max(1);
        let mut distances: HashMap<String, usize> = HashMap::new();
        let mut queue: VecDeque<String> = VecDeque::new();

        for seed_id in seed_ids {
            if self.docs_by_id.contains_key(seed_id) {
                distances.insert(seed_id.clone(), 0);
                queue.push_back(seed_id.clone());
            }
        }

        while let Some(current) = queue.pop_front() {
            let Some(depth) = distances.get(&current).copied() else {
                continue;
            };
            if depth >= bounded_distance {
                continue;
            }
            let next_depth = depth + 1;

            if let Some(targets) = self.outgoing.get(&current) {
                for target in targets {
                    if !self.docs_by_id.contains_key(target) {
                        continue;
                    }
                    let should_update = match distances.get(target) {
                        Some(existing) => next_depth < *existing,
                        None => true,
                    };
                    if should_update {
                        distances.insert(target.clone(), next_depth);
                        queue.push_back(target.clone());
                    }
                }
            }

            if let Some(sources) = self.incoming.get(&current) {
                for source in sources {
                    if !self.docs_by_id.contains_key(source) {
                        continue;
                    }
                    let should_update = match distances.get(source) {
                        Some(existing) => next_depth < *existing,
                        None => true,
                    };
                    if should_update {
                        distances.insert(source.clone(), next_depth);
                        queue.push_back(source.clone());
                    }
                }
            }
        }

        distances
    }

    fn sort_doc_ids_for_runtime(&self, doc_ids: &mut [String]) {
        doc_ids.sort_by(|left, right| {
            match (self.docs_by_id.get(left), self.docs_by_id.get(right)) {
                (Some(a), Some(b)) => doc_sort_key(a).cmp(&doc_sort_key(b)),
                _ => left.cmp(right),
            }
        });
    }

    fn build_graph_nodes_for_related_ppr(
        &self,
        horizon_distances: &HashMap<String, usize>,
        restrict_to_horizon: bool,
    ) -> Vec<String> {
        let mut graph_nodes: Vec<String> = if restrict_to_horizon {
            horizon_distances.keys().cloned().collect()
        } else {
            self.docs_by_id.keys().cloned().collect()
        };
        self.sort_doc_ids_for_runtime(&mut graph_nodes);
        graph_nodes
    }

    fn should_partition_related_ppr(
        subgraph_mode: LinkGraphPprSubgraphMode,
        restrict_to_horizon: bool,
        graph_node_count: usize,
        seed_count: usize,
    ) -> bool {
        if !restrict_to_horizon || seed_count <= 1 {
            return false;
        }
        match subgraph_mode {
            LinkGraphPprSubgraphMode::Disabled => false,
            LinkGraphPprSubgraphMode::Force => true,
            LinkGraphPprSubgraphMode::Auto => {
                graph_node_count >= RELATED_PPR_PARTITION_TRIGGER_NODES
            }
        }
    }

    fn build_related_ppr_partitions(
        &self,
        seed_ids: &HashSet<String>,
        max_distance: usize,
        universe: &HashSet<String>,
    ) -> Vec<Vec<String>> {
        let mut ordered_seeds: Vec<String> = seed_ids.iter().cloned().collect();
        self.sort_doc_ids_for_runtime(&mut ordered_seeds);
        if ordered_seeds.is_empty() {
            return Vec::new();
        }

        let mut seed_groups: Vec<HashSet<String>> = Vec::new();
        let direct_limit = RELATED_PPR_MAX_PARTITIONS.saturating_sub(1);
        if ordered_seeds.len() <= RELATED_PPR_MAX_PARTITIONS {
            for seed_id in ordered_seeds {
                let mut group: HashSet<String> = HashSet::new();
                group.insert(seed_id);
                seed_groups.push(group);
            }
        } else {
            for seed_id in ordered_seeds.iter().take(direct_limit) {
                let mut group: HashSet<String> = HashSet::new();
                group.insert(seed_id.clone());
                seed_groups.push(group);
            }
            let mut tail_group: HashSet<String> = HashSet::new();
            for seed_id in ordered_seeds.iter().skip(direct_limit) {
                tail_group.insert(seed_id.clone());
            }
            if !tail_group.is_empty() {
                seed_groups.push(tail_group);
            }
        }

        let mut partitions: Vec<Vec<String>> = Vec::new();
        let mut seen_keys: HashSet<String> = HashSet::new();
        for group in seed_groups {
            let horizon = self.collect_bidirectional_distance_map(&group, max_distance);
            if horizon.is_empty() {
                continue;
            }
            let mut nodes: Vec<String> = horizon
                .keys()
                .filter(|doc_id| universe.contains(*doc_id))
                .cloned()
                .collect();
            if nodes.is_empty() {
                continue;
            }
            self.sort_doc_ids_for_runtime(&mut nodes);
            let key = nodes.join("\x1f");
            if seen_keys.insert(key) {
                partitions.push(nodes);
            }
        }
        if partitions.is_empty() {
            let mut nodes: Vec<String> = universe.iter().cloned().collect();
            self.sort_doc_ids_for_runtime(&mut nodes);
            partitions.push(nodes);
        }
        partitions
    }

    fn run_related_ppr_kernel(
        &self,
        graph_nodes: &[String],
        seed_ids: &HashSet<String>,
        alpha: f64,
        max_iter: usize,
        tol: f64,
    ) -> Option<RelatedPprKernelResult> {
        if graph_nodes.is_empty() {
            return None;
        }
        let mut node_to_idx: HashMap<String, usize> = HashMap::with_capacity(graph_nodes.len());
        for (idx, doc_id) in graph_nodes.iter().enumerate() {
            node_to_idx.insert(doc_id.clone(), idx);
        }

        let mut adjacency: Vec<Vec<usize>> = vec![Vec::new(); graph_nodes.len()];
        for (source_idx, source_id) in graph_nodes.iter().enumerate() {
            let mut neighbors: HashSet<usize> = HashSet::new();
            if let Some(targets) = self.outgoing.get(source_id) {
                for target in targets {
                    if let Some(target_idx) = node_to_idx.get(target).copied()
                        && target_idx != source_idx
                    {
                        neighbors.insert(target_idx);
                    }
                }
            }
            if let Some(sources) = self.incoming.get(source_id) {
                for source in sources {
                    if let Some(source_idx_inner) = node_to_idx.get(source).copied()
                        && source_idx_inner != source_idx
                    {
                        neighbors.insert(source_idx_inner);
                    }
                }
            }
            let mut ordered: Vec<usize> = neighbors.into_iter().collect();
            ordered.sort_unstable();
            adjacency[source_idx] = ordered;
        }

        let mut teleport = vec![0.0_f64; graph_nodes.len()];
        let mut seed_count = 0_usize;
        for seed_id in seed_ids {
            if let Some(seed_idx) = node_to_idx.get(seed_id).copied() {
                seed_count += 1;
                teleport[seed_idx] = 1.0;
            }
        }
        if seed_count == 0 {
            return None;
        }
        let seed_weight = 1.0 / seed_count as f64;
        for value in &mut teleport {
            if *value > 0.0 {
                *value = seed_weight;
            }
        }

        let mut scores = teleport.clone();
        let mut next_scores = vec![0.0_f64; graph_nodes.len()];
        let mut iteration_count = 0_usize;
        let mut final_residual = 0.0_f64;
        for _ in 0..max_iter {
            next_scores.fill(0.0);
            let restart_scale = (1.0 - alpha).clamp(0.0, 1.0);
            for (idx, restart) in teleport.iter().copied().enumerate() {
                if restart > 0.0 {
                    next_scores[idx] = restart_scale * restart;
                }
            }

            let mut dangling_mass = 0.0_f64;
            for (source_idx, outgoing) in adjacency.iter().enumerate() {
                let source_score = scores[source_idx];
                if source_score <= 0.0 {
                    continue;
                }
                if outgoing.is_empty() {
                    dangling_mass += source_score;
                    continue;
                }
                let step = alpha * source_score / outgoing.len() as f64;
                for target_idx in outgoing {
                    next_scores[*target_idx] += step;
                }
            }

            if dangling_mass > 0.0 {
                let leak = alpha * dangling_mass;
                for (idx, restart) in teleport.iter().copied().enumerate() {
                    if restart > 0.0 {
                        next_scores[idx] += leak * restart;
                    }
                }
            }

            let residual: f64 = next_scores
                .iter()
                .zip(scores.iter())
                .map(|(next, current)| (next - current).abs())
                .sum();
            iteration_count += 1;
            final_residual = residual;
            std::mem::swap(&mut scores, &mut next_scores);
            if residual <= tol {
                break;
            }
        }

        let scores_by_doc_id: HashMap<String, f64> = graph_nodes
            .iter()
            .enumerate()
            .map(|(idx, doc_id)| (doc_id.clone(), scores[idx]))
            .collect();

        Some(RelatedPprKernelResult {
            scores_by_doc_id,
            iteration_count,
            final_residual,
        })
    }

    pub(super) fn related_ppr_compute(
        &self,
        seed_ids: &HashSet<String>,
        max_distance: usize,
        options: Option<&LinkGraphRelatedPprOptions>,
    ) -> Option<RelatedPprComputation> {
        let total_start = Instant::now();
        if seed_ids.is_empty() {
            return None;
        }
        let bounded_distance = max_distance.max(1);
        let horizon_distances = self.collect_bidirectional_distance_map(seed_ids, bounded_distance);
        if horizon_distances.is_empty() {
            return None;
        }

        let (alpha, max_iter, tol, subgraph_mode) = Self::resolve_related_ppr_runtime(options);
        let restrict_to_horizon = match subgraph_mode {
            LinkGraphPprSubgraphMode::Disabled => false,
            LinkGraphPprSubgraphMode::Force => true,
            LinkGraphPprSubgraphMode::Auto => horizon_distances.len() < self.docs_by_id.len(),
        };

        let graph_nodes =
            self.build_graph_nodes_for_related_ppr(&horizon_distances, restrict_to_horizon);
        if graph_nodes.is_empty() {
            return None;
        }
        let candidate_count = horizon_distances
            .keys()
            .filter(|doc_id| !seed_ids.contains(*doc_id))
            .count();

        let mut fused_scores_by_doc_id: HashMap<String, f64> = HashMap::new();
        let mut iteration_count = 0_usize;
        let mut final_residual = 0.0_f64;
        let mut subgraph_count = 0_usize;
        let mut partition_sizes: Vec<usize> = Vec::new();
        let mut partition_duration_ms = 0.0_f64;
        let mut kernel_duration_ms = 0.0_f64;
        let mut fusion_duration_ms = 0.0_f64;

        let should_partition = Self::should_partition_related_ppr(
            subgraph_mode,
            restrict_to_horizon,
            graph_nodes.len(),
            seed_ids.len(),
        );
        if should_partition {
            let partition_start = Instant::now();
            let universe: HashSet<String> = graph_nodes.iter().cloned().collect();
            let partitions =
                self.build_related_ppr_partitions(seed_ids, bounded_distance, &universe);
            partition_duration_ms = partition_start.elapsed().as_secs_f64() * 1000.0;
            partition_sizes = partitions.iter().map(Vec::len).collect();

            let kernel_start = Instant::now();
            let kernels: Vec<RelatedPprKernelResult> = partitions
                .par_iter()
                .filter_map(|partition_nodes| {
                    self.run_related_ppr_kernel(partition_nodes, seed_ids, alpha, max_iter, tol)
                })
                .collect();
            kernel_duration_ms = kernel_start.elapsed().as_secs_f64() * 1000.0;

            let fusion_start = Instant::now();
            for kernel in kernels {
                subgraph_count += 1;
                iteration_count = iteration_count.max(kernel.iteration_count);
                final_residual = final_residual.max(kernel.final_residual);
                for (doc_id, score) in kernel.scores_by_doc_id {
                    let current = fused_scores_by_doc_id.entry(doc_id).or_insert(0.0);
                    *current = current.max(score);
                }
            }
            fusion_duration_ms = fusion_start.elapsed().as_secs_f64() * 1000.0;
        }
        if subgraph_count == 0 {
            let kernel_start = Instant::now();
            let kernel =
                self.run_related_ppr_kernel(&graph_nodes, seed_ids, alpha, max_iter, tol)?;
            kernel_duration_ms = kernel_start.elapsed().as_secs_f64() * 1000.0;
            subgraph_count = 1;
            iteration_count = kernel.iteration_count;
            final_residual = kernel.final_residual;
            fused_scores_by_doc_id = kernel.scores_by_doc_id;
            partition_sizes = vec![graph_nodes.len()];
        }
        let partition_max_node_count = partition_sizes.iter().copied().max().unwrap_or(0);
        let partition_min_node_count = partition_sizes.iter().copied().min().unwrap_or(0);
        let partition_avg_node_count = if partition_sizes.is_empty() {
            0.0
        } else {
            partition_sizes.iter().sum::<usize>() as f64 / partition_sizes.len() as f64
        };

        let mut ranked: Vec<(String, usize, f64)> = horizon_distances
            .into_iter()
            .filter(|(doc_id, distance)| *distance > 0 && !seed_ids.contains(doc_id))
            .filter_map(|(doc_id, distance)| {
                fused_scores_by_doc_id
                    .get(&doc_id)
                    .copied()
                    .map(|score| (doc_id, distance, score))
            })
            .collect();

        ranked.sort_by(|left, right| {
            right
                .2
                .partial_cmp(&left.2)
                .unwrap_or(Ordering::Equal)
                .then(left.1.cmp(&right.1))
                .then_with(
                    || match (self.docs_by_id.get(&left.0), self.docs_by_id.get(&right.0)) {
                        (Some(a), Some(b)) => doc_sort_key(a).cmp(&doc_sort_key(b)),
                        _ => left.0.cmp(&right.0),
                    },
                )
        });

        let diagnostics = LinkGraphRelatedPprDiagnostics {
            alpha,
            max_iter,
            tol,
            iteration_count,
            final_residual,
            candidate_count,
            graph_node_count: graph_nodes.len(),
            subgraph_count,
            partition_max_node_count,
            partition_min_node_count,
            partition_avg_node_count,
            total_duration_ms: total_start.elapsed().as_secs_f64() * 1000.0,
            partition_duration_ms,
            kernel_duration_ms,
            fusion_duration_ms,
            subgraph_mode,
            horizon_restricted: restrict_to_horizon,
        };
        Some(RelatedPprComputation {
            ranked_doc_ids: ranked,
            diagnostics,
        })
    }

    pub(super) fn related_ppr_ranked_doc_ids(
        &self,
        seed_ids: &HashSet<String>,
        max_distance: usize,
        options: Option<&LinkGraphRelatedPprOptions>,
    ) -> Vec<(String, usize, f64)> {
        self.related_ppr_compute(seed_ids, max_distance, options)
            .map(|row| row.ranked_doc_ids)
            .unwrap_or_default()
    }
}
