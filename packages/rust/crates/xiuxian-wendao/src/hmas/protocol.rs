use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum HmasRecordKind {
    Task,
    Evidence,
    Conclusion,
    DigitalThread,
}

impl HmasRecordKind {
    #[must_use]
    pub fn from_header(raw: &str) -> Option<Self> {
        let trimmed = raw.trim();
        let open = trimmed.find('[')?;
        let close = trimmed[open + 1..].find(']')? + open + 1;
        Self::from_label(trimmed[open + 1..close].trim())
    }

    #[must_use]
    pub fn from_heading_text(raw: &str) -> Option<Self> {
        Self::from_header(raw)
    }

    #[must_use]
    pub fn from_fence_tag(raw: &str) -> Option<Self> {
        let normalized = raw
            .trim()
            .to_uppercase()
            .replace('-', "_")
            .replace(' ', "_");
        match normalized.as_str() {
            "HMAS_TASK" => Some(Self::Task),
            "HMAS_EVIDENCE" => Some(Self::Evidence),
            "HMAS_CONCLUSION" => Some(Self::Conclusion),
            "HMAS_DIGITAL_THREAD" => Some(Self::DigitalThread),
            _ => None,
        }
    }

    fn from_label(raw: &str) -> Option<Self> {
        let label = raw
            .trim()
            .to_uppercase()
            .replace('-', "_")
            .replace(' ', "_");
        match label.as_str() {
            "TASK" => Some(Self::Task),
            "EVIDENCE" => Some(Self::Evidence),
            "CONCLUSION" => Some(Self::Conclusion),
            "DIGITAL_THREAD" => Some(Self::DigitalThread),
            _ => None,
        }
    }

    #[must_use]
    pub const fn as_code(self) -> &'static str {
        match self {
            Self::Task => "task",
            Self::Evidence => "evidence",
            Self::Conclusion => "conclusion",
            Self::DigitalThread => "digital_thread",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HmasSourceNode {
    pub node_id: String,
    #[serde(default)]
    pub saliency_at_time: Option<f64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HmasTaskPayload {
    pub requirement_id: String,
    pub objective: String,
    #[serde(default)]
    pub hard_constraints: Vec<String>,
    #[serde(default)]
    pub assigned_to: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HmasEvidencePayload {
    pub requirement_id: String,
    pub evidence: String,
    #[serde(default)]
    pub source_nodes_accessed: Vec<HmasSourceNode>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HmasConclusionPayload {
    pub requirement_id: String,
    pub summary: String,
    pub confidence_score: f64,
    #[serde(default)]
    pub hard_constraints_checked: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HmasDigitalThreadPayload {
    pub requirement_id: String,
    pub source_nodes_accessed: Vec<HmasSourceNode>,
    pub hard_constraints_checked: Vec<String>,
    pub confidence_score: f64,
}
