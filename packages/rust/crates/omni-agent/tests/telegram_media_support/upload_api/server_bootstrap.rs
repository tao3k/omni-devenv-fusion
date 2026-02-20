use anyhow::Result;
use axum::{Router, routing::post};

use super::super::bootstrap::spawn_test_server;
use super::{
    MockTelegramUploadState, media_group::handle_upload_media_group, photo::handle_upload_photo,
};

pub(super) async fn spawn_upload_photo_server(
    state: MockTelegramUploadState,
) -> Result<Option<(String, MockTelegramUploadState, tokio::task::JoinHandle<()>)>> {
    let app = Router::new()
        .route("/botfake-token/sendPhoto", post(handle_upload_photo))
        .with_state(state.clone());
    spawn_test_server(
        app,
        state,
        "skipping telegram upload tests: local socket bind is not permitted",
    )
    .await
}

pub(super) async fn spawn_upload_media_group_server(
    state: MockTelegramUploadState,
) -> Result<Option<(String, MockTelegramUploadState, tokio::task::JoinHandle<()>)>> {
    let app = Router::new()
        .route(
            "/botfake-token/sendMediaGroup",
            post(handle_upload_media_group),
        )
        .with_state(state.clone());
    spawn_test_server(
        app,
        state,
        "skipping telegram media-group upload tests: local socket bind is not permitted",
    )
    .await
}
