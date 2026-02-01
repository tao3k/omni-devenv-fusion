use omni_tui::components::{FoldablePanel, PanelCollection, PanelState};

#[test]
fn test_foldable_panel_toggle() {
    let mut panel = FoldablePanel::new("Test", "Content");

    assert_eq!(*panel.state(), PanelState::Folded);
    assert!(!panel.is_expanded());

    panel.toggle();
    assert_eq!(*panel.state(), PanelState::Expanded);
    assert!(panel.is_expanded());

    panel.toggle();
    assert_eq!(*panel.state(), PanelState::Folded);
}

#[test]
fn test_panel_collection() {
    let mut collection = PanelCollection::new();

    assert!(collection.is_empty());
    assert_eq!(collection.len(), 0);

    collection.add("Panel 1", "Content 1");
    collection.add("Panel 2", "Content 2");

    assert_eq!(collection.len(), 2);
    assert!(!collection.is_empty());
}
