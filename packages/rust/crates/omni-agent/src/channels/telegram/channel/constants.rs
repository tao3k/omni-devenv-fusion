/// Telegram's maximum message length for text messages.
#[doc(hidden)]
pub const TELEGRAM_MAX_MESSAGE_LENGTH: usize = 4096;

pub(super) const TELEGRAM_DEFAULT_API_BASE: &str = "https://api.telegram.org";
pub(super) const TELEGRAM_POLL_RETRY_SECS: u64 = 5;
pub(super) const TELEGRAM_POLL_CONFLICT_RETRY_SECS: u64 = 2;
pub(super) const TELEGRAM_POLL_DEFAULT_RATE_LIMIT_RETRY_SECS: u64 = 1;
pub(super) const TELEGRAM_POLL_MAX_RATE_LIMIT_RETRY_SECS: u64 = 60;
pub(super) const TELEGRAM_HTTP_CONNECT_TIMEOUT_SECS: u64 = 10;
pub(super) const TELEGRAM_HTTP_REQUEST_TIMEOUT_SECS: u64 = 30;
pub(super) const TELEGRAM_SEND_MAX_RETRIES: usize = 2;
pub(super) const TELEGRAM_SEND_RETRY_BASE_MS: u64 = 200;
pub(super) const TELEGRAM_SEND_RETRY_MAX_MS: u64 = 2_000;
pub(super) const TELEGRAM_SEND_RATE_LIMIT_SPREAD_STEP_MS: u64 = 50;
pub(super) const TELEGRAM_SEND_RATE_LIMIT_SPREAD_MAX_MS: u64 = 500;
pub(super) const TELEGRAM_MEDIA_GROUP_MAX_ITEMS: usize = 10;
pub(super) const TELEGRAM_MAX_CAPTION_LENGTH: usize = 1024;

pub(super) const CHUNK_CONTINUED_PREFIX: &str = "(continued)\n\n";
pub(super) const CHUNK_CONTINUES_SUFFIX: &str = "\n\n(continues...)";
