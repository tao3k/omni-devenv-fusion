//! Entity types for knowledge graph.
//!
//! Provides Entity and Relation types for knowledge graph operations.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Entity type enumeration.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EntityType {
    #[serde(rename = "PERSON")]
    /// A human individual.
    Person,
    #[serde(rename = "ORGANIZATION")]
    /// A company, team, or institution.
    Organization,
    #[serde(rename = "CONCEPT")]
    /// An abstract idea or topic.
    Concept,
    #[serde(rename = "PROJECT")]
    /// A project, repository, or initiative.
    Project,
    #[serde(rename = "TOOL")]
    /// A software tool or library.
    Tool,
    #[serde(rename = "SKILL")]
    /// A reusable capability or skill.
    Skill,
    #[serde(rename = "LOCATION")]
    /// A physical or logical location.
    Location,
    #[serde(rename = "EVENT")]
    /// A time-bounded event.
    Event,
    #[serde(rename = "DOCUMENT")]
    /// A document or note.
    Document,
    #[serde(rename = "CODE")]
    /// A code artifact.
    Code,
    #[serde(rename = "API")]
    /// An API surface.
    Api,
    #[serde(rename = "ERROR")]
    /// An error category or instance.
    Error,
    #[serde(rename = "PATTERN")]
    /// A design or implementation pattern.
    Pattern,
    #[serde(rename = "OTHER")]
    /// A custom entity type represented by free-form text.
    Other(String),
}

impl Default for EntityType {
    fn default() -> Self {
        EntityType::Concept
    }
}

impl std::fmt::Display for EntityType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EntityType::Person => write!(f, "PERSON"),
            EntityType::Organization => write!(f, "ORGANIZATION"),
            EntityType::Concept => write!(f, "CONCEPT"),
            EntityType::Project => write!(f, "PROJECT"),
            EntityType::Tool => write!(f, "TOOL"),
            EntityType::Skill => write!(f, "SKILL"),
            EntityType::Location => write!(f, "LOCATION"),
            EntityType::Event => write!(f, "EVENT"),
            EntityType::Document => write!(f, "DOCUMENT"),
            EntityType::Code => write!(f, "CODE"),
            EntityType::Api => write!(f, "API"),
            EntityType::Error => write!(f, "ERROR"),
            EntityType::Pattern => write!(f, "PATTERN"),
            EntityType::Other(s) => write!(f, "OTHER({})", s),
        }
    }
}

/// Relation type enumeration.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RelationType {
    #[serde(rename = "WORKS_FOR")]
    /// Employment/affiliation relation.
    WorksFor,
    #[serde(rename = "PART_OF")]
    /// Membership/composition relation.
    PartOf,
    #[serde(rename = "USES")]
    /// Usage/dependency relation.
    Uses,
    #[serde(rename = "DEPENDS_ON")]
    /// Hard dependency relation.
    DependsOn,
    #[serde(rename = "SIMILAR_TO")]
    /// Similarity relation.
    SimilarTo,
    #[serde(rename = "LOCATED_IN")]
    /// Spatial or logical containment relation.
    LocatedIn,
    #[serde(rename = "CREATED_BY")]
    /// Authorship/ownership relation.
    CreatedBy,
    #[serde(rename = "DOCUMENTED_IN")]
    /// Documentation linkage relation.
    DocumentedIn,
    #[serde(rename = "RELATED_TO")]
    /// Generic relatedness relation.
    RelatedTo,
    #[serde(rename = "IMPLEMENTS")]
    /// Implementation relation.
    Implements,
    #[serde(rename = "EXTENDS")]
    /// Inheritance/extension relation.
    Extends,
    #[serde(rename = "CONTAINS")]
    /// Container/content relation.
    Contains,
    #[serde(rename = "OTHER")]
    /// A custom relation represented by free-form text.
    Other(String),
}

impl Default for RelationType {
    fn default() -> Self {
        RelationType::RelatedTo
    }
}

impl std::fmt::Display for RelationType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            RelationType::WorksFor => write!(f, "WORKS_FOR"),
            RelationType::PartOf => write!(f, "PART_OF"),
            RelationType::Uses => write!(f, "USES"),
            RelationType::DependsOn => write!(f, "DEPENDS_ON"),
            RelationType::SimilarTo => write!(f, "SIMILAR_TO"),
            RelationType::LocatedIn => write!(f, "LOCATED_IN"),
            RelationType::CreatedBy => write!(f, "CREATED_BY"),
            RelationType::DocumentedIn => write!(f, "DOCUMENTED_IN"),
            RelationType::RelatedTo => write!(f, "RELATED_TO"),
            RelationType::Implements => write!(f, "IMPLEMENTS"),
            RelationType::Extends => write!(f, "EXTENDS"),
            RelationType::Contains => write!(f, "CONTAINS"),
            RelationType::Other(s) => write!(f, "OTHER({})", s),
        }
    }
}

/// Represents an entity extracted from text.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Entity {
    /// Unique identifier
    pub id: String,
    /// Entity name
    pub name: String,
    /// Entity type
    pub entity_type: EntityType,
    /// Brief description
    pub description: String,
    /// Source document
    pub source: Option<String>,
    /// Alternative names
    pub aliases: Vec<String>,
    /// Confidence score (0.0-1.0)
    pub confidence: f32,
    /// Vector embedding (for semantic search)
    pub vector: Option<Vec<f32>>,
    /// Additional metadata
    pub metadata: HashMap<String, serde_json::Value>,
    /// Creation timestamp
    pub created_at: DateTime<Utc>,
    /// Last update timestamp
    pub updated_at: DateTime<Utc>,
}

impl Entity {
    /// Create a new entity.
    pub fn new(id: String, name: String, entity_type: EntityType, description: String) -> Self {
        let now = Utc::now();
        Self {
            id,
            name,
            entity_type,
            description,
            source: None,
            aliases: Vec::new(),
            confidence: 1.0,
            vector: None,
            metadata: HashMap::new(),
            created_at: now,
            updated_at: now,
        }
    }

    /// Set source.
    pub fn with_source(mut self, source: Option<String>) -> Self {
        self.source = source;
        self.updated_at = Utc::now();
        self
    }

    /// Set aliases.
    pub fn with_aliases(mut self, aliases: Vec<String>) -> Self {
        self.aliases = aliases;
        self.updated_at = Utc::now();
        self
    }

    /// Set confidence.
    pub fn with_confidence(mut self, confidence: f32) -> Self {
        self.confidence = confidence.clamp(0.0, 1.0);
        self.updated_at = Utc::now();
        self
    }

    /// Set vector embedding.
    pub fn with_vector(mut self, vector: Vec<f32>) -> Self {
        self.vector = Some(vector);
        self.updated_at = Utc::now();
        self
    }

    /// Add metadata.
    pub fn with_metadata(mut self, key: String, value: serde_json::Value) -> Self {
        self.metadata.insert(key, value);
        self.updated_at = Utc::now();
        self
    }
}

/// Represents a relation between two entities.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Relation {
    /// Unique identifier
    pub id: String,
    /// Source entity name
    pub source: String,
    /// Target entity name
    pub target: String,
    /// Relation type
    pub relation_type: RelationType,
    /// Brief description
    pub description: String,
    /// Source document
    pub source_doc: Option<String>,
    /// Confidence score (0.0-1.0)
    pub confidence: f32,
    /// Additional metadata
    pub metadata: HashMap<String, serde_json::Value>,
    /// Creation timestamp
    pub created_at: DateTime<Utc>,
}

impl Relation {
    /// Create a new relation.
    pub fn new(
        source: String,
        target: String,
        relation_type: RelationType,
        description: String,
    ) -> Self {
        let id = format!(
            "{}|{}|{}",
            source.to_lowercase().replace(" ", "_"),
            relation_type.to_string().to_lowercase().replace(" ", "_"),
            target.to_lowercase().replace(" ", "_")
        );
        Self {
            id,
            source,
            target,
            relation_type,
            description,
            source_doc: None,
            confidence: 1.0,
            metadata: HashMap::new(),
            created_at: Utc::now(),
        }
    }

    /// Set source document.
    pub fn with_source_doc(mut self, source_doc: Option<String>) -> Self {
        self.source_doc = source_doc;
        self
    }

    /// Set confidence.
    pub fn with_confidence(mut self, confidence: f32) -> Self {
        self.confidence = confidence.clamp(0.0, 1.0);
        self
    }

    /// Add metadata.
    pub fn with_metadata(mut self, key: String, value: serde_json::Value) -> Self {
        self.metadata.insert(key, value);
        self
    }
}

/// Knowledge graph statistics.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct GraphStats {
    /// Total entities
    pub total_entities: i64,
    /// Total relations
    pub total_relations: i64,
    /// Entities by type
    pub entities_by_type: HashMap<String, i64>,
    /// Relations by type
    pub relations_by_type: HashMap<String, i64>,
    /// Last update
    pub last_updated: Option<DateTime<Utc>>,
}

/// Search query for entities.
#[derive(Debug, Clone)]
pub struct EntitySearchQuery {
    /// Query text
    pub query: String,
    /// Entity type filter
    pub entity_type: Option<EntityType>,
    /// Maximum results
    pub limit: i32,
}

impl Default for EntitySearchQuery {
    fn default() -> Self {
        Self {
            query: String::new(),
            entity_type: None,
            limit: 10,
        }
    }
}

impl EntitySearchQuery {
    /// Create new query.
    pub fn new(query: String) -> Self {
        Self {
            query,
            ..Default::default()
        }
    }

    /// Set entity type filter.
    pub fn with_entity_type(mut self, entity_type: EntityType) -> Self {
        self.entity_type = Some(entity_type);
        self
    }

    /// Set limit.
    pub fn with_limit(mut self, limit: i32) -> Self {
        self.limit = limit;
        self
    }
}

/// Multi-hop search options.
#[derive(Debug, Clone)]
pub struct MultiHopOptions {
    /// Starting entity names
    pub start_entities: Vec<String>,
    /// Relation types to follow
    pub relation_types: Vec<RelationType>,
    /// Maximum hops
    pub max_hops: usize,
    /// Maximum results
    pub limit: i32,
}

impl Default for MultiHopOptions {
    fn default() -> Self {
        Self {
            start_entities: Vec::new(),
            relation_types: Vec::new(),
            max_hops: 2,
            limit: 20,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_entity_creation() {
        let entity = Entity::new(
            "entity-001".to_string(),
            "Claude Code".to_string(),
            EntityType::Tool,
            "AI coding assistant".to_string(),
        );

        assert_eq!(entity.id, "entity-001");
        assert_eq!(entity.name, "Claude Code");
        assert_eq!(entity.entity_type, EntityType::Tool);
        assert_eq!(entity.confidence, 1.0);
    }

    #[test]
    fn test_entity_builder() {
        let entity = Entity::new(
            "entity-002".to_string(),
            "Python".to_string(),
            EntityType::Skill,
            "Programming language".to_string(),
        )
        .with_aliases(vec!["py".to_string(), "python3".to_string()])
        .with_confidence(0.95)
        .with_source(Some("docs/lang.md".to_string()));

        assert_eq!(entity.aliases.len(), 2);
        assert_eq!(entity.confidence, 0.95);
        assert_eq!(entity.source, Some("docs/lang.md".to_string()));
    }

    #[test]
    fn test_relation_creation() {
        let relation = Relation::new(
            "Claude Code".to_string(),
            "Omni-Dev-Fusion".to_string(),
            RelationType::PartOf,
            "Part of the Omni-Dev-Fusion project".to_string(),
        );

        assert!(relation.id.contains("claude_code"));
        assert!(relation.id.contains("part_of"));
        assert!(relation.id.contains("omni-dev-fusion"));
    }

    #[test]
    fn test_entity_type_display() {
        assert_eq!(EntityType::Person.to_string(), "PERSON");
        assert_eq!(EntityType::Organization.to_string(), "ORGANIZATION");
        assert_eq!(EntityType::Concept.to_string(), "CONCEPT");
    }

    #[test]
    fn test_relation_type_display() {
        assert_eq!(RelationType::WorksFor.to_string(), "WORKS_FOR");
        assert_eq!(RelationType::DependsOn.to_string(), "DEPENDS_ON");
        assert_eq!(RelationType::RelatedTo.to_string(), "RELATED_TO");
    }
}
