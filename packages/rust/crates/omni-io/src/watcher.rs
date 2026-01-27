//! Rust-Native File Watcher with Event Bus Integration
//!
//! Uses `notify` crate for cross-platform file system monitoring.
//! Publishes file events to the global `omni-events` EventBus for reactive architecture.

use std::path::Path;
use std::time::Duration;

use globset::{Glob, GlobSetBuilder};
use notify::{Config, Event, RecommendedWatcher, RecursiveMode, Watcher};
use tokio::sync::mpsc;

#[cfg(feature = "notify")]
use omni_events::{GLOBAL_BUS, OmniEvent, topics};

/// Configuration for file watcher
#[derive(Debug, Clone)]
pub struct WatcherConfig {
    /// Paths to watch
    pub paths: Vec<String>,
    /// File patterns to include (glob patterns)
    pub patterns: Vec<String>,
    /// File patterns to exclude
    pub exclude: Vec<String>,
    /// Debounce duration for rapid changes
    pub debounce_ms: u64,
    /// Whether to watch recursively
    pub recursive: bool,
}

impl Default for WatcherConfig {
    fn default() -> Self {
        Self {
            paths: vec![],
            patterns: vec!["**/*".to_string()],
            exclude: vec![
                "**/*.pyc".to_string(),
                "**/__pycache__/**".to_string(),
                "**/.git/**".to_string(),
                "**/*.tmp".to_string(),
            ],
            debounce_ms: 100,
            recursive: true,
        }
    }
}

/// File system event types matching notify crate
#[derive(Debug, Clone)]
pub enum FileEvent {
    Created { path: String, is_dir: bool },
    Modified { path: String },
    Deleted { path: String, is_dir: bool },
    Error { path: String, error: String },
}

/// Result from file watcher
pub type WatcherResult = (FileEvent, Option<OmniEvent>);

/// Handle to control the file watcher
#[derive(Clone)]
pub struct FileWatcherHandle {
    tx: mpsc::Sender<()>,
}

impl FileWatcherHandle {
    /// Stop the watcher
    pub async fn stop(&self) {
        let _ = self.tx.send(()).await;
    }
}

/// Convert notify event kind to topic
#[cfg(feature = "notify")]
fn event_to_topic(kind: &notify::EventKind) -> &'static str {
    match kind {
        notify::EventKind::Create(_) => topics::FILE_CREATED,
        notify::EventKind::Modify(_) => topics::FILE_CHANGED,
        notify::EventKind::Remove(_) => topics::FILE_DELETED,
        _ => topics::FILE_CHANGED,
    }
}

/// Check if path matches any pattern using high-performance GlobSet
fn matches_patterns(path: &Path, patterns: &[String], exclude: &[String]) -> bool {
    let path_str = path.to_string_lossy();

    // Build exclude set
    let exclude_set = if !exclude.is_empty() {
        let mut builder = GlobSetBuilder::new();
        for ex in exclude {
            if let Ok(glob) = Glob::new(ex) {
                builder.add(glob);
            }
        }
        Some(builder.build())
    } else {
        None
    };

    // Check exclude patterns first
    if let Some(Ok(set)) = exclude_set {
        if !set.matches(&*path_str).is_empty() {
            return false;
        }
    }

    // Build include set
    if !patterns.is_empty() {
        let mut builder = GlobSetBuilder::new();
        for pat in patterns {
            if let Ok(glob) = Glob::new(pat) {
                builder.add(glob);
            }
        }
        if let Ok(set) = builder.build() {
            return !set.matches(&*path_str).is_empty();
        }
    }

    patterns.is_empty()
}

/// Start a file watcher that publishes events to the global EventBus.
#[cfg(feature = "notify")]
pub async fn start_file_watcher<F>(
    config: WatcherConfig,
    callback: Option<F>,
) -> Result<FileWatcherHandle, Box<dyn std::error::Error>>
where
    F: Fn(WatcherResult) + Send + 'static,
{
    use std::collections::HashMap;
    use std::time::Instant;
    use tokio::sync::Mutex as TokioMutex;

    let (tx, mut rx) = mpsc::channel(1);

    // Debounce map - using tokio's async Mutex
    let debounce_map = std::sync::Arc::new(TokioMutex::new(HashMap::new()));
    let debounce_duration = Duration::from_millis(config.debounce_ms);

    // Create watcher
    let (watcher_tx, mut watcher_rx) = mpsc::channel(100);

    let mut watcher = RecommendedWatcher::new(
        move |result: Result<Event, notify::Error>| {
            let _ = watcher_tx.blocking_send(result);
        },
        Config::default().with_poll_interval(Duration::from_millis(50)),
    )?;

    // Add paths to watch
    for path in &config.paths {
        watcher.watch(
            Path::new(path),
            if config.recursive {
                RecursiveMode::Recursive
            } else {
                RecursiveMode::NonRecursive
            },
        )?;
    }

    // Clone config for the async task
    let patterns = config.patterns.clone();
    let exclude = config.exclude.clone();
    let cb = callback;

    // Spawn watcher task
    let _task = tokio::spawn(async move {
        // Keep watcher alive by moving it into this closure
        let _watcher = watcher;

        loop {
            tokio::select! {
                _ = rx.recv() => {
                    // Stop signal received
                    break;
                }
                result = watcher_rx.recv() => {
                    match result {
                        Some(Ok(event)) => {
                            // Get first path
                            let path = match event.paths.first() {
                                Some(p) => p,
                                None => continue,
                            };

                            // Filter by patterns
                            if !matches_patterns(path, &patterns, &exclude) {
                                continue;
                            }

                            // Check debounce - ONLY for Modify events
                            // Create and Remove should always pass through to avoid missing
                            // "Create then Write" sequences (common in editors/macOS)
                            let path_str = path.to_string_lossy().to_string();
                            let should_debounce = matches!(event.kind, notify::EventKind::Modify(_));

                            if should_debounce {
                                let mut debounce = debounce_map.lock().await;
                                let now = Instant::now();
                                if let Some(last) = debounce.get(&path_str) {
                                    if now.duration_since(*last) < debounce_duration {
                                        continue; // Skip debounced event
                                    }
                                }
                                debounce.insert(path_str.clone(), now);
                            }

                            // Convert to FileEvent
                            let file_event = match event.kind {
                                notify::EventKind::Create(_) => FileEvent::Created {
                                    path: path_str.clone(),
                                    is_dir: path.is_dir(),
                                },
                                notify::EventKind::Remove(_) => FileEvent::Deleted {
                                    path: path_str.clone(),
                                    is_dir: path.is_dir(),
                                },
                                _ => FileEvent::Modified { path: path_str.clone() },
                            };

                            // Create OmniEvent and publish to global bus
                            let topic = event_to_topic(&event.kind);
                            let payload = serde_json::json!({
                                "path": path_str,
                                "is_dir": path.is_dir(),
                                "event_type": format!("{:?}", event.kind),
                            });

                            let omni_event = OmniEvent::new("watcher", topic, payload);

                            // Publish to global bus
                            let _ = GLOBAL_BUS.publish(omni_event.clone());

                            // Call callback if provided
                            if let Some(ref cb) = cb {
                                cb((file_event, Some(omni_event)));
                            }
                        }
                        Some(Err(e)) => {
                            // Error from watcher
                            if let Some(ref cb) = cb {
                                cb((FileEvent::Error {
                                    path: String::new(),
                                    error: e.to_string(),
                                }, None));
                            }
                        }
                        None => {
                            // Channel closed
                            break;
                        }
                    }
                }
            }
        }
    });

    Ok(FileWatcherHandle { tx })
}

/// Start watching with default config
#[cfg(feature = "notify")]
pub async fn watch_path<P: AsRef<Path>>(
    path: P,
) -> Result<FileWatcherHandle, Box<dyn std::error::Error>> {
    let mut config = WatcherConfig::default();
    config.paths = vec![path.as_ref().to_string_lossy().to_string()];
    start_file_watcher::<fn(WatcherResult)>(config, None).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    #[tokio::test]
    async fn test_watcher_config() {
        let config = WatcherConfig::default();
        assert!(config.patterns.contains(&"**/*".to_string()));
        assert!(config.exclude.iter().any(|e| e.contains("*.pyc")));
    }

    #[tokio::test]
    async fn test_matches_patterns() {
        let patterns = vec!["**/*.rs".to_string(), "**/*.py".to_string()];
        let exclude = vec!["**/target/**".to_string()];

        // Match Rust file
        assert!(matches_patterns(
            Path::new("src/main.rs"),
            &patterns,
            &exclude
        ));

        // Match Python file
        assert!(matches_patterns(
            Path::new("script.py"),
            &patterns,
            &exclude
        ));

        // Exclude target directory
        assert!(!matches_patterns(
            Path::new("target/debug/main"),
            &patterns,
            &exclude
        ));

        // Exclude non-matching extension
        assert!(!matches_patterns(
            Path::new("data.json"),
            &patterns,
            &exclude
        ));
    }
}
