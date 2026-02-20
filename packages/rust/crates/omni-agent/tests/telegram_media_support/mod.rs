#![allow(dead_code)]

mod bootstrap;
mod media_api;
mod upload_api;

#[allow(unused_imports)]
pub use media_api::{
    MediaCall, MockTelegramMediaState, spawn_mock_telegram_media_api,
    spawn_mock_telegram_media_api_with_group_failure,
    spawn_mock_telegram_media_api_with_group_failure_and_markdown_error,
    spawn_mock_telegram_media_api_with_markdown_error,
};
#[allow(unused_imports)]
pub use upload_api::{
    MockTelegramUploadState, UploadCall, spawn_mock_telegram_media_group_upload_api,
    spawn_mock_telegram_upload_api, spawn_mock_telegram_upload_api_with_markdown_error,
};
