use super::shared::parse_background_prompt as parse_background_prompt_shared;

/// Parse background command forms:
/// - `/bg <prompt>`
/// - `bg <prompt>`
/// - `/research <prompt>`
/// - `research <prompt>` (auto-background because this skill is typically long-running)
pub fn parse_background_prompt(input: &str) -> Option<String> {
    parse_background_prompt_shared(input)
}
