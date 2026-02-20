//! Integration tests for the `wendao` CLI binary.

use serde_json::Value;
use std::fs;
use std::path::Path;
use std::process::Command;
use tempfile::TempDir;

fn write_file(path: &Path, content: &str) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, content)?;
    Ok(())
}

fn wendao_cmd() -> Command {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_wendao"));
    cmd.env("VALKEY_URL", "redis://127.0.0.1:6379/0");
    cmd
}

#[test]
fn test_wendao_search_returns_matches() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("notes/alpha.md"),
        "# Alpha Note\n\nReference [[beta]].\n",
    )?;
    write_file(
        &tmp.path().join("notes/beta.md"),
        "---\ntitle: Beta Knowledge\ntags:\n  - rust\n---\n\nReference [[alpha]].\n",
    )?;

    let output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("search")
        .arg("beta")
        .arg("--limit")
        .arg("5")
        .output()?;

    assert!(
        output.status.success(),
        "wendao search failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    let stdout = String::from_utf8(output.stdout)?;
    let payload: Value = serde_json::from_str(&stdout)?;
    assert_eq!(payload.get("query").and_then(Value::as_str), Some("beta"));
    assert_eq!(payload.get("limit").and_then(Value::as_u64), Some(5));
    assert_eq!(
        payload.get("match_strategy").and_then(Value::as_str),
        Some("fts")
    );
    let sort_terms = payload
        .get("sort_terms")
        .and_then(Value::as_array)
        .ok_or("missing sort_terms")?;
    assert_eq!(sort_terms.len(), 1);
    assert_eq!(
        sort_terms[0].get("field").and_then(Value::as_str),
        Some("score")
    );
    assert_eq!(
        sort_terms[0].get("order").and_then(Value::as_str),
        Some("desc")
    );
    assert_eq!(
        payload.get("case_sensitive").and_then(Value::as_bool),
        Some(false)
    );
    let filters = payload.get("filters").ok_or("missing filters payload")?;
    assert_eq!(
        filters
            .get("link_to")
            .and_then(|row| row.get("seeds"))
            .and_then(Value::as_array)
            .map(std::vec::Vec::len),
        None
    );
    assert_eq!(
        filters
            .get("linked_by")
            .and_then(|row| row.get("seeds"))
            .and_then(Value::as_array)
            .map(std::vec::Vec::len),
        None
    );
    assert_eq!(
        filters
            .get("related")
            .and_then(|row| row.get("seeds"))
            .and_then(Value::as_array)
            .map(std::vec::Vec::len),
        None
    );

    let Some(results) = payload.get("results").and_then(Value::as_array) else {
        return Err("missing search results array".into());
    };
    assert!(!results.is_empty());
    assert!(
        results
            .iter()
            .any(|row| row.get("stem").and_then(Value::as_str) == Some("beta")),
        "expected search results to include stem=beta; payload={payload}"
    );

    Ok(())
}

#[test]
fn test_wendao_stats_reports_note_counts() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# A\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\n[[a]]\n")?;

    let output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("stats")
        .output()?;

    assert!(
        output.status.success(),
        "wendao stats failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    let stdout = String::from_utf8(output.stdout)?;
    let payload: Value = serde_json::from_str(&stdout)?;
    assert_eq!(payload.get("total_notes").and_then(Value::as_u64), Some(2));
    assert_eq!(
        payload.get("links_in_graph").and_then(Value::as_u64),
        Some(2)
    );

    Ok(())
}

#[test]
fn test_wendao_allows_global_root_after_subcommand() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# Alpha\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# Beta\n\n[[a]]\n")?;

    let output = wendao_cmd()
        .arg("search")
        .arg("alpha")
        .arg("--root")
        .arg(tmp.path())
        .arg("--limit")
        .arg("2")
        .output()?;

    assert!(
        output.status.success(),
        "wendao search with trailing --root failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    let stdout = String::from_utf8(output.stdout)?;
    let payload: Value = serde_json::from_str(&stdout)?;
    assert_eq!(payload.get("query").and_then(Value::as_str), Some("alpha"));
    assert!(
        payload
            .get("results")
            .and_then(Value::as_array)
            .is_some_and(|rows| !rows.is_empty())
    );
    Ok(())
}

#[test]
fn test_wendao_search_strategy_and_path_sort_flags() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("notes/zeta.md"), "# Zeta\n\nkeyword\n")?;
    write_file(&tmp.path().join("notes/alpha.md"), "# Alpha\n\nkeyword\n")?;

    let output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("search")
        .arg(".md")
        .arg("--limit")
        .arg("5")
        .arg("--match-strategy")
        .arg("fts")
        .arg("--sort-term")
        .arg("path_asc")
        .output()?;

    assert!(
        output.status.success(),
        "wendao search with strategy/path sort failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    let stdout = String::from_utf8(output.stdout)?;
    let payload: Value = serde_json::from_str(&stdout)?;
    assert_eq!(
        payload.get("match_strategy").and_then(Value::as_str),
        Some("fts")
    );
    let sort_terms = payload
        .get("sort_terms")
        .and_then(Value::as_array)
        .ok_or("missing sort_terms")?;
    assert_eq!(sort_terms.len(), 1);
    assert_eq!(
        sort_terms[0].get("field").and_then(Value::as_str),
        Some("path")
    );
    assert_eq!(
        sort_terms[0].get("order").and_then(Value::as_str),
        Some("asc")
    );
    let rows = payload
        .get("results")
        .and_then(Value::as_array)
        .ok_or("missing results")?;
    assert_eq!(rows.len(), 2);
    assert_eq!(
        rows.first()
            .and_then(|row| row.get("path"))
            .and_then(Value::as_str),
        Some("notes/alpha.md")
    );
    Ok(())
}

#[test]
fn test_wendao_search_path_fuzzy_emits_section_context() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/architecture/graph.md"),
        "# Architecture\n\n## Graph Engine\n\nDetails.\n",
    )?;
    write_file(
        &tmp.path().join("docs/misc.md"),
        "# Misc\n\nGraph mention.\n",
    )?;

    let output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("search")
        .arg("architecture graph engine")
        .arg("--limit")
        .arg("5")
        .arg("--match-strategy")
        .arg("path_fuzzy")
        .output()?;

    assert!(
        output.status.success(),
        "wendao search with path_fuzzy failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    let stdout = String::from_utf8(output.stdout)?;
    let payload: Value = serde_json::from_str(&stdout)?;
    assert_eq!(
        payload.get("match_strategy").and_then(Value::as_str),
        Some("path_fuzzy")
    );
    let rows = payload
        .get("results")
        .and_then(Value::as_array)
        .ok_or("missing results")?;
    assert!(!rows.is_empty());
    assert_eq!(
        rows.first()
            .and_then(|row| row.get("path"))
            .and_then(Value::as_str),
        Some("docs/architecture/graph.md")
    );
    assert!(
        rows.first()
            .and_then(|row| row.get("best_section"))
            .and_then(Value::as_str)
            .is_some_and(|v| v.contains("Graph Engine"))
    );
    Ok(())
}

#[test]
fn test_wendao_search_link_filters_flags() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# A\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/c.md"), "# C\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\nNo links.\n")?;

    let output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("search")
        .arg(".md")
        .arg("--limit")
        .arg("10")
        .arg("--link-to")
        .arg("b")
        .arg("--sort-term")
        .arg("path_asc")
        .output()?;

    assert!(
        output.status.success(),
        "wendao search with link filters failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    let stdout = String::from_utf8(output.stdout)?;
    let payload: Value = serde_json::from_str(&stdout)?;
    let filters = payload.get("filters").ok_or("missing filters payload")?;
    assert_eq!(
        filters
            .get("link_to")
            .and_then(|row| row.get("seeds"))
            .and_then(Value::as_array)
            .map(std::vec::Vec::len),
        Some(1)
    );
    let rows = payload
        .get("results")
        .and_then(Value::as_array)
        .ok_or("missing results")?;
    assert_eq!(rows.len(), 2);
    assert_eq!(
        rows.first()
            .and_then(|row| row.get("path"))
            .and_then(Value::as_str),
        Some("docs/a.md")
    );
    assert_eq!(
        rows.get(1)
            .and_then(|row| row.get("path"))
            .and_then(Value::as_str),
        Some("docs/c.md")
    );
    Ok(())
}

#[test]
fn test_wendao_hmas_validate_command() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("thread.md"),
        r#"
#### [CONCLUSION]
```json
{
  "requirement_id": "REQ-CLI-1",
  "summary": "CLI validator smoke test",
  "confidence_score": 0.9,
  "hard_constraints_checked": ["RULE"]
}
```

#### [DIGITAL THREAD]
```json
{
  "requirement_id": "REQ-CLI-1",
  "source_nodes_accessed": [{"node_id": "note-1"}],
  "hard_constraints_checked": ["RULE"],
  "confidence_score": 0.9
}
```
"#,
    )?;

    let output = wendao_cmd()
        .arg("hmas")
        .arg("validate")
        .arg("--file")
        .arg(tmp.path().join("thread.md"))
        .output()?;

    assert!(
        output.status.success(),
        "wendao hmas validate failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    let stdout = String::from_utf8(output.stdout)?;
    let payload: Value = serde_json::from_str(&stdout)?;
    assert_eq!(payload.get("valid").and_then(Value::as_bool), Some(true));
    assert_eq!(
        payload.get("digital_thread_count").and_then(Value::as_u64),
        Some(1)
    );

    Ok(())
}

#[test]
fn test_wendao_search_related_ppr_flags() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# A\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\n[[c]]\n")?;
    write_file(&tmp.path().join("docs/c.md"), "# C\n\n[[d]]\n")?;
    write_file(&tmp.path().join("docs/d.md"), "# D\n\nNo links.\n")?;

    let output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("search")
        .arg(".md")
        .arg("--limit")
        .arg("10")
        .arg("--related")
        .arg("b")
        .arg("--max-distance")
        .arg("2")
        .arg("--related-ppr-alpha")
        .arg("0.9")
        .arg("--related-ppr-max-iter")
        .arg("64")
        .arg("--related-ppr-tol")
        .arg("1e-6")
        .arg("--related-ppr-subgraph-mode")
        .arg("force")
        .arg("--sort-term")
        .arg("path_asc")
        .output()?;

    assert!(
        output.status.success(),
        "wendao search with related ppr flags failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    let payload: Value = serde_json::from_str(&String::from_utf8(output.stdout)?)?;
    let related = payload
        .get("filters")
        .and_then(|row| row.get("related"))
        .ok_or("missing related filter payload")?;
    assert_eq!(
        related
            .get("seeds")
            .and_then(Value::as_array)
            .map(std::vec::Vec::len),
        Some(1)
    );
    assert_eq!(related.get("max_distance").and_then(Value::as_u64), Some(2));
    let ppr = related.get("ppr").ok_or("missing related ppr payload")?;
    assert_eq!(ppr.get("alpha").and_then(Value::as_f64), Some(0.9));
    assert_eq!(ppr.get("max_iter").and_then(Value::as_u64), Some(64));
    assert_eq!(ppr.get("tol").and_then(Value::as_f64), Some(1e-6));
    assert_eq!(
        ppr.get("subgraph_mode").and_then(Value::as_str),
        Some("force")
    );

    Ok(())
}

#[test]
fn test_wendao_related_command_accepts_ppr_flags() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# A\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\n[[c]]\n")?;
    write_file(&tmp.path().join("docs/c.md"), "# C\n\n[[d]]\n")?;
    write_file(&tmp.path().join("docs/d.md"), "# D\n\nNo links.\n")?;

    let output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("related")
        .arg("b")
        .arg("--max-distance")
        .arg("2")
        .arg("--limit")
        .arg("10")
        .arg("--ppr-alpha")
        .arg("0.9")
        .arg("--ppr-max-iter")
        .arg("64")
        .arg("--ppr-tol")
        .arg("1e-6")
        .arg("--ppr-subgraph-mode")
        .arg("force")
        .output()?;

    assert!(
        output.status.success(),
        "wendao related with ppr flags failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    let payload: Value = serde_json::from_str(&String::from_utf8(output.stdout)?)?;
    let rows = payload
        .as_array()
        .ok_or("expected related output to be a json array")?;
    assert_eq!(rows.len(), 3);
    let stems: Vec<&str> = rows
        .iter()
        .filter_map(|row| row.get("stem").and_then(Value::as_str))
        .collect();
    assert!(stems.contains(&"a"));
    assert!(stems.contains(&"c"));
    assert!(stems.contains(&"d"));

    Ok(())
}

#[test]
fn test_wendao_related_verbose_includes_diagnostics() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# A\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\n[[c]]\n")?;
    write_file(&tmp.path().join("docs/c.md"), "# C\n\n[[d]]\n")?;
    write_file(&tmp.path().join("docs/d.md"), "# D\n\nNo links.\n")?;

    let output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("related")
        .arg("b")
        .arg("--max-distance")
        .arg("2")
        .arg("--limit")
        .arg("10")
        .arg("--verbose")
        .arg("--ppr-alpha")
        .arg("0.9")
        .arg("--ppr-max-iter")
        .arg("64")
        .arg("--ppr-tol")
        .arg("1e-6")
        .arg("--ppr-subgraph-mode")
        .arg("force")
        .output()?;

    assert!(
        output.status.success(),
        "wendao related --verbose failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    let payload: Value = serde_json::from_str(&String::from_utf8(output.stdout)?)?;
    assert_eq!(payload.get("stem").and_then(Value::as_str), Some("b"));
    assert_eq!(payload.get("max_distance").and_then(Value::as_u64), Some(2));
    assert_eq!(payload.get("limit").and_then(Value::as_u64), Some(10));
    let ppr = payload.get("ppr").ok_or("missing ppr payload")?;
    assert_eq!(ppr.get("alpha").and_then(Value::as_f64), Some(0.9));
    assert_eq!(ppr.get("max_iter").and_then(Value::as_u64), Some(64));
    assert_eq!(ppr.get("tol").and_then(Value::as_f64), Some(1e-6));
    assert_eq!(
        ppr.get("subgraph_mode").and_then(Value::as_str),
        Some("force")
    );

    let diagnostics = payload
        .get("diagnostics")
        .ok_or("missing diagnostics payload")?;
    assert_eq!(diagnostics.get("alpha").and_then(Value::as_f64), Some(0.9));
    assert_eq!(
        diagnostics.get("max_iter").and_then(Value::as_u64),
        Some(64)
    );
    assert_eq!(diagnostics.get("tol").and_then(Value::as_f64), Some(1e-6));
    assert!(
        diagnostics
            .get("iteration_count")
            .and_then(Value::as_u64)
            .is_some()
    );
    assert!(
        diagnostics
            .get("final_residual")
            .and_then(Value::as_f64)
            .is_some()
    );
    assert!(
        diagnostics
            .get("candidate_count")
            .and_then(Value::as_u64)
            .is_some()
    );
    assert!(
        diagnostics
            .get("graph_node_count")
            .and_then(Value::as_u64)
            .is_some()
    );
    assert_eq!(
        diagnostics.get("subgraph_count").and_then(Value::as_u64),
        Some(1)
    );
    assert_eq!(
        diagnostics
            .get("partition_max_node_count")
            .and_then(Value::as_u64),
        Some(4)
    );
    assert_eq!(
        diagnostics
            .get("partition_min_node_count")
            .and_then(Value::as_u64),
        Some(4)
    );
    assert_eq!(
        diagnostics
            .get("partition_avg_node_count")
            .and_then(Value::as_f64),
        Some(4.0)
    );
    assert!(
        diagnostics
            .get("total_duration_ms")
            .and_then(Value::as_f64)
            .is_some()
    );
    assert!(
        diagnostics
            .get("partition_duration_ms")
            .and_then(Value::as_f64)
            .is_some()
    );
    assert!(
        diagnostics
            .get("kernel_duration_ms")
            .and_then(Value::as_f64)
            .is_some()
    );
    assert!(
        diagnostics
            .get("fusion_duration_ms")
            .and_then(Value::as_f64)
            .is_some()
    );
    assert_eq!(
        diagnostics.get("subgraph_mode").and_then(Value::as_str),
        Some("force")
    );
    assert_eq!(
        diagnostics
            .get("horizon_restricted")
            .and_then(Value::as_bool),
        Some(true)
    );

    let rows = payload
        .get("results")
        .and_then(Value::as_array)
        .ok_or("expected verbose results array")?;
    assert_eq!(rows.len(), 3);
    assert_eq!(payload.get("total").and_then(Value::as_u64), Some(3));

    Ok(())
}

#[test]
fn test_wendao_search_semantic_filter_flags() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "---\ntags:\n  - core\n---\n# A\n\nAlpha signal appears here.\n\n[[b]]\n",
    )?;
    write_file(
        &tmp.path().join("docs/b.md"),
        "---\ntags:\n  - team\n---\n# B\n\nBeta note.\n",
    )?;
    write_file(
        &tmp.path().join("docs/c.md"),
        "# C\n\nAlpha signal appears here too.\n",
    )?;

    let mention_output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("search")
        .arg(".md")
        .arg("--limit")
        .arg("10")
        .arg("--mentions-of")
        .arg("Alpha signal")
        .arg("--sort-term")
        .arg("path_asc")
        .output()?;

    assert!(
        mention_output.status.success(),
        "wendao search with mentions-of failed: {}",
        String::from_utf8_lossy(&mention_output.stderr)
    );

    let mention_payload: Value = serde_json::from_str(&String::from_utf8(mention_output.stdout)?)?;
    let mention_rows = mention_payload
        .get("results")
        .and_then(Value::as_array)
        .ok_or("missing mention results")?;
    assert_eq!(mention_rows.len(), 2);
    assert_eq!(
        mention_rows
            .first()
            .and_then(|row| row.get("path"))
            .and_then(Value::as_str),
        Some("docs/a.md")
    );
    assert_eq!(
        mention_rows
            .get(1)
            .and_then(|row| row.get("path"))
            .and_then(Value::as_str),
        Some("docs/c.md")
    );

    let missing_backlink_output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("search")
        .arg(".md")
        .arg("--limit")
        .arg("10")
        .arg("--missing-backlink")
        .arg("--sort-term")
        .arg("path_asc")
        .output()?;

    assert!(
        missing_backlink_output.status.success(),
        "wendao search with missing-backlink failed: {}",
        String::from_utf8_lossy(&missing_backlink_output.stderr)
    );

    let missing_backlink_payload: Value =
        serde_json::from_str(&String::from_utf8(missing_backlink_output.stdout)?)?;
    let missing_backlink_rows = missing_backlink_payload
        .get("results")
        .and_then(Value::as_array)
        .ok_or("missing missing-backlink results")?;
    assert_eq!(missing_backlink_rows.len(), 1);
    assert_eq!(
        missing_backlink_rows
            .first()
            .and_then(|row| row.get("path"))
            .and_then(Value::as_str),
        Some("docs/a.md")
    );

    Ok(())
}

#[test]
fn test_wendao_search_query_directives_apply_without_cli_flags()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# A\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/c.md"), "# C\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\nNo links.\n")?;

    let output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("search")
        .arg("to:b sort:path_asc .md")
        .arg("--limit")
        .arg("10")
        .output()?;

    assert!(
        output.status.success(),
        "wendao search with query directives failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    let payload: Value = serde_json::from_str(&String::from_utf8(output.stdout)?)?;
    assert_eq!(payload.get("query").and_then(Value::as_str), Some(".md"));
    let filters = payload.get("filters").ok_or("missing filters payload")?;
    assert_eq!(
        filters
            .get("link_to")
            .and_then(|row| row.get("seeds"))
            .and_then(Value::as_array)
            .map(std::vec::Vec::len),
        Some(1)
    );
    let sort_terms = payload
        .get("sort_terms")
        .and_then(Value::as_array)
        .ok_or("missing sort_terms")?;
    assert_eq!(sort_terms.len(), 1);
    assert_eq!(
        sort_terms[0].get("field").and_then(Value::as_str),
        Some("path")
    );
    assert_eq!(
        sort_terms[0].get("order").and_then(Value::as_str),
        Some("asc")
    );
    let rows = payload
        .get("results")
        .and_then(Value::as_array)
        .ok_or("missing results")?;
    assert_eq!(rows.len(), 2);
    assert_eq!(
        rows.first()
            .and_then(|row| row.get("path"))
            .and_then(Value::as_str),
        Some("docs/a.md")
    );
    assert_eq!(
        rows.get(1)
            .and_then(|row| row.get("path"))
            .and_then(Value::as_str),
        Some("docs/c.md")
    );
    Ok(())
}

#[test]
fn test_wendao_search_temporal_flags_filter_results() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "---\ncreated: 2024-01-01\nmodified: 2024-01-05\n---\n# A\n",
    )?;
    write_file(
        &tmp.path().join("docs/b.md"),
        "---\ncreated: 2024-01-03\nmodified: 2024-01-02\n---\n# B\n",
    )?;
    write_file(
        &tmp.path().join("docs/c.md"),
        "---\ncreated: 2024-01-10\nmodified: 2024-01-12\n---\n# C\n",
    )?;

    let output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("search")
        .arg(".md")
        .arg("--limit")
        .arg("10")
        .arg("--sort-term")
        .arg("created_asc")
        .arg("--created-after")
        .arg("1704153600")
        .arg("--created-before")
        .arg("1704758400")
        .output()?;

    assert!(
        output.status.success(),
        "wendao search with temporal flags failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    let payload: Value = serde_json::from_str(&String::from_utf8(output.stdout)?)?;
    assert_eq!(
        payload.get("created_after").and_then(Value::as_i64),
        Some(1_704_153_600)
    );
    assert_eq!(
        payload.get("created_before").and_then(Value::as_i64),
        Some(1_704_758_400)
    );
    let sort_terms = payload
        .get("sort_terms")
        .and_then(Value::as_array)
        .ok_or("missing sort_terms")?;
    assert_eq!(sort_terms.len(), 1);
    assert_eq!(
        sort_terms[0].get("field").and_then(Value::as_str),
        Some("created")
    );
    assert_eq!(
        sort_terms[0].get("order").and_then(Value::as_str),
        Some("asc")
    );
    let rows = payload
        .get("results")
        .and_then(Value::as_array)
        .ok_or("missing results")?;
    assert_eq!(rows.len(), 1);
    assert_eq!(
        rows.first()
            .and_then(|row| row.get("path"))
            .and_then(Value::as_str),
        Some("docs/b.md")
    );
    Ok(())
}

#[test]
fn test_wendao_search_rejects_legacy_sort_flag() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# A\n")?;

    let output = wendao_cmd()
        .arg("--root")
        .arg(tmp.path())
        .arg("search")
        .arg("a")
        .arg("--sort")
        .arg("path_asc")
        .output()?;

    assert!(
        !output.status.success(),
        "legacy --sort flag should be rejected, but command succeeded"
    );
    let stderr = String::from_utf8(output.stderr)?;
    assert!(stderr.contains("unexpected argument '--sort'"));
    assert!(stderr.contains("--sort-term"));
    Ok(())
}
