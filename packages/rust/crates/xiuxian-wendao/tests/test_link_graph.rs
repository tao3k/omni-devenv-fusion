use redis::Connection;
use serde_json::json;
use std::collections::HashMap;
use std::fs;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};
use tempfile::TempDir;
use xiuxian_wendao::link_graph::{
    LinkGraphDirection, LinkGraphEdgeType, LinkGraphIndex, LinkGraphLinkFilter,
    LinkGraphMatchStrategy, LinkGraphPprSubgraphMode, LinkGraphRefreshMode, LinkGraphRelatedFilter,
    LinkGraphRelatedPprOptions, LinkGraphScope, LinkGraphSearchFilters, LinkGraphSearchOptions,
    LinkGraphSortField, LinkGraphSortOrder, LinkGraphSortTerm, parse_search_query,
};
use xiuxian_wendao::{
    LinkGraphSaliencyPolicy, compute_link_graph_saliency, valkey_saliency_get_with_valkey,
};

fn write_file(path: &Path, content: &str) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, content)?;
    Ok(())
}

fn sort_term(field: LinkGraphSortField, order: LinkGraphSortOrder) -> LinkGraphSortTerm {
    LinkGraphSortTerm { field, order }
}

fn valkey_connection() -> Result<Connection, Box<dyn std::error::Error>> {
    let client = redis::Client::open("redis://127.0.0.1:6379/0")?;
    let conn = client.get_connection()?;
    Ok(conn)
}

fn clear_cache_keys(prefix: &str) -> Result<(), Box<dyn std::error::Error>> {
    let mut conn = valkey_connection()?;
    let pattern = format!("{prefix}:*");
    let keys: Vec<String> = redis::cmd("KEYS").arg(&pattern).query(&mut conn)?;
    if !keys.is_empty() {
        redis::cmd("DEL").arg(keys).query::<()>(&mut conn)?;
    }
    Ok(())
}

fn count_cache_keys(prefix: &str) -> Result<usize, Box<dyn std::error::Error>> {
    let mut conn = valkey_connection()?;
    let pattern = format!("{prefix}:*");
    let keys: Vec<String> = redis::cmd("KEYS").arg(&pattern).query(&mut conn)?;
    Ok(keys.len())
}

fn unique_cache_prefix() -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|v| v.as_nanos())
        .unwrap_or(0);
    format!("omni:test:link_graph:{nanos}")
}

#[test]
fn test_link_graph_build_with_cache_reuses_snapshot() -> Result<(), Box<dyn std::error::Error>> {
    let prefix = unique_cache_prefix();
    clear_cache_keys(&prefix)?;

    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "# Alpha\n\nThis is alpha.\n\n[[b]]\n",
    )?;
    write_file(
        &tmp.path().join("docs/b.md"),
        "# Beta\n\nThis is beta.\n\n[[a]]\n",
    )?;

    let index1 = LinkGraphIndex::build_with_cache_with_valkey(
        tmp.path(),
        &[],
        &[],
        "redis://127.0.0.1:6379/0",
        Some(&prefix),
        Some(300),
    )
    .map_err(|e| e.to_string())?;
    let index2 = LinkGraphIndex::build_with_cache_with_valkey(
        tmp.path(),
        &[],
        &[],
        "redis://127.0.0.1:6379/0",
        Some(&prefix),
        Some(300),
    )
    .map_err(|e| e.to_string())?;

    assert_eq!(index1.stats().total_notes, 2);
    assert_eq!(index1.stats().total_notes, index2.stats().total_notes);
    assert_eq!(index1.stats().links_in_graph, index2.stats().links_in_graph);

    let key_count = count_cache_keys(&prefix)?;
    assert!(key_count >= 1, "expected at least one valkey cache key");
    clear_cache_keys(&prefix)?;
    Ok(())
}

#[test]
fn test_link_graph_build_with_cache_detects_file_change() -> Result<(), Box<dyn std::error::Error>>
{
    let prefix = unique_cache_prefix();
    clear_cache_keys(&prefix)?;

    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# Alpha\n\nlegacy phrase\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# Beta\n\nstable note\n")?;

    let _ = LinkGraphIndex::build_with_cache_with_valkey(
        tmp.path(),
        &[],
        &[],
        "redis://127.0.0.1:6379/0",
        Some(&prefix),
        Some(300),
    )
    .map_err(|e| e.to_string())?;

    write_file(
        &tmp.path().join("docs/a.md"),
        "# Alpha\n\nupdated phrase for cache invalidation\n",
    )?;

    let refreshed = LinkGraphIndex::build_with_cache_with_valkey(
        tmp.path(),
        &[],
        &[],
        "redis://127.0.0.1:6379/0",
        Some(&prefix),
        Some(300),
    )
    .map_err(|e| e.to_string())?;
    let hits = refreshed
        .search_planned(
            "updated phrase for cache invalidation",
            5,
            LinkGraphSearchOptions::default(),
        )
        .1;
    assert!(!hits.is_empty(), "updated content should be searchable");
    assert_eq!(hits[0].stem, "a");
    clear_cache_keys(&prefix)?;
    Ok(())
}

#[test]
fn test_link_graph_build_with_cache_seeds_saliency_from_frontmatter()
-> Result<(), Box<dyn std::error::Error>> {
    let prefix = unique_cache_prefix();
    clear_cache_keys(&prefix)?;

    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "---\nsaliency_base: 9.0\ndecay_rate: 0.2\n---\n# Alpha\n\n[[b]]\n",
    )?;
    write_file(&tmp.path().join("docs/b.md"), "# Beta\n\n[[a]]\n")?;

    let _index = LinkGraphIndex::build_with_cache_with_valkey(
        tmp.path(),
        &[],
        &[],
        "redis://127.0.0.1:6379/0",
        Some(&prefix),
        Some(300),
    )
    .map_err(|e| e.to_string())?;

    let state =
        valkey_saliency_get_with_valkey("docs/a", "redis://127.0.0.1:6379/0", Some(&prefix))
            .map_err(|e| e.to_string())?;
    assert!(state.is_some(), "expected seeded saliency state");
    let seeded = state.ok_or("missing seeded saliency state for docs/a")?;
    let expected =
        compute_link_graph_saliency(9.0, 0.2, 0, 0.0, LinkGraphSaliencyPolicy::default());
    assert!((seeded.current_saliency - expected).abs() < 1e-9);

    clear_cache_keys(&prefix)?;
    Ok(())
}

#[test]
fn test_link_graph_build_search_and_stats() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "# Alpha\n\nThis is alpha.\n\n[[b]]\n",
    )?;
    write_file(
        &tmp.path().join("docs/b.md"),
        "---\ntitle: Beta Doc\ntags:\n  - tag-x\n---\n\n[[a]]\n",
    )?;
    write_file(&tmp.path().join("docs/c.md"), "# Gamma\n\nNo links here.\n")?;

    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;
    let stats = index.stats();
    assert_eq!(stats.total_notes, 3);
    assert_eq!(stats.nodes_in_graph, 3);
    assert_eq!(stats.links_in_graph, 2);
    assert_eq!(stats.orphans, 1);

    let hits = index
        .search_planned("beta", 5, LinkGraphSearchOptions::default())
        .1;
    assert!(!hits.is_empty());
    assert_eq!(hits[0].stem, "b");
    assert_eq!(hits[0].path, "docs/b.md");

    Ok(())
}

#[test]
fn test_link_graph_search_limit_is_enforced() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# A\n\nshared keyword\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\nshared keyword\n")?;
    write_file(&tmp.path().join("docs/c.md"), "# C\n\nshared keyword\n")?;
    write_file(&tmp.path().join("docs/d.md"), "# D\n\nshared keyword\n")?;

    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;
    let hits = index
        .search_planned("shared keyword", 2, LinkGraphSearchOptions::default())
        .1;
    assert_eq!(hits.len(), 2);
    Ok(())
}

#[test]
fn test_link_graph_search_fts_boosts_high_reference_notes() -> Result<(), Box<dyn std::error::Error>>
{
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/hub.md"), "# Hub\n\nshared phrase\n")?;
    write_file(
        &tmp.path().join("docs/leaf.md"),
        "# Leaf\n\nshared phrase\n",
    )?;
    write_file(&tmp.path().join("docs/ref-1.md"), "# R1\n\n[[hub]]\n")?;
    write_file(&tmp.path().join("docs/ref-2.md"), "# R2\n\n[[hub]]\n")?;
    write_file(&tmp.path().join("docs/ref-3.md"), "# R3\n\n[[hub]]\n")?;

    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;
    let hits = index
        .search_planned("shared phrase", 5, LinkGraphSearchOptions::default())
        .1;
    assert!(hits.len() >= 2);
    assert_eq!(hits[0].stem, "hub");
    assert_eq!(hits[1].stem, "leaf");
    assert!(hits[0].score > hits[1].score);
    Ok(())
}

#[test]
fn test_link_graph_parse_search_query_supports_path_fuzzy_strategy() {
    let parsed = parse_search_query(
        "match:path_fuzzy architecture graph",
        LinkGraphSearchOptions::default(),
    );
    assert_eq!(parsed.query, "architecture graph");
    assert_eq!(
        parsed.options.match_strategy,
        LinkGraphMatchStrategy::PathFuzzy
    );
}

#[test]
fn test_link_graph_search_path_fuzzy_prefers_path_and_section()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/architecture/graph.md"),
        "# Architecture\n\n## Graph Engine\n\nImplementation details.\n",
    )?;
    write_file(
        &tmp.path().join("docs/notes/misc.md"),
        "# Misc\n\nSome graph mention without architecture path.\n",
    )?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let options = LinkGraphSearchOptions {
        match_strategy: LinkGraphMatchStrategy::PathFuzzy,
        case_sensitive: false,
        ..LinkGraphSearchOptions::default()
    };
    let hits = index
        .search_planned("architecture graph engine", 5, options)
        .1;
    assert!(!hits.is_empty());
    assert_eq!(hits[0].path, "docs/architecture/graph.md");
    assert_eq!(
        hits[0].best_section,
        Some("Architecture / Graph Engine".to_string())
    );
    assert!(
        hits[0]
            .match_reason
            .as_deref()
            .unwrap_or_default()
            .contains("path_fuzzy")
    );
    Ok(())
}

#[test]
fn test_link_graph_search_path_fuzzy_ignores_fenced_headings()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/architecture/engine.md"),
        "# Architecture\n\n```md\n## Fake Heading\n```\n\n## Real Heading\n\nGraph runtime pipeline.\n",
    )?;
    write_file(
        &tmp.path().join("docs/notes/misc.md"),
        "# Misc\n\nGraph runtime note.\n",
    )?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let options = LinkGraphSearchOptions {
        match_strategy: LinkGraphMatchStrategy::PathFuzzy,
        case_sensitive: false,
        ..LinkGraphSearchOptions::default()
    };
    let hits = index
        .search_planned("architecture real heading graph", 5, options)
        .1;
    assert!(!hits.is_empty());
    assert_eq!(hits[0].path, "docs/architecture/engine.md");
    assert_eq!(
        hits[0].best_section,
        Some("Architecture / Real Heading".to_string())
    );
    Ok(())
}

#[test]
fn test_link_graph_search_path_fuzzy_handles_duplicate_headings()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/architecture/api.md"),
        "# Architecture\n\n## API\n\nOverview.\n\n## API\n\nRouter graph query constraints.\n",
    )?;
    write_file(
        &tmp.path().join("docs/notes/other.md"),
        "# Other\n\nRouter query text.\n",
    )?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let options = LinkGraphSearchOptions {
        match_strategy: LinkGraphMatchStrategy::PathFuzzy,
        case_sensitive: false,
        ..LinkGraphSearchOptions::default()
    };
    let hits = index
        .search_planned("architecture api router", 5, options)
        .1;
    assert!(!hits.is_empty());
    assert_eq!(hits[0].path, "docs/architecture/api.md");
    assert_eq!(hits[0].best_section, Some("Architecture / API".to_string()));
    assert!(
        hits[0]
            .match_reason
            .as_deref()
            .unwrap_or_default()
            .contains("path_fuzzy")
    );
    Ok(())
}

#[test]
fn test_link_graph_search_with_exact_strategy() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# Alpha\n\n[[b]]\n")?;
    write_file(
        &tmp.path().join("docs/b.md"),
        "---\ntitle: Rust Tokenizer\ntags:\n  - rust\n---\n",
    )?;

    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;
    let options = LinkGraphSearchOptions {
        match_strategy: LinkGraphMatchStrategy::Exact,
        case_sensitive: false,
        ..LinkGraphSearchOptions::default()
    };
    let hits = index.search_planned("rust tokenizer", 5, options).1;
    assert_eq!(hits.len(), 1);
    assert_eq!(hits[0].stem, "b");
    Ok(())
}

#[test]
fn test_link_graph_search_with_regex_strategy() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/alpha-note.md"),
        "# Alpha Note\n\n[[beta-note]]\n",
    )?;
    write_file(
        &tmp.path().join("docs/beta-note.md"),
        "# Beta Note\n\n[[alpha-note]]\n",
    )?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let options = LinkGraphSearchOptions {
        match_strategy: LinkGraphMatchStrategy::Re,
        case_sensitive: false,
        ..LinkGraphSearchOptions::default()
    };
    let hits = index.search_planned("^beta", 5, options).1;
    assert_eq!(hits.len(), 1);
    assert_eq!(hits[0].stem, "beta-note");
    Ok(())
}

#[test]
fn test_link_graph_parse_search_query_supports_directives_and_time_filters() {
    let parsed = parse_search_query(
        "match:re sort:modified_desc case:true link-to:a,b linked-by:c related:seed~3 related_ppr_alpha:0.9 related_ppr_max_iter:64 related_ppr_tol:1e-6 related_ppr_subgraph_mode:force created>=2024-01-01 modified<=2024-01-31 hello",
        LinkGraphSearchOptions::default(),
    );

    assert_eq!(parsed.query, "hello");
    assert_eq!(parsed.options.match_strategy, LinkGraphMatchStrategy::Re);
    assert_eq!(
        parsed.options.sort_terms,
        vec![sort_term(
            LinkGraphSortField::Modified,
            LinkGraphSortOrder::Desc
        )]
    );
    assert!(parsed.options.case_sensitive);
    assert_eq!(
        parsed
            .options
            .filters
            .link_to
            .as_ref()
            .map(|row| row.seeds.clone()),
        Some(vec!["a".to_string(), "b".to_string()])
    );
    assert_eq!(
        parsed
            .options
            .filters
            .linked_by
            .as_ref()
            .map(|row| row.seeds.clone()),
        Some(vec!["c".to_string()])
    );
    assert_eq!(
        parsed
            .options
            .filters
            .related
            .as_ref()
            .map(|row| row.seeds.clone()),
        Some(vec!["seed".to_string()])
    );
    assert_eq!(
        parsed
            .options
            .filters
            .related
            .as_ref()
            .and_then(|row| row.max_distance),
        Some(3)
    );
    assert_eq!(
        parsed
            .options
            .filters
            .related
            .as_ref()
            .and_then(|row| row.ppr.as_ref())
            .and_then(|ppr| ppr.alpha),
        Some(0.9)
    );
    assert_eq!(
        parsed
            .options
            .filters
            .related
            .as_ref()
            .and_then(|row| row.ppr.as_ref())
            .and_then(|ppr| ppr.max_iter),
        Some(64)
    );
    assert_eq!(
        parsed
            .options
            .filters
            .related
            .as_ref()
            .and_then(|row| row.ppr.as_ref())
            .and_then(|ppr| ppr.tol),
        Some(1e-6)
    );
    assert_eq!(
        parsed
            .options
            .filters
            .related
            .as_ref()
            .and_then(|row| row.ppr.as_ref())
            .and_then(|ppr| ppr.subgraph_mode),
        Some(LinkGraphPprSubgraphMode::Force)
    );
    assert_eq!(parsed.options.created_after, Some(1_704_067_200));
    assert_eq!(parsed.options.modified_before, Some(1_706_659_200));
}

#[test]
fn test_link_graph_parse_search_query_supports_related_ppr_key_variants() {
    let parsed = parse_search_query(
        "related:seed related.ppr.alpha:0.75 related-ppr-max-iter:32 ppr_tol:1e-5 ppr-subgraph-mode:auto",
        LinkGraphSearchOptions::default(),
    );

    let related = parsed
        .options
        .filters
        .related
        .as_ref()
        .expect("expected related filter");
    assert_eq!(related.seeds, vec!["seed".to_string()]);
    let ppr = related.ppr.as_ref().expect("expected related ppr options");
    assert_eq!(ppr.alpha, Some(0.75));
    assert_eq!(ppr.max_iter, Some(32));
    assert_eq!(ppr.tol, Some(1e-5));
    assert_eq!(ppr.subgraph_mode, Some(LinkGraphPprSubgraphMode::Auto));
}

#[test]
fn test_link_graph_parse_search_query_keeps_fts_for_extension_only_query() {
    let parsed = parse_search_query(".md", LinkGraphSearchOptions::default());
    assert_eq!(parsed.query, ".md");
    assert_eq!(parsed.options.match_strategy, LinkGraphMatchStrategy::Fts);
}

#[test]
fn test_link_graph_parse_search_query_supports_parenthesized_boolean_tags() {
    let parsed = parse_search_query(
        "tag:(core OR infra) roadmap",
        LinkGraphSearchOptions::default(),
    );

    assert_eq!(parsed.query, "roadmap");
    let tags = parsed.options.filters.tags.expect("expected tags filter");
    assert!(tags.all.is_empty());
    assert_eq!(tags.any, vec!["core".to_string(), "infra".to_string()]);
    assert!(tags.not_tags.is_empty());
}

#[test]
fn test_link_graph_parse_search_query_supports_negated_directives_and_pipe_values() {
    let parsed = parse_search_query(
        "-tag:legacy -to:archive to:hub|index from:a|b",
        LinkGraphSearchOptions::default(),
    );

    assert_eq!(parsed.query, "");
    let tags = parsed.options.filters.tags.expect("expected tags filter");
    assert_eq!(tags.not_tags, vec!["legacy".to_string()]);

    let link_to = parsed
        .options
        .filters
        .link_to
        .expect("expected link_to filter");
    assert!(link_to.negate);
    assert_eq!(
        link_to.seeds,
        vec![
            "archive".to_string(),
            "hub".to_string(),
            "index".to_string()
        ]
    );

    let linked_by = parsed
        .options
        .filters
        .linked_by
        .expect("expected linked_by filter");
    assert_eq!(linked_by.seeds, vec!["a".to_string(), "b".to_string()]);
}

#[test]
fn test_link_graph_parse_search_query_supports_multi_sort_terms_in_directive() {
    let parsed = parse_search_query(
        "sort:path_asc,modified_desc,score_desc hello",
        LinkGraphSearchOptions::default(),
    );

    assert_eq!(parsed.query, "hello");
    assert_eq!(
        parsed.options.sort_terms,
        vec![
            sort_term(LinkGraphSortField::Path, LinkGraphSortOrder::Asc),
            sort_term(LinkGraphSortField::Modified, LinkGraphSortOrder::Desc),
            sort_term(LinkGraphSortField::Score, LinkGraphSortOrder::Desc),
        ]
    );
}

#[test]
fn test_link_graph_search_sort_by_path() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("zeta.md"), "# Zeta\n\nkeyword\n")?;
    write_file(&tmp.path().join("alpha.md"), "# Alpha\n\nkeyword\n")?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let options = LinkGraphSearchOptions {
        match_strategy: LinkGraphMatchStrategy::Fts,
        case_sensitive: false,
        sort_terms: vec![sort_term(LinkGraphSortField::Path, LinkGraphSortOrder::Asc)],
        ..LinkGraphSearchOptions::default()
    };
    let hits = index.search_planned(".md", 5, options).1;
    assert_eq!(hits.len(), 2);
    assert_eq!(hits[0].path, "alpha.md");
    assert_eq!(hits[1].path, "zeta.md");
    Ok(())
}

#[test]
fn test_link_graph_search_temporal_filters_and_sorting() -> Result<(), Box<dyn std::error::Error>> {
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
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let created_window = LinkGraphSearchOptions {
        sort_terms: vec![sort_term(
            LinkGraphSortField::Created,
            LinkGraphSortOrder::Asc,
        )],
        created_after: Some(1_704_153_600),  // 2024-01-02
        created_before: Some(1_704_758_400), // 2024-01-09
        ..LinkGraphSearchOptions::default()
    };
    let created_hits = index.search_planned("", 10, created_window).1;
    assert_eq!(created_hits.len(), 1);
    assert_eq!(created_hits[0].path, "docs/b.md");

    let modified_sorted = LinkGraphSearchOptions {
        sort_terms: vec![sort_term(
            LinkGraphSortField::Modified,
            LinkGraphSortOrder::Desc,
        )],
        modified_after: Some(1_704_153_600), // 2024-01-02
        ..LinkGraphSearchOptions::default()
    };
    let modified_hits = index.search_planned("", 10, modified_sorted).1;
    assert_eq!(modified_hits.len(), 3);
    assert_eq!(modified_hits[0].path, "docs/c.md");
    assert_eq!(modified_hits[1].path, "docs/a.md");
    assert_eq!(modified_hits[2].path, "docs/b.md");
    Ok(())
}

#[test]
fn test_link_graph_search_filters_link_to_and_linked_by() -> Result<(), Box<dyn std::error::Error>>
{
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# A\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/c.md"), "# C\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\n[[d]]\n")?;
    write_file(&tmp.path().join("docs/d.md"), "# D\n\nNo links.\n")?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let link_to_options = LinkGraphSearchOptions {
        sort_terms: vec![sort_term(LinkGraphSortField::Path, LinkGraphSortOrder::Asc)],
        filters: LinkGraphSearchFilters {
            link_to: Some(LinkGraphLinkFilter {
                seeds: vec!["b".to_string()],
                ..LinkGraphLinkFilter::default()
            }),
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let link_to_hits = index.search_planned("", 10, link_to_options).1;
    let link_to_paths: Vec<String> = link_to_hits.into_iter().map(|row| row.path).collect();
    assert_eq!(
        link_to_paths,
        vec!["docs/a.md".to_string(), "docs/c.md".to_string()]
    );

    let linked_by_options = LinkGraphSearchOptions {
        sort_terms: vec![sort_term(LinkGraphSortField::Path, LinkGraphSortOrder::Asc)],
        filters: LinkGraphSearchFilters {
            linked_by: Some(LinkGraphLinkFilter {
                seeds: vec!["b".to_string()],
                ..LinkGraphLinkFilter::default()
            }),
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let linked_by_hits = index.search_planned("", 10, linked_by_options).1;
    assert_eq!(linked_by_hits.len(), 1);
    assert_eq!(linked_by_hits[0].path, "docs/d.md");
    Ok(())
}

#[test]
fn test_link_graph_search_filters_related_with_distance() -> Result<(), Box<dyn std::error::Error>>
{
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# A\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\n[[c]]\n")?;
    write_file(&tmp.path().join("docs/c.md"), "# C\n\n[[d]]\n")?;
    write_file(&tmp.path().join("docs/d.md"), "# D\n\nNo links.\n")?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let options_distance_1 = LinkGraphSearchOptions {
        sort_terms: vec![sort_term(LinkGraphSortField::Path, LinkGraphSortOrder::Asc)],
        filters: LinkGraphSearchFilters {
            related: Some(LinkGraphRelatedFilter {
                seeds: vec!["b".to_string()],
                max_distance: Some(1),
                ppr: None,
            }),
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let hits_1 = index.search_planned("", 10, options_distance_1).1;
    let paths_1: Vec<String> = hits_1.into_iter().map(|row| row.path).collect();
    assert_eq!(
        paths_1,
        vec!["docs/a.md".to_string(), "docs/c.md".to_string()]
    );

    let options_distance_2 = LinkGraphSearchOptions {
        sort_terms: vec![sort_term(LinkGraphSortField::Path, LinkGraphSortOrder::Asc)],
        filters: LinkGraphSearchFilters {
            related: Some(LinkGraphRelatedFilter {
                seeds: vec!["b".to_string()],
                max_distance: Some(2),
                ppr: None,
            }),
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let hits_2 = index.search_planned("", 10, options_distance_2).1;
    let paths_2: Vec<String> = hits_2.into_iter().map(|row| row.path).collect();
    assert_eq!(
        paths_2,
        vec![
            "docs/a.md".to_string(),
            "docs/c.md".to_string(),
            "docs/d.md".to_string(),
        ]
    );
    Ok(())
}

#[test]
fn test_link_graph_search_filters_related_accepts_ppr_options()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# A\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\n[[c]]\n")?;
    write_file(&tmp.path().join("docs/c.md"), "# C\n\n[[d]]\n")?;
    write_file(&tmp.path().join("docs/d.md"), "# D\n\nNo links.\n")?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let options = LinkGraphSearchOptions {
        sort_terms: vec![sort_term(LinkGraphSortField::Path, LinkGraphSortOrder::Asc)],
        filters: LinkGraphSearchFilters {
            related: Some(LinkGraphRelatedFilter {
                seeds: vec!["b".to_string()],
                max_distance: Some(2),
                ppr: Some(LinkGraphRelatedPprOptions {
                    alpha: Some(0.9),
                    max_iter: Some(64),
                    tol: Some(1e-6),
                    subgraph_mode: Some(LinkGraphPprSubgraphMode::Force),
                }),
            }),
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let hits = index.search_planned("", 10, options).1;
    let paths: Vec<String> = hits.into_iter().map(|row| row.path).collect();
    assert_eq!(
        paths,
        vec![
            "docs/a.md".to_string(),
            "docs/c.md".to_string(),
            "docs/d.md".to_string(),
        ]
    );
    Ok(())
}

#[test]
fn test_link_graph_search_options_validate_rejects_invalid_related_ppr_alpha() {
    let options = LinkGraphSearchOptions {
        filters: LinkGraphSearchFilters {
            related: Some(LinkGraphRelatedFilter {
                seeds: vec!["b".to_string()],
                max_distance: Some(2),
                ppr: Some(LinkGraphRelatedPprOptions {
                    alpha: Some(1.2),
                    max_iter: Some(32),
                    tol: Some(1e-6),
                    subgraph_mode: Some(LinkGraphPprSubgraphMode::Auto),
                }),
            }),
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let err = options.validate().expect_err("alpha > 1 must fail");
    assert!(err.contains("filters.related.ppr.alpha"));
}

#[test]
fn test_link_graph_search_filters_mentions_orphan_tagless_and_missing_backlink()
-> Result<(), Box<dyn std::error::Error>> {
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
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let mentions_options = LinkGraphSearchOptions {
        sort_terms: vec![sort_term(LinkGraphSortField::Path, LinkGraphSortOrder::Asc)],
        filters: LinkGraphSearchFilters {
            mentions_of: vec!["alpha signal".to_string()],
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let mention_hits = index.search_planned("", 10, mentions_options).1;
    let mention_paths: Vec<String> = mention_hits.into_iter().map(|row| row.path).collect();
    assert_eq!(
        mention_paths,
        vec!["docs/a.md".to_string(), "docs/c.md".to_string()]
    );

    let mentioned_by_options = LinkGraphSearchOptions {
        sort_terms: vec![sort_term(LinkGraphSortField::Path, LinkGraphSortOrder::Asc)],
        filters: LinkGraphSearchFilters {
            mentioned_by_notes: vec!["a".to_string()],
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let mentioned_by_hits = index.search_planned("", 10, mentioned_by_options).1;
    assert_eq!(mentioned_by_hits.len(), 1);
    assert_eq!(mentioned_by_hits[0].path, "docs/b.md");

    let orphan_options = LinkGraphSearchOptions {
        sort_terms: vec![sort_term(LinkGraphSortField::Path, LinkGraphSortOrder::Asc)],
        filters: LinkGraphSearchFilters {
            orphan: true,
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let orphan_hits = index.search_planned("", 10, orphan_options).1;
    assert_eq!(orphan_hits.len(), 1);
    assert_eq!(orphan_hits[0].path, "docs/c.md");

    let tagless_options = LinkGraphSearchOptions {
        sort_terms: vec![sort_term(LinkGraphSortField::Path, LinkGraphSortOrder::Asc)],
        filters: LinkGraphSearchFilters {
            tagless: true,
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let tagless_hits = index.search_planned("", 10, tagless_options).1;
    let tagless_paths: Vec<String> = tagless_hits.into_iter().map(|row| row.path).collect();
    assert_eq!(tagless_paths, vec!["docs/c.md".to_string()]);

    let missing_backlink_options = LinkGraphSearchOptions {
        sort_terms: vec![sort_term(LinkGraphSortField::Path, LinkGraphSortOrder::Asc)],
        filters: LinkGraphSearchFilters {
            missing_backlink: true,
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let missing_backlink_hits = index.search_planned("", 10, missing_backlink_options).1;
    assert_eq!(missing_backlink_hits.len(), 1);
    assert_eq!(missing_backlink_hits[0].path, "docs/a.md");

    Ok(())
}

#[test]
fn test_link_graph_neighbors_related_metadata_and_toc() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("root/a.md"),
        "# Alpha\n\n[[b]]\n[[sub/c]]\n",
    )?;
    write_file(
        &tmp.path().join("root/b.md"),
        "---\ntags:\n  - one\n  - two\n---\n\n[[a]]\n",
    )?;
    write_file(&tmp.path().join("root/sub/c.md"), "# C\n\n[[a]]\n")?;

    let index = LinkGraphIndex::build(&tmp.path().join("root")).map_err(|e| e.to_string())?;

    let neighbors = index.neighbors("a", LinkGraphDirection::Both, 1, 10);
    assert_eq!(neighbors.len(), 2);
    assert!(neighbors.iter().any(|row| row.stem == "b"));
    assert!(neighbors.iter().any(|row| row.stem == "c"));
    for row in &neighbors {
        assert_eq!(row.distance, 1);
        assert_eq!(row.direction, LinkGraphDirection::Both);
    }

    let related = index.related("a", 2, 10);
    assert!(related.iter().any(|row| row.stem == "b"));

    let metadata = index.metadata("b").ok_or("missing metadata")?;
    assert_eq!(metadata.stem, "b");
    assert_eq!(metadata.path, "b.md");
    assert_eq!(metadata.tags, vec!["one".to_string(), "two".to_string()]);

    let toc = index.toc(10);
    assert_eq!(toc.len(), 3);
    assert!(toc.iter().any(|row| row.path == "a.md"));
    assert!(toc.iter().any(|row| row.path == "b.md"));
    assert!(toc.iter().any(|row| row.path == "sub/c.md"));

    Ok(())
}

#[test]
fn test_link_graph_related_with_diagnostics_returns_metrics()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("root/a.md"), "# A\n\n[[b]]\n")?;
    write_file(&tmp.path().join("root/b.md"), "# B\n\n[[c]]\n")?;
    write_file(&tmp.path().join("root/c.md"), "# C\n\n[[d]]\n")?;
    write_file(&tmp.path().join("root/d.md"), "# D\n\nNo links.\n")?;
    let index = LinkGraphIndex::build(&tmp.path().join("root")).map_err(|e| e.to_string())?;

    let ppr = LinkGraphRelatedPprOptions {
        alpha: Some(0.9),
        max_iter: Some(64),
        tol: Some(1e-6),
        subgraph_mode: Some(LinkGraphPprSubgraphMode::Force),
    };
    let (rows, diagnostics) = index.related_with_diagnostics("b", 2, 10, Some(&ppr));
    assert_eq!(rows.len(), 3);
    assert!(rows.iter().any(|row| row.stem == "a"));
    assert!(rows.iter().any(|row| row.stem == "c"));
    assert!(rows.iter().any(|row| row.stem == "d"));

    let metrics = diagnostics.ok_or("missing related diagnostics")?;
    assert_eq!(metrics.alpha, 0.9);
    assert_eq!(metrics.max_iter, 64);
    assert_eq!(metrics.tol, 1e-6);
    assert!(metrics.iteration_count >= 1);
    assert!(metrics.final_residual >= 0.0);
    assert_eq!(metrics.candidate_count, 3);
    assert_eq!(metrics.graph_node_count, 4);
    assert_eq!(metrics.subgraph_count, 1);
    assert_eq!(metrics.partition_max_node_count, 4);
    assert_eq!(metrics.partition_min_node_count, 4);
    assert_eq!(metrics.partition_avg_node_count, 4.0);
    assert!(metrics.total_duration_ms >= 0.0);
    assert!(metrics.partition_duration_ms >= 0.0);
    assert!(metrics.kernel_duration_ms >= 0.0);
    assert!(metrics.fusion_duration_ms >= 0.0);
    assert_eq!(metrics.subgraph_mode, LinkGraphPprSubgraphMode::Force);
    assert!(metrics.horizon_restricted);

    Ok(())
}

#[test]
fn test_link_graph_related_from_seeds_with_diagnostics_partitions_when_forced()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("root/a.md"), "# A\n\n[[b]]\n")?;
    write_file(&tmp.path().join("root/b.md"), "# B\n\n[[c]]\n")?;
    write_file(&tmp.path().join("root/c.md"), "# C\n\nNo links.\n")?;
    write_file(&tmp.path().join("root/d.md"), "# D\n\n[[e]]\n")?;
    write_file(&tmp.path().join("root/e.md"), "# E\n\n[[f]]\n")?;
    write_file(&tmp.path().join("root/f.md"), "# F\n\nNo links.\n")?;
    let index = LinkGraphIndex::build(&tmp.path().join("root")).map_err(|e| e.to_string())?;

    let seeds = vec!["b".to_string(), "e".to_string()];
    let ppr = LinkGraphRelatedPprOptions {
        alpha: Some(0.85),
        max_iter: Some(48),
        tol: Some(1e-6),
        subgraph_mode: Some(LinkGraphPprSubgraphMode::Force),
    };
    let (rows, diagnostics) = index.related_from_seeds_with_diagnostics(&seeds, 2, 20, Some(&ppr));
    let metrics = diagnostics.ok_or("missing related diagnostics")?;
    assert_eq!(metrics.subgraph_mode, LinkGraphPprSubgraphMode::Force);
    assert!(metrics.horizon_restricted);
    assert_eq!(metrics.subgraph_count, 2);
    assert_eq!(metrics.partition_max_node_count, 3);
    assert_eq!(metrics.partition_min_node_count, 3);
    assert_eq!(metrics.partition_avg_node_count, 3.0);
    assert!(metrics.total_duration_ms >= 0.0);
    assert!(metrics.partition_duration_ms >= 0.0);
    assert!(metrics.kernel_duration_ms >= 0.0);
    assert!(metrics.fusion_duration_ms >= 0.0);

    let mut stems: Vec<String> = rows.into_iter().map(|row| row.stem).collect();
    stems.sort_unstable();
    assert_eq!(stems, vec!["a", "c", "d", "f"]);
    Ok(())
}

#[test]
fn test_link_graph_build_with_excluded_dirs_skips_cache_tree()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# Alpha\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# Beta\n\n[[a]]\n")?;
    write_file(
        &tmp.path().join(".cache/huge.md"),
        "# Should Be Skipped\n\n[[docs/a]]\n",
    )?;

    let excluded = vec![".cache".to_string()];
    let index = LinkGraphIndex::build_with_excluded_dirs(tmp.path(), &excluded)
        .map_err(|e| e.to_string())?;

    let stats = index.stats();
    assert_eq!(stats.total_notes, 2);
    assert_eq!(stats.links_in_graph, 2);
    assert_eq!(stats.orphans, 0);

    let toc_paths: Vec<String> = index.toc(10).into_iter().map(|row| row.path).collect();
    assert!(!toc_paths.iter().any(|path| path.contains(".cache/")));
    Ok(())
}

#[test]
fn test_link_graph_build_skips_hidden_dirs_by_default() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# Alpha\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# Beta\n\n[[a]]\n")?;
    write_file(
        &tmp.path().join(".github/hidden.md"),
        "# Hidden\n\n[[docs/a]]\n",
    )?;

    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;
    let stats = index.stats();
    assert_eq!(stats.total_notes, 2);
    assert_eq!(stats.links_in_graph, 2);

    let toc_paths: Vec<String> = index.toc(10).into_iter().map(|row| row.path).collect();
    assert!(!toc_paths.iter().any(|path| path.starts_with(".github/")));
    Ok(())
}

#[test]
fn test_link_graph_build_with_include_dirs_limits_scope() -> Result<(), Box<dyn std::error::Error>>
{
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# Alpha\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# Beta\n\n[[a]]\n")?;
    write_file(
        &tmp.path().join("assets/knowledge/c.md"),
        "# Gamma\n\n[[docs/a]]\n",
    )?;

    let include = vec!["docs".to_string()];
    let index =
        LinkGraphIndex::build_with_filters(tmp.path(), &include, &[]).map_err(|e| e.to_string())?;

    let stats = index.stats();
    assert_eq!(stats.total_notes, 2);
    assert_eq!(stats.links_in_graph, 2);
    assert_eq!(stats.orphans, 0);

    let toc_paths: Vec<String> = index.toc(10).into_iter().map(|row| row.path).collect();
    assert!(toc_paths.iter().all(|path| path.starts_with("docs/")));
    Ok(())
}

#[test]
fn test_link_graph_refresh_incremental_updates_and_deletes_notes()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    let b_path = tmp.path().join("docs/b.md");
    write_file(&tmp.path().join("docs/a.md"), "# Alpha\n\n[[b]]\n")?;
    write_file(&b_path, "# Beta\n\nold keyword\n")?;

    let mut index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;
    let old_hits = index
        .search_planned("old keyword", 5, LinkGraphSearchOptions::default())
        .1;
    assert_eq!(old_hits.len(), 1);

    write_file(&b_path, "# Beta\n\nnew keyword\n")?;
    let mode = index
        .refresh_incremental_with_threshold(std::slice::from_ref(&b_path), 256)
        .map_err(|e| e.to_string())?;
    assert_eq!(mode, LinkGraphRefreshMode::Delta);
    let new_hits = index
        .search_planned("new keyword", 5, LinkGraphSearchOptions::default())
        .1;
    assert_eq!(new_hits.len(), 1);
    assert_eq!(new_hits[0].stem, "b");

    fs::remove_file(&b_path)?;
    let mode = index
        .refresh_incremental_with_threshold(std::slice::from_ref(&b_path), 256)
        .map_err(|e| e.to_string())?;
    assert_eq!(mode, LinkGraphRefreshMode::Delta);
    let stats = index.stats();
    assert_eq!(stats.total_notes, 1);
    assert_eq!(stats.links_in_graph, 0);
    Ok(())
}

#[test]
fn test_link_graph_refresh_incremental_with_threshold_modes()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    let a_path = tmp.path().join("docs/a.md");
    let b_path = tmp.path().join("docs/b.md");
    write_file(&a_path, "# Alpha\n\n[[b]]\n")?;
    write_file(&b_path, "# Beta\n\n[[a]]\n")?;

    let mut index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;
    let noop = index
        .refresh_incremental_with_threshold(&[], 1)
        .map_err(|e| e.to_string())?;
    assert_eq!(noop, LinkGraphRefreshMode::Noop);

    write_file(&a_path, "# Alpha\n\n[[b]]\n\nnew token\n")?;
    let full = index
        .refresh_incremental_with_threshold(std::slice::from_ref(&a_path), 1)
        .map_err(|e| e.to_string())?;
    assert_eq!(full, LinkGraphRefreshMode::Full);

    let hits = index
        .search_planned("new token", 5, LinkGraphSearchOptions::default())
        .1;
    assert_eq!(hits.len(), 1);
    assert_eq!(hits[0].stem, "a");
    Ok(())
}

#[test]
fn test_link_graph_search_planned_payload_has_consistent_counts()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "# Alpha\n\n## Architecture\n\ngraph engine planner token\n",
    )?;
    write_file(&tmp.path().join("docs/b.md"), "# Beta\n\ngraph token\n")?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let payload =
        index.search_planned_payload("architecture graph", 10, LinkGraphSearchOptions::default());
    assert_eq!(payload.hit_count, payload.results.len());
    assert_eq!(payload.hit_count, payload.hits.len());
    assert_eq!(payload.query, "architecture graph");
    assert!(payload.section_hit_count <= payload.hit_count);
    assert!(payload.hits.iter().all(|hit| hit.score >= 0.0));
    Ok(())
}

#[test]
fn test_link_graph_extracts_markdown_links_relative_and_anchor()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "# A\n\n[B](b.md)\n[C](sub/c.md#section)\n[External](https://example.com)\n",
    )?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\nNo links.\n")?;
    write_file(
        &tmp.path().join("docs/sub/c.md"),
        "# C\n\n[A](../a.md)\n[Up](#top)\n",
    )?;

    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;
    let stats = index.stats();
    assert_eq!(stats.total_notes, 3);
    assert_eq!(stats.links_in_graph, 3);

    let neighbors = index.neighbors("a", LinkGraphDirection::Both, 1, 10);
    let stems: Vec<String> = neighbors.into_iter().map(|row| row.stem).collect();
    assert!(stems.contains(&"b".to_string()));
    assert!(stems.contains(&"c".to_string()));
    Ok(())
}

#[test]
fn test_link_graph_extracts_markdown_reference_links() -> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "# A\n\n[B][b-ref]\n[C][]\n[D][missing]\n\n[b-ref]: b.md \"Beta\"\n[C]: sub/c.md#top\n",
    )?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\nNo links.\n")?;
    write_file(&tmp.path().join("docs/sub/c.md"), "# C\n\nNo links.\n")?;

    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;
    let stats = index.stats();
    assert_eq!(stats.total_notes, 3);
    assert_eq!(stats.links_in_graph, 2);

    let neighbors = index.neighbors("a", LinkGraphDirection::Both, 1, 10);
    let stems: Vec<String> = neighbors.into_iter().map(|row| row.stem).collect();
    assert!(stems.contains(&"b".to_string()));
    assert!(stems.contains(&"c".to_string()));
    Ok(())
}

#[test]
fn test_link_graph_uses_comrak_for_complex_markdown_links() -> Result<(), Box<dyn std::error::Error>>
{
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "# A\n\n[Paren](b(1).md)\n\n`[Nope](c.md)`\n\n```md\n[AlsoNope](c.md)\n```\n",
    )?;
    write_file(&tmp.path().join("docs/b(1).md"), "# B\n\nNo links.\n")?;
    write_file(&tmp.path().join("docs/c.md"), "# C\n\nNo links.\n")?;

    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;
    let stats = index.stats();
    assert_eq!(stats.total_notes, 3);
    assert_eq!(stats.links_in_graph, 1);

    let neighbors = index.neighbors("a", LinkGraphDirection::Both, 1, 10);
    assert_eq!(neighbors.len(), 1);
    assert_eq!(neighbors[0].stem, "b(1)");
    Ok(())
}

#[test]
fn test_link_graph_parse_search_query_supports_tree_filter_directives() {
    let parsed = parse_search_query(
        "scope:section_only edge_types:structural,verified max_heading_level:3 max_tree_hops:2 collapse_to_doc:false per_doc_section_cap:4 min_section_words:18 architecture",
        LinkGraphSearchOptions::default(),
    );

    assert_eq!(parsed.query, "architecture");
    assert_eq!(
        parsed.options.filters.scope,
        Some(LinkGraphScope::SectionOnly)
    );
    assert_eq!(
        parsed.options.filters.edge_types,
        vec![LinkGraphEdgeType::Structural, LinkGraphEdgeType::Verified]
    );
    assert_eq!(parsed.options.filters.max_heading_level, Some(3));
    assert_eq!(parsed.options.filters.max_tree_hops, Some(2));
    assert_eq!(parsed.options.filters.collapse_to_doc, Some(false));
    assert_eq!(parsed.options.filters.per_doc_section_cap, Some(4));
    assert_eq!(parsed.options.filters.min_section_words, Some(18));
}

#[test]
fn test_link_graph_search_options_deserialize_accepts_tree_filters() {
    let payload = json!({
        "match_strategy": "fts",
        "case_sensitive": false,
        "sort_terms": [{"field": "score", "order": "desc"}],
        "filters": {
            "scope": "mixed",
            "max_heading_level": 4,
            "max_tree_hops": 3,
            "collapse_to_doc": true,
            "edge_types": ["semantic", "verified"],
            "per_doc_section_cap": 5,
            "min_section_words": 12
        }
    });
    let parsed: LinkGraphSearchOptions =
        serde_json::from_value(payload).expect("tree filters should deserialize");
    assert_eq!(parsed.filters.scope, Some(LinkGraphScope::Mixed));
    assert_eq!(
        parsed.filters.edge_types,
        vec![LinkGraphEdgeType::Semantic, LinkGraphEdgeType::Verified]
    );
    assert_eq!(parsed.filters.max_heading_level, Some(4));
    assert_eq!(parsed.filters.max_tree_hops, Some(3));
    assert_eq!(parsed.filters.collapse_to_doc, Some(true));
    assert_eq!(parsed.filters.per_doc_section_cap, Some(5));
    assert_eq!(parsed.filters.min_section_words, Some(12));
}

#[test]
fn test_link_graph_search_options_validate_rejects_invalid_tree_filters() {
    let payload = json!({
        "match_strategy": "fts",
        "case_sensitive": false,
        "sort_terms": [{"field": "score", "order": "desc"}],
        "filters": {
            "max_heading_level": 9,
            "per_doc_section_cap": 0
        }
    });
    let parsed: LinkGraphSearchOptions =
        serde_json::from_value(payload).expect("payload should deserialize before validation");
    let error = parsed
        .validate()
        .expect_err("validation should reject invalid tree filters");
    assert!(error.contains("max_heading_level") || error.contains("per_doc_section_cap"));
}

#[test]
fn test_link_graph_search_section_scope_respects_per_doc_cap()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "# A\n\n## Alpha One\n\nalpha marker content line one.\n\n## Alpha Two\n\nalpha marker content line two.\n",
    )?;
    write_file(
        &tmp.path().join("docs/b.md"),
        "# B\n\n## Beta One\n\nalpha marker content line one.\n\n## Beta Two\n\nalpha marker content line two.\n",
    )?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let options = LinkGraphSearchOptions {
        filters: LinkGraphSearchFilters {
            scope: Some(LinkGraphScope::SectionOnly),
            per_doc_section_cap: Some(1),
            min_section_words: Some(0),
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let hits = index.search_planned("alpha marker", 20, options).1;
    assert_eq!(hits.len(), 2);
    assert!(hits.iter().all(|row| row.best_section.is_some()));

    let mut per_path: HashMap<String, usize> = HashMap::new();
    for row in hits {
        *per_path.entry(row.path).or_insert(0) += 1;
    }
    assert!(per_path.values().all(|count| *count == 1));
    Ok(())
}

#[test]
fn test_link_graph_search_tree_level_and_min_words_filters()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "# Root\n\n## Allowed\n\nneedle appears with enough words for filtering.\n\n#### Too Deep\n\nneedle appears here but must be filtered by heading depth.\n\n## Too Short\n\nneedle\n",
    )?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let options = LinkGraphSearchOptions {
        filters: LinkGraphSearchFilters {
            scope: Some(LinkGraphScope::SectionOnly),
            max_heading_level: Some(2),
            min_section_words: Some(4),
            per_doc_section_cap: Some(10),
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let hits = index.search_planned("needle", 20, options).1;
    assert_eq!(hits.len(), 1);
    assert_eq!(hits[0].best_section.as_deref(), Some("Root / Allowed"));
    Ok(())
}

#[test]
fn test_link_graph_search_tree_hops_limit_section_expansion()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "# Root\n\n## Parent\n\nneedle parent context words here.\n\n### Needle Focus\n\nneedle focus context words here.\n\n### Sibling\n\nneedle sibling context words here.\n\n## Other\n\nneedle other branch words here.\n",
    )?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let base = LinkGraphSearchOptions {
        filters: LinkGraphSearchFilters {
            scope: Some(LinkGraphScope::SectionOnly),
            per_doc_section_cap: Some(10),
            min_section_words: Some(0),
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let hops_zero = LinkGraphSearchOptions {
        filters: LinkGraphSearchFilters {
            max_tree_hops: Some(0),
            ..base.filters.clone()
        },
        ..base.clone()
    };
    let hits_zero = index.search_planned("needle focus", 20, hops_zero).1;
    assert_eq!(hits_zero.len(), 1);
    assert_eq!(
        hits_zero[0].best_section.as_deref(),
        Some("Root / Parent / Needle Focus")
    );

    let hops_one = LinkGraphSearchOptions {
        filters: LinkGraphSearchFilters {
            max_tree_hops: Some(1),
            ..base.filters.clone()
        },
        ..base
    };
    let hits_one = index.search_planned("needle focus", 20, hops_one).1;
    let sections_one: Vec<String> = hits_one
        .iter()
        .filter_map(|row| row.best_section.clone())
        .collect();
    assert!(sections_one.contains(&"Root / Parent / Needle Focus".to_string()));
    assert!(sections_one.contains(&"Root / Parent".to_string()));
    assert!(!sections_one.contains(&"Root / Parent / Sibling".to_string()));
    assert!(!sections_one.contains(&"Root / Other".to_string()));
    Ok(())
}

#[test]
fn test_link_graph_search_mixed_scope_collapse_toggle_changes_output_shape()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "# A\n\n## One\n\nalpha context words one.\n\n## Two\n\nalpha context words two.\n",
    )?;
    write_file(
        &tmp.path().join("docs/b.md"),
        "# B\n\n## B One\n\nalpha context words.\n",
    )?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let collapse_true = LinkGraphSearchOptions {
        filters: LinkGraphSearchFilters {
            scope: Some(LinkGraphScope::Mixed),
            collapse_to_doc: Some(true),
            per_doc_section_cap: Some(3),
            min_section_words: Some(0),
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let hits_collapsed = index.search_planned("alpha context", 20, collapse_true).1;
    let mut collapsed_counts: HashMap<String, usize> = HashMap::new();
    for row in hits_collapsed {
        *collapsed_counts.entry(row.path).or_insert(0) += 1;
    }
    assert!(collapsed_counts.values().all(|count| *count == 1));

    let collapse_false = LinkGraphSearchOptions {
        filters: LinkGraphSearchFilters {
            scope: Some(LinkGraphScope::Mixed),
            collapse_to_doc: Some(false),
            per_doc_section_cap: Some(3),
            min_section_words: Some(0),
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let hits_expanded = index.search_planned("alpha context", 20, collapse_false).1;
    let mut expanded_counts: HashMap<String, usize> = HashMap::new();
    for row in hits_expanded {
        *expanded_counts.entry(row.path).or_insert(0) += 1;
    }
    assert!(expanded_counts.values().any(|count| *count > 1));
    Ok(())
}

#[test]
fn test_link_graph_search_edge_type_filter_restricts_semantic_graph_filters()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(&tmp.path().join("docs/a.md"), "# A\n\n[[b]]\n")?;
    write_file(&tmp.path().join("docs/b.md"), "# B\n\nNo links.\n")?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let options = LinkGraphSearchOptions {
        filters: LinkGraphSearchFilters {
            link_to: Some(LinkGraphLinkFilter {
                seeds: vec!["b".to_string()],
                ..LinkGraphLinkFilter::default()
            }),
            edge_types: vec![LinkGraphEdgeType::Structural],
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let hits = index.search_planned("", 10, options).1;
    assert!(hits.is_empty());
    Ok(())
}

#[test]
fn test_link_graph_search_edge_type_filter_restricts_structural_scope()
-> Result<(), Box<dyn std::error::Error>> {
    let tmp = TempDir::new()?;
    write_file(
        &tmp.path().join("docs/a.md"),
        "# A\n\n## Section\n\nalpha words here.\n",
    )?;
    let index = LinkGraphIndex::build(tmp.path()).map_err(|e| e.to_string())?;

    let options = LinkGraphSearchOptions {
        filters: LinkGraphSearchFilters {
            scope: Some(LinkGraphScope::SectionOnly),
            edge_types: vec![LinkGraphEdgeType::Semantic],
            min_section_words: Some(0),
            ..LinkGraphSearchFilters::default()
        },
        ..LinkGraphSearchOptions::default()
    };
    let hits = index.search_planned("alpha", 10, options).1;
    assert!(hits.is_empty());
    Ok(())
}
