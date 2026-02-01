//! TUI Components - Foldable panels and UI elements

mod collection;
mod layout;
mod panel;
mod tui_app;

pub use collection::{PanelCollection, PanelLayout};
pub use layout::AppLayout;
pub use panel::{FOLDED_HEIGHT, FoldablePanel, MAX_EXPANDED_HEIGHT, PanelState};
pub use tui_app::TuiApp;
