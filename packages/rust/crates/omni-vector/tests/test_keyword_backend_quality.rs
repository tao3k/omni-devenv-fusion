//! Quality comparison scenarios for Tantivy vs Lance FTS keyword retrieval.

use std::collections::{HashMap, HashSet};

use insta::assert_json_snapshot;
use omni_vector::{KeywordSearchBackend, ToolSearchResult, VectorStore};
use serde_json::json;

const TABLE: &str = "tools";
const K: usize = 5;
const FETCH_K: usize = 20;

struct ScenarioQuery {
    name: &'static str,
    query: &'static str,
    relevant: &'static [&'static str],
}

struct ScenarioQueryV2 {
    name: &'static str,
    query: &'static str,
    relevant: &'static [(&'static str, u8)],
}

#[derive(Debug, Clone)]
struct ScenarioQueryDyn {
    name: String,
    query: String,
    scene: String,
    relevant: Vec<(String, u8)>,
}

#[derive(Debug, Clone)]
struct QueryMetrics {
    precision_at_k: f32,
    recall_at_k: f32,
    reciprocal_rank: f32,
    ndcg_at_k: f32,
    success_at_1: f32,
}

fn eval_query(hits: &[ToolSearchResult], relevant: &[&str], k: usize) -> QueryMetrics {
    let relevant_set: HashSet<&str> = relevant.iter().copied().collect();
    let topk = hits.iter().take(k).collect::<Vec<_>>();
    let relevant_hits = topk
        .iter()
        .filter(|h| relevant_set.contains(h.tool_name.as_str()))
        .count();
    let precision_at_k = relevant_hits as f32 / k as f32;
    let recall_at_k = if relevant.is_empty() {
        0.0
    } else {
        relevant_hits as f32 / relevant.len() as f32
    };

    let reciprocal_rank = topk
        .iter()
        .position(|h| relevant_set.contains(h.tool_name.as_str()))
        .map(|idx| 1.0 / (idx as f32 + 1.0))
        .unwrap_or(0.0);

    QueryMetrics {
        precision_at_k,
        recall_at_k,
        reciprocal_rank,
        ndcg_at_k: 0.0,
        success_at_1: 0.0,
    }
}

fn eval_query_v2(hits: &[ToolSearchResult], relevant: &[(&str, u8)], k: usize) -> QueryMetrics {
    let relevance: HashMap<&str, u8> = relevant.iter().copied().collect();
    let topk = hits.iter().take(k).collect::<Vec<_>>();

    let relevant_hits = topk
        .iter()
        .filter(|h| relevance.contains_key(h.tool_name.as_str()))
        .count();
    let precision_at_k = relevant_hits as f32 / k as f32;
    let recall_at_k = if relevant.is_empty() {
        0.0
    } else {
        relevant_hits as f32 / relevant.len() as f32
    };

    let reciprocal_rank = topk
        .iter()
        .position(|h| relevance.contains_key(h.tool_name.as_str()))
        .map(|idx| 1.0 / (idx as f32 + 1.0))
        .unwrap_or(0.0);

    let dcg = topk.iter().enumerate().fold(0.0f32, |acc, (idx, hit)| {
        let rel = relevance.get(hit.tool_name.as_str()).copied().unwrap_or(0) as f32;
        if rel <= 0.0 {
            acc
        } else {
            let gain = 2.0f32.powf(rel) - 1.0;
            let discount = (idx as f32 + 2.0).log2();
            acc + gain / discount
        }
    });

    let mut ideal_rels = relevant.iter().map(|(_, r)| *r as f32).collect::<Vec<_>>();
    ideal_rels.sort_by(|a, b| b.partial_cmp(a).unwrap_or(std::cmp::Ordering::Equal));
    let idcg = ideal_rels
        .iter()
        .take(k)
        .enumerate()
        .fold(0.0f32, |acc, (idx, rel)| {
            if *rel <= 0.0 {
                acc
            } else {
                let gain = 2.0f32.powf(*rel) - 1.0;
                let discount = (idx as f32 + 2.0).log2();
                acc + gain / discount
            }
        });
    let ndcg_at_k = if idcg > 0.0 { dcg / idcg } else { 0.0 };

    let success_at_1 = topk
        .first()
        .map(|h| relevance.contains_key(h.tool_name.as_str()) as i32 as f32)
        .unwrap_or(0.0);

    QueryMetrics {
        precision_at_k,
        recall_at_k,
        reciprocal_rank,
        ndcg_at_k,
        success_at_1,
    }
}

fn eval_query_dyn(hits: &[ToolSearchResult], relevant: &[(String, u8)], k: usize) -> QueryMetrics {
    let relevance: HashMap<&str, u8> = relevant.iter().map(|(n, r)| (n.as_str(), *r)).collect();
    let topk = hits.iter().take(k).collect::<Vec<_>>();

    let relevant_hits = topk
        .iter()
        .filter(|h| relevance.contains_key(h.tool_name.as_str()))
        .count();
    let precision_at_k = relevant_hits as f32 / k as f32;
    let recall_at_k = if relevant.is_empty() {
        0.0
    } else {
        relevant_hits as f32 / relevant.len() as f32
    };

    let reciprocal_rank = topk
        .iter()
        .position(|h| relevance.contains_key(h.tool_name.as_str()))
        .map(|idx| 1.0 / (idx as f32 + 1.0))
        .unwrap_or(0.0);

    let dcg = topk.iter().enumerate().fold(0.0f32, |acc, (idx, hit)| {
        let rel = relevance.get(hit.tool_name.as_str()).copied().unwrap_or(0) as f32;
        if rel <= 0.0 {
            acc
        } else {
            let gain = 2.0f32.powf(rel) - 1.0;
            let discount = (idx as f32 + 2.0).log2();
            acc + gain / discount
        }
    });

    let mut ideal_rels = relevant.iter().map(|(_, r)| *r as f32).collect::<Vec<_>>();
    ideal_rels.sort_by(|a, b| b.partial_cmp(a).unwrap_or(std::cmp::Ordering::Equal));
    let idcg = ideal_rels
        .iter()
        .take(k)
        .enumerate()
        .fold(0.0f32, |acc, (idx, rel)| {
            if *rel <= 0.0 {
                acc
            } else {
                let gain = 2.0f32.powf(*rel) - 1.0;
                let discount = (idx as f32 + 2.0).log2();
                acc + gain / discount
            }
        });
    let ndcg_at_k = if idcg > 0.0 { dcg / idcg } else { 0.0 };

    let success_at_1 = topk
        .first()
        .map(|h| relevance.contains_key(h.tool_name.as_str()) as i32 as f32)
        .unwrap_or(0.0);

    QueryMetrics {
        precision_at_k,
        recall_at_k,
        reciprocal_rank,
        ndcg_at_k,
        success_at_1,
    }
}

fn avg(values: impl Iterator<Item = f32>, count: usize) -> f32 {
    if count == 0 {
        return 0.0;
    }
    values.sum::<f32>() / count as f32
}

fn normalize_hits(mut hits: Vec<ToolSearchResult>, k: usize) -> Vec<ToolSearchResult> {
    hits.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.tool_name.cmp(&b.tool_name))
    });
    hits.truncate(k);
    hits
}

fn matched_relevant_from_v1(hits: &[ToolSearchResult], relevant: &[&str]) -> Vec<String> {
    let relevant_set: HashSet<&str> = relevant.iter().copied().collect();
    let mut matched = hits
        .iter()
        .filter_map(|h| {
            if relevant_set.contains(h.tool_name.as_str()) {
                Some(h.tool_name.clone())
            } else {
                None
            }
        })
        .collect::<Vec<_>>();
    matched.sort();
    matched.dedup();
    matched
}

fn matched_relevant_from_v2(hits: &[ToolSearchResult], relevant: &[(&str, u8)]) -> Vec<String> {
    let relevant_set: HashSet<&str> = relevant.iter().map(|(name, _)| *name).collect();
    let mut matched = hits
        .iter()
        .filter_map(|h| {
            if relevant_set.contains(h.tool_name.as_str()) {
                Some(h.tool_name.clone())
            } else {
                None
            }
        })
        .collect::<Vec<_>>();
    matched.sort();
    matched.dedup();
    matched
}

fn matched_relevant_from_dyn(hits: &[ToolSearchResult], relevant: &[(String, u8)]) -> Vec<String> {
    let relevant_set: HashSet<&str> = relevant.iter().map(|(name, _)| name.as_str()).collect();
    let mut matched = hits
        .iter()
        .filter_map(|h| {
            if relevant_set.contains(h.tool_name.as_str()) {
                Some(h.tool_name.clone())
            } else {
                None
            }
        })
        .collect::<Vec<_>>();
    matched.sort();
    matched.dedup();
    matched
}

async fn build_quality_store() -> (tempfile::TempDir, VectorStore) {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("keyword_quality_store");
    let store = VectorStore::new_with_keyword_index(db_path.to_str().unwrap(), Some(8), true)
        .await
        .unwrap();

    let docs = vec![
        (
            "git.commit",
            "Create commit message and record staged changes in git history.",
            "git",
            vec!["commit", "message", "changes"],
            vec!["save changes", "record work"],
        ),
        (
            "git.rebase",
            "Rewrite git history and squash commits with interactive rebase.",
            "git",
            vec!["rebase", "squash", "history"],
            vec!["rewrite history", "clean commits"],
        ),
        (
            "git.status",
            "Inspect repository working tree status and staged changes.",
            "git",
            vec!["status", "staged", "working tree"],
            vec!["check state"],
        ),
        (
            "docker.build",
            "Build container image from Dockerfile with tags and cache controls.",
            "docker",
            vec!["docker", "build", "image"],
            vec!["build image"],
        ),
        (
            "docker.run",
            "Run container interactively with environment variables and ports.",
            "docker",
            vec!["docker", "run", "container"],
            vec!["start container"],
        ),
        (
            "python.pytest",
            "Execute pytest test suite with markers and coverage options.",
            "python",
            vec!["pytest", "tests", "coverage"],
            vec!["run tests", "unit test"],
        ),
        (
            "python.mypy",
            "Run static type checking and report typing errors.",
            "python",
            vec!["typing", "mypy", "type check"],
            vec!["check typing"],
        ),
        (
            "k8s.rollout_restart",
            "Restart Kubernetes deployment rollout to pick up new image.",
            "k8s",
            vec!["kubernetes", "deployment", "rollout"],
            vec!["restart deployment"],
        ),
        (
            "security.gitleaks",
            "Scan repository for hardcoded secrets and leaked tokens.",
            "security",
            vec!["secrets", "scan", "token"],
            vec!["secret scan"],
        ),
        (
            "ci.github_actions",
            "Trigger GitHub Actions workflow and inspect pipeline jobs.",
            "ci",
            vec!["github actions", "workflow", "pipeline"],
            vec!["run ci", "inspect jobs"],
        ),
    ];

    let ids = docs.iter().map(|d| d.0.to_string()).collect::<Vec<_>>();
    let vectors = (0..docs.len()).map(|_| vec![0.0; 8]).collect::<Vec<_>>();
    let contents = docs.iter().map(|d| d.1.to_string()).collect::<Vec<_>>();
    let metadatas = docs
        .iter()
        .map(|d| {
            json!({
                "type":"command",
                "skill_name": d.2,
                "tool_name": d.0,
                "keywords": d.3,
                "intents": d.4,
            })
            .to_string()
        })
        .collect::<Vec<_>>();

    store
        .add_documents(TABLE, ids, vectors, contents, metadatas)
        .await
        .unwrap();
    store.create_fts_index(TABLE).await.unwrap();

    (temp_dir, store)
}

#[tokio::test]
async fn snapshot_keyword_backend_quality_scenarios_v1() {
    let (_temp_dir, mut store) = build_quality_store().await;

    let scenarios = vec![
        ScenarioQuery {
            name: "commit_flow",
            query: "commit changes message",
            relevant: &["git.commit"],
        },
        ScenarioQuery {
            name: "history_rewrite",
            query: "rewrite history squash commits",
            relevant: &["git.rebase"],
        },
        ScenarioQuery {
            name: "container_image",
            query: "build container image dockerfile",
            relevant: &["docker.build"],
        },
        ScenarioQuery {
            name: "test_execution",
            query: "run pytest coverage test suite",
            relevant: &["python.pytest"],
        },
        ScenarioQuery {
            name: "secret_scanning",
            query: "scan repository leaked tokens secrets",
            relevant: &["security.gitleaks"],
        },
        ScenarioQuery {
            name: "deployment_restart",
            query: "restart kubernetes deployment rollout",
            relevant: &["k8s.rollout_restart"],
        },
    ];

    let mut tantivy_rows = Vec::new();
    let mut fts_rows = Vec::new();
    let mut tantivy_metrics = Vec::new();
    let mut fts_metrics = Vec::new();

    for scenario in &scenarios {
        store
            .set_keyword_backend(KeywordSearchBackend::Tantivy)
            .unwrap();
        let tantivy_hits = store
            .keyword_search(TABLE, scenario.query, FETCH_K)
            .await
            .unwrap();
        let tantivy_hits = normalize_hits(tantivy_hits, K);
        let tantivy_eval = eval_query(&tantivy_hits, scenario.relevant, K);
        tantivy_metrics.push(tantivy_eval.clone());
        tantivy_rows.push(json!({
            "query": scenario.name,
            "text": scenario.query,
            "top1": tantivy_hits.first().map(|h| h.tool_name.clone()).unwrap_or_default(),
            "matched_relevant": matched_relevant_from_v1(&tantivy_hits, scenario.relevant),
            "p_at_5": format!("{:.4}", tantivy_eval.precision_at_k),
            "r_at_5": format!("{:.4}", tantivy_eval.recall_at_k),
            "rr": format!("{:.4}", tantivy_eval.reciprocal_rank),
        }));

        store
            .set_keyword_backend(KeywordSearchBackend::LanceFts)
            .unwrap();
        let fts_hits = store
            .keyword_search(TABLE, scenario.query, FETCH_K)
            .await
            .unwrap();
        let fts_hits = normalize_hits(fts_hits, K);
        let fts_eval = eval_query(&fts_hits, scenario.relevant, K);
        fts_metrics.push(fts_eval.clone());
        fts_rows.push(json!({
            "query": scenario.name,
            "text": scenario.query,
            "top1": fts_hits.first().map(|h| h.tool_name.clone()).unwrap_or_default(),
            "matched_relevant": matched_relevant_from_v1(&fts_hits, scenario.relevant),
            "p_at_5": format!("{:.4}", fts_eval.precision_at_k),
            "r_at_5": format!("{:.4}", fts_eval.recall_at_k),
            "rr": format!("{:.4}", fts_eval.reciprocal_rank),
        }));
    }

    let n = scenarios.len();
    let summary = json!({
        "tantivy": {
            "mean_p_at_5": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.precision_at_k), n)),
            "mean_r_at_5": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.recall_at_k), n)),
            "mrr": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.reciprocal_rank), n)),
        },
        "lance_fts": {
            "mean_p_at_5": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.precision_at_k), n)),
            "mean_r_at_5": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.recall_at_k), n)),
            "mrr": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.reciprocal_rank), n)),
        }
    });

    let report = json!({
        "k": K,
        "queries": n,
        "summary": summary,
        "tantivy_details": tantivy_rows,
        "lance_fts_details": fts_rows,
    });

    assert_json_snapshot!("keyword_backend_quality_scenarios_v1", report);
}

#[tokio::test]
async fn snapshot_keyword_backend_quality_scenarios_v2() {
    let (_temp_dir, mut store) = build_quality_store().await;

    let scenarios = vec![
        ScenarioQueryV2 {
            name: "git_state_management",
            query: "staged changes repository state",
            relevant: &[("git.status", 3), ("git.commit", 2)],
        },
        ScenarioQueryV2 {
            name: "history_cleanup",
            query: "squash commits and rewrite history",
            relevant: &[("git.rebase", 3), ("git.commit", 1)],
        },
        ScenarioQueryV2 {
            name: "container_lifecycle",
            query: "docker build image and run container",
            relevant: &[("docker.build", 3), ("docker.run", 2)],
        },
        ScenarioQueryV2 {
            name: "testing_ci_pipeline",
            query: "run tests in github actions pipeline",
            relevant: &[("ci.github_actions", 3), ("python.pytest", 3)],
        },
        ScenarioQueryV2 {
            name: "security_audit",
            query: "scan leaked secrets and token exposure",
            relevant: &[("security.gitleaks", 3)],
        },
        ScenarioQueryV2 {
            name: "typing_quality",
            query: "python static typing type check",
            relevant: &[("python.mypy", 3), ("python.pytest", 1)],
        },
        ScenarioQueryV2 {
            name: "deployment_restart",
            query: "restart rollout deployment",
            relevant: &[("k8s.rollout_restart", 3)],
        },
        ScenarioQueryV2 {
            name: "ambiguous_run_workflow",
            query: "run workflow and tests",
            relevant: &[
                ("ci.github_actions", 3),
                ("python.pytest", 2),
                ("docker.run", 1),
            ],
        },
    ];

    let mut tantivy_rows = Vec::new();
    let mut fts_rows = Vec::new();
    let mut tantivy_metrics = Vec::new();
    let mut fts_metrics = Vec::new();

    for scenario in &scenarios {
        store
            .set_keyword_backend(KeywordSearchBackend::Tantivy)
            .unwrap();
        let tantivy_hits = store
            .keyword_search(TABLE, scenario.query, FETCH_K)
            .await
            .unwrap();
        let tantivy_hits = normalize_hits(tantivy_hits, K);
        let tantivy_eval = eval_query_v2(&tantivy_hits, scenario.relevant, K);
        tantivy_metrics.push(tantivy_eval.clone());
        tantivy_rows.push(json!({
            "query": scenario.name,
            "text": scenario.query,
            "relevant": scenario.relevant.iter().map(|(name, rel)| json!({"tool": name, "grade": rel})).collect::<Vec<_>>(),
            "top1": tantivy_hits.first().map(|h| h.tool_name.clone()).unwrap_or_default(),
            "matched_relevant": matched_relevant_from_v2(&tantivy_hits, scenario.relevant),
            "p_at_5": format!("{:.4}", tantivy_eval.precision_at_k),
            "r_at_5": format!("{:.4}", tantivy_eval.recall_at_k),
            "mrr_rr": format!("{:.4}", tantivy_eval.reciprocal_rank),
            "ndcg_at_5": format!("{:.4}", tantivy_eval.ndcg_at_k),
            "success_at_1": format!("{:.4}", tantivy_eval.success_at_1),
        }));

        store
            .set_keyword_backend(KeywordSearchBackend::LanceFts)
            .unwrap();
        let fts_hits = store
            .keyword_search(TABLE, scenario.query, FETCH_K)
            .await
            .unwrap();
        let fts_hits = normalize_hits(fts_hits, K);
        let fts_eval = eval_query_v2(&fts_hits, scenario.relevant, K);
        fts_metrics.push(fts_eval.clone());
        fts_rows.push(json!({
            "query": scenario.name,
            "text": scenario.query,
            "relevant": scenario.relevant.iter().map(|(name, rel)| json!({"tool": name, "grade": rel})).collect::<Vec<_>>(),
            "top1": fts_hits.first().map(|h| h.tool_name.clone()).unwrap_or_default(),
            "matched_relevant": matched_relevant_from_v2(&fts_hits, scenario.relevant),
            "p_at_5": format!("{:.4}", fts_eval.precision_at_k),
            "r_at_5": format!("{:.4}", fts_eval.recall_at_k),
            "mrr_rr": format!("{:.4}", fts_eval.reciprocal_rank),
            "ndcg_at_5": format!("{:.4}", fts_eval.ndcg_at_k),
            "success_at_1": format!("{:.4}", fts_eval.success_at_1),
        }));
    }

    let n = scenarios.len();
    let summary = json!({
        "tantivy": {
            "mean_p_at_5": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.precision_at_k), n)),
            "mean_r_at_5": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.recall_at_k), n)),
            "mrr": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.reciprocal_rank), n)),
            "mean_ndcg_at_5": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.ndcg_at_k), n)),
            "success_at_1": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.success_at_1), n)),
        },
        "lance_fts": {
            "mean_p_at_5": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.precision_at_k), n)),
            "mean_r_at_5": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.recall_at_k), n)),
            "mrr": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.reciprocal_rank), n)),
            "mean_ndcg_at_5": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.ndcg_at_k), n)),
            "success_at_1": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.success_at_1), n)),
        }
    });

    let report = json!({
        "k": K,
        "queries": n,
        "summary": summary,
        "tantivy_details": tantivy_rows,
        "lance_fts_details": fts_rows,
    });

    assert_json_snapshot!("keyword_backend_quality_scenarios_v2", report);
}

#[tokio::test]
async fn snapshot_keyword_backend_quality_scenarios_v3_skill_based() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("keyword_quality_store_v3");
    let mut store = VectorStore::new_with_keyword_backend(
        db_path.to_str().unwrap(),
        Some(8),
        true,
        KeywordSearchBackend::Tantivy,
    )
    .await
    .unwrap();

    let docs = vec![
        (
            "advanced_tools.smart_search",
            "High-performance code search using ripgrep with file globs and context lines.",
            "advanced_tools",
            vec!["search", "ripgrep", "regex", "code"],
            vec!["find text in code", "search symbols"],
        ),
        (
            "advanced_tools.smart_find",
            "Fast recursive file and directory discovery powered by fd.",
            "advanced_tools",
            vec!["find", "files", "fd", "path"],
            vec!["locate files", "discover directories"],
        ),
        (
            "advanced_tools.batch_replace",
            "Batch regex refactoring with dry-run safety and diff preview.",
            "advanced_tools",
            vec!["replace", "refactor", "regex", "dry run"],
            vec!["mass edit code", "safe replacement"],
        ),
        (
            "knowledge.dependency_search",
            "Search symbols in external crate dependencies after upgrades.",
            "knowledge",
            vec!["dependency", "crate", "symbol", "rust"],
            vec!["inspect external api", "crate symbol lookup"],
        ),
        (
            "knowledge.zk_hybrid_search",
            "Hybrid knowledge search combining ZK links and vector fallback.",
            "knowledge",
            vec!["knowledge", "zk", "hybrid", "notes"],
            vec!["find related notes", "semantic notebook search"],
        ),
        (
            "git.smart_commit",
            "Guided git commit workflow with security scan and approval steps.",
            "git",
            vec!["git", "commit", "workflow", "security scan"],
            vec!["safe commit", "approved commit flow"],
        ),
        (
            "crawl4ai.crawl_url",
            "Crawl web pages with smart chunk planning and markdown extraction.",
            "crawl4ai",
            vec!["crawl", "web", "chunk", "markdown"],
            vec!["extract web docs", "crawl urls"],
        ),
        (
            "researcher.git_repo_analyer",
            "Sharded deep repository analysis and architecture synthesis.",
            "researcher",
            vec!["research", "repository", "analyze", "architecture"],
            vec!["analyze repo", "deep research"],
        ),
        (
            "writer.polish_text",
            "Polish text with style linting and markdown structure checks.",
            "writer",
            vec!["writing", "polish", "lint", "markdown"],
            vec!["improve docs", "fix writing style"],
        ),
        (
            "omniCell.execute",
            "Execute Nushell commands with safety analysis and structured output.",
            "omniCell",
            vec!["nushell", "execute", "command", "safety"],
            vec!["run shell safely", "structured command output"],
        ),
        (
            "skill.discover",
            "Capability discovery and intent-to-tool resolution gateway.",
            "skill",
            vec!["discover", "intent", "capability", "tooling"],
            vec!["find tool", "resolve capabilities"],
        ),
        (
            "memory.search_memory",
            "Semantic search over long-term memories and project insights.",
            "memory",
            vec!["memory", "semantic", "search", "history"],
            vec!["retrieve prior insights", "search memory bank"],
        ),
    ];

    let ids = docs.iter().map(|d| d.0.to_string()).collect::<Vec<_>>();
    let vectors = (0..docs.len()).map(|_| vec![0.0; 8]).collect::<Vec<_>>();
    let contents = docs.iter().map(|d| d.1.to_string()).collect::<Vec<_>>();
    let metadatas = docs
        .iter()
        .map(|d| {
            json!({
                "type":"command",
                "skill_name": d.2,
                "tool_name": d.0,
                "keywords": d.3,
                "intents": d.4,
            })
            .to_string()
        })
        .collect::<Vec<_>>();

    store
        .add_documents(TABLE, ids, vectors, contents, metadatas)
        .await
        .unwrap();
    store.create_fts_index(TABLE).await.unwrap();

    let scenarios = vec![
        ScenarioQueryV2 {
            name: "repo_refactor_dry_run",
            query: "批量替换 代码 dry run regex refactor",
            relevant: &[
                ("advanced_tools.batch_replace", 3),
                ("advanced_tools.smart_search", 2),
                ("advanced_tools.smart_find", 1),
            ],
        },
        ScenarioQueryV2 {
            name: "find_external_crate_symbols",
            query: "升级依赖后 查 crate symbol api",
            relevant: &[
                ("knowledge.dependency_search", 3),
                ("knowledge.zk_hybrid_search", 1),
            ],
        },
        ScenarioQueryV2 {
            name: "safe_commit_pipeline",
            query: "安全提交 需要扫描并审批 commit workflow",
            relevant: &[("git.smart_commit", 3)],
        },
        ScenarioQueryV2 {
            name: "crawl_docs_then_summarize",
            query: "crawl url 提取 markdown chunk 文档",
            relevant: &[
                ("crawl4ai.crawl_url", 3),
                ("researcher.git_repo_analyer", 1),
            ],
        },
        ScenarioQueryV2 {
            name: "choose_right_tooling",
            query: "先发现能力再执行命令 tool discover",
            relevant: &[
                ("skill.discover", 3),
                ("omniCell.execute", 2),
                ("advanced_tools.smart_search", 1),
            ],
        },
        ScenarioQueryV2 {
            name: "doc_quality_audit",
            query: "文档润色 markdown 结构 style lint",
            relevant: &[("writer.polish_text", 3)],
        },
        ScenarioQueryV2 {
            name: "memory_and_knowledge_lookup",
            query: "找历史经验 zk 笔记 hybrid search",
            relevant: &[
                ("memory.search_memory", 3),
                ("knowledge.zk_hybrid_search", 2),
            ],
        },
        ScenarioQueryV2 {
            name: "deep_repo_analysis",
            query: "大型仓库 深度分析 architecture shard",
            relevant: &[("researcher.git_repo_analyer", 3), ("skill.discover", 1)],
        },
    ];

    let mut tantivy_rows = Vec::new();
    let mut fts_rows = Vec::new();
    let mut tantivy_metrics = Vec::new();
    let mut fts_metrics = Vec::new();

    for scenario in &scenarios {
        store
            .set_keyword_backend(KeywordSearchBackend::Tantivy)
            .unwrap();
        let tantivy_hits = store
            .keyword_search(TABLE, scenario.query, FETCH_K)
            .await
            .unwrap();
        let tantivy_hits = normalize_hits(tantivy_hits, K);
        let tantivy_eval = eval_query_v2(&tantivy_hits, scenario.relevant, K);
        tantivy_metrics.push(tantivy_eval.clone());
        tantivy_rows.push(json!({
            "query": scenario.name,
            "text": scenario.query,
            "top1": tantivy_hits.first().map(|h| h.tool_name.clone()).unwrap_or_default(),
            "matched_relevant": matched_relevant_from_v2(&tantivy_hits, scenario.relevant),
            "p_at_5": format!("{:.4}", tantivy_eval.precision_at_k),
            "r_at_5": format!("{:.4}", tantivy_eval.recall_at_k),
            "mrr_rr": format!("{:.4}", tantivy_eval.reciprocal_rank),
            "ndcg_at_5": format!("{:.4}", tantivy_eval.ndcg_at_k),
            "success_at_1": format!("{:.4}", tantivy_eval.success_at_1),
        }));

        store
            .set_keyword_backend(KeywordSearchBackend::LanceFts)
            .unwrap();
        let fts_hits = store
            .keyword_search(TABLE, scenario.query, FETCH_K)
            .await
            .unwrap();
        let fts_hits = normalize_hits(fts_hits, K);
        let fts_eval = eval_query_v2(&fts_hits, scenario.relevant, K);
        fts_metrics.push(fts_eval.clone());
        fts_rows.push(json!({
            "query": scenario.name,
            "text": scenario.query,
            "top1": fts_hits.first().map(|h| h.tool_name.clone()).unwrap_or_default(),
            "matched_relevant": matched_relevant_from_v2(&fts_hits, scenario.relevant),
            "p_at_5": format!("{:.4}", fts_eval.precision_at_k),
            "r_at_5": format!("{:.4}", fts_eval.recall_at_k),
            "mrr_rr": format!("{:.4}", fts_eval.reciprocal_rank),
            "ndcg_at_5": format!("{:.4}", fts_eval.ndcg_at_k),
            "success_at_1": format!("{:.4}", fts_eval.success_at_1),
        }));
    }

    let n = scenarios.len();
    let report = json!({
        "k": K,
        "queries": n,
        "summary": {
            "tantivy": {
                "mean_p_at_5": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.precision_at_k), n)),
                "mean_r_at_5": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.recall_at_k), n)),
                "mrr": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.reciprocal_rank), n)),
                "mean_ndcg_at_5": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.ndcg_at_k), n)),
                "success_at_1": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.success_at_1), n)),
            },
            "lance_fts": {
                "mean_p_at_5": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.precision_at_k), n)),
                "mean_r_at_5": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.recall_at_k), n)),
                "mrr": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.reciprocal_rank), n)),
                "mean_ndcg_at_5": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.ndcg_at_k), n)),
                "success_at_1": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.success_at_1), n)),
            }
        },
        "tantivy_details": tantivy_rows,
        "lance_fts_details": fts_rows,
    });

    assert_json_snapshot!("keyword_backend_quality_scenarios_v3_skill_based", report);
}

#[tokio::test]
async fn snapshot_keyword_backend_quality_scenarios_v4_large() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("keyword_quality_store_v4");
    let mut store = VectorStore::new_with_keyword_backend(
        db_path.to_str().unwrap(),
        Some(8),
        true,
        KeywordSearchBackend::Tantivy,
    )
    .await
    .unwrap();

    let docs = vec![
        (
            "advanced_tools.smart_search",
            "High-performance code search using ripgrep with file globs and context lines.",
            "advanced_tools",
            vec!["search", "ripgrep", "regex", "code"],
            vec!["find text in code", "search symbols"],
        ),
        (
            "advanced_tools.smart_find",
            "Fast recursive file and directory discovery powered by fd.",
            "advanced_tools",
            vec!["find", "files", "fd", "path"],
            vec!["locate files", "discover directories"],
        ),
        (
            "advanced_tools.batch_replace",
            "Batch regex refactoring with dry-run safety and diff preview.",
            "advanced_tools",
            vec!["replace", "refactor", "regex", "dry run"],
            vec!["mass edit code", "safe replacement"],
        ),
        (
            "knowledge.dependency_search",
            "Search symbols in external crate dependencies after upgrades.",
            "knowledge",
            vec!["dependency", "crate", "symbol", "rust"],
            vec!["inspect external api", "crate symbol lookup"],
        ),
        (
            "knowledge.zk_hybrid_search",
            "Hybrid knowledge search combining ZK links and vector fallback.",
            "knowledge",
            vec!["knowledge", "zk", "hybrid", "notes"],
            vec!["find related notes", "semantic notebook search"],
        ),
        (
            "git.smart_commit",
            "Guided git commit workflow with security scan and approval steps.",
            "git",
            vec!["git", "commit", "workflow", "security scan"],
            vec!["safe commit", "approved commit flow"],
        ),
        (
            "crawl4ai.crawl_url",
            "Crawl web pages with smart chunk planning and markdown extraction.",
            "crawl4ai",
            vec!["crawl", "web", "chunk", "markdown"],
            vec!["extract web docs", "crawl urls"],
        ),
        (
            "researcher.git_repo_analyer",
            "Sharded deep repository analysis and architecture synthesis.",
            "researcher",
            vec!["research", "repository", "analyze", "architecture"],
            vec!["analyze repo", "deep research"],
        ),
        (
            "writer.polish_text",
            "Polish text with style linting and markdown structure checks.",
            "writer",
            vec!["writing", "polish", "lint", "markdown"],
            vec!["improve docs", "fix writing style"],
        ),
        (
            "omniCell.execute",
            "Execute Nushell commands with safety analysis and structured output.",
            "omniCell",
            vec!["nushell", "execute", "command", "safety"],
            vec!["run shell safely", "structured command output"],
        ),
        (
            "skill.discover",
            "Capability discovery and intent-to-tool resolution gateway.",
            "skill",
            vec!["discover", "intent", "capability", "tooling"],
            vec!["find tool", "resolve capabilities"],
        ),
        (
            "memory.search_memory",
            "Semantic search over long-term memories and project insights.",
            "memory",
            vec!["memory", "semantic", "search", "history"],
            vec!["retrieve prior insights", "search memory bank"],
        ),
    ];

    let ids = docs.iter().map(|d| d.0.to_string()).collect::<Vec<_>>();
    let vectors = (0..docs.len()).map(|_| vec![0.0; 8]).collect::<Vec<_>>();
    let contents = docs.iter().map(|d| d.1.to_string()).collect::<Vec<_>>();
    let metadatas = docs
        .iter()
        .map(|d| {
            json!({
                "type":"command",
                "skill_name": d.2,
                "tool_name": d.0,
                "keywords": d.3,
                "intents": d.4,
            })
            .to_string()
        })
        .collect::<Vec<_>>();

    store
        .add_documents(TABLE, ids, vectors, contents, metadatas)
        .await
        .unwrap();
    store.create_fts_index(TABLE).await.unwrap();

    let mut by_skill: HashMap<&str, Vec<&str>> = HashMap::new();
    for d in &docs {
        by_skill.entry(d.2).or_default().push(d.0);
    }

    let mut scenarios: Vec<ScenarioQueryDyn> = Vec::new();
    for (idx, d) in docs.iter().enumerate() {
        let primary = d.0;
        let skill = d.2;
        let keywords = &d.3;
        let intents = &d.4;
        let sibling = by_skill
            .get(skill)
            .and_then(|items| items.iter().copied().find(|name| *name != primary));

        let base_relevant = {
            let mut r = vec![(primary.to_string(), 3u8)];
            if let Some(sib) = sibling {
                r.push((sib.to_string(), 2u8));
            }
            if primary != "skill.discover" {
                r.push(("skill.discover".to_string(), 1u8));
            }
            r
        };

        let variants = vec![
            (
                "exact_keyword",
                format!("{} {} {}", keywords[0], keywords[1], keywords[2]),
            ),
            ("intent_phrase", format!("{} {}", intents[0], intents[1])),
            (
                "bilingual_mix",
                format!("{} 中文 场景 {}", keywords[0], intents[0]),
            ),
            (
                "workflow_ambiguous",
                format!("run {} workflow {}", keywords[0], keywords[1]),
            ),
            (
                "tool_discovery",
                format!("discover right tool for {} {}", keywords[0], keywords[2]),
            ),
            ("ops_short", format!("{} {}", keywords[0], keywords[1])),
            (
                "troubleshooting",
                format!("fix issue with {} and {}", keywords[0], keywords[2]),
            ),
            (
                "planning",
                format!("plan task using {} {}", intents[0], keywords[1]),
            ),
            (
                "audit",
                format!("audit and verify {} {}", keywords[0], intents[0]),
            ),
            (
                "automation",
                format!("automate {} {} pipeline", keywords[0], keywords[1]),
            ),
        ];

        for (variant_idx, (scene, query)) in variants.into_iter().enumerate() {
            scenarios.push(ScenarioQueryDyn {
                name: format!("v4_{}_{}_{}", idx, variant_idx, scene),
                query,
                scene: scene.to_string(),
                relevant: base_relevant.clone(),
            });
        }
    }

    assert!(scenarios.len() >= 100, "expected >=100 scenarios");

    let mut tantivy_rows = Vec::new();
    let mut fts_rows = Vec::new();
    let mut tantivy_metrics = Vec::new();
    let mut fts_metrics = Vec::new();
    let mut scene_metrics_t: HashMap<String, Vec<QueryMetrics>> = HashMap::new();
    let mut scene_metrics_f: HashMap<String, Vec<QueryMetrics>> = HashMap::new();

    for scenario in &scenarios {
        store
            .set_keyword_backend(KeywordSearchBackend::Tantivy)
            .unwrap();
        let tantivy_hits = store
            .keyword_search(TABLE, &scenario.query, FETCH_K)
            .await
            .unwrap();
        let tantivy_hits = normalize_hits(tantivy_hits, K);
        let tantivy_eval = eval_query_dyn(&tantivy_hits, &scenario.relevant, K);
        tantivy_metrics.push(tantivy_eval.clone());
        scene_metrics_t
            .entry(scenario.scene.clone())
            .or_default()
            .push(tantivy_eval.clone());
        tantivy_rows.push(json!({
            "query": scenario.name,
            "scene": scenario.scene,
            "text": scenario.query,
            "top1": tantivy_hits.first().map(|h| h.tool_name.clone()).unwrap_or_default(),
            "matched_relevant": matched_relevant_from_dyn(&tantivy_hits, &scenario.relevant),
            "p_at_5": format!("{:.4}", tantivy_eval.precision_at_k),
            "r_at_5": format!("{:.4}", tantivy_eval.recall_at_k),
            "mrr_rr": format!("{:.4}", tantivy_eval.reciprocal_rank),
            "ndcg_at_5": format!("{:.4}", tantivy_eval.ndcg_at_k),
            "success_at_1": format!("{:.4}", tantivy_eval.success_at_1),
        }));

        store
            .set_keyword_backend(KeywordSearchBackend::LanceFts)
            .unwrap();
        let fts_hits = store
            .keyword_search(TABLE, &scenario.query, FETCH_K)
            .await
            .unwrap();
        let fts_hits = normalize_hits(fts_hits, K);
        let fts_eval = eval_query_dyn(&fts_hits, &scenario.relevant, K);
        fts_metrics.push(fts_eval.clone());
        scene_metrics_f
            .entry(scenario.scene.clone())
            .or_default()
            .push(fts_eval.clone());
        fts_rows.push(json!({
            "query": scenario.name,
            "scene": scenario.scene,
            "text": scenario.query,
            "top1": fts_hits.first().map(|h| h.tool_name.clone()).unwrap_or_default(),
            "matched_relevant": matched_relevant_from_dyn(&fts_hits, &scenario.relevant),
            "p_at_5": format!("{:.4}", fts_eval.precision_at_k),
            "r_at_5": format!("{:.4}", fts_eval.recall_at_k),
            "mrr_rr": format!("{:.4}", fts_eval.reciprocal_rank),
            "ndcg_at_5": format!("{:.4}", fts_eval.ndcg_at_k),
            "success_at_1": format!("{:.4}", fts_eval.success_at_1),
        }));
    }

    let mut scenes = scene_metrics_t.keys().cloned().collect::<Vec<_>>();
    scenes.sort();
    let scene_summary = scenes
        .iter()
        .map(|scene| {
            let t = scene_metrics_t.get(scene).cloned().unwrap_or_default();
            let f = scene_metrics_f.get(scene).cloned().unwrap_or_default();
            let nt = t.len();
            let nf = f.len();
            json!({
                "scene": scene,
                "queries": nt,
                "tantivy": {
                    "mean_p_at_5": format!("{:.4}", avg(t.iter().map(|m| m.precision_at_k), nt)),
                    "mean_r_at_5": format!("{:.4}", avg(t.iter().map(|m| m.recall_at_k), nt)),
                    "mean_ndcg_at_5": format!("{:.4}", avg(t.iter().map(|m| m.ndcg_at_k), nt)),
                },
                "lance_fts": {
                    "mean_p_at_5": format!("{:.4}", avg(f.iter().map(|m| m.precision_at_k), nf)),
                    "mean_r_at_5": format!("{:.4}", avg(f.iter().map(|m| m.recall_at_k), nf)),
                    "mean_ndcg_at_5": format!("{:.4}", avg(f.iter().map(|m| m.ndcg_at_k), nf)),
                }
            })
        })
        .collect::<Vec<_>>();

    let n = scenarios.len();
    let report = json!({
        "k": K,
        "queries": n,
        "summary": {
            "tantivy": {
                "mean_p_at_5": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.precision_at_k), n)),
                "mean_r_at_5": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.recall_at_k), n)),
                "mrr": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.reciprocal_rank), n)),
                "mean_ndcg_at_5": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.ndcg_at_k), n)),
                "success_at_1": format!("{:.4}", avg(tantivy_metrics.iter().map(|m| m.success_at_1), n)),
            },
            "lance_fts": {
                "mean_p_at_5": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.precision_at_k), n)),
                "mean_r_at_5": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.recall_at_k), n)),
                "mrr": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.reciprocal_rank), n)),
                "mean_ndcg_at_5": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.ndcg_at_k), n)),
                "success_at_1": format!("{:.4}", avg(fts_metrics.iter().map(|m| m.success_at_1), n)),
            }
        },
        "scene_summary": scene_summary,
        "tantivy_details": tantivy_rows,
        "lance_fts_details": fts_rows,
    });

    assert_json_snapshot!("keyword_backend_quality_scenarios_v4_large", report);
}
