mod decision;
mod fallback;

pub(crate) use decision::{apply_policy_hint, decide_for_shortcut, decide_for_standard_turn};
pub(crate) use fallback::{ShortcutFallbackAction, resolve_shortcut_fallback};
