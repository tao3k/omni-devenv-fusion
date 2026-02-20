use serde_yaml::{Mapping, Value};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

pub(crate) const LINK_GRAPH_CACHE_VALKEY_URL_ENV: &str = "VALKEY_URL";
pub(crate) const LINK_GRAPH_VALKEY_KEY_PREFIX_ENV: &str =
    "XIUXIAN_WENDAO_LINK_GRAPH_VALKEY_KEY_PREFIX";
pub(crate) const LINK_GRAPH_VALKEY_TTL_SECONDS_ENV: &str =
    "XIUXIAN_WENDAO_LINK_GRAPH_VALKEY_TTL_SECONDS";
pub(crate) const DEFAULT_LINK_GRAPH_VALKEY_KEY_PREFIX: &str = "xiuxian_wendao:link_graph:index";

#[derive(Debug, Clone)]
pub(crate) struct LinkGraphCacheRuntimeConfig {
    pub valkey_url: String,
    pub key_prefix: String,
    pub ttl_seconds: Option<u64>,
}

impl LinkGraphCacheRuntimeConfig {
    pub(crate) fn from_parts(
        valkey_url: &str,
        key_prefix: Option<&str>,
        ttl_seconds: Option<u64>,
    ) -> Self {
        let resolved_url = valkey_url.trim().to_string();
        let resolved_prefix = key_prefix
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .unwrap_or(DEFAULT_LINK_GRAPH_VALKEY_KEY_PREFIX)
            .to_string();
        Self {
            valkey_url: resolved_url,
            key_prefix: resolved_prefix,
            ttl_seconds: ttl_seconds.filter(|value| *value > 0),
        }
    }
}

static PROJECT_ROOT_CACHE: OnceLock<PathBuf> = OnceLock::new();
static PRJ_CONFIG_HOME_OVERRIDE: OnceLock<PathBuf> = OnceLock::new();
static WENDAO_CONFIG_FILE_OVERRIDE: OnceLock<PathBuf> = OnceLock::new();

/// CLI/runtime override for config home (`$PRJ_CONFIG_HOME` equivalent).
///
/// Used by `wendao --cf <dir>` so Rust-side runtime and index scope resolve
/// against the same config directory as user-specified experiments.
pub fn set_link_graph_config_home_override(path: PathBuf) -> Result<(), String> {
    let normalized = if path.is_absolute() {
        path
    } else {
        std::env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join(path)
    };

    if let Some(existing) = PRJ_CONFIG_HOME_OVERRIDE.get() {
        if existing == &normalized {
            return Ok(());
        }
        return Err(format!(
            "link_graph config home override already set to '{}' (requested '{}')",
            existing.display(),
            normalized.display()
        ));
    }

    PRJ_CONFIG_HOME_OVERRIDE
        .set(normalized)
        .map_err(|_| "failed to set link_graph config home override".to_string())
}

/// CLI/runtime override for the exact wendao config file path.
///
/// Used by `wendao --conf <file>` for deterministic experiments where the
/// caller provides a concrete YAML file location.
pub fn set_link_graph_wendao_config_override(path: PathBuf) -> Result<(), String> {
    let normalized = if path.is_absolute() {
        path
    } else {
        std::env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join(path)
    };

    if let Some(existing) = WENDAO_CONFIG_FILE_OVERRIDE.get() {
        if existing == &normalized {
            return Ok(());
        }
        return Err(format!(
            "wendao config override already set to '{}' (requested '{}')",
            existing.display(),
            normalized.display()
        ));
    }

    WENDAO_CONFIG_FILE_OVERRIDE
        .set(normalized)
        .map_err(|_| "failed to set wendao config override".to_string())
}

fn parse_positive_u64(raw: &str) -> Option<u64> {
    raw.trim().parse::<u64>().ok().filter(|value| *value > 0)
}

fn first_non_empty(values: &[Option<String>]) -> Option<String> {
    values.iter().flatten().find_map(|value| {
        let trimmed = value.trim();
        if trimmed.is_empty() {
            None
        } else {
            Some(trimmed.to_string())
        }
    })
}

fn resolve_project_root_uncached() -> PathBuf {
    if let Ok(raw) = std::env::var("PRJ_ROOT") {
        let trimmed = raw.trim();
        if !trimmed.is_empty() {
            let path = PathBuf::from(trimmed);
            if path.is_absolute() {
                return path;
            }
            if let Ok(cwd) = std::env::current_dir() {
                return cwd.join(path);
            }
            return path;
        }
    }

    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let mut cursor = cwd.clone();
    loop {
        let marker = cursor.join(".git");
        if marker.exists() {
            return cursor;
        }
        match cursor.parent() {
            Some(parent) => cursor = parent.to_path_buf(),
            None => return cwd,
        }
    }
}

fn resolve_project_root() -> PathBuf {
    PROJECT_ROOT_CACHE
        .get_or_init(resolve_project_root_uncached)
        .clone()
}

fn resolve_prj_config_home(project_root: &Path) -> PathBuf {
    if let Some(override_path) = PRJ_CONFIG_HOME_OVERRIDE.get() {
        return override_path.clone();
    }

    if let Ok(raw) = std::env::var("PRJ_CONFIG_HOME") {
        let trimmed = raw.trim();
        if !trimmed.is_empty() {
            let path = PathBuf::from(trimmed);
            return if path.is_absolute() {
                path
            } else {
                project_root.join(path)
            };
        }
    }
    project_root.join(".config")
}

fn read_yaml_file(path: &Path) -> Option<Value> {
    let content = std::fs::read_to_string(path).ok()?;
    serde_yaml::from_str::<Value>(&content).ok()
}

fn deep_merge(base: &mut Value, overlay: Value) {
    match (base, overlay) {
        (Value::Mapping(base_map), Value::Mapping(overlay_map)) => {
            for (key, value) in overlay_map {
                if let Some(existing) = base_map.get_mut(&key) {
                    deep_merge(existing, value);
                } else {
                    base_map.insert(key, value);
                }
            }
        }
        (base_value, overlay_value) => {
            *base_value = overlay_value;
        }
    }
}

fn merged_wendao_settings() -> Value {
    let root = resolve_project_root();
    let system_path = root.join("packages/conf/wendao.yaml");
    let user_path = WENDAO_CONFIG_FILE_OVERRIDE
        .get()
        .cloned()
        .unwrap_or_else(|| resolve_prj_config_home(&root).join("omni-dev-fusion/wendao.yaml"));

    let mut merged = Value::Mapping(Mapping::new());
    if let Some(system) = read_yaml_file(&system_path) {
        deep_merge(&mut merged, system);
    }
    if let Some(user) = read_yaml_file(&user_path) {
        deep_merge(&mut merged, user);
    }
    merged
}

fn setting_value_to_string(value: &Value) -> Option<String> {
    match value {
        Value::String(value) => Some(value.clone()),
        Value::Number(number) => Some(number.to_string()),
        Value::Bool(flag) => Some(flag.to_string()),
        _ => None,
    }
}

fn setting_value_to_bool(value: &Value) -> Option<bool> {
    match value {
        Value::Bool(flag) => Some(*flag),
        Value::String(text) => match text.trim().to_lowercase().as_str() {
            "1" | "true" | "yes" | "on" => Some(true),
            "0" | "false" | "no" | "off" => Some(false),
            _ => None,
        },
        Value::Number(number) => number.as_i64().map(|v| v != 0),
        _ => None,
    }
}

fn get_setting_value<'a>(settings: &'a Value, dotted_key: &str) -> Option<&'a Value> {
    let mut cursor = settings;
    for segment in dotted_key.split('.') {
        match cursor {
            Value::Mapping(map) => {
                let key = Value::String(segment.to_string());
                cursor = map.get(&key)?;
            }
            _ => return None,
        }
    }
    Some(cursor)
}

fn get_setting_string(settings: &Value, dotted_key: &str) -> Option<String> {
    get_setting_value(settings, dotted_key).and_then(setting_value_to_string)
}

fn get_setting_bool(settings: &Value, dotted_key: &str) -> Option<bool> {
    get_setting_value(settings, dotted_key).and_then(setting_value_to_bool)
}

fn get_setting_string_list(settings: &Value, dotted_key: &str) -> Vec<String> {
    let Some(value) = get_setting_value(settings, dotted_key) else {
        return Vec::new();
    };
    match value {
        Value::String(single) => {
            let text = single.trim();
            if text.is_empty() {
                Vec::new()
            } else {
                vec![text.to_string()]
            }
        }
        Value::Sequence(items) => items
            .iter()
            .filter_map(setting_value_to_string)
            .map(|item| item.trim().to_string())
            .filter(|item| !item.is_empty())
            .collect(),
        _ => Vec::new(),
    }
}

fn normalize_relative_dir(value: &str) -> Option<String> {
    let normalized = value
        .trim()
        .replace('\\', "/")
        .trim_matches('/')
        .to_string();
    if normalized.is_empty() || normalized == "." {
        None
    } else {
        Some(normalized)
    }
}

fn dedup_dirs(entries: Vec<String>) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
    for entry in entries {
        let lowered = entry.to_lowercase();
        if seen.insert(lowered) {
            out.push(entry);
        }
    }
    out
}

#[derive(Debug, Clone, Default)]
pub struct LinkGraphIndexRuntimeConfig {
    pub include_dirs: Vec<String>,
    pub exclude_dirs: Vec<String>,
}

/// Resolve LinkGraph index scope from merged wendao settings.
///
/// Order:
/// 1) Explicit `link_graph.include_dirs`
/// 2) `link_graph.include_dirs_auto_candidates` when `include_dirs_auto=true`
///    and candidate directory exists under `root_dir`
/// 3) `link_graph.exclude_dirs` (non-hidden additions only)
pub fn resolve_link_graph_index_runtime(root_dir: &Path) -> LinkGraphIndexRuntimeConfig {
    let settings = merged_wendao_settings();

    let explicit_include = dedup_dirs(
        get_setting_string_list(&settings, "link_graph.include_dirs")
            .into_iter()
            .filter_map(|item| normalize_relative_dir(&item))
            .collect(),
    );

    let include_dirs = if explicit_include.is_empty()
        && get_setting_bool(&settings, "link_graph.include_dirs_auto").unwrap_or(true)
    {
        dedup_dirs(
            get_setting_string_list(&settings, "link_graph.include_dirs_auto_candidates")
                .into_iter()
                .filter_map(|item| normalize_relative_dir(&item))
                .filter(|candidate| root_dir.join(candidate).is_dir())
                .collect(),
        )
    } else {
        explicit_include
    };

    let exclude_dirs = dedup_dirs(
        get_setting_string_list(&settings, "link_graph.exclude_dirs")
            .into_iter()
            .filter_map(|item| normalize_relative_dir(&item))
            .filter(|value| !value.starts_with('.'))
            .collect(),
    );

    LinkGraphIndexRuntimeConfig {
        include_dirs,
        exclude_dirs,
    }
}

pub(crate) fn resolve_link_graph_cache_runtime() -> Result<LinkGraphCacheRuntimeConfig, String> {
    let settings = merged_wendao_settings();

    let valkey_url = first_non_empty(&[
        get_setting_string(&settings, "link_graph.cache.valkey_url"),
        std::env::var(LINK_GRAPH_CACHE_VALKEY_URL_ENV).ok(),
    ])
    .ok_or_else(|| {
        "link_graph cache valkey url is required (set VALKEY_URL or link_graph.cache.valkey_url)"
            .to_string()
    })?;

    let key_prefix = first_non_empty(&[
        get_setting_string(&settings, "link_graph.cache.key_prefix"),
        std::env::var(LINK_GRAPH_VALKEY_KEY_PREFIX_ENV).ok(),
        Some(DEFAULT_LINK_GRAPH_VALKEY_KEY_PREFIX.to_string()),
    ])
    .unwrap_or_else(|| DEFAULT_LINK_GRAPH_VALKEY_KEY_PREFIX.to_string());

    let ttl_raw = first_non_empty(&[
        get_setting_string(&settings, "link_graph.cache.ttl_seconds"),
        std::env::var(LINK_GRAPH_VALKEY_TTL_SECONDS_ENV).ok(),
    ]);
    let ttl_seconds = ttl_raw.as_deref().and_then(parse_positive_u64);

    Ok(LinkGraphCacheRuntimeConfig::from_parts(
        &valkey_url,
        Some(&key_prefix),
        ttl_seconds,
    ))
}
