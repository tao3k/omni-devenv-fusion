//! Benchmark tests for entity_aware search performance.

use omni_vector::HybridSearchResult;
use omni_vector::keyword::entity_aware::{
    EntityAwareSearchResult, EntityMatch, EntityMatchType, apply_entity_boost, apply_triple_rrf,
};
use omni_vector::skill::ToolSearchResult;
use rand::Rng;
use serde_json::Value;

/// Generate test entities for benchmarking.
fn generate_entities(count: usize) -> Vec<EntityMatch> {
    let mut entities = Vec::with_capacity(count);
    let types = ["PERSON", "TOOL", "CONCEPT", "ORG", "EVENT"];

    for i in 0..count {
        entities.push(EntityMatch {
            entity_name: format!("entity_{}", i),
            entity_type: types[i % types.len()].to_string(),
            confidence: 0.5 + (i as f32 % 10.0) / 20.0,
            match_type: EntityMatchType::NameMatch,
        });
    }

    entities
}

/// Generate test search results for benchmarking.
fn generate_results(count: usize) -> Vec<HybridSearchResult> {
    let mut results = Vec::with_capacity(count);
    let mut rng = rand::thread_rng();

    for i in 0..count {
        results.push(HybridSearchResult {
            tool_name: format!("tool_{}", i % 50),
            rrf_score: rng.gen_range(0.01..1.0),
            vector_score: rng.gen_range(0.0..1.0),
            keyword_score: rng.gen_range(0.0..1.0),
        });
    }

    results
}

/// Generate test keyword results.
fn generate_keyword_results(count: usize) -> Vec<ToolSearchResult> {
    let results: Vec<ToolSearchResult> = (0..count)
        .map(|i| ToolSearchResult {
            name: format!("tool_{}", i % 50),
            description: format!("Description for tool {}", i % 50),
            input_schema: Value::Object(serde_json::Map::new()),
            score: rand::thread_rng().gen_range(0.0..1.0),
            vector_score: None,
            keyword_score: None,
            skill_name: format!("skill_{}", i % 5),
            tool_name: format!("tool_{}", i % 50),
            file_path: format!("/tools/tool_{}.yaml", i % 50),
            routing_keywords: vec![],
            intents: vec![],
            category: "benchmark".to_string(),
            parameters: vec![],
        })
        .collect();

    results
}

/// Benchmark test for entity matching performance.
#[test]
fn test_entity_matching_performance() {
    const ENTITY_COUNT: usize = 100;
    const RESULT_COUNT: usize = 100;

    let entities = generate_entities(ENTITY_COUNT);
    let results = generate_results(RESULT_COUNT);

    let start = std::time::Instant::now();

    for _ in 0..100 {
        let _aware = apply_entity_boost(results.clone(), entities.clone(), 0.3, None);
    }

    let elapsed = start.elapsed();

    // Should complete 100 iterations in under 100ms
    let max_duration = std::time::Duration::from_millis(100);
    assert!(
        elapsed < max_duration,
        "Entity matching took {:.2}ms for 100 iterations, expected < 100ms",
        elapsed.as_secs_f64() * 1000.0
    );

    println!(
        "Entity matching: 100 iterations x {} entities x {} results = {:.2}ms",
        ENTITY_COUNT,
        RESULT_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for entity matching with metadata.
#[test]
fn test_entity_matching_with_metadata_performance() {
    const ENTITY_COUNT: usize = 50;
    const RESULT_COUNT: usize = 50;
    const METADATA_COUNT: usize = 10;

    let entities = generate_entities(ENTITY_COUNT);
    let results = generate_results(RESULT_COUNT);

    // Generate metadata
    let metadata: Vec<serde_json::Value> = (0..METADATA_COUNT)
        .map(|i| {
            serde_json::json!({
                "content": format!("This document mentions entity_{} in the context of tool_{}", i, i % 10),
                "source": format!("doc_{}.md", i)
            })
        })
        .collect();

    let start = std::time::Instant::now();

    for _ in 0..50 {
        let _aware = apply_entity_boost(results.clone(), entities.clone(), 0.3, Some(&metadata));
    }

    let elapsed = start.elapsed();

    // Should complete 50 iterations in under 500ms (metadata adds overhead)
    let max_duration = std::time::Duration::from_millis(500);
    assert!(
        elapsed < max_duration,
        "Entity matching with metadata took {:.2}ms for 50 iterations, expected < 500ms",
        elapsed.as_secs_f64() * 1000.0
    );

    println!(
        "Entity matching with metadata: 50 iterations = {:.2}ms",
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for triple RRF fusion performance.
#[test]
fn test_triple_rrf_performance() {
    const RESULT_COUNT: usize = 100;

    let semantic_results: Vec<(String, f32)> = (0..RESULT_COUNT)
        .map(|i| {
            (
                format!("tool_{}", i % 50),
                1.0 - (i as f32 / RESULT_COUNT as f32),
            )
        })
        .collect();

    let keyword_results = generate_keyword_results(RESULT_COUNT);

    let entity_results: Vec<EntityAwareSearchResult> = (0..RESULT_COUNT)
        .map(|i| EntityAwareSearchResult {
            base: HybridSearchResult {
                tool_name: format!("tool_{}", i % 50),
                rrf_score: 0.1,
                vector_score: 0.0,
                keyword_score: 0.0,
            },
            entity_matches: vec![EntityMatch {
                entity_name: format!("entity_{}", i),
                entity_type: "TOOL".to_string(),
                confidence: 0.8,
                match_type: EntityMatchType::NameMatch,
            }],
            boosted_score: 0.15,
        })
        .collect();

    let start = std::time::Instant::now();

    for _ in 0..100 {
        let _fused = apply_triple_rrf(
            semantic_results.clone(),
            keyword_results.clone(),
            entity_results.clone(),
            60.0,
        );
    }

    let elapsed = start.elapsed();

    // Should complete 100 iterations in under 50ms
    let max_duration = std::time::Duration::from_millis(50);
    assert!(
        elapsed < max_duration,
        "Triple RRF took {:.2}ms for 100 iterations, expected < 50ms",
        elapsed.as_secs_f64() * 1000.0
    );

    println!(
        "Triple RRF fusion: 100 iterations x {} results = {:.2}ms",
        RESULT_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for large-scale entity matching.
#[test]
fn test_large_scale_entity_matching() {
    const ENTITY_COUNT: usize = 500;
    const RESULT_COUNT: usize = 200;

    let entities = generate_entities(ENTITY_COUNT);
    let results = generate_results(RESULT_COUNT);

    let start = std::time::Instant::now();

    for _ in 0..10 {
        let _aware = apply_entity_boost(results.clone(), entities.clone(), 0.3, None);
    }

    let elapsed = start.elapsed();

    // Should complete 10 iterations in under 50ms
    let max_duration = std::time::Duration::from_millis(50);
    assert!(
        elapsed < max_duration,
        "Large-scale matching took {:.2}ms for 10 iterations, expected < 50ms",
        elapsed.as_secs_f64() * 1000.0
    );

    println!(
        "Large-scale entity matching: 10 iterations x {} entities x {} results = {:.2}ms",
        ENTITY_COUNT,
        RESULT_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}
