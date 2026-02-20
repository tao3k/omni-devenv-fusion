#![allow(missing_docs)]

use omni_agent::{markdown_to_telegram_html, markdown_to_telegram_markdown_v2};

fn normalize(rendered: &str) -> String {
    rendered.trim_end_matches('\n').to_string()
}

#[test]
fn markdown_renderer_escapes_plain_reserved_characters() {
    let rendered = markdown_to_telegram_markdown_v2("A_B*C! #+-=|{}.");
    assert_eq!(
        normalize(&rendered),
        "A\\_B\\*C\\! \\#\\+\\-\\=\\|\\{\\}\\."
    );
}

#[test]
fn markdown_renderer_converts_emphasis_and_strong() {
    let rendered = markdown_to_telegram_markdown_v2("**Bold** and *italic*");
    assert_eq!(normalize(&rendered), "*Bold* and _italic_");
}

#[test]
fn markdown_renderer_formats_ordered_and_task_lists() {
    let rendered =
        markdown_to_telegram_markdown_v2("1. first\n2. second\n\n- [x] done\n- [ ] todo");
    let rendered = normalize(&rendered);

    assert!(rendered.contains("1\\. first"));
    assert!(rendered.contains("2\\. second"));
    assert!(rendered.contains("\\[x\\]"));
    assert!(rendered.contains("\\[ \\]"));
}

#[test]
fn markdown_renderer_escapes_link_url_and_preserves_inline_code() {
    let rendered = markdown_to_telegram_markdown_v2("[doc](https://example.com/a(b)) and `a_b`");
    let rendered = normalize(&rendered);

    assert!(rendered.contains("[doc](https://example.com/a(b\\))"));
    assert!(rendered.contains("`a_b`"));
}

#[test]
fn markdown_renderer_keeps_non_ascii_text_intact() {
    let rendered = markdown_to_telegram_markdown_v2("中文段落：*强调*");
    assert_eq!(normalize(&rendered), "中文段落：_强调_");
}

#[test]
fn markdown_renderer_keeps_code_block_symbols_unescaped() {
    let rendered = markdown_to_telegram_markdown_v2("```\nlet value = a_b * 2;\n```");
    let rendered = normalize(&rendered);

    assert!(rendered.contains("```\nlet value = a_b * 2;\n```"));
    assert!(
        !rendered.contains("a\\_b"),
        "code block content should not be text-escaped"
    );
}

#[test]
fn markdown_renderer_preserves_fenced_code_language_identifier() {
    let rendered = markdown_to_telegram_markdown_v2("```Rust\nlet value = a_b * 2;\n```");
    assert_eq!(rendered, "```rust\nlet value = a_b * 2;\n```");
}

#[test]
fn markdown_renderer_drops_unsupported_fenced_code_language_identifier() {
    let rendered = markdown_to_telegram_markdown_v2("```foo/bar\nlet value = 1;\n```");
    assert_eq!(rendered, "```\nlet value = 1;\n```");
}

#[test]
fn markdown_renderer_extracts_fenced_code_language_from_extended_info_string() {
    let rendered =
        markdown_to_telegram_markdown_v2("```Rust {.numberLines}\nlet value = a_b * 2;\n```");
    assert_eq!(rendered, "```rust\nlet value = a_b * 2;\n```");
}

#[test]
fn markdown_renderer_keeps_cjk_fullwidth_punctuation_inside_fenced_code_block() {
    let rendered =
        markdown_to_telegram_markdown_v2("```Python\n标题：交易说明\nprint(\"买入：BTC\")\n```");
    assert_eq!(
        rendered,
        "```python\n标题：交易说明\nprint(\"买入：BTC\")\n```"
    );
}

#[test]
fn markdown_renderer_preserves_large_multibyte_fenced_code_block_without_truncation() {
    let code_line = "说明：value = a_b * 2";
    let code_body = (0..512).map(|_| code_line).collect::<Vec<_>>().join("\n");
    let markdown = format!("```text\n{code_body}\n```");

    let rendered = markdown_to_telegram_markdown_v2(&markdown);

    assert!(rendered.starts_with("```text\n"));
    assert!(rendered.ends_with("\n```"));
    let rendered_body = rendered
        .trim_start_matches("```text\n")
        .trim_end_matches("\n```");
    assert_eq!(rendered_body, code_body);
}

#[test]
fn markdown_renderer_does_not_append_trailing_newline_for_plain_paragraph() {
    let rendered = markdown_to_telegram_markdown_v2("summary");
    assert_eq!(rendered, "summary");
}

#[test]
fn markdown_renderer_does_not_append_trailing_newline_for_code_block_only() {
    let rendered = markdown_to_telegram_markdown_v2("```\nlet value = 1;\n```");
    assert!(
        !rendered.ends_with('\n'),
        "rendered output should not end with trailing newline"
    );
    assert_eq!(rendered, "```\nlet value = 1;\n```");
}

#[test]
fn html_renderer_converts_markdown_to_telegram_supported_tags() {
    let rendered = markdown_to_telegram_html("## Title\n\n**Bold** *italic* `code`");
    let rendered = normalize(&rendered);

    assert!(rendered.contains("<b>Title</b>"));
    assert!(rendered.contains("<b>Bold</b>"));
    assert!(rendered.contains("<i>italic</i>"));
    assert!(rendered.contains("<code>code</code>"));
}

#[test]
fn html_renderer_escapes_html_sensitive_characters() {
    let rendered = markdown_to_telegram_html("<raw> & value");
    let rendered = normalize(&rendered);
    assert_eq!(rendered, "&lt;raw&gt; &amp; value");
}

#[test]
fn html_renderer_keeps_cjk_fullwidth_punctuation_in_code_block() {
    let rendered =
        markdown_to_telegram_html("```Python\n标题：交易说明\nprint(\"买入：BTC\")\n```");
    let rendered = normalize(&rendered);

    assert!(rendered.contains("标题：交易说明"));
    assert!(rendered.contains("print(\"买入：BTC\")"));
    assert!(rendered.contains("<pre><code>"));
    assert!(rendered.contains("</code></pre>"));
}
