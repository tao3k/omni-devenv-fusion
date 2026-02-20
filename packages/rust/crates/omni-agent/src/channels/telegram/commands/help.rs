use super::session::SessionOutputFormat;
use super::shared::parse_help_command as parse_help_command_shared;

/// Parse help command:
/// - `/help` / `help`
/// - `/help json`
/// - `/slash help` / `slash help`
/// - `/slash help json`
/// - `/commands` / `/commands json`
pub fn parse_help_command(input: &str) -> Option<SessionOutputFormat> {
    parse_help_command_shared(input)
}
