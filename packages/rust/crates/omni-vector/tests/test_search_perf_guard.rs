//! Performance regression guard for `search_optimized`.
//!
//! This test uses a deterministic dataset and query set to track search latency
//! across scanner tuning profiles. The goal is to catch major regressions, not
//! to provide micro-benchmark precision.

use omni_vector::{SearchOptions, VectorStore};
use std::time::Instant;

const DIM: usize = 64;
const DOC_COUNT: usize = 1200;
const QUERY_COUNT: usize = 24;
const LIMIT: usize = 10;

fn synthetic_vector(seed: usize, dim: usize) -> Vec<f32> {
    (0..dim)
        .map(|j| {
            let v = ((seed * 31 + j * 17) % 1000) as f32 / 1000.0;
            v * 2.0 - 1.0
        })
        .collect()
}

fn percentile(sorted_ms: &[f64], p: f64) -> f64 {
    if sorted_ms.is_empty() {
        return 0.0;
    }
    let idx = ((sorted_ms.len() - 1) as f64 * p).round() as usize;
    sorted_ms[idx]
}

fn env_f64(key: &str, default: f64) -> f64 {
    std::env::var(key)
        .ok()
        .and_then(|v| v.parse::<f64>().ok())
        .unwrap_or(default)
}

#[derive(Debug)]
struct ProfileStats {
    avg_ms: f64,
    p50_ms: f64,
    p95_ms: f64,
}

async fn run_profile(
    store: &VectorStore,
    table: &str,
    profile_name: &'static str,
    options: SearchOptions,
    queries: &[Vec<f32>],
) -> ProfileStats {
    let mut samples_ms = Vec::with_capacity(queries.len());
    for q in queries {
        let start = Instant::now();
        let results = store
            .search_optimized(table, q.clone(), LIMIT, options.clone())
            .await
            .unwrap();
        assert!(
            !results.is_empty(),
            "profile={} returned no results for a deterministic query",
            profile_name
        );
        samples_ms.push(start.elapsed().as_secs_f64() * 1000.0);
    }

    samples_ms.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let sum: f64 = samples_ms.iter().sum();
    let avg_ms = sum / samples_ms.len() as f64;
    let p50_ms = percentile(&samples_ms, 0.50);
    let p95_ms = percentile(&samples_ms, 0.95);

    ProfileStats {
        avg_ms,
        p50_ms,
        p95_ms,
    }
}

#[tokio::test]
async fn test_search_optimized_perf_guard() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("search_perf_guard_store");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(DIM))
        .await
        .unwrap();
    let table = "skills";

    // Deterministic synthetic corpus.
    let ids: Vec<String> = (0..DOC_COUNT).map(|i| format!("tool.{i:04}")).collect();
    let vectors: Vec<Vec<f32>> = (0..DOC_COUNT).map(|i| synthetic_vector(i, DIM)).collect();
    let contents: Vec<String> = (0..DOC_COUNT)
        .map(|i| format!("tool {i} deterministic benchmark document"))
        .collect();
    let metadata: Vec<String> = (0..DOC_COUNT)
        .map(|i| serde_json::json!({ "bucket": i % 16, "kind": "bench" }).to_string())
        .collect();

    store
        .add_documents(table, ids, vectors, contents, metadata)
        .await
        .unwrap();

    // Deterministic query set with slight perturbation from corpus vectors.
    let queries: Vec<Vec<f32>> = (0..QUERY_COUNT)
        .map(|i| {
            let mut q = synthetic_vector(i * 13, DIM);
            q[0] += 0.01;
            q[1] -= 0.01;
            q
        })
        .collect();

    // Warm-up to reduce one-time IO/cache effects.
    let warmup = SearchOptions::default();
    for q in queries.iter().take(4) {
        let _ = store
            .search_optimized(table, q.clone(), LIMIT, warmup.clone())
            .await
            .unwrap();
    }

    let small = SearchOptions {
        batch_size: Some(256),
        fragment_readahead: Some(2),
        batch_readahead: Some(4),
        scan_limit: Some(64),
        ..SearchOptions::default()
    };
    let medium = SearchOptions {
        batch_size: Some(1024),
        fragment_readahead: Some(4),
        batch_readahead: Some(16),
        scan_limit: Some(128),
        ..SearchOptions::default()
    };
    let large = SearchOptions {
        batch_size: Some(2048),
        fragment_readahead: Some(8),
        batch_readahead: Some(32),
        scan_limit: Some(256),
        ..SearchOptions::default()
    };

    let small_stats = run_profile(&store, table, "small", small, &queries).await;
    let medium_stats = run_profile(&store, table, "medium", medium, &queries).await;
    let large_stats = run_profile(&store, table, "large", large, &queries).await;

    let max_p95 = env_f64("OMNI_VECTOR_PERF_P95_MS", 700.0);
    let max_ratio = env_f64("OMNI_VECTOR_PERF_RATIO_MAX", 4.0);

    println!(
        "search_optimized perf: small(avg={:.2}ms,p50={:.2}ms,p95={:.2}ms), \
medium(avg={:.2}ms,p50={:.2}ms,p95={:.2}ms), \
large(avg={:.2}ms,p50={:.2}ms,p95={:.2}ms)",
        small_stats.avg_ms,
        small_stats.p50_ms,
        small_stats.p95_ms,
        medium_stats.avg_ms,
        medium_stats.p50_ms,
        medium_stats.p95_ms,
        large_stats.avg_ms,
        large_stats.p50_ms,
        large_stats.p95_ms
    );

    // Absolute guardrails (conservative for CI variability).
    // Catch multi-second regressions or accidental full scans.
    assert!(
        small_stats.p95_ms < max_p95,
        "small profile regression: p95={:.2}ms",
        small_stats.p95_ms
    );
    assert!(
        medium_stats.p95_ms < max_p95,
        "medium profile regression: p95={:.2}ms",
        medium_stats.p95_ms
    );
    assert!(
        large_stats.p95_ms < max_p95,
        "large profile regression: p95={:.2}ms",
        large_stats.p95_ms
    );

    // Relative guardrails: profiles should not diverge wildly.
    assert!(
        medium_stats.avg_ms <= small_stats.avg_ms * max_ratio,
        "medium profile too slow vs small: medium={:.2}ms small={:.2}ms ratio_max={:.2}",
        medium_stats.avg_ms,
        small_stats.avg_ms,
        max_ratio
    );
    assert!(
        large_stats.avg_ms <= medium_stats.avg_ms * max_ratio,
        "large profile too slow vs medium: large={:.2}ms medium={:.2}ms ratio_max={:.2}",
        large_stats.avg_ms,
        medium_stats.avg_ms,
        max_ratio
    );
}
