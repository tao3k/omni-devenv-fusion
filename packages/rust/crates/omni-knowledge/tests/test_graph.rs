//! Integration tests for the KnowledgeGraph module.
//!
//! Covers: CRUD, multi-hop search, persistence, skill registration,
//! query-time tool relevance, and export/import roundtrip.

use omni_knowledge::graph::{KnowledgeGraph, SkillDoc, entity_from_dict};
use omni_knowledge::{Entity, EntityType, Relation, RelationType};
use serde_json::json;
use tempfile::TempDir;

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

#[test]
fn test_add_entity() {
    let graph = KnowledgeGraph::new();

    let entity = Entity::new(
        "person:john_doe".to_string(),
        "John Doe".to_string(),
        EntityType::Person,
        "A developer".to_string(),
    );

    assert!(graph.add_entity(entity).is_ok());
    assert_eq!(graph.get_stats().total_entities, 1);
}

#[test]
fn test_add_relation() {
    let graph = KnowledgeGraph::new();

    let entity1 = Entity::new(
        "person:john_doe".to_string(),
        "John Doe".to_string(),
        EntityType::Person,
        "A developer".to_string(),
    );
    let entity2 = Entity::new(
        "organization:acme".to_string(),
        "Acme Corp".to_string(),
        EntityType::Organization,
        "A company".to_string(),
    );

    graph.add_entity(entity1).unwrap();
    graph.add_entity(entity2).unwrap();

    let relation = Relation::new(
        "John Doe".to_string(),
        "Acme Corp".to_string(),
        RelationType::WorksFor,
        "Works at the company".to_string(),
    );

    assert!(graph.add_relation(relation).is_ok());
    assert_eq!(graph.get_stats().total_relations, 1);
}

// ---------------------------------------------------------------------------
// Multi-hop search
// ---------------------------------------------------------------------------

#[test]
fn test_multi_hop_search() {
    let graph = KnowledgeGraph::new();

    let entities = vec![
        ("A", EntityType::Concept),
        ("B", EntityType::Concept),
        ("C", EntityType::Concept),
        ("D", EntityType::Concept),
    ];

    for (name, etype) in &entities {
        let entity = Entity::new(
            format!("concept:{}", name),
            name.to_string(),
            etype.clone(),
            format!("Concept {}", name),
        );
        graph.add_entity(entity).unwrap();
    }

    for i in 0..entities.len() - 1 {
        let relation = Relation::new(
            entities[i].0.to_string(),
            entities[i + 1].0.to_string(),
            RelationType::RelatedTo,
            "Related".to_string(),
        );
        graph.add_relation(relation).unwrap();
    }

    let results = graph.multi_hop_search("A", 2);
    assert!(results.len() >= 2);

    let results = graph.multi_hop_search("A", 3);
    assert!(results.len() >= 3);
}

// ---------------------------------------------------------------------------
// Persistence (dict parsing)
// ---------------------------------------------------------------------------

#[test]
fn test_entity_from_dict() {
    let data = json!({
        "name": "Claude Code",
        "entity_type": "TOOL",
        "description": "AI coding assistant",
        "source": "docs/tools.md",
        "aliases": ["claude", "claude-dev"],
        "confidence": 0.95
    });

    let entity = entity_from_dict(&data).unwrap();
    assert_eq!(entity.name, "Claude Code");
    assert!(matches!(entity.entity_type, EntityType::Tool));
    assert_eq!(entity.aliases.len(), 2);
}

#[test]
fn test_save_and_load_graph() {
    let temp_dir = TempDir::new().unwrap();
    let graph_path = temp_dir.path().join("test_graph.json");

    {
        let graph = KnowledgeGraph::new();

        let entity1 = Entity::new(
            "tool:python".to_string(),
            "Python".to_string(),
            EntityType::Skill,
            "Programming language".to_string(),
        );
        let entity2 = Entity::new(
            "tool:claude-code".to_string(),
            "Claude Code".to_string(),
            EntityType::Tool,
            "AI coding assistant".to_string(),
        );

        graph.add_entity(entity1).unwrap();
        graph.add_entity(entity2).unwrap();

        let relation = Relation::new(
            "Claude Code".to_string(),
            "Python".to_string(),
            RelationType::Uses,
            "Claude Code uses Python".to_string(),
        );
        graph.add_relation(relation).unwrap();
        graph.save_to_file(graph_path.to_str().unwrap()).unwrap();
    }

    {
        let mut graph = KnowledgeGraph::new();
        graph.load_from_file(graph_path.to_str().unwrap()).unwrap();

        let stats = graph.get_stats();
        assert_eq!(stats.total_entities, 2);
        assert_eq!(stats.total_relations, 1);

        let python = graph.get_entity_by_name("Python");
        assert!(python.is_some());
        assert_eq!(python.unwrap().entity_type, EntityType::Skill);

        let relations = graph.get_relations(None, None);
        assert_eq!(relations.len(), 1);
        assert_eq!(relations[0].source, "Claude Code");
    }
}

#[test]
fn test_export_as_json() {
    let graph = KnowledgeGraph::new();

    let entity = Entity::new(
        "project:omni".to_string(),
        "Omni Dev Fusion".to_string(),
        EntityType::Project,
        "Development environment".to_string(),
    );

    graph.add_entity(entity).unwrap();

    let json = graph.export_as_json().unwrap();
    assert!(json.contains("Omni Dev Fusion"));
    assert!(json.contains("entities"));
    assert!(json.contains("relations"));
}

#[test]
fn test_export_import_roundtrip() {
    let temp_dir = TempDir::new().unwrap();
    let graph_path = temp_dir.path().join("roundtrip.json");

    let graph1 = KnowledgeGraph::new();

    let entities = vec![
        ("Python", EntityType::Skill),
        ("Rust", EntityType::Skill),
        ("Claude Code", EntityType::Tool),
        ("Omni Dev Fusion", EntityType::Project),
    ];

    for (name, etype) in &entities {
        let entity = Entity::new(
            format!(
                "{}:{}",
                etype.to_string().to_lowercase(),
                name.to_lowercase().replace(' ', "_")
            ),
            name.to_string(),
            etype.clone(),
            format!("Description of {}", name),
        );
        graph1.add_entity(entity).unwrap();
    }

    let relations = vec![
        ("Claude Code", "Python", RelationType::Uses),
        ("Claude Code", "Rust", RelationType::Uses),
        ("Omni Dev Fusion", "Claude Code", RelationType::CreatedBy),
    ];

    for (source, target, rtype) in &relations {
        let relation = Relation::new(
            source.to_string(),
            target.to_string(),
            rtype.clone(),
            format!("{} -> {}", source, target),
        );
        graph1.add_relation(relation).unwrap();
    }

    graph1.save_to_file(graph_path.to_str().unwrap()).unwrap();

    let mut graph2 = KnowledgeGraph::new();
    graph2.load_from_file(graph_path.to_str().unwrap()).unwrap();

    let stats1 = graph1.get_stats();
    let stats2 = graph2.get_stats();
    assert_eq!(stats1.total_entities, stats2.total_entities);
    assert_eq!(stats1.total_relations, stats2.total_relations);
}

// ---------------------------------------------------------------------------
// Lance persistence roundtrip
// ---------------------------------------------------------------------------

#[tokio::test]
async fn test_save_and_load_lance_roundtrip() {
    let temp_dir = TempDir::new().unwrap();
    let lance_dir = temp_dir.path().join("knowledge.lance");
    std::fs::create_dir_all(&lance_dir).unwrap();

    // Build graph
    let graph = KnowledgeGraph::new();

    let mut entity1 = Entity::new(
        "tool:python".to_string(),
        "Python".to_string(),
        EntityType::Skill,
        "Programming language".to_string(),
    );
    entity1.aliases = vec!["py".to_string(), "python3".to_string()];
    entity1.confidence = 0.95;

    let mut entity2 = Entity::new(
        "tool:claude-code".to_string(),
        "Claude Code".to_string(),
        EntityType::Tool,
        "AI coding assistant".to_string(),
    );
    entity2.vector = Some(vec![0.1; 128]);

    graph.add_entity(entity1).unwrap();
    graph.add_entity(entity2).unwrap();

    let relation = Relation::new(
        "Claude Code".to_string(),
        "Python".to_string(),
        RelationType::Uses,
        "Claude Code uses Python".to_string(),
    )
    .with_confidence(0.8);
    graph.add_relation(relation).unwrap();

    // Save to Lance
    graph
        .save_to_lance(lance_dir.to_str().unwrap(), 128)
        .await
        .unwrap();

    // Load into new graph
    let mut graph2 = KnowledgeGraph::new();
    graph2
        .load_from_lance(lance_dir.to_str().unwrap())
        .await
        .unwrap();

    // Verify entity counts
    let stats = graph2.get_stats();
    assert_eq!(stats.total_entities, 2, "Should have 2 entities");
    assert_eq!(stats.total_relations, 1, "Should have 1 relation");

    // Verify entity data
    let python = graph2.get_entity_by_name("Python").unwrap();
    assert_eq!(python.aliases.len(), 2);
    assert!(python.aliases.contains(&"py".to_string()));
    assert_eq!(python.confidence, 0.95);
    assert!(
        python.vector.is_none(),
        "Python entity should have no vector"
    );

    let claude = graph2.get_entity_by_name("Claude Code").unwrap();
    assert!(
        claude.vector.is_some(),
        "Claude entity should have a vector"
    );
    assert_eq!(claude.vector.as_ref().unwrap().len(), 128);

    // Verify relation data
    let rels = graph2.get_relations(None, None);
    assert_eq!(rels.len(), 1);
    assert_eq!(rels[0].source, "Claude Code");
    assert_eq!(rels[0].target, "Python");
    assert_eq!(rels[0].confidence, 0.8);
}

#[tokio::test]
async fn test_lance_persistence_with_skill_registration() {
    let temp_dir = TempDir::new().unwrap();
    let lance_dir = temp_dir.path().join("knowledge.lance");
    std::fs::create_dir_all(&lance_dir).unwrap();

    let graph = KnowledgeGraph::new();

    let docs = vec![
        SkillDoc {
            id: "git".to_string(),
            doc_type: "skill".to_string(),
            skill_name: "git".to_string(),
            tool_name: String::new(),
            content: "Git operations".to_string(),
            routing_keywords: vec![],
        },
        SkillDoc {
            id: "git.commit".to_string(),
            doc_type: "command".to_string(),
            skill_name: "git".to_string(),
            tool_name: "git.commit".to_string(),
            content: "Create a commit".to_string(),
            routing_keywords: vec!["commit".to_string(), "git".to_string()],
        },
    ];
    graph.register_skill_entities(&docs).unwrap();

    let stats_before = graph.get_stats();

    // Save → Load cycle via Lance
    graph
        .save_to_lance(lance_dir.to_str().unwrap(), 1024)
        .await
        .unwrap();

    let mut graph2 = KnowledgeGraph::new();
    graph2
        .load_from_lance(lance_dir.to_str().unwrap())
        .await
        .unwrap();

    let stats_after = graph2.get_stats();
    assert_eq!(stats_before.total_entities, stats_after.total_entities);
    assert_eq!(stats_before.total_relations, stats_after.total_relations);

    // Verify search still works after roundtrip
    let results = graph2.search_entities("git", 10);
    assert!(
        !results.is_empty(),
        "Search should find git entities after Lance roundtrip"
    );
}

// ---------------------------------------------------------------------------
// Enhanced search_entities scoring
// ---------------------------------------------------------------------------

#[test]
fn test_search_entities_exact_name_ranks_highest() {
    let graph = KnowledgeGraph::new();

    let entities = vec![
        ("git.commit", EntityType::Tool, "Create a git commit"),
        ("git.status", EntityType::Tool, "Show git status"),
        ("knowledge.recall", EntityType::Tool, "Recall knowledge"),
    ];

    for (name, etype, desc) in &entities {
        let entity = Entity::new(
            format!("tool:{}", name),
            name.to_string(),
            etype.clone(),
            desc.to_string(),
        );
        graph.add_entity(entity).unwrap();
    }

    let results = graph.search_entities("git.commit", 10);
    assert!(!results.is_empty());
    assert_eq!(results[0].name, "git.commit", "Exact match should be first");
}

#[test]
fn test_search_entities_alias_match() {
    let graph = KnowledgeGraph::new();

    let mut entity = Entity::new(
        "tool:claude_code".to_string(),
        "Claude Code".to_string(),
        EntityType::Tool,
        "AI coding assistant".to_string(),
    );
    entity.aliases = vec!["claude-dev".to_string(), "cc".to_string()];
    graph.add_entity(entity).unwrap();

    let other = Entity::new(
        "concept:devtools".to_string(),
        "Developer Tools".to_string(),
        EntityType::Concept,
        "Development tools and utilities".to_string(),
    );
    graph.add_entity(other).unwrap();

    // Search by alias
    let results = graph.search_entities("claude-dev", 10);
    assert!(!results.is_empty());
    assert_eq!(
        results[0].name, "Claude Code",
        "Alias exact match should find Claude Code"
    );

    // Short alias
    let results = graph.search_entities("cc", 10);
    assert!(!results.is_empty());
    assert_eq!(results[0].name, "Claude Code");
}

#[test]
fn test_search_entities_token_overlap() {
    let graph = KnowledgeGraph::new();

    let entities = vec![
        ("git.smart_commit", EntityType::Tool, "Create smart commits"),
        ("git.status", EntityType::Tool, "Show git status"),
        ("knowledge.code_search", EntityType::Tool, "Search code"),
    ];

    for (name, etype, desc) in &entities {
        let entity = Entity::new(
            format!("tool:{}", name),
            name.to_string(),
            etype.clone(),
            desc.to_string(),
        );
        graph.add_entity(entity).unwrap();
    }

    // "smart commit" should match "git.smart_commit" via token overlap
    let results = graph.search_entities("smart commit", 10);
    assert!(!results.is_empty());
    assert_eq!(
        results[0].name, "git.smart_commit",
        "Token overlap should match 'smart commit' to 'git.smart_commit'"
    );
}

#[test]
fn test_search_entities_fuzzy_match() {
    let graph = KnowledgeGraph::new();

    let entity = Entity::new(
        "concept:zettelkasten".to_string(),
        "zettelkasten".to_string(),
        EntityType::Concept,
        "Note-taking method".to_string(),
    );
    graph.add_entity(entity).unwrap();

    // Typo: "zettelkastn" should still find "zettelkasten" via fuzzy match
    let results = graph.search_entities("zettelkastn", 10);
    assert!(
        !results.is_empty(),
        "Fuzzy match should find 'zettelkasten' when querying 'zettelkastn'"
    );
    assert_eq!(results[0].name, "zettelkasten");
}

#[test]
fn test_search_entities_description_fallback() {
    let graph = KnowledgeGraph::new();

    let entity = Entity::new(
        "tool:research_web".to_string(),
        "researcher.search".to_string(),
        EntityType::Tool,
        "Search the internet for information about any topic".to_string(),
    );
    graph.add_entity(entity).unwrap();

    // "internet" doesn't appear in name, aliases, or tokens — only description
    let results = graph.search_entities("internet", 10);
    assert!(!results.is_empty());
    assert_eq!(results[0].name, "researcher.search");
}

#[test]
fn test_search_entities_empty_query() {
    let graph = KnowledgeGraph::new();
    let entity = Entity::new(
        "tool:git".to_string(),
        "git".to_string(),
        EntityType::Tool,
        "Git".to_string(),
    );
    graph.add_entity(entity).unwrap();

    let results = graph.search_entities("", 10);
    assert!(results.is_empty(), "Empty query should return no results");
}

#[test]
fn test_search_entities_confidence_boost() {
    let graph = KnowledgeGraph::new();

    let mut high_conf = Entity::new(
        "tool:primary".to_string(),
        "primary_tool".to_string(),
        EntityType::Tool,
        "A primary tool for search".to_string(),
    );
    high_conf.confidence = 1.0;

    let mut low_conf = Entity::new(
        "tool:secondary".to_string(),
        "secondary_tool".to_string(),
        EntityType::Tool,
        "A secondary tool for search".to_string(),
    );
    low_conf.confidence = 0.3;

    graph.add_entity(high_conf).unwrap();
    graph.add_entity(low_conf).unwrap();

    // Both match via description ("search"), but high confidence should rank first
    let results = graph.search_entities("search", 10);
    assert!(results.len() >= 2);
    // High-confidence entity should have higher final score
    let names: Vec<String> = results.iter().map(|e| e.name.clone()).collect();
    assert_eq!(
        names[0], "primary_tool",
        "Higher confidence entity should rank first"
    );
}

// ---------------------------------------------------------------------------
// Bidirectional multi-hop search
// ---------------------------------------------------------------------------

#[test]
fn test_multi_hop_search_bidirectional() {
    let graph = KnowledgeGraph::new();

    // Create: A -> B -> C, D -> B (D points TO B, not from B)
    for name in &["A", "B", "C", "D"] {
        let entity = Entity::new(
            format!("concept:{}", name),
            name.to_string(),
            EntityType::Concept,
            format!("Concept {}", name),
        );
        graph.add_entity(entity).unwrap();
    }

    // A -> B
    graph
        .add_relation(Relation::new(
            "A".to_string(),
            "B".to_string(),
            RelationType::RelatedTo,
            "A to B".to_string(),
        ))
        .unwrap();

    // B -> C
    graph
        .add_relation(Relation::new(
            "B".to_string(),
            "C".to_string(),
            RelationType::RelatedTo,
            "B to C".to_string(),
        ))
        .unwrap();

    // D -> B (D points to B; from B's perspective this is an incoming edge)
    graph
        .add_relation(Relation::new(
            "D".to_string(),
            "B".to_string(),
            RelationType::DependsOn,
            "D depends on B".to_string(),
        ))
        .unwrap();

    // From B with 2 hops: should reach A (via incoming), C (via outgoing), D (via incoming)
    let results = graph.multi_hop_search("B", 2);
    let names: Vec<String> = results.iter().map(|e| e.name.clone()).collect();

    assert!(
        names.contains(&"B".to_string()),
        "Start entity should be included. Got: {:?}",
        names
    );
    assert!(
        names.contains(&"C".to_string()),
        "Outgoing neighbor C should be found. Got: {:?}",
        names
    );
    assert!(
        names.contains(&"D".to_string()),
        "Incoming neighbor D should be found via bidirectional traversal. Got: {:?}",
        names
    );
    assert!(
        names.contains(&"A".to_string()),
        "Incoming neighbor A should be found via bidirectional traversal. Got: {:?}",
        names
    );
}

// ---------------------------------------------------------------------------
// Skill registration (Bridge 4)
// ---------------------------------------------------------------------------

#[test]
fn test_register_skill_entities_creates_entities_and_relations() {
    let graph = KnowledgeGraph::new();

    let docs = vec![
        SkillDoc {
            id: "git".to_string(),
            doc_type: "skill".to_string(),
            skill_name: "git".to_string(),
            tool_name: String::new(),
            content: "Git version control operations".to_string(),
            routing_keywords: vec![],
        },
        SkillDoc {
            id: "git.smart_commit".to_string(),
            doc_type: "command".to_string(),
            skill_name: "git".to_string(),
            tool_name: "git.smart_commit".to_string(),
            content: "Create a smart commit with AI-generated message".to_string(),
            routing_keywords: vec!["commit".to_string(), "git".to_string()],
        },
        SkillDoc {
            id: "git.status".to_string(),
            doc_type: "command".to_string(),
            skill_name: "git".to_string(),
            tool_name: "git.status".to_string(),
            content: "Show working tree status".to_string(),
            routing_keywords: vec!["status".to_string(), "git".to_string()],
        },
        SkillDoc {
            id: "knowledge".to_string(),
            doc_type: "skill".to_string(),
            skill_name: "knowledge".to_string(),
            tool_name: String::new(),
            content: "Knowledge base operations".to_string(),
            routing_keywords: vec![],
        },
        SkillDoc {
            id: "knowledge.recall".to_string(),
            doc_type: "command".to_string(),
            skill_name: "knowledge".to_string(),
            tool_name: "knowledge.recall".to_string(),
            content: "Recall knowledge from memory".to_string(),
            routing_keywords: vec!["search".to_string(), "recall".to_string()],
        },
    ];

    let result = graph.register_skill_entities(&docs).unwrap();

    // 2 skills + 3 tools + 4 unique keywords = 9 entities
    assert!(
        result.entities_added >= 9,
        "Expected >= 9 entities, got {}",
        result.entities_added
    );

    // CONTAINS: git->git.smart_commit, git->git.status, knowledge->knowledge.recall = 3
    // RELATED_TO: git.smart_commit->{commit,git}, git.status->{status,git}, knowledge.recall->{search,recall} = 6
    assert!(
        result.relations_added >= 9,
        "Expected >= 9 relations, got {}",
        result.relations_added
    );

    let stats = graph.get_stats();
    assert_eq!(*stats.entities_by_type.get("SKILL").unwrap_or(&0), 2);
    assert_eq!(*stats.entities_by_type.get("TOOL").unwrap_or(&0), 3);

    let hops = graph.multi_hop_search("git", 2);
    let names: Vec<String> = hops.iter().map(|e| e.name.clone()).collect();
    assert!(
        names.contains(&"git.smart_commit".to_string()),
        "Multi-hop from 'git' should reach 'git.smart_commit', got: {:?}",
        names
    );
}

#[test]
fn test_register_skill_entities_idempotent() {
    let graph = KnowledgeGraph::new();

    let docs = vec![SkillDoc {
        id: "git".to_string(),
        doc_type: "skill".to_string(),
        skill_name: "git".to_string(),
        tool_name: String::new(),
        content: "Git operations".to_string(),
        routing_keywords: vec![],
    }];

    let r1 = graph.register_skill_entities(&docs).unwrap();
    let r2 = graph.register_skill_entities(&docs).unwrap();

    assert_eq!(r1.entities_added, 1);
    assert_eq!(r2.entities_added, 0);
    assert_eq!(graph.get_stats().total_entities, 1);
}

#[test]
fn test_register_skill_entities_shared_keyword_creates_graph_connections() {
    let graph = KnowledgeGraph::new();

    let docs = vec![
        SkillDoc {
            id: "knowledge".to_string(),
            doc_type: "skill".to_string(),
            skill_name: "knowledge".to_string(),
            tool_name: String::new(),
            content: "Knowledge skill".to_string(),
            routing_keywords: vec![],
        },
        SkillDoc {
            id: "knowledge.recall".to_string(),
            doc_type: "command".to_string(),
            skill_name: "knowledge".to_string(),
            tool_name: "knowledge.recall".to_string(),
            content: "Recall from knowledge base".to_string(),
            routing_keywords: vec!["search".to_string()],
        },
        SkillDoc {
            id: "researcher".to_string(),
            doc_type: "skill".to_string(),
            skill_name: "researcher".to_string(),
            tool_name: String::new(),
            content: "Research skill".to_string(),
            routing_keywords: vec![],
        },
        SkillDoc {
            id: "researcher.search".to_string(),
            doc_type: "command".to_string(),
            skill_name: "researcher".to_string(),
            tool_name: "researcher.search".to_string(),
            content: "Search the web".to_string(),
            routing_keywords: vec!["search".to_string()],
        },
    ];

    graph.register_skill_entities(&docs).unwrap();

    let search_rels = graph.get_relations(Some("keyword:search"), None);
    assert!(
        search_rels.len() >= 2,
        "keyword:search should have relations from both tools, got: {}",
        search_rels.len()
    );
}

// ---------------------------------------------------------------------------
// Query-time tool relevance (Bridge 5)
// ---------------------------------------------------------------------------

#[test]
fn test_query_tool_relevance_finds_tools_by_keyword() {
    let graph = KnowledgeGraph::new();

    let docs = vec![
        SkillDoc {
            id: "git".to_string(),
            doc_type: "skill".to_string(),
            skill_name: "git".to_string(),
            tool_name: String::new(),
            content: "Git operations".to_string(),
            routing_keywords: vec![],
        },
        SkillDoc {
            id: "git.commit".to_string(),
            doc_type: "command".to_string(),
            skill_name: "git".to_string(),
            tool_name: "git.commit".to_string(),
            content: "Create a commit".to_string(),
            routing_keywords: vec!["commit".to_string(), "git".to_string()],
        },
        SkillDoc {
            id: "git.status".to_string(),
            doc_type: "command".to_string(),
            skill_name: "git".to_string(),
            tool_name: "git.status".to_string(),
            content: "Show status".to_string(),
            routing_keywords: vec!["status".to_string(), "git".to_string()],
        },
    ];
    graph.register_skill_entities(&docs).unwrap();

    let results = graph.query_tool_relevance(&["commit".to_string()], 2, 10);

    let tool_names: Vec<&str> = results.iter().map(|(n, _)| n.as_str()).collect();
    assert!(
        tool_names.contains(&"git.commit"),
        "Expected git.commit in results, got: {:?}",
        tool_names
    );

    let commit_score = results
        .iter()
        .find(|(n, _)| n == "git.commit")
        .map(|(_, s)| *s);
    let status_score = results
        .iter()
        .find(|(n, _)| n == "git.status")
        .map(|(_, s)| *s);
    if let (Some(cs), Some(ss)) = (commit_score, status_score) {
        assert!(
            cs > ss,
            "git.commit ({}) should score higher than git.status ({})",
            cs,
            ss,
        );
    }
}

#[test]
fn test_query_tool_relevance_empty_graph() {
    let graph = KnowledgeGraph::new();
    let results = graph.query_tool_relevance(&["anything".to_string()], 2, 10);
    assert!(results.is_empty());
}

#[test]
fn test_query_tool_relevance_multi_term() {
    let graph = KnowledgeGraph::new();

    let docs = vec![
        SkillDoc {
            id: "knowledge".to_string(),
            doc_type: "skill".to_string(),
            skill_name: "knowledge".to_string(),
            tool_name: String::new(),
            content: "Knowledge base".to_string(),
            routing_keywords: vec![],
        },
        SkillDoc {
            id: "knowledge.recall".to_string(),
            doc_type: "command".to_string(),
            skill_name: "knowledge".to_string(),
            tool_name: "knowledge.recall".to_string(),
            content: "Recall knowledge".to_string(),
            routing_keywords: vec!["search".to_string(), "recall".to_string()],
        },
        SkillDoc {
            id: "researcher".to_string(),
            doc_type: "skill".to_string(),
            skill_name: "researcher".to_string(),
            tool_name: String::new(),
            content: "Web research".to_string(),
            routing_keywords: vec![],
        },
        SkillDoc {
            id: "researcher.search".to_string(),
            doc_type: "command".to_string(),
            skill_name: "researcher".to_string(),
            tool_name: "researcher.search".to_string(),
            content: "Search the web".to_string(),
            routing_keywords: vec!["search".to_string(), "web".to_string()],
        },
    ];
    graph.register_skill_entities(&docs).unwrap();

    let results = graph.query_tool_relevance(&["search".to_string(), "recall".to_string()], 2, 10);

    let tool_names: Vec<&str> = results.iter().map(|(n, _)| n.as_str()).collect();
    assert!(
        tool_names.contains(&"knowledge.recall"),
        "Expected knowledge.recall, got: {:?}",
        tool_names,
    );
    assert!(
        tool_names.contains(&"researcher.search"),
        "Expected researcher.search, got: {:?}",
        tool_names,
    );
}
