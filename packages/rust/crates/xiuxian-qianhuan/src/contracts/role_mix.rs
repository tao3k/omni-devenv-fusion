use serde::{Deserialize, Serialize};

/// Weighted role item in a role-mix profile.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RoleMixRole {
    /// Stable role identifier.
    pub role: String,
    /// Relative role weight.
    pub weight: f32,
}

/// Role-mix profile carried by an injection snapshot.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RoleMixProfile {
    /// Profile identifier for observability/replay.
    pub profile_id: String,
    /// Ordered role list used for this turn.
    pub roles: Vec<RoleMixRole>,
    /// Why this profile was selected.
    pub rationale: String,
}
