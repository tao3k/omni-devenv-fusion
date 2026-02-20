use xiuxian_wendao::{HmasRecordKind, validate_blackboard_markdown};

const VALID_BLACKBOARD: &str = r#"
### Sub-Task: Stock Signal

#### [TASK]
```json
{
  "requirement_id": "REQ-001",
  "objective": "Analyze market structure",
  "hard_constraints": ["NOT_ST_STOCK", "MARKET_CAP_OVER_50B"],
  "assigned_to": "worker-01"
}
```

#### [EVIDENCE]
```json
{
  "requirement_id": "REQ-001",
  "evidence": "Two supporting notes were found.",
  "source_nodes_accessed": [
    {"node_id": "note-market-01", "saliency_at_time": 7.2}
  ]
}
```

#### [CONCLUSION]
```json
{
  "requirement_id": "REQ-001",
  "summary": "The setup is valid but requires risk controls.",
  "confidence_score": 0.85,
  "hard_constraints_checked": ["NOT_ST_STOCK", "MARKET_CAP_OVER_50B"]
}
```

#### [DIGITAL THREAD]
```json
{
  "requirement_id": "REQ-001",
  "source_nodes_accessed": [
    {"node_id": "note-market-01", "saliency_at_time": 7.2}
  ],
  "hard_constraints_checked": ["NOT_ST_STOCK", "MARKET_CAP_OVER_50B"],
  "confidence_score": 0.85
}
```
"#;

#[test]
fn test_validate_blackboard_markdown_success() {
    let report = validate_blackboard_markdown(VALID_BLACKBOARD);
    assert!(report.valid, "expected valid report: {:?}", report.issues);
    assert_eq!(report.task_count, 1);
    assert_eq!(report.evidence_count, 1);
    assert_eq!(report.conclusion_count, 1);
    assert_eq!(report.digital_thread_count, 1);
}

#[test]
fn test_validate_blackboard_missing_digital_thread_fails() {
    let payload = r#"
#### [CONCLUSION]
```json
{
  "requirement_id": "REQ-100",
  "summary": "No digital thread should fail.",
  "confidence_score": 0.7,
  "hard_constraints_checked": ["RULE"]
}
```
"#;

    let report = validate_blackboard_markdown(payload);
    assert!(!report.valid);
    assert!(
        report
            .issues
            .iter()
            .any(|row| row.code == "missing_digital_thread"
                && row.kind == Some(HmasRecordKind::Conclusion))
    );
}

#[test]
fn test_validate_blackboard_invalid_json_fails() {
    let payload = r#"
#### [TASK]
```json
{"requirement_id":"REQ-2", "objective":
```
"#;
    let report = validate_blackboard_markdown(payload);
    assert!(!report.valid);
    assert!(
        report
            .issues
            .iter()
            .any(|row| row.code == "invalid_json_payload")
    );
}

#[test]
fn test_validate_blackboard_requires_constraints_and_sources() {
    let payload = r#"
#### [DIGITAL THREAD]
```json
{
  "requirement_id": "REQ-300",
  "source_nodes_accessed": [],
  "hard_constraints_checked": [],
  "confidence_score": 1.2
}
```
"#;
    let report = validate_blackboard_markdown(payload);
    assert!(!report.valid);
    assert!(
        report
            .issues
            .iter()
            .any(|row| row.code == "missing_source_nodes")
    );
    assert!(
        report
            .issues
            .iter()
            .any(|row| row.code == "missing_constraints_checked")
    );
    assert!(
        report
            .issues
            .iter()
            .any(|row| row.code == "invalid_confidence_score")
    );
}
