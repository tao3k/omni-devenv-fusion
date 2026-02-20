//! Tests for LinkGraph entity reference extraction.

use xiuxian_wendao::link_graph_refs::{
    LinkGraphEntityRef, LinkGraphRefStats, extract_entity_refs, find_notes_referencing_entity,
    get_ref_stats, is_valid_entity_ref, parse_entity_ref,
};

#[test]
fn test_extract_single_ref() {
    let content = "See [[FactoryPattern]] for details.";
    let refs = extract_entity_refs(content);
    assert_eq!(refs.len(), 1);
    assert_eq!(refs[0].name, "FactoryPattern");
    assert_eq!(refs[0].entity_type, None);
}

#[test]
fn test_extract_typed_ref() {
    let content = "Use [[SingletonPattern#py]] implementation.";
    let refs = extract_entity_refs(content);
    assert_eq!(refs.len(), 1);
    assert_eq!(refs[0].name, "SingletonPattern");
    assert_eq!(refs[0].entity_type, Some("py".to_string()));
}

#[test]
fn test_extract_multiple_refs() {
    let content = "See [[FactoryPattern]], [[SingletonPattern#py]], and [[ObserverPattern]].";
    let refs = extract_entity_refs(content);
    assert_eq!(refs.len(), 3);
}

#[test]
fn test_extract_refs_with_alias() {
    let content = "Use [[FactoryPattern|FP]] for creation.";
    let refs = extract_entity_refs(content);
    assert_eq!(refs.len(), 1);
    assert_eq!(refs[0].name, "FactoryPattern");
}

#[test]
fn test_deduplicate_refs() {
    let content = "First [[FactoryPattern]] then [[FactoryPattern]] again.";
    let refs = extract_entity_refs(content);
    assert_eq!(refs.len(), 1);
}

#[test]
fn test_empty_content() {
    let content = "";
    let refs = extract_entity_refs(content);
    assert!(refs.is_empty());
}

#[test]
fn test_no_refs() {
    let content = "Just regular text without any links.";
    let refs = extract_entity_refs(content);
    assert!(refs.is_empty());
}

#[test]
fn test_to_wikilink() {
    let ref1 = LinkGraphEntityRef::new(
        "FactoryPattern".to_string(),
        None,
        "[[FactoryPattern]]".to_string(),
    );
    assert_eq!(ref1.to_wikilink(), "[[FactoryPattern]]");

    let ref2 = LinkGraphEntityRef::new(
        "SingletonPattern".to_string(),
        Some("py".to_string()),
        "[[SingletonPattern#py]]".to_string(),
    );
    assert_eq!(ref2.to_wikilink(), "[[SingletonPattern#py]]");
}

#[test]
fn test_to_tag() {
    let ref1 = LinkGraphEntityRef::new(
        "FactoryPattern".to_string(),
        None,
        "[[FactoryPattern]]".to_string(),
    );
    assert_eq!(ref1.to_tag(), "#entity");

    let ref2 = LinkGraphEntityRef::new(
        "SingletonPattern".to_string(),
        Some("py".to_string()),
        "[[SingletonPattern#py]]".to_string(),
    );
    assert_eq!(ref2.to_tag(), "#entity-py");
}

#[test]
fn test_count_entity_refs() {
    let content = "[[A]] [[B]] [[C]]";
    assert_eq!(extract_entity_refs(content).len(), 3);
}

#[test]
fn test_is_valid_entity_ref() {
    assert!(is_valid_entity_ref("[[FactoryPattern]]"));
    assert!(is_valid_entity_ref("[[SingletonPattern#py]]"));
    assert!(!is_valid_entity_ref("not a ref"));
    assert!(is_valid_entity_ref("[[Pattern|alias]]"));
}

#[test]
fn test_parse_entity_ref() {
    let ref1 = parse_entity_ref("[[FactoryPattern]]").unwrap();
    assert_eq!(ref1.name, "FactoryPattern");
    assert_eq!(ref1.entity_type, None);

    let ref2 = parse_entity_ref("[[SingletonPattern#rust]]").unwrap();
    assert_eq!(ref2.name, "SingletonPattern");
    assert_eq!(ref2.entity_type, Some("rust".to_string()));
}

#[test]
fn test_find_notes_referencing_entity() {
    let notes = vec![
        ("note1", "See [[FactoryPattern]]"),
        ("note2", "SingletonPattern is related"),
        ("note3", "Check [[FactoryPattern#py]]"),
    ];

    let refs = find_notes_referencing_entity("FactoryPattern", &notes);
    assert_eq!(refs.len(), 2);
    assert!(refs.contains(&"note1"));
    assert!(refs.contains(&"note3"));
}

#[test]
fn test_ref_stats() {
    let refs = vec![
        LinkGraphEntityRef::new(
            "A".to_string(),
            Some("py".to_string()),
            "[[A#py]]".to_string(),
        ),
        LinkGraphEntityRef::new(
            "B".to_string(),
            Some("py".to_string()),
            "[[B#py]]".to_string(),
        ),
        LinkGraphEntityRef::new(
            "C".to_string(),
            Some("rust".to_string()),
            "[[C#rust]]".to_string(),
        ),
    ];

    let stats = LinkGraphRefStats::from_refs(&refs);
    assert_eq!(stats.total_refs, 3);
    assert_eq!(stats.unique_entities, 3);
    assert_eq!(stats.by_type.len(), 2);
}

#[test]
fn test_get_ref_stats() {
    let content = "[[A#py]] [[B#py]] [[C#rust]]";
    let stats = get_ref_stats(content);
    assert_eq!(stats.total_refs, 3);
    assert_eq!(stats.unique_entities, 3);
}
