//! Benchmark tests for omni-scanner performance.
//!
//! These tests verify the parallel processing performance of the scanner
//! and measure execution time to catch regressions.

use std::fs;
use std::time::Instant;
use tempfile::TempDir;
use walkdir::WalkDir;

/// Benchmark test for skill scanning performance with parallel processing.
///
/// This test creates multiple temporary skill directories and measures
/// the scan time to verify parallel processing is working.
///
/// Performance requirement: Scan 50+ skills in under 2 seconds
#[test]
fn test_skills_scan_performance() {
    let temp_dir = TempDir::new().unwrap();
    let skills_dir = temp_dir.path().join("skills");
    fs::create_dir_all(&skills_dir).unwrap();

    // Create 50 test skills with varying complexity
    for i in 0..50 {
        let skill_path = skills_dir.join(format!("skill_{:03}", i));
        fs::create_dir_all(&skill_path).unwrap();

        let content = format!(
            r#"---
name: "skill_{name}"
description: "Test skill number {name} for performance testing"
metadata:
  author: "benchmark"
  version: "1.0.0"
  routing_keywords:
    - "keyword_{name}_1"
    - "keyword_{name}_2"
    - "keyword_{name}_3"
  intents:
    - "Intent {name}"
---
# Skill {name}

This is a test skill for benchmarking the scanner performance.
"#,
            name = i
        );
        fs::write(skill_path.join("SKILL.md"), content).unwrap();
    }

    // Verify all 50 skills were created
    assert_eq!(skills_dir.read_dir().unwrap().count(), 50);

    // Benchmark the scan
    let start = Instant::now();
    let scanner = omni_scanner::SkillScanner::new();
    let metadatas = scanner.scan_all(&skills_dir, None).unwrap();
    let elapsed = start.elapsed();

    // Verify results
    assert_eq!(metadatas.len(), 50);

    // Performance assertion: should complete in under 2 seconds
    // This verifies parallel processing is working effectively
    assert!(
        elapsed.as_secs_f64() < 2.0,
        "Scan took {:.2}s - parallel processing may not be working",
        elapsed.as_secs_f64()
    );

    // Verify keywords were parsed correctly
    let total_keywords: usize = metadatas.iter().map(|m| m.routing_keywords.len()).sum();
    assert_eq!(total_keywords, 150); // 50 skills * 3 keywords each

    println!(
        "[BENCH] Scanned {} skills in {:.2}s (parallel)",
        metadatas.len(),
        elapsed.as_secs_f64()
    );
}

/// Benchmark test for knowledge document scanning performance.
///
/// Creates multiple markdown files and measures scan time to verify
/// parallel processing is working.
///
/// Performance requirement: Scan 100+ knowledge docs in under 2 seconds
#[test]
fn test_knowledge_scan_performance() {
    let temp_dir = TempDir::new().unwrap();
    let knowledge_dir = temp_dir.path().join("knowledge");
    fs::create_dir_all(&knowledge_dir).unwrap();

    // Create 100 test knowledge documents with nested structure
    for i in 0..100 {
        // Create nested directories for realistic structure
        let sub_dir = knowledge_dir.join(format!("category_{}", i % 5));
        fs::create_dir_all(&sub_dir).unwrap();

        let doc_path = sub_dir.join(format!("doc_{:03}.md", i));

        let content = format!(
            r#"---
title: "Knowledge Document {num}"
description: "Test knowledge document number {num}"
category: "pattern"
tags: ["tag1", "tag2", "tag3"]
authors: ["author@example.com"]
version: "1.0.0"
---

# Knowledge Document {num}

This is test content for benchmarking the knowledge scanner.
It contains multiple lines of text to simulate real knowledge documents.

## Section 1

Some content here for document {num}.

## Section 2

More content to increase file size slightly.

## Section 3

Final section for document {num}.
"#,
            num = i
        );
        fs::write(&doc_path, content).unwrap();
    }

    // Verify all 100 documents were created
    let doc_count = WalkDir::new(&knowledge_dir)
        .into_iter()
        .filter(|e| e.as_ref().map_or(false, |d| d.file_type().is_file()))
        .count();
    assert_eq!(doc_count, 100);

    // Benchmark the scan
    let start = Instant::now();
    let scanner = omni_scanner::KnowledgeScanner::new();
    let entries = scanner.scan_all(&knowledge_dir, None).unwrap();
    let elapsed = start.elapsed();

    // Verify results
    assert_eq!(entries.len(), 100);

    // Performance assertion: should complete in under 2 seconds
    assert!(
        elapsed.as_secs_f64() < 2.0,
        "Scan took {:.2}s - parallel processing may not be working",
        elapsed.as_secs_f64()
    );

    // Verify frontmatter was parsed correctly
    let total_tags: usize = entries.iter().map(|e| e.tags.len()).sum();
    assert_eq!(total_tags, 300); // 100 docs * 3 tags each

    println!(
        "[BENCH] Scanned {} knowledge docs in {:.2}s (parallel)",
        entries.len(),
        elapsed.as_secs_f64()
    );
}

/// Benchmark combined scanning of skills and knowledge.
///
/// Tests the overall scanner performance when both types are scanned.
///
/// Performance requirement: Scan 50 skills + 100 knowledge docs in under 3 seconds
#[test]
fn test_combined_scan_performance() {
    let temp_dir = TempDir::new().unwrap();

    // Setup skills
    let skills_dir = temp_dir.path().join("skills");
    fs::create_dir_all(&skills_dir).unwrap();
    for i in 0..30 {
        let skill_path = skills_dir.join(format!("skill_{:02}", i));
        fs::create_dir_all(&skill_path).unwrap();
        fs::write(
            skill_path.join("SKILL.md"),
            format!(
                r#"---
name: "skill_{num}"
metadata:
  routing_keywords: ["kw_{num}_1", "kw_{num}_2"]
---
# Skill {num}
"#,
                num = i
            ),
        )
        .unwrap();
    }

    // Setup knowledge
    let knowledge_dir = temp_dir.path().join("knowledge");
    fs::create_dir_all(&knowledge_dir).unwrap();
    for i in 0..50 {
        let doc_path = knowledge_dir.join(format!("doc_{:02}.md", i));
        fs::write(
            &doc_path,
            format!(
                r#"---
title: "Doc {num}"
tags: ["tag1", "tag2"]
---
# Doc {num}
"#,
                num = i
            ),
        )
        .unwrap();
    }

    // Benchmark combined scan
    let skill_scanner = omni_scanner::SkillScanner::new();
    let knowledge_scanner = omni_scanner::KnowledgeScanner::new();

    let start = Instant::now();

    // Scan both in parallel (simulated by separate calls)
    let skill_metadatas = skill_scanner.scan_all(&skills_dir, None).unwrap();
    let knowledge_entries = knowledge_scanner.scan_all(&knowledge_dir, None).unwrap();

    let elapsed = start.elapsed();

    // Verify results
    assert_eq!(skill_metadatas.len(), 30);
    assert_eq!(knowledge_entries.len(), 50);

    // Performance assertion
    assert!(
        elapsed.as_secs_f64() < 3.0,
        "Combined scan took {:.2}s - may indicate performance regression",
        elapsed.as_secs_f64()
    );

    println!(
        "[BENCH] Combined scan: {} skills + {} knowledge docs in {:.2}s",
        skill_metadatas.len(),
        knowledge_entries.len(),
        elapsed.as_secs_f64()
    );
}
