const LOG_PREVIEW_LEN: usize = 80;

pub(super) fn log_preview(s: &str) -> String {
    let one_line: String = s.chars().map(|c| if c == '\n' { ' ' } else { c }).collect();
    if one_line.chars().count() > LOG_PREVIEW_LEN {
        format!(
            "{}...",
            one_line
                .chars()
                .take(LOG_PREVIEW_LEN)
                .collect::<String>()
                .trim_end()
        )
    } else {
        one_line
    }
}
