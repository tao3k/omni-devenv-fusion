use serde::{Deserialize, Serialize};

/// Namespace-scoped schema version for LinkGraph saliency persistence.
pub const LINK_GRAPH_SALIENCY_SCHEMA_VERSION: &str = "xiuxian_wendao.link_graph.saliency.v1";

/// Default frontmatter/in-memory saliency base when not explicitly configured.
pub const DEFAULT_SALIENCY_BASE: f64 = 5.0;
/// Default frontmatter/in-memory saliency decay rate when not explicitly configured.
pub const DEFAULT_DECAY_RATE: f64 = 0.05;

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LinkGraphSaliencyPolicy {
    pub alpha: f64,
    pub minimum: f64,
    pub maximum: f64,
}

impl Default for LinkGraphSaliencyPolicy {
    fn default() -> Self {
        Self {
            alpha: 0.5,
            minimum: 1.0,
            maximum: 10.0,
        }
    }
}

impl LinkGraphSaliencyPolicy {
    #[must_use]
    pub fn normalized(self) -> Self {
        let alpha = if self.alpha.is_finite() {
            self.alpha.max(0.0)
        } else {
            Self::default().alpha
        };
        let minimum = if self.minimum.is_finite() {
            self.minimum
        } else {
            Self::default().minimum
        };
        let maximum_raw = if self.maximum.is_finite() {
            self.maximum
        } else {
            Self::default().maximum
        };
        let maximum = if maximum_raw >= minimum {
            maximum_raw
        } else {
            minimum
        };
        Self {
            alpha,
            minimum,
            maximum,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LinkGraphSaliencyState {
    pub schema: String,
    pub node_id: String,
    pub saliency_base: f64,
    pub decay_rate: f64,
    /// Historical touch count (observability only). The online score update uses
    /// per-touch delta and settles new saliency as the next baseline.
    pub activation_count: u64,
    pub last_accessed_unix: i64,
    pub current_saliency: f64,
    pub updated_at_unix: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LinkGraphSaliencyTouchRequest {
    pub node_id: String,
    #[serde(default)]
    pub activation_delta: u64,
    #[serde(default)]
    pub saliency_base: Option<f64>,
    #[serde(default)]
    pub decay_rate: Option<f64>,
    #[serde(default)]
    pub alpha: Option<f64>,
    #[serde(default)]
    pub minimum_saliency: Option<f64>,
    #[serde(default)]
    pub maximum_saliency: Option<f64>,
    #[serde(default)]
    pub now_unix: Option<i64>,
}

impl Default for LinkGraphSaliencyTouchRequest {
    fn default() -> Self {
        Self {
            node_id: String::new(),
            activation_delta: 1,
            saliency_base: None,
            decay_rate: None,
            alpha: None,
            minimum_saliency: None,
            maximum_saliency: None,
            now_unix: None,
        }
    }
}
