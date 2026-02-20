#![allow(missing_docs)]

use axum::http::StatusCode;
use omni_agent::{MessageRequest, validate_message_request};

#[test]
fn validate_rejects_empty_session_id() {
    let body = MessageRequest {
        session_id: String::new(),
        message: "hi".to_string(),
    };
    let result = validate_message_request(&body);
    assert!(result.is_err());
    assert_eq!(result.expect_err("err").0, StatusCode::BAD_REQUEST);
}

#[test]
fn validate_rejects_empty_message() {
    let body = MessageRequest {
        session_id: "s1".to_string(),
        message: "  ".to_string(),
    };
    let result = validate_message_request(&body);
    assert!(result.is_err());
    assert_eq!(result.expect_err("err").0, StatusCode::BAD_REQUEST);
}

#[test]
fn validate_accepts_trimmed_values() {
    let body = MessageRequest {
        session_id: "  s1  ".to_string(),
        message: " hello ".to_string(),
    };
    let (session_id, message) = validate_message_request(&body).expect("ok");
    assert_eq!(session_id, "s1");
    assert_eq!(message, "hello");
}
