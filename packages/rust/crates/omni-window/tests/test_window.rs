//! Integration tests for SessionWindow.

use omni_window::SessionWindow;

#[test]
fn test_append_and_get_recent() {
    let mut w = SessionWindow::new("s1", 10);
    w.append_turn("user", "hello", 0, None);
    w.append_turn("assistant", "hi", 1, None);
    let recent = w.get_recent_turns(5);
    assert_eq!(recent.len(), 2);
    assert_eq!(recent[0].role, "user");
    assert_eq!(recent[0].content, "hello");
    assert_eq!(recent[1].tool_count, 1);
}

#[test]
fn test_get_stats() {
    let mut w = SessionWindow::new("s1", 100);
    w.append_turn("user", "a", 0, None);
    w.append_turn("assistant", "b", 2, None);
    let (total_turns, total_tool_calls, window_used) = w.get_stats();
    assert_eq!(total_turns, 2);
    assert_eq!(total_tool_calls, 2);
    assert_eq!(window_used, 2);
}

#[test]
fn test_max_turns_trim() {
    let mut w = SessionWindow::new("s1", 3);
    for i in 0..5 {
        w.append_turn("user", &i.to_string(), 0, None);
    }
    let (total_turns, _, _) = w.get_stats();
    assert_eq!(total_turns, 3);
    let recent = w.get_recent_turns(10);
    assert_eq!(recent.len(), 3);
    assert_eq!(recent[0].content, "2");
}
