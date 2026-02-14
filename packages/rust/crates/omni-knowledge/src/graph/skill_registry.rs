//! Bulk skill entity registration (Bridge 4: Core 2 → Core 1).
//!
//! Accepts parsed skill docs and creates SKILL, TOOL, CONCEPT entities
//! with CONTAINS and RELATED_TO relations in the KnowledgeGraph.

use super::{GraphError, KnowledgeGraph};
use crate::entity::{Entity, EntityType, Relation, RelationType};
use log::info;
use std::collections::{HashMap, HashSet};

/// A parsed skill document for bulk registration.
#[derive(Debug, Clone, Default)]
pub struct SkillDoc {
    /// Document ID
    pub id: String,
    /// "skill" or "command"
    pub doc_type: String,
    /// Parent skill name
    pub skill_name: String,
    /// Tool name (for commands)
    pub tool_name: String,
    /// Text content / description
    pub content: String,
    /// Routing keywords
    pub routing_keywords: Vec<String>,
}

/// Result of skill entity registration.
#[derive(Debug, Clone, Default)]
pub struct SkillRegistrationResult {
    /// Number of entities added
    pub entities_added: usize,
    /// Number of relations added
    pub relations_added: usize,
}

impl KnowledgeGraph {
    /// Batch-register skill docs as entities and relations.
    ///
    /// Creates:
    /// - SKILL entities for each unique skill
    /// - TOOL entities for each command
    /// - CONTAINS relations: Skill → Tool
    /// - CONCEPT entities for each routing keyword
    /// - RELATED_TO relations: Tool → keyword:*
    ///
    /// Called during `omni sync` / `omni reindex`.
    pub fn register_skill_entities(
        &self,
        docs: &[SkillDoc],
    ) -> Result<SkillRegistrationResult, GraphError> {
        let mut entities_added: usize = 0;
        let mut relations_added: usize = 0;

        // Phase 1: Collect skills and tools
        let mut skills: HashMap<String, Vec<String>> = HashMap::new();
        let mut tool_keywords: HashMap<String, HashSet<String>> = HashMap::new();

        for doc in docs {
            match doc.doc_type.as_str() {
                "skill" => {
                    if !doc.skill_name.is_empty() {
                        let id =
                            format!("skill:{}", doc.skill_name.to_lowercase().replace(' ', "_"));
                        let desc = if doc.content.is_empty() {
                            format!("Skill: {}", doc.skill_name)
                        } else {
                            doc.content.chars().take(200).collect()
                        };
                        let entity =
                            Entity::new(id, doc.skill_name.clone(), EntityType::Skill, desc);
                        if self.add_entity(entity).unwrap_or(false) {
                            entities_added += 1;
                        }
                        skills.entry(doc.skill_name.clone()).or_default();
                    }
                }
                "command" => {
                    let tool_name = if doc.tool_name.is_empty() {
                        doc.id.clone()
                    } else {
                        doc.tool_name.clone()
                    };
                    if !tool_name.is_empty() {
                        let id = format!(
                            "tool:{}",
                            tool_name.to_lowercase().replace(' ', "_").replace('.', "_")
                        );
                        let desc: String = doc.content.chars().take(200).collect();
                        let entity = Entity::new(id, tool_name.clone(), EntityType::Tool, desc);
                        if self.add_entity(entity).unwrap_or(false) {
                            entities_added += 1;
                        }

                        if !doc.skill_name.is_empty() {
                            skills
                                .entry(doc.skill_name.clone())
                                .or_default()
                                .push(tool_name.clone());
                        }

                        let kw_set: HashSet<String> = doc
                            .routing_keywords
                            .iter()
                            .filter(|k| !k.is_empty())
                            .map(|k| k.to_lowercase())
                            .collect();
                        if !kw_set.is_empty() {
                            tool_keywords.insert(tool_name, kw_set);
                        }
                    }
                }
                _ => {}
            }
        }

        // Phase 2: CONTAINS relations
        for (skill_name, tool_ids) in &skills {
            for tool_id in tool_ids {
                let relation = Relation::new(
                    skill_name.clone(),
                    tool_id.clone(),
                    RelationType::Contains,
                    format!("{} contains {}", skill_name, tool_id),
                );
                if self.add_relation(relation).is_ok() {
                    relations_added += 1;
                }
            }
        }

        // Phase 3: CONCEPT entities for keywords + RELATED_TO relations
        let mut all_keywords: HashSet<String> = HashSet::new();
        for kw_set in tool_keywords.values() {
            all_keywords.extend(kw_set.iter().cloned());
        }

        for kw in &all_keywords {
            let concept_name = format!("keyword:{}", kw);
            let entity = Entity::new(
                format!("concept:{}", kw.replace(' ', "_")),
                concept_name,
                EntityType::Concept,
                format!("Routing keyword: {}", kw),
            );
            if self.add_entity(entity).unwrap_or(false) {
                entities_added += 1;
            }
        }

        for (tool_name, kw_set) in &tool_keywords {
            for kw in kw_set {
                let concept_name = format!("keyword:{}", kw);
                let relation = Relation::new(
                    tool_name.clone(),
                    concept_name,
                    RelationType::RelatedTo,
                    format!("{} has keyword {}", tool_name, kw),
                );
                if self.add_relation(relation).is_ok() {
                    relations_added += 1;
                }
            }
        }

        info!(
            "Skill entities registered: +{} entities, +{} relations",
            entities_added, relations_added
        );
        Ok(SkillRegistrationResult {
            entities_added,
            relations_added,
        })
    }
}
