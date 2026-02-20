use anyhow::Result;
use axum::{Router, routing::post};

use super::super::bootstrap::spawn_test_server;
use super::{MockTelegramMediaState, routing::handle_method};

pub(super) async fn spawn_media_api_server(
    state: MockTelegramMediaState,
) -> Result<Option<(String, MockTelegramMediaState, tokio::task::JoinHandle<()>)>> {
    let app = Router::new()
        .route("/botfake-token/{method}", post(handle_method))
        .with_state(state.clone());
    spawn_test_server(
        app,
        state,
        "skipping telegram media tests: local socket bind is not permitted",
    )
    .await
}
