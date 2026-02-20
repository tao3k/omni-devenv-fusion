//! 3-in-1 memory gate: retain / obsolete / promote.
//!
//! This module provides a deterministic utility ledger and gate policy that
//! can be replayed for audits.

use serde::{Deserialize, Serialize};

use crate::Episode;

/// 3-in-1 gate verdict for memory lifecycle transitions.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MemoryGateVerdict {
    /// Keep the episode in short-term memory.
    Retain,
    /// Remove the episode from memory storage.
    Obsolete,
    /// Promote the episode to long-term knowledge workflows.
    Promote,
}

impl MemoryGateVerdict {
    /// String form used in contracts/logs.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Retain => "retain",
            Self::Obsolete => "obsolete",
            Self::Promote => "promote",
        }
    }
}

/// Lifecycle state used by gate events.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MemoryLifecycleState {
    /// Episode has been opened but not yet validated.
    Open,
    /// Episode is currently active in short-term memory.
    Active,
    /// Episode is cooling down pending more evidence.
    Cooling,
    /// Episode needs explicit revalidation before next transition.
    RevalidatePending,
    /// Episode was purged by gate policy.
    Purged,
    /// Episode was promoted by gate policy.
    Promoted,
}

impl MemoryLifecycleState {
    /// String form used in event payload fields.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Open => "open",
            Self::Active => "active",
            Self::Cooling => "cooling",
            Self::RevalidatePending => "revalidate_pending",
            Self::Purged => "purged",
            Self::Promoted => "promoted",
        }
    }
}

/// Evidence-based gate decision payload.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MemoryGateDecision {
    /// Final verdict.
    pub verdict: MemoryGateVerdict,
    /// Confidence score in [0, 1].
    pub confidence: f32,
    /// ReAct evidence references.
    pub react_evidence_refs: Vec<String>,
    /// Graph evidence references.
    pub graph_evidence_refs: Vec<String>,
    /// Omega factors and notes.
    pub omega_factors: Vec<String>,
    /// Audit reason.
    pub reason: String,
    /// Next action command.
    pub next_action: String,
}

/// Utility ledger that powers gate decisions.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MemoryUtilityLedger {
    /// ReAct re-validation score.
    pub react_revalidation_score: f32,
    /// Graph structural consistency score.
    pub graph_consistency_score: f32,
    /// Omega governance alignment score.
    pub omega_alignment_score: f32,
    /// TTL/frequency score.
    pub ttl_score: f32,
    /// Final weighted utility score.
    pub utility_score: f32,
    /// Current Q-value.
    pub q_value: f32,
    /// Observed usage count.
    pub usage_count: u32,
    /// Failure ratio in [0, 1].
    pub failure_rate: f32,
}

impl MemoryUtilityLedger {
    /// Build utility ledger from an episode and runtime evidence scores.
    #[must_use]
    #[allow(clippy::cast_precision_loss)]
    pub fn from_episode(
        episode: &Episode,
        react_revalidation_score: f32,
        graph_consistency_score: f32,
        omega_alignment_score: f32,
    ) -> Self {
        let usage_count = episode.total_uses();
        let success = episode.success_count as f32;
        let failure = episode.failure_count as f32;
        let failure_rate = if usage_count == 0 {
            if episode.outcome.eq_ignore_ascii_case("error") {
                1.0
            } else {
                0.0
            }
        } else {
            (failure / usage_count as f32).clamp(0.0, 1.0)
        };

        let q_value = episode.q_value.clamp(0.0, 1.0);
        let frequency_score = if usage_count == 0 {
            0.0
        } else {
            (usage_count as f32 / (usage_count as f32 + 3.0)).clamp(0.0, 1.0)
        };
        let stability_score = (1.0 - failure_rate).clamp(0.0, 1.0);
        let success_bias = ((success + 1.0) / (success + failure + 2.0)).clamp(0.0, 1.0);
        let ttl_score =
            (0.45 * frequency_score + 0.35 * stability_score + 0.20 * success_bias).clamp(0.0, 1.0);

        let react_score = react_revalidation_score.clamp(0.0, 1.0);
        let graph_score = graph_consistency_score.clamp(0.0, 1.0);
        let omega_score = omega_alignment_score.clamp(0.0, 1.0);
        let utility_score =
            (0.32 * react_score + 0.23 * graph_score + 0.25 * omega_score + 0.20 * q_value)
                .clamp(0.0, 1.0);

        Self {
            react_revalidation_score: react_score,
            graph_consistency_score: graph_score,
            omega_alignment_score: omega_score,
            ttl_score,
            utility_score,
            q_value,
            usage_count,
            failure_rate,
        }
    }
}

/// Deterministic policy thresholds for memory gate.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct MemoryGatePolicy {
    /// Minimum utility score for promotion.
    pub promote_threshold: f32,
    /// Maximum utility score for obsolescence.
    pub obsolete_threshold: f32,
    /// Minimum usage before promotion is allowed.
    pub promote_min_usage: u32,
    /// Minimum usage before obsolescence is allowed.
    pub obsolete_min_usage: u32,
    /// Failure-rate ceiling for promotion.
    pub promote_failure_rate_ceiling: f32,
    /// Failure-rate floor for obsolescence.
    pub obsolete_failure_rate_floor: f32,
    /// Minimum TTL score for promotion.
    pub promote_min_ttl_score: f32,
    /// Maximum TTL score for obsolescence.
    pub obsolete_max_ttl_score: f32,
}

impl Default for MemoryGatePolicy {
    fn default() -> Self {
        Self {
            promote_threshold: 0.78,
            obsolete_threshold: 0.32,
            promote_min_usage: 3,
            obsolete_min_usage: 2,
            promote_failure_rate_ceiling: 0.25,
            obsolete_failure_rate_floor: 0.70,
            promote_min_ttl_score: 0.50,
            obsolete_max_ttl_score: 0.45,
        }
    }
}

impl MemoryGatePolicy {
    /// Evaluate one utility ledger with explicit evidence references.
    #[must_use]
    pub fn evaluate(
        self,
        ledger: &MemoryUtilityLedger,
        react_evidence_refs: Vec<String>,
        graph_evidence_refs: Vec<String>,
        mut omega_factors: Vec<String>,
    ) -> MemoryGateDecision {
        omega_factors.push(format!("utility_score={:.3}", ledger.utility_score));
        omega_factors.push(format!("ttl_score={:.3}", ledger.ttl_score));
        omega_factors.push(format!("q_value={:.3}", ledger.q_value));
        omega_factors.push(format!("failure_rate={:.3}", ledger.failure_rate));
        omega_factors.push(format!("usage_count={}", ledger.usage_count));

        let verdict = if ledger.usage_count >= self.promote_min_usage
            && ledger.utility_score >= self.promote_threshold
            && ledger.failure_rate <= self.promote_failure_rate_ceiling
            && ledger.ttl_score >= self.promote_min_ttl_score
        {
            MemoryGateVerdict::Promote
        } else if ledger.usage_count >= self.obsolete_min_usage
            && ledger.utility_score <= self.obsolete_threshold
            && ledger.failure_rate >= self.obsolete_failure_rate_floor
            && ledger.ttl_score <= self.obsolete_max_ttl_score
        {
            MemoryGateVerdict::Obsolete
        } else {
            MemoryGateVerdict::Retain
        };

        let confidence = match verdict {
            MemoryGateVerdict::Promote => {
                let utility_margin = (ledger.utility_score - self.promote_threshold).max(0.0);
                let failure_margin =
                    (self.promote_failure_rate_ceiling - ledger.failure_rate).max(0.0);
                (0.55 + utility_margin * 1.8 + failure_margin * 0.8).clamp(0.0, 1.0)
            }
            MemoryGateVerdict::Obsolete => {
                let utility_margin = (self.obsolete_threshold - ledger.utility_score).max(0.0);
                let failure_margin =
                    (ledger.failure_rate - self.obsolete_failure_rate_floor).max(0.0);
                (0.55 + utility_margin * 1.8 + failure_margin * 0.8).clamp(0.0, 1.0)
            }
            MemoryGateVerdict::Retain => {
                let to_promote = (self.promote_threshold - ledger.utility_score).abs();
                let to_obsolete = (ledger.utility_score - self.obsolete_threshold).abs();
                (0.42 + to_promote.min(to_obsolete) * 0.6).clamp(0.0, 0.85)
            }
        };

        let reason = format!(
            "utility={:.3}, ttl={:.3}, uses={}, failure_rate={:.3}, react={:.3}, graph={:.3}, omega={:.3}",
            ledger.utility_score,
            ledger.ttl_score,
            ledger.usage_count,
            ledger.failure_rate,
            ledger.react_revalidation_score,
            ledger.graph_consistency_score,
            ledger.omega_alignment_score
        );

        MemoryGateDecision {
            verdict,
            confidence,
            react_evidence_refs,
            graph_evidence_refs,
            omega_factors,
            reason,
            next_action: verdict.as_str().to_string(),
        }
    }
}

/// Auditable gate-event payload aligned with `omni.memory.gate_event.v1`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MemoryGateEvent {
    /// Session identifier of the decision context.
    pub session_id: String,
    /// Monotonic turn identifier within the runtime.
    pub turn_id: u64,
    /// Memory episode id this decision targets.
    pub memory_id: String,
    /// Lifecycle state before decision.
    pub state_before: MemoryLifecycleState,
    /// Lifecycle state after decision.
    pub state_after: MemoryLifecycleState,
    /// TTL/frequency score used by the decision.
    pub ttl_score: f32,
    /// Full decision payload with evidence and verdict.
    pub decision: MemoryGateDecision,
}

impl MemoryGateEvent {
    /// Build a canonical gate event from one decision.
    #[must_use]
    pub fn from_decision(
        session_id: &str,
        turn_id: u64,
        memory_id: &str,
        ledger: &MemoryUtilityLedger,
        decision: MemoryGateDecision,
    ) -> Self {
        let state_before = MemoryLifecycleState::Active;
        let state_after = match decision.verdict {
            MemoryGateVerdict::Retain => MemoryLifecycleState::Active,
            MemoryGateVerdict::Obsolete => MemoryLifecycleState::Purged,
            MemoryGateVerdict::Promote => MemoryLifecycleState::Promoted,
        };

        Self {
            session_id: session_id.to_string(),
            turn_id,
            memory_id: memory_id.to_string(),
            state_before,
            state_after,
            ttl_score: ledger.ttl_score,
            decision,
        }
    }
}
