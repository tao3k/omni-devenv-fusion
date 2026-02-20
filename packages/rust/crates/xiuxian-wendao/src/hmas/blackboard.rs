use super::protocol::{
    HmasConclusionPayload, HmasDigitalThreadPayload, HmasEvidencePayload, HmasRecordKind,
    HmasSourceNode, HmasTaskPayload,
};
use comrak::{
    Arena, Options,
    nodes::{AstNode, NodeValue},
    parse_document,
};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HmasValidationIssue {
    pub line: usize,
    pub code: String,
    pub message: String,
    #[serde(default)]
    pub kind: Option<HmasRecordKind>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HmasValidationReport {
    pub valid: bool,
    pub task_count: usize,
    pub evidence_count: usize,
    pub conclusion_count: usize,
    pub digital_thread_count: usize,
    pub issues: Vec<HmasValidationIssue>,
}

impl HmasValidationReport {
    #[must_use]
    pub fn ok() -> Self {
        Self {
            valid: true,
            task_count: 0,
            evidence_count: 0,
            conclusion_count: 0,
            digital_thread_count: 0,
            issues: Vec::new(),
        }
    }

    fn push_issue(
        &mut self,
        line: usize,
        code: &str,
        message: impl Into<String>,
        kind: Option<HmasRecordKind>,
    ) {
        self.valid = false;
        self.issues.push(HmasValidationIssue {
            line,
            code: code.to_string(),
            message: message.into(),
            kind,
        });
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ExtractedBlock {
    kind: HmasRecordKind,
    line: usize,
    json_payload: String,
}

fn node_line(node: &AstNode<'_>) -> usize {
    let line = node.data.borrow().sourcepos.start.line;
    if line <= 0 { 1 } else { line as usize }
}

fn push_text_from_node<'a>(node: &'a AstNode<'a>, out: &mut String) {
    match &node.data.borrow().value {
        NodeValue::Text(value) => out.push_str(value),
        NodeValue::Code(value) => out.push_str(&value.literal),
        NodeValue::SoftBreak | NodeValue::LineBreak => out.push(' '),
        _ => {
            for child in node.children() {
                push_text_from_node(child, out);
            }
        }
    }
}

fn heading_text<'a>(node: &'a AstNode<'a>) -> String {
    let mut out = String::new();
    for child in node.children() {
        push_text_from_node(child, &mut out);
    }
    out
}

fn parse_code_fence_info(info: &str) -> (bool, Option<HmasRecordKind>) {
    let mut tokens = info.split_whitespace();
    let Some(language) = tokens.next() else {
        return (false, None);
    };
    let is_json = language.eq_ignore_ascii_case("json");
    let fence_kind = tokens.next().and_then(HmasRecordKind::from_fence_tag);
    (is_json, fence_kind)
}

fn collect_blocks(markdown: &str, report: &mut HmasValidationReport) -> Vec<ExtractedBlock> {
    let arena = Arena::new();
    let root = parse_document(&arena, markdown, &Options::default());
    let mut blocks = Vec::new();
    let mut active_heading_kind: Option<HmasRecordKind> = None;

    let mut stack = vec![root];
    while let Some(node) = stack.pop() {
        let mut children: Vec<&AstNode<'_>> = node.children().collect();
        children.reverse();
        stack.extend(children);

        match &node.data.borrow().value {
            NodeValue::Heading(_) => {
                active_heading_kind = HmasRecordKind::from_heading_text(&heading_text(node));
            }
            NodeValue::CodeBlock(block) => {
                let line = node_line(node);
                let info = block.info.trim().to_string();
                let payload = block.literal.clone();
                let (is_json, explicit_kind) = parse_code_fence_info(&info);

                let resolved_kind = match (active_heading_kind, explicit_kind) {
                    (Some(heading_kind), Some(fence_kind)) => {
                        if heading_kind != fence_kind {
                            report.push_issue(
                                line,
                                "fence_heading_kind_mismatch",
                                format!(
                                    "heading kind {} does not match fenced block kind {}",
                                    heading_kind.as_code(),
                                    fence_kind.as_code()
                                ),
                                Some(fence_kind),
                            );
                        }
                        Some(fence_kind)
                    }
                    (Some(heading_kind), None) => Some(heading_kind),
                    (None, Some(fence_kind)) => Some(fence_kind),
                    (None, None) => None,
                };

                let Some(kind) = resolved_kind else {
                    continue;
                };

                if !is_json {
                    report.push_issue(
                        line,
                        "unexpected_fence_language",
                        format!(
                            "{} block must use JSON fenced code block (`json` language)",
                            kind.as_code()
                        ),
                        Some(kind),
                    );
                    continue;
                }
                blocks.push(ExtractedBlock {
                    kind,
                    line,
                    json_payload: payload,
                });
            }
            _ => {}
        }
    }

    blocks
}

fn has_empty_source_nodes(source_nodes: &[HmasSourceNode]) -> bool {
    source_nodes
        .iter()
        .any(|node| node.node_id.trim().is_empty())
}

pub fn validate_blackboard_markdown(markdown: &str) -> HmasValidationReport {
    let mut report = HmasValidationReport::ok();
    let blocks = collect_blocks(markdown, &mut report);

    let mut digital_thread_requirements = HashSet::new();
    let mut conclusion_requirements = Vec::new();

    for block in blocks {
        match block.kind {
            HmasRecordKind::Task => {
                report.task_count += 1;
                match serde_json::from_str::<HmasTaskPayload>(&block.json_payload) {
                    Ok(payload) => {
                        if payload.requirement_id.trim().is_empty() {
                            report.push_issue(
                                block.line,
                                "missing_requirement_id",
                                "task.requirement_id must be non-empty",
                                Some(block.kind),
                            );
                        }
                        if payload.hard_constraints.is_empty() {
                            report.push_issue(
                                block.line,
                                "missing_hard_constraints",
                                "task.hard_constraints must be non-empty",
                                Some(block.kind),
                            );
                        }
                    }
                    Err(err) => report.push_issue(
                        block.line,
                        "invalid_json_payload",
                        format!("failed to decode task payload: {err}"),
                        Some(block.kind),
                    ),
                }
            }
            HmasRecordKind::Evidence => {
                report.evidence_count += 1;
                match serde_json::from_str::<HmasEvidencePayload>(&block.json_payload) {
                    Ok(payload) => {
                        if payload.requirement_id.trim().is_empty() {
                            report.push_issue(
                                block.line,
                                "missing_requirement_id",
                                "evidence.requirement_id must be non-empty",
                                Some(block.kind),
                            );
                        }
                    }
                    Err(err) => report.push_issue(
                        block.line,
                        "invalid_json_payload",
                        format!("failed to decode evidence payload: {err}"),
                        Some(block.kind),
                    ),
                }
            }
            HmasRecordKind::Conclusion => {
                report.conclusion_count += 1;
                match serde_json::from_str::<HmasConclusionPayload>(&block.json_payload) {
                    Ok(payload) => {
                        let requirement_id = payload.requirement_id.trim().to_string();
                        if requirement_id.is_empty() {
                            report.push_issue(
                                block.line,
                                "missing_requirement_id",
                                "conclusion.requirement_id must be non-empty",
                                Some(block.kind),
                            );
                        } else {
                            conclusion_requirements.push((requirement_id, block.line));
                        }
                        if !(0.0..=1.0).contains(&payload.confidence_score) {
                            report.push_issue(
                                block.line,
                                "invalid_confidence_score",
                                "conclusion.confidence_score must be between 0 and 1",
                                Some(block.kind),
                            );
                        }
                    }
                    Err(err) => report.push_issue(
                        block.line,
                        "invalid_json_payload",
                        format!("failed to decode conclusion payload: {err}"),
                        Some(block.kind),
                    ),
                }
            }
            HmasRecordKind::DigitalThread => {
                report.digital_thread_count += 1;
                match serde_json::from_str::<HmasDigitalThreadPayload>(&block.json_payload) {
                    Ok(payload) => {
                        let requirement_id = payload.requirement_id.trim();
                        if requirement_id.is_empty() {
                            report.push_issue(
                                block.line,
                                "missing_requirement_id",
                                "digital_thread.requirement_id must be non-empty",
                                Some(block.kind),
                            );
                        } else {
                            digital_thread_requirements.insert(requirement_id.to_string());
                        }

                        if payload.source_nodes_accessed.is_empty() {
                            report.push_issue(
                                block.line,
                                "missing_source_nodes",
                                "digital_thread.source_nodes_accessed must be non-empty",
                                Some(block.kind),
                            );
                        } else if has_empty_source_nodes(&payload.source_nodes_accessed) {
                            report.push_issue(
                                block.line,
                                "empty_source_node_id",
                                "digital_thread.source_nodes_accessed[*].node_id must be non-empty",
                                Some(block.kind),
                            );
                        }

                        if payload.hard_constraints_checked.is_empty() {
                            report.push_issue(
                                block.line,
                                "missing_constraints_checked",
                                "digital_thread.hard_constraints_checked must be non-empty",
                                Some(block.kind),
                            );
                        }
                        if !(0.0..=1.0).contains(&payload.confidence_score) {
                            report.push_issue(
                                block.line,
                                "invalid_confidence_score",
                                "digital_thread.confidence_score must be between 0 and 1",
                                Some(block.kind),
                            );
                        }
                    }
                    Err(err) => report.push_issue(
                        block.line,
                        "invalid_json_payload",
                        format!("failed to decode digital_thread payload: {err}"),
                        Some(block.kind),
                    ),
                }
            }
        }
    }

    for (requirement_id, line) in conclusion_requirements {
        if !digital_thread_requirements.contains(&requirement_id) {
            report.push_issue(
                line,
                "missing_digital_thread",
                format!(
                    "conclusion requirement_id={requirement_id} has no matching digital_thread payload"
                ),
                Some(HmasRecordKind::Conclusion),
            );
        }
    }

    report
}

pub fn validate_blackboard_file(path: &Path) -> Result<HmasValidationReport, String> {
    let content = std::fs::read_to_string(path).map_err(|err| {
        format!(
            "failed to read blackboard markdown file {}: {err}",
            path.display()
        )
    })?;
    Ok(validate_blackboard_markdown(&content))
}
