#![allow(missing_docs)]

use anyhow::{Context, Result};
use clap::{Parser, Subcommand, ValueEnum};
use serde::Serialize;
use serde_json::json;
use std::path::PathBuf;
use xiuxian_wendao::{
    LinkGraphDirection, LinkGraphIndex, LinkGraphLinkFilter, LinkGraphMatchStrategy,
    LinkGraphPprSubgraphMode, LinkGraphRelatedFilter, LinkGraphRelatedPprOptions,
    LinkGraphSaliencyTouchRequest, LinkGraphSearchFilters, LinkGraphSearchOptions,
    LinkGraphSortField, LinkGraphSortOrder, LinkGraphSortTerm, LinkGraphTagFilter,
    resolve_link_graph_index_runtime, set_link_graph_wendao_config_override,
    validate_blackboard_file, valkey_saliency_get, valkey_saliency_touch,
};

#[derive(Parser, Debug)]
#[command(
    name = "wendao",
    about = "Wendao link-graph CLI for local note search and traversal",
    arg_required_else_help = true
)]
struct Cli {
    /// Notebook root directory.
    #[arg(
        long,
        short = 'r',
        value_name = "DIR",
        default_value = ".",
        global = true
    )]
    root: PathBuf,

    /// Explicit wendao config file path (for example: `.config/omni-dev-fusion/wendao.yaml`).
    ///
    /// This overrides the default user settings path resolution.
    #[arg(long = "conf", short = 'c', value_name = "FILE", global = true)]
    config_file: Option<PathBuf>,

    /// Include only these relative directories (repeatable).
    #[arg(long = "include-dir", value_name = "DIR", global = true)]
    include_dirs: Vec<String>,

    /// Exclude these directory names globally (repeatable).
    #[arg(long = "exclude-dir", value_name = "DIR", global = true)]
    exclude_dirs: Vec<String>,

    /// Output format.
    #[arg(long, short = 'o', value_enum, default_value_t = OutputFormat::Json, global = true)]
    output: OutputFormat,

    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Search notes by title/path/stem/tags.
    Search {
        query: String,
        #[arg(short, long, default_value_t = 20)]
        limit: usize,
        #[arg(long = "match-strategy", default_value = "fts")]
        match_strategy: String,
        #[arg(long = "sort-term", value_name = "TERM", num_args = 1..)]
        sort_terms: Vec<String>,
        #[arg(long, default_value_t = false)]
        case_sensitive: bool,
        #[arg(long = "include-path", value_name = "PATH", num_args = 1..)]
        include_paths: Vec<String>,
        #[arg(long = "exclude-path", value_name = "PATH", num_args = 1..)]
        exclude_paths: Vec<String>,
        #[arg(long = "tag-all", value_name = "TAG", num_args = 1..)]
        tags_all: Vec<String>,
        #[arg(long = "tag-any", value_name = "TAG", num_args = 1..)]
        tags_any: Vec<String>,
        #[arg(long = "tag-not", value_name = "TAG", num_args = 1..)]
        tags_not: Vec<String>,
        #[arg(long = "link-to", value_name = "NOTE", num_args = 1..)]
        link_to: Vec<String>,
        #[arg(long = "link-to-negate", default_value_t = false)]
        link_to_negate: bool,
        #[arg(long = "link-to-recursive", default_value_t = false)]
        link_to_recursive: bool,
        #[arg(long = "link-to-max-distance")]
        link_to_max_distance: Option<usize>,
        #[arg(long = "linked-by", value_name = "NOTE", num_args = 1..)]
        linked_by: Vec<String>,
        #[arg(long = "linked-by-negate", default_value_t = false)]
        linked_by_negate: bool,
        #[arg(long = "linked-by-recursive", default_value_t = false)]
        linked_by_recursive: bool,
        #[arg(long = "linked-by-max-distance")]
        linked_by_max_distance: Option<usize>,
        #[arg(long = "related", value_name = "NOTE", num_args = 1..)]
        related: Vec<String>,
        #[arg(long = "max-distance")]
        max_distance: Option<usize>,
        #[arg(long = "related-ppr-alpha", requires = "related")]
        related_ppr_alpha: Option<f64>,
        #[arg(long = "related-ppr-max-iter", requires = "related")]
        related_ppr_max_iter: Option<usize>,
        #[arg(long = "related-ppr-tol", requires = "related")]
        related_ppr_tol: Option<f64>,
        #[arg(long = "related-ppr-subgraph-mode", requires = "related", value_enum)]
        related_ppr_subgraph_mode: Option<RelatedPprSubgraphModeArg>,
        #[arg(long = "mentions-of", value_name = "PHRASE", num_args = 1..)]
        mentions_of: Vec<String>,
        #[arg(long = "mentioned-by-notes", value_name = "NOTE", num_args = 1..)]
        mentioned_by_notes: Vec<String>,
        #[arg(long = "orphan", default_value_t = false)]
        orphan: bool,
        #[arg(long = "tagless", default_value_t = false)]
        tagless: bool,
        #[arg(long = "missing-backlink", default_value_t = false)]
        missing_backlink: bool,
        #[arg(long = "created-after")]
        created_after: Option<i64>,
        #[arg(long = "created-before")]
        created_before: Option<i64>,
        #[arg(long = "modified-after")]
        modified_after: Option<i64>,
        #[arg(long = "modified-before")]
        modified_before: Option<i64>,
    },
    /// Return link-graph stats.
    Stats,
    /// Return table-of-contents rows.
    Toc {
        #[arg(short, long, default_value_t = 100)]
        limit: usize,
    },
    /// Return neighbors for a note.
    Neighbors {
        stem: String,
        #[arg(long, default_value = "both")]
        direction: String,
        #[arg(long, default_value_t = 1)]
        hops: usize,
        #[arg(short, long, default_value_t = 50)]
        limit: usize,
    },
    /// Return related notes for a note.
    Related {
        stem: String,
        #[arg(long, default_value_t = 2)]
        max_distance: usize,
        #[arg(short, long, default_value_t = 20)]
        limit: usize,
        #[arg(long, default_value_t = false)]
        verbose: bool,
        #[arg(long = "ppr-alpha")]
        ppr_alpha: Option<f64>,
        #[arg(long = "ppr-max-iter")]
        ppr_max_iter: Option<usize>,
        #[arg(long = "ppr-tol")]
        ppr_tol: Option<f64>,
        #[arg(long = "ppr-subgraph-mode", value_enum)]
        ppr_subgraph_mode: Option<RelatedPprSubgraphModeArg>,
    },
    /// Return metadata for a note.
    Metadata { stem: String },
    /// Read/update GraphMem saliency state.
    Saliency {
        #[command(subcommand)]
        command: SaliencyCommand,
    },
    /// Validate HMAS markdown blackboard protocol blocks.
    Hmas {
        #[command(subcommand)]
        command: HmasCommand,
    },
}

#[derive(Subcommand, Debug)]
enum SaliencyCommand {
    /// Read a saliency state by node id.
    Get { node_id: String },
    /// Touch a node and update saliency with decay + activation.
    Touch {
        node_id: String,
        #[arg(long, default_value_t = 1)]
        activation_delta: u64,
        #[arg(long)]
        saliency_base: Option<f64>,
        #[arg(long)]
        decay_rate: Option<f64>,
        #[arg(long)]
        alpha: Option<f64>,
        #[arg(long)]
        minimum_saliency: Option<f64>,
        #[arg(long)]
        maximum_saliency: Option<f64>,
        #[arg(long)]
        now_unix: Option<i64>,
    },
}

#[derive(Subcommand, Debug)]
enum HmasCommand {
    /// Validate markdown blackboard protocol blocks from a file.
    Validate {
        #[arg(long)]
        file: PathBuf,
    },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
enum OutputFormat {
    Json,
    Pretty,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
enum RelatedPprSubgraphModeArg {
    Auto,
    Disabled,
    Force,
}

impl From<RelatedPprSubgraphModeArg> for LinkGraphPprSubgraphMode {
    fn from(value: RelatedPprSubgraphModeArg) -> Self {
        match value {
            RelatedPprSubgraphModeArg::Auto => Self::Auto,
            RelatedPprSubgraphModeArg::Disabled => Self::Disabled,
            RelatedPprSubgraphModeArg::Force => Self::Force,
        }
    }
}

fn parse_sort_field(raw: &str) -> Option<LinkGraphSortField> {
    match raw.trim().to_lowercase().as_str() {
        "score" => Some(LinkGraphSortField::Score),
        "path" => Some(LinkGraphSortField::Path),
        "title" => Some(LinkGraphSortField::Title),
        "stem" => Some(LinkGraphSortField::Stem),
        "created" => Some(LinkGraphSortField::Created),
        "modified" | "updated" => Some(LinkGraphSortField::Modified),
        "random" => Some(LinkGraphSortField::Random),
        "word_count" | "word-count" => Some(LinkGraphSortField::WordCount),
        _ => None,
    }
}

fn parse_sort_order(raw: &str) -> Option<LinkGraphSortOrder> {
    match raw.trim().to_lowercase().as_str() {
        "asc" | "+" => Some(LinkGraphSortOrder::Asc),
        "desc" | "-" => Some(LinkGraphSortOrder::Desc),
        _ => None,
    }
}

fn default_order_for_field(field: LinkGraphSortField) -> LinkGraphSortOrder {
    match field {
        LinkGraphSortField::Path
        | LinkGraphSortField::Title
        | LinkGraphSortField::Stem
        | LinkGraphSortField::Random => LinkGraphSortOrder::Asc,
        LinkGraphSortField::Score
        | LinkGraphSortField::Created
        | LinkGraphSortField::Modified
        | LinkGraphSortField::WordCount => LinkGraphSortOrder::Desc,
    }
}

fn parse_sort_term(raw: &str) -> LinkGraphSortTerm {
    let value = raw.trim().to_lowercase().replace('-', "_");
    if value.is_empty() {
        return LinkGraphSortTerm::default();
    }

    let pair = value
        .split_once(':')
        .or_else(|| value.split_once('/'))
        .or_else(|| value.rsplit_once('_'));
    if let Some((field_raw, order_raw)) = pair
        && let (Some(field), Some(order)) =
            (parse_sort_field(field_raw), parse_sort_order(order_raw))
    {
        return LinkGraphSortTerm { field, order };
    }

    if let Some(field) = parse_sort_field(&value) {
        return LinkGraphSortTerm {
            field,
            order: default_order_for_field(field),
        };
    }

    LinkGraphSortTerm::default()
}

fn build_optional_link_filter(
    seeds: &[String],
    negate: bool,
    recursive: bool,
    max_distance: Option<usize>,
) -> Option<LinkGraphLinkFilter> {
    if seeds.is_empty() {
        return None;
    }
    Some(LinkGraphLinkFilter {
        seeds: seeds.to_vec(),
        negate,
        recursive,
        max_distance,
    })
}

fn build_optional_related_filter(
    seeds: &[String],
    max_distance: Option<usize>,
    ppr: Option<LinkGraphRelatedPprOptions>,
) -> Option<LinkGraphRelatedFilter> {
    if seeds.is_empty() {
        return None;
    }
    Some(LinkGraphRelatedFilter {
        seeds: seeds.to_vec(),
        max_distance,
        ppr,
    })
}

fn build_optional_related_ppr_options(
    alpha: Option<f64>,
    max_iter: Option<usize>,
    tol: Option<f64>,
    subgraph_mode: Option<RelatedPprSubgraphModeArg>,
) -> Option<LinkGraphRelatedPprOptions> {
    if alpha.is_none() && max_iter.is_none() && tol.is_none() && subgraph_mode.is_none() {
        return None;
    }
    Some(LinkGraphRelatedPprOptions {
        alpha,
        max_iter,
        tol,
        subgraph_mode: subgraph_mode.map(Into::into),
    })
}

fn build_optional_tag_filter(
    all: &[String],
    any: &[String],
    not_tags: &[String],
) -> Option<LinkGraphTagFilter> {
    if all.is_empty() && any.is_empty() && not_tags.is_empty() {
        return None;
    }
    Some(LinkGraphTagFilter {
        all: all.to_vec(),
        any: any.to_vec(),
        not_tags: not_tags.to_vec(),
    })
}

fn build_index(cli: &Cli) -> Result<LinkGraphIndex> {
    let root_for_scope = if cli.root.is_absolute() {
        cli.root.clone()
    } else {
        std::env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join(&cli.root)
    };

    let runtime_scope = resolve_link_graph_index_runtime(&root_for_scope);
    let include_dirs = if cli.include_dirs.is_empty() {
        runtime_scope.include_dirs
    } else {
        cli.include_dirs.clone()
    };
    let exclude_dirs = if cli.exclude_dirs.is_empty() {
        runtime_scope.exclude_dirs
    } else {
        cli.exclude_dirs.clone()
    };

    LinkGraphIndex::build_with_cache(&cli.root, &include_dirs, &exclude_dirs)
        .map_err(anyhow::Error::msg)
}

fn emit<T: Serialize>(value: &T, output: OutputFormat) -> Result<()> {
    let rendered = match output {
        OutputFormat::Json => serde_json::to_string(value),
        OutputFormat::Pretty => serde_json::to_string_pretty(value),
    }
    .context("failed to serialize CLI output as JSON")?;
    println!("{rendered}");
    Ok(())
}

fn execute(cli: &Cli, index: Option<&LinkGraphIndex>) -> Result<()> {
    match &cli.command {
        Command::Search {
            query,
            limit,
            match_strategy,
            sort_terms,
            case_sensitive,
            include_paths,
            exclude_paths,
            tags_all,
            tags_any,
            tags_not,
            link_to,
            link_to_negate,
            link_to_recursive,
            link_to_max_distance,
            linked_by,
            linked_by_negate,
            linked_by_recursive,
            linked_by_max_distance,
            related,
            max_distance,
            related_ppr_alpha,
            related_ppr_max_iter,
            related_ppr_tol,
            related_ppr_subgraph_mode,
            mentions_of,
            mentioned_by_notes,
            orphan,
            tagless,
            missing_backlink,
            created_after,
            created_before,
            modified_after,
            modified_before,
        } => {
            let index = index.context("link_graph index is required for search command")?;
            let bounded = (*limit).max(1);
            let normalized_sort_terms: Vec<LinkGraphSortTerm> = if sort_terms.is_empty() {
                vec![LinkGraphSortTerm::default()]
            } else {
                sort_terms
                    .iter()
                    .map(|term| parse_sort_term(term))
                    .collect()
            };
            let related_ppr = build_optional_related_ppr_options(
                *related_ppr_alpha,
                *related_ppr_max_iter,
                *related_ppr_tol,
                *related_ppr_subgraph_mode,
            );

            let filters = LinkGraphSearchFilters {
                include_paths: include_paths.clone(),
                exclude_paths: exclude_paths.clone(),
                tags: build_optional_tag_filter(tags_all, tags_any, tags_not),
                link_to: build_optional_link_filter(
                    link_to,
                    *link_to_negate,
                    *link_to_recursive,
                    *link_to_max_distance,
                ),
                linked_by: build_optional_link_filter(
                    linked_by,
                    *linked_by_negate,
                    *linked_by_recursive,
                    *linked_by_max_distance,
                ),
                related: build_optional_related_filter(related, *max_distance, related_ppr),
                mentions_of: mentions_of.clone(),
                mentioned_by_notes: mentioned_by_notes.clone(),
                orphan: *orphan,
                tagless: *tagless,
                missing_backlink: *missing_backlink,
                ..LinkGraphSearchFilters::default()
            };
            let base_options = LinkGraphSearchOptions {
                match_strategy: LinkGraphMatchStrategy::from_alias(match_strategy),
                case_sensitive: *case_sensitive,
                sort_terms: normalized_sort_terms,
                filters,
                created_after: *created_after,
                created_before: *created_before,
                modified_after: *modified_after,
                modified_before: *modified_before,
            };
            let planned = index.search_planned_payload(query, bounded, base_options);
            let payload = json!({
                "query": planned.query,
                "limit": bounded,
                "match_strategy": planned.options.match_strategy,
                "sort_terms": planned.options.sort_terms,
                "case_sensitive": planned.options.case_sensitive,
                "filters": planned.options.filters,
                "created_after": planned.options.created_after,
                "created_before": planned.options.created_before,
                "modified_after": planned.options.modified_after,
                "modified_before": planned.options.modified_before,
                "total": planned.hit_count,
                "hits": planned.hits,
                "section_hit_count": planned.section_hit_count,
                "results": planned.results,
            });
            emit(&payload, cli.output)
        }
        Command::Stats => {
            let index = index.context("link_graph index is required for stats command")?;
            emit(&index.stats(), cli.output)
        }
        Command::Toc { limit } => {
            let index = index.context("link_graph index is required for toc command")?;
            emit(&index.toc((*limit).max(1)), cli.output)
        }
        Command::Neighbors {
            stem,
            direction,
            hops,
            limit,
        } => {
            let index = index.context("link_graph index is required for neighbors command")?;
            let payload = index.neighbors(
                stem,
                LinkGraphDirection::from_alias(direction),
                (*hops).max(1),
                (*limit).max(1),
            );
            emit(&payload, cli.output)
        }
        Command::Related {
            stem,
            max_distance,
            limit,
            verbose,
            ppr_alpha,
            ppr_max_iter,
            ppr_tol,
            ppr_subgraph_mode,
        } => {
            let index = index.context("link_graph index is required for related command")?;
            let ppr = build_optional_related_ppr_options(
                *ppr_alpha,
                *ppr_max_iter,
                *ppr_tol,
                *ppr_subgraph_mode,
            );
            let bounded_distance = (*max_distance).max(1);
            let bounded_limit = (*limit).max(1);
            if *verbose {
                let (results, diagnostics) = index.related_with_diagnostics(
                    stem,
                    bounded_distance,
                    bounded_limit,
                    ppr.as_ref(),
                );
                let payload = json!({
                    "stem": stem,
                    "max_distance": bounded_distance,
                    "limit": bounded_limit,
                    "ppr": ppr,
                    "diagnostics": diagnostics,
                    "total": results.len(),
                    "results": results,
                });
                emit(&payload, cli.output)
            } else {
                let payload =
                    index.related_with_options(stem, bounded_distance, bounded_limit, ppr.as_ref());
                emit(&payload, cli.output)
            }
        }
        Command::Metadata { stem } => {
            let index = index.context("link_graph index is required for metadata command")?;
            emit(&index.metadata(stem), cli.output)
        }
        Command::Saliency { command } => match command {
            SaliencyCommand::Get { node_id } => {
                let payload = valkey_saliency_get(node_id).map_err(anyhow::Error::msg)?;
                emit(&json!({"node_id": node_id, "state": payload}), cli.output)
            }
            SaliencyCommand::Touch {
                node_id,
                activation_delta,
                saliency_base,
                decay_rate,
                alpha,
                minimum_saliency,
                maximum_saliency,
                now_unix,
            } => {
                let state = valkey_saliency_touch(LinkGraphSaliencyTouchRequest {
                    node_id: node_id.clone(),
                    activation_delta: *activation_delta,
                    saliency_base: *saliency_base,
                    decay_rate: *decay_rate,
                    alpha: *alpha,
                    minimum_saliency: *minimum_saliency,
                    maximum_saliency: *maximum_saliency,
                    now_unix: *now_unix,
                })
                .map_err(anyhow::Error::msg)?;
                emit(&state, cli.output)
            }
        },
        Command::Hmas { command } => match command {
            HmasCommand::Validate { file } => {
                let report = validate_blackboard_file(file).map_err(anyhow::Error::msg)?;
                emit(&report, cli.output)
            }
        },
    }
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    if let Some(conf) = &cli.config_file {
        set_link_graph_wendao_config_override(conf.clone()).map_err(anyhow::Error::msg)?;
    }

    let needs_index = matches!(
        &cli.command,
        Command::Search { .. }
            | Command::Stats
            | Command::Toc { .. }
            | Command::Neighbors { .. }
            | Command::Related { .. }
            | Command::Metadata { .. }
    );
    if needs_index {
        let index = build_index(&cli)?;
        execute(&cli, Some(&index))
    } else {
        execute(&cli, None)
    }
}
