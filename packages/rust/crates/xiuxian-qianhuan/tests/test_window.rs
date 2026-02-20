#![doc = "Integration tests for the system prompt injection window."]

use xiuxian_qianhuan::{
    InjectionError, InjectionWindowConfig, QaEntry, SYSTEM_PROMPT_INJECTION_TAG,
    SystemPromptInjectionWindow,
};

#[test]
fn parse_and_render_xml_roundtrip() {
    let raw = r#"
<system_prompt_injection>
  <qa>
    <q>What is the current deployment target?</q>
    <a>Use valkey + postgres only.</a>
    <source>ops</source>
  </qa>
  <qa>
    <q>What should be avoided?</q>
    <a>Do not use file-based memory fallback.</a>
  </qa>
</system_prompt_injection>
"#;
    let window = SystemPromptInjectionWindow::from_xml(raw, InjectionWindowConfig::default())
        .expect("xml should parse");
    assert_eq!(window.len(), 2);

    let rendered = window.render_xml();
    assert!(rendered.contains("<system_prompt_injection>"));
    assert!(rendered.contains("<q>What is the current deployment target?</q>"));
    assert!(rendered.contains("<source>ops</source>"));
    assert!(rendered.contains("</system_prompt_injection>"));
}

#[test]
fn normalize_xml_enforces_window_limits() {
    let mut window = SystemPromptInjectionWindow::new(InjectionWindowConfig {
        max_entries: 2,
        max_chars: 120,
    });
    window.push(QaEntry {
        question: "q1".to_string(),
        answer: "a1".to_string(),
        source: None,
    });
    window.push(QaEntry {
        question: "q2".to_string(),
        answer: "a2".to_string(),
        source: None,
    });
    window.push(QaEntry {
        question: "q3".to_string(),
        answer: "a3".to_string(),
        source: None,
    });

    assert_eq!(window.len(), 2, "window should keep latest entries");
    let xml = window.render_xml();
    assert!(!xml.contains("<q>q1</q>"));
    assert!(xml.contains("<q>q2</q>"));
    assert!(xml.contains("<q>q3</q>"));
}

#[test]
fn parse_single_qa_without_root_is_supported() {
    let raw = r#"<qa><q>q</q><a>a</a></qa>"#;
    let window = SystemPromptInjectionWindow::from_xml(raw, InjectionWindowConfig::default())
        .expect("single qa should parse");
    assert_eq!(window.len(), 1);
    let rendered = window.render_xml();
    assert!(rendered.starts_with(&format!("<{SYSTEM_PROMPT_INJECTION_TAG}>")));
}

#[test]
fn parse_rejects_invalid_payload() {
    let raw = r#"<system_prompt_injection><qa><q>question only</q></qa></system_prompt_injection>"#;
    let error = SystemPromptInjectionWindow::from_xml(raw, InjectionWindowConfig::default())
        .expect_err("invalid qa should fail");
    assert_eq!(error, InjectionError::MissingAnswer);
}
