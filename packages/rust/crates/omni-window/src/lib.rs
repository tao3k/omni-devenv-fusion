//! omni-window: high-performance session window for 1k–10k turns.
//!
//! Ring-buffer of turn metadata for context building without holding full history in memory.
//! Python can use this via `PyO3` when feature "pybindings" is enabled.

mod turn_slot;
mod window;

pub use turn_slot::TurnSlot;
pub use window::SessionWindow;

#[cfg(feature = "pybindings")]
mod pymodule_impl;

#[cfg(feature = "pybindings")]
pub use pymodule_impl::PySessionWindow;
