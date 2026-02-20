use pulldown_cmark::{CodeBlockKind, Event, Options, Parser, Tag, TagEnd};

pub fn markdown_to_telegram_markdown_v2(markdown: &str) -> String {
    let mut options = Options::empty();
    options.insert(Options::ENABLE_STRIKETHROUGH);
    options.insert(Options::ENABLE_TABLES);
    options.insert(Options::ENABLE_TASKLISTS);

    let parser = Parser::new_ext(markdown, options);
    let mut rendered = String::new();
    let mut ordered_list_stack: Vec<usize> = Vec::new();
    let mut list_is_ordered_stack: Vec<bool> = Vec::new();
    let mut link_stack: Vec<String> = Vec::new();
    let mut in_code_block = false;

    for event in parser {
        match event {
            Event::Start(tag) => match tag {
                Tag::Strong => rendered.push('*'),
                Tag::Emphasis => rendered.push('_'),
                Tag::Strikethrough => rendered.push('~'),
                Tag::CodeBlock(kind) => {
                    in_code_block = true;
                    rendered.push_str("```");
                    if let Some(language) = normalize_code_fence_language(kind) {
                        rendered.push_str(&language);
                    }
                    rendered.push('\n');
                }
                Tag::Link { dest_url, .. } => {
                    rendered.push('[');
                    link_stack.push(dest_url.into_string());
                }
                Tag::Heading { .. } => rendered.push('*'),
                Tag::List(start) => {
                    if let Some(start_number) = start {
                        ordered_list_stack.push(start_number as usize);
                        list_is_ordered_stack.push(true);
                    } else {
                        ordered_list_stack.push(1);
                        list_is_ordered_stack.push(false);
                    }
                }
                Tag::Item => {
                    if !rendered.is_empty() && !rendered.ends_with('\n') {
                        rendered.push('\n');
                    }
                    match list_is_ordered_stack.last().copied() {
                        Some(true) => {
                            if let Some(current) = ordered_list_stack.last_mut() {
                                rendered.push_str(&format!("{current}\\. "));
                                *current += 1;
                            } else {
                                rendered.push_str("• ");
                            }
                        }
                        _ => rendered.push_str("• "),
                    }
                }
                Tag::BlockQuote(_) => rendered.push_str("> "),
                _ => {}
            },
            Event::End(tag_end) => match tag_end {
                TagEnd::Strong => rendered.push('*'),
                TagEnd::Emphasis => rendered.push('_'),
                TagEnd::Strikethrough => rendered.push('~'),
                TagEnd::CodeBlock => {
                    in_code_block = false;
                    if !rendered.ends_with('\n') {
                        rendered.push('\n');
                    }
                    rendered.push_str("```\n\n");
                }
                TagEnd::Link => {
                    let link_target = link_stack.pop().unwrap_or_default();
                    rendered.push(']');
                    rendered.push('(');
                    rendered.push_str(&escape_markdown_v2_url(&link_target));
                    rendered.push(')');
                }
                TagEnd::Heading(_) => rendered.push_str("*\n\n"),
                TagEnd::Paragraph => rendered.push_str("\n\n"),
                TagEnd::List(_) => {
                    ordered_list_stack.pop();
                    list_is_ordered_stack.pop();
                    rendered.push('\n');
                }
                _ => {}
            },
            Event::Text(text) => {
                if in_code_block {
                    rendered.push_str(&escape_markdown_v2_code(text.as_ref()));
                } else {
                    rendered.push_str(&escape_markdown_v2_text(text.as_ref()));
                }
            }
            Event::Code(text) => {
                rendered.push('`');
                rendered.push_str(&escape_markdown_v2_code(text.as_ref()));
                rendered.push('`');
            }
            Event::SoftBreak | Event::HardBreak => rendered.push('\n'),
            Event::Rule => rendered.push_str("\n\\-\\-\\-\\-\n"),
            Event::Html(text) | Event::InlineHtml(text) => {
                rendered.push_str(&escape_markdown_v2_text(text.as_ref()));
            }
            Event::TaskListMarker(checked) => {
                if checked {
                    rendered.push_str("\\[x\\] ");
                } else {
                    rendered.push_str("\\[ \\] ");
                }
            }
            Event::FootnoteReference(name) => {
                rendered.push_str("\\[");
                rendered.push_str(&escape_markdown_v2_text(name.as_ref()));
                rendered.push_str("\\]");
            }
            _ => {}
        }
    }

    trim_trailing_blank_lines(&mut rendered);
    if rendered.is_empty() {
        escape_markdown_v2_text(markdown)
    } else {
        rendered
    }
}

pub fn markdown_to_telegram_html(markdown: &str) -> String {
    let mut options = Options::empty();
    options.insert(Options::ENABLE_STRIKETHROUGH);
    options.insert(Options::ENABLE_TABLES);
    options.insert(Options::ENABLE_TASKLISTS);

    let parser = Parser::new_ext(markdown, options);
    let mut rendered = String::new();
    let mut ordered_list_stack: Vec<usize> = Vec::new();
    let mut list_is_ordered_stack: Vec<bool> = Vec::new();

    for event in parser {
        match event {
            Event::Start(tag) => match tag {
                Tag::Strong => rendered.push_str("<b>"),
                Tag::Emphasis => rendered.push_str("<i>"),
                Tag::Strikethrough => rendered.push_str("<s>"),
                Tag::CodeBlock(_) => {
                    rendered.push_str("<pre><code>");
                }
                Tag::Link { dest_url, .. } => {
                    rendered.push_str("<a href=\"");
                    rendered.push_str(&escape_html_attr(dest_url.as_ref()));
                    rendered.push_str("\">");
                }
                Tag::Heading { .. } => rendered.push_str("<b>"),
                Tag::List(start) => {
                    if let Some(start_number) = start {
                        ordered_list_stack.push(start_number as usize);
                        list_is_ordered_stack.push(true);
                    } else {
                        ordered_list_stack.push(1);
                        list_is_ordered_stack.push(false);
                    }
                }
                Tag::Item => {
                    if !rendered.is_empty() && !rendered.ends_with('\n') {
                        rendered.push('\n');
                    }
                    match list_is_ordered_stack.last().copied() {
                        Some(true) => {
                            if let Some(current) = ordered_list_stack.last_mut() {
                                rendered.push_str(&format!("{current}. "));
                                *current += 1;
                            } else {
                                rendered.push_str("• ");
                            }
                        }
                        _ => rendered.push_str("• "),
                    }
                }
                Tag::BlockQuote(_) => rendered.push_str("&gt; "),
                _ => {}
            },
            Event::End(tag_end) => match tag_end {
                TagEnd::Strong => rendered.push_str("</b>"),
                TagEnd::Emphasis => rendered.push_str("</i>"),
                TagEnd::Strikethrough => rendered.push_str("</s>"),
                TagEnd::CodeBlock => {
                    rendered.push_str("</code></pre>\n\n");
                }
                TagEnd::Link => rendered.push_str("</a>"),
                TagEnd::Heading(_) => rendered.push_str("</b>\n\n"),
                TagEnd::Paragraph => rendered.push_str("\n\n"),
                TagEnd::List(_) => {
                    ordered_list_stack.pop();
                    list_is_ordered_stack.pop();
                    rendered.push('\n');
                }
                _ => {}
            },
            Event::Text(text) => {
                rendered.push_str(&escape_html_text(text.as_ref()));
            }
            Event::Code(text) => {
                rendered.push_str("<code>");
                rendered.push_str(&escape_html_text(text.as_ref()));
                rendered.push_str("</code>");
            }
            Event::SoftBreak | Event::HardBreak => rendered.push('\n'),
            Event::Rule => rendered.push_str("\n----\n"),
            Event::Html(text) | Event::InlineHtml(text) => {
                rendered.push_str(&escape_html_text(text.as_ref()));
            }
            Event::TaskListMarker(checked) => {
                if checked {
                    rendered.push_str("[x] ");
                } else {
                    rendered.push_str("[ ] ");
                }
            }
            Event::FootnoteReference(name) => {
                rendered.push('[');
                rendered.push_str(&escape_html_text(name.as_ref()));
                rendered.push(']');
            }
            _ => {}
        }
    }

    trim_trailing_blank_lines(&mut rendered);
    if rendered.is_empty() {
        escape_html_text(markdown)
    } else {
        rendered
    }
}

fn escape_markdown_v2_text(text: &str) -> String {
    text.chars()
        .fold(String::with_capacity(text.len()), |mut escaped, ch| {
            match ch {
                '_' | '*' | '[' | ']' | '(' | ')' | '~' | '`' | '>' | '#' | '+' | '-' | '='
                | '|' | '{' | '}' | '.' | '!' | '\\' => {
                    escaped.push('\\');
                    escaped.push(ch);
                }
                _ => escaped.push(ch),
            }
            escaped
        })
}

fn escape_markdown_v2_code(text: &str) -> String {
    text.chars()
        .fold(String::with_capacity(text.len()), |mut escaped, ch| {
            if ch == '\\' || ch == '`' {
                escaped.push('\\');
            }
            escaped.push(ch);
            escaped
        })
}

fn escape_markdown_v2_url(url: &str) -> String {
    url.chars()
        .fold(String::with_capacity(url.len()), |mut escaped, ch| {
            if ch == '\\' || ch == ')' {
                escaped.push('\\');
            }
            escaped.push(ch);
            escaped
        })
}

fn trim_trailing_blank_lines(text: &mut String) {
    while text.ends_with('\n') {
        text.pop();
    }
}

fn normalize_code_fence_language(kind: CodeBlockKind<'_>) -> Option<String> {
    let CodeBlockKind::Fenced(info) = kind else {
        return None;
    };
    let candidate = info.split_whitespace().next()?.trim();
    if candidate.is_empty() {
        return None;
    }
    if candidate
        .chars()
        .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-' | '+' | '#'))
    {
        return Some(candidate.to_ascii_lowercase());
    }
    None
}

fn escape_html_text(text: &str) -> String {
    text.chars()
        .fold(String::with_capacity(text.len()), |mut escaped, ch| {
            match ch {
                '&' => escaped.push_str("&amp;"),
                '<' => escaped.push_str("&lt;"),
                '>' => escaped.push_str("&gt;"),
                _ => escaped.push(ch),
            }
            escaped
        })
}

fn escape_html_attr(text: &str) -> String {
    text.chars()
        .fold(String::with_capacity(text.len()), |mut escaped, ch| {
            match ch {
                '&' => escaped.push_str("&amp;"),
                '<' => escaped.push_str("&lt;"),
                '>' => escaped.push_str("&gt;"),
                '"' => escaped.push_str("&quot;"),
                '\'' => escaped.push_str("&#39;"),
                _ => escaped.push(ch),
            }
            escaped
        })
}
