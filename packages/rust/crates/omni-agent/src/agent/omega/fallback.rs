use crate::contracts::{OmegaDecision, OmegaFallbackPolicy};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ShortcutFallbackAction {
    Abort,
    RetryBridgeWithoutMetadata,
    RouteToReact,
}

impl ShortcutFallbackAction {
    pub(crate) const fn as_str(self) -> &'static str {
        match self {
            Self::Abort => "abort",
            Self::RetryBridgeWithoutMetadata => "retry_bridge_without_metadata",
            Self::RouteToReact => "route_to_react",
        }
    }
}

pub(crate) fn resolve_shortcut_fallback(
    decision: &OmegaDecision,
    attempt: u8,
) -> ShortcutFallbackAction {
    if attempt > 0 {
        return ShortcutFallbackAction::Abort;
    }

    match decision.fallback_policy {
        OmegaFallbackPolicy::Abort => ShortcutFallbackAction::Abort,
        OmegaFallbackPolicy::SwitchToGraph => ShortcutFallbackAction::RetryBridgeWithoutMetadata,
        OmegaFallbackPolicy::RetryReact => ShortcutFallbackAction::RouteToReact,
    }
}
