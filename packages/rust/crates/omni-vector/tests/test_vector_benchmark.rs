//! Benchmark tests for vector operations performance.
//!
//! These tests measure the performance of L2 distance calculations,
//! JSON parsing in search paths, and other vector operations.

use rand::Rng;
use std::time::Duration;

/// Generate a random vector for benchmarking.
fn generate_vector(dim: usize) -> Vec<f32> {
    let mut rng = rand::thread_rng();
    (0..dim).map(|_| rng.gen_range(-1.0..1.0)).collect()
}

/// Generate vectors for benchmarking.
fn generate_vectors(count: usize, dim: usize) -> Vec<Vec<f32>> {
    (0..count).map(|_| generate_vector(dim)).collect()
}

/// Compute L2 distance between two vectors.
fn compute_l2_distance(a: &[f32], b: &[f32]) -> f32 {
    let mut distance = 0.0f32;
    let len = a.len().min(b.len());
    for i in 0..len {
        let diff = a[i] - b[i];
        distance += diff * diff;
    }
    distance.sqrt()
}

/// Compute L2 distance using iterator (potential SIMD-friendly).
fn compute_l2_distance_iter(a: &[f32], b: &[f32]) -> f32 {
    a.iter()
        .zip(b.iter())
        .map(|(x, y)| {
            let diff = x - y;
            diff * diff
        })
        .sum::<f32>()
        .sqrt()
}

/// Benchmark test for L2 distance calculation.
#[test]
fn test_l2_distance_performance() {
    const DIM: usize = 1536;
    const ITERATIONS: usize = 1000;

    let query = generate_vector(DIM);
    let candidates = generate_vectors(100, DIM);

    let start = std::time::Instant::now();

    for _ in 0..ITERATIONS {
        for candidate in &candidates {
            let _ = compute_l2_distance(&query, candidate);
        }
    }

    let elapsed = start.elapsed();

    // Should compute 1000 x 100 = 100K distances in under 1s (relaxed for dev environment)
    let max_duration = Duration::from_secs(1);
    assert!(
        elapsed < max_duration,
        "L2 distance calculation took {:.2}ms for {} iterations",
        elapsed.as_secs_f64() * 1000.0,
        ITERATIONS
    );

    println!(
        "L2 distance: {} iterations x {} vectors (dim={}) = {:.2}ms",
        ITERATIONS,
        candidates.len(),
        DIM,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for L2 distance with varying dimensions.
#[test]
fn test_l2_distance_varying_dimensions() {
    const ITERATIONS: usize = 1000;

    let dims = [384, 768, 1536, 3072];

    for dim in dims {
        let query = generate_vector(dim);
        let candidates = generate_vectors(50, dim);

        let start = std::time::Instant::now();

        for _ in 0..ITERATIONS {
            for candidate in &candidates {
                let _ = compute_l2_distance(&query, candidate);
            }
        }

        let elapsed = start.elapsed();

        println!(
            "L2 distance (dim={}): {:.2}ms for {} iterations",
            dim,
            elapsed.as_secs_f64() * 1000.0,
            ITERATIONS
        );
    }
}

/// Benchmark test for iterator-based L2 distance.
#[test]
fn test_l2_distance_iterator() {
    const DIM: usize = 1536;
    const ITERATIONS: usize = 100;

    let query = generate_vector(DIM);
    let candidates = generate_vectors(100, DIM);

    let start = std::time::Instant::now();

    for _ in 0..ITERATIONS {
        for candidate in &candidates {
            let _ = compute_l2_distance_iter(&query, candidate);
        }
    }

    let elapsed = start.elapsed();

    // Iterator version may be slower but is SIMD-friendly (relaxed for dev)
    let max_duration = Duration::from_secs(2);
    assert!(
        elapsed < max_duration,
        "Iterator L2 distance took {:.2}ms",
        elapsed.as_secs_f64() * 1000.0
    );

    println!(
        "Iterator L2 distance: {} iterations = {:.2}ms",
        ITERATIONS,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for JSON parsing in search paths.
#[test]
fn test_json_parsing_performance() {
    const ITERATIONS: usize = 1000;

    // Generate realistic metadata JSON
    let metadata = serde_json::json!({
        "skill_name": "test_skill",
        "tool_name": "test_tool",
        "file_path": "path/to/file.py",
        "function_name": "test_function",
        "keywords": ["test", "benchmark", "performance"],
        "docstring": "This is a test function",
        "input_schema": {
            "type": "object",
            "properties": {
                "param1": {"type": "string"},
                "param2": {"type": "integer"}
            }
        }
    });
    let metadata_str = metadata.to_string();

    let start = std::time::Instant::now();

    for _ in 0..ITERATIONS {
        let parsed: Result<serde_json::Value, _> = serde_json::from_str(&metadata_str);
        assert!(parsed.is_ok());
    }

    let elapsed = start.elapsed();

    // Should parse 1000 JSON objects in under 50ms
    let max_duration = Duration::from_millis(50);
    assert!(
        elapsed < max_duration,
        "JSON parsing took {:.2}ms for {} iterations",
        elapsed.as_secs_f64() * 1000.0,
        ITERATIONS
    );

    println!(
        "JSON parsing: {} iterations = {:.2}ms",
        ITERATIONS,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for JSON filtering.
#[test]
fn test_json_filtering_performance() {
    const ITERATIONS: usize = 100;

    // Generate metadata with various types
    let metadata_items: Vec<(String, serde_json::Value)> = (0..100)
        .map(|i| {
            let meta = serde_json::json!({
                "skill_name": format!("skill_{}", i % 10),
                "tool_name": format!("tool_{}", i % 20),
                "file_path": format!("path/to/file_{}.py", i),
                "keywords": ["test"],
                "score": i as f64 / 100.0
            });
            (meta.to_string(), meta)
        })
        .collect();

    // Create filter
    let filter = serde_json::json!({
        "skill_name": "skill_5"
    });

    let start = std::time::Instant::now();

    for _ in 0..ITERATIONS {
        for (str_val, _) in &metadata_items {
            // Simulate filter matching
            if let Ok(parsed_val) = serde_json::from_str::<serde_json::Value>(str_val) {
                if let Some(skill) = parsed_val.get("skill_name") {
                    if skill == filter.get("skill_name").unwrap() {
                        continue;
                    }
                }
            }
        }
    }

    let elapsed = start.elapsed();

    // Should complete 100 iterations in under 1s (relaxed for dev environment)
    let max_duration = Duration::from_secs(1);
    assert!(
        elapsed < max_duration,
        "JSON filtering took {:.2}ms",
        elapsed.as_secs_f64() * 1000.0
    );

    println!(
        "JSON filtering: {} iterations x 100 items = {:.2}ms",
        ITERATIONS,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for batch L2 distance computation.
#[test]
fn test_batch_l2_distance_performance() {
    const BATCH_SIZE: usize = 100;
    const DIM: usize = 1536;
    const QUERY_COUNT: usize = 10;

    let queries: Vec<Vec<f32>> = (0..QUERY_COUNT).map(|_| generate_vector(DIM)).collect();
    let database: Vec<Vec<f32>> = generate_vectors(BATCH_SIZE, DIM);

    let start = std::time::Instant::now();

    // Compute distances for all query-database pairs
    for query in &queries {
        for db_vec in &database {
            let _ = compute_l2_distance(query, db_vec);
        }
    }

    let elapsed = start.elapsed();
    let total_distances = QUERY_COUNT * BATCH_SIZE;

    // Should compute 1000 distances in under 10ms
    let max_duration = Duration::from_millis(10);
    assert!(
        elapsed < max_duration,
        "Batch L2 took {:.2}ms for {} distances",
        elapsed.as_secs_f64() * 1000.0,
        total_distances
    );

    println!(
        "Batch L2: {} queries x {} vectors = {:.2}ms ({} distances)",
        QUERY_COUNT,
        BATCH_SIZE,
        elapsed.as_secs_f64() * 1000.0,
        total_distances
    );
}

/// Benchmark test for vector sorting by distance.
#[test]
fn test_vector_sorting_performance() {
    const VECTOR_COUNT: usize = 1000;
    const DIM: usize = 384;

    let query = generate_vector(DIM);
    let mut vectors: Vec<(Vec<f32>, String)> = generate_vectors(VECTOR_COUNT, DIM)
        .into_iter()
        .enumerate()
        .map(|(i, v)| (v, format!("vector_{}", i)))
        .collect();

    let start = std::time::Instant::now();

    // Sort by distance to query
    vectors.sort_by(|a, b| {
        let dist_a = compute_l2_distance(&query, &a.0);
        let dist_b = compute_l2_distance(&query, &b.0);
        dist_a
            .partial_cmp(&dist_b)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let elapsed = start.elapsed();

    // Should sort 1000 vectors with distance computation in under 1s (relaxed for dev)
    let max_duration = Duration::from_secs(1);
    assert!(
        elapsed < max_duration,
        "Vector sorting took {:.2}ms",
        elapsed.as_secs_f64() * 1000.0
    );

    println!(
        "Vector sorting: {} vectors = {:.2}ms",
        VECTOR_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Verify correctness of L2 distance computation.
#[test]
fn test_l2_distance_correctness() {
    // Simple case: identical vectors should have distance 0
    let v1 = vec![1.0, 0.0, 0.0];
    let v2 = vec![1.0, 0.0, 0.0];
    assert_eq!(compute_l2_distance(&v1, &v2), 0.0);

    // Distance from origin
    let origin = vec![0.0, 0.0, 0.0];
    let v = vec![3.0, 4.0, 0.0];
    assert_eq!(compute_l2_distance(&origin, &v), 5.0);

    // Symmetry
    let a = vec![1.0, 2.0, 3.0];
    let b = vec![4.0, 5.0, 6.0];
    let d1 = compute_l2_distance(&a, &b);
    let d2 = compute_l2_distance(&b, &a);
    assert!((d1 - d2).abs() < 1e-6);

    // Both implementations should match
    assert!((compute_l2_distance(&a, &b) - compute_l2_distance_iter(&a, &b)).abs() < 1e-6);
}
