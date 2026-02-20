#![allow(missing_docs)]

use omni_agent::summarise_drained_turns;

#[test]
fn summarise_drained_turns_intent_first_user() {
    let drained = vec![
        ("user".to_string(), "what is 2+2?".to_string(), 0),
        ("assistant".to_string(), "4".to_string(), 0),
    ];
    let (intent, experience, outcome) = summarise_drained_turns(&drained);
    assert_eq!(intent, "what is 2+2?");
    assert_eq!(experience, "4");
    assert_eq!(outcome, "completed");
}

#[test]
fn summarise_drained_turns_outcome_error() {
    let drained = vec![
        ("user".to_string(), "run tool".to_string(), 0),
        (
            "assistant".to_string(),
            "Error: connection failed".to_string(),
            1,
        ),
    ];
    let (_intent, _experience, outcome) = summarise_drained_turns(&drained);
    assert_eq!(outcome, "error");
}

#[test]
fn summarise_drained_turns_no_user_fallback() {
    let drained = vec![("assistant".to_string(), "ok".to_string(), 0)];
    let (intent, experience, outcome) = summarise_drained_turns(&drained);
    assert_eq!(intent, "(no user message)");
    assert_eq!(experience, "ok");
    assert_eq!(outcome, "completed");
}
