//! Unit tests for stdio gateway: constants and wiring (no stdin loop).

use omni_agent::DEFAULT_STDIO_SESSION_ID;

#[test]
fn default_stdio_session_id() {
    assert_eq!(DEFAULT_STDIO_SESSION_ID, "default");
}

#[test]
fn gateway_exports_run_stdio() {
    // Compile-time check that run_stdio is in the public API.
    let _ = omni_agent::run_stdio;
}
