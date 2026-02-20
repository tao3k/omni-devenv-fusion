//! Gateway namespace: HTTP and stdio entrypoints.

mod http;
mod stdio;

pub use http::{
    GatewayHealthResponse, GatewayMcpHealthResponse, GatewayState, MessageRequest, MessageResponse,
    router, run_http, validate_message_request,
};
pub use stdio::{DEFAULT_STDIO_SESSION_ID, run_stdio};
