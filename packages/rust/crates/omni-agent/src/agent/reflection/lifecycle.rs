use std::fmt;

use serde::{Deserialize, Serialize};

/// Explicit reflection lifecycle stages.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReflectiveRuntimeStage {
    Diagnose,
    Plan,
    Apply,
}

impl ReflectiveRuntimeStage {
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Diagnose => "diagnose",
            Self::Plan => "plan",
            Self::Apply => "apply",
        }
    }
}

/// Explicit runtime error for illegal reflection lifecycle transitions.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ReflectiveRuntimeError {
    pub from: Option<ReflectiveRuntimeStage>,
    pub to: ReflectiveRuntimeStage,
}

impl fmt::Display for ReflectiveRuntimeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let from = self.from.map_or("none", ReflectiveRuntimeStage::as_str);
        write!(
            f,
            "illegal reflection lifecycle transition: {from} -> {}",
            self.to.as_str()
        )
    }
}

impl std::error::Error for ReflectiveRuntimeError {}

/// Runtime lifecycle guard for reflection.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct ReflectiveRuntime {
    stage: Option<ReflectiveRuntimeStage>,
}

impl ReflectiveRuntime {
    #[allow(dead_code)]
    #[must_use]
    pub const fn stage(self) -> Option<ReflectiveRuntimeStage> {
        self.stage
    }

    pub fn transition(
        &mut self,
        next: ReflectiveRuntimeStage,
    ) -> Result<(), ReflectiveRuntimeError> {
        let valid = matches!(
            (self.stage, next),
            (None, ReflectiveRuntimeStage::Diagnose)
                | (
                    Some(ReflectiveRuntimeStage::Diagnose),
                    ReflectiveRuntimeStage::Plan
                )
                | (
                    Some(ReflectiveRuntimeStage::Plan),
                    ReflectiveRuntimeStage::Apply
                )
        );
        if !valid {
            return Err(ReflectiveRuntimeError {
                from: self.stage,
                to: next,
            });
        }
        self.stage = Some(next);
        Ok(())
    }
}
