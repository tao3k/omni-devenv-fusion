/// Tests for entity-aware search enhancement

#[cfg(test)]
mod tests {
    use crate::HybridSearchResult;
    use crate::ToolSearchResult;
    use crate::keyword::entity_aware::{
        EntityAwareSearchResult, EntityMatch, EntityMatchType, apply_entity_boost, apply_triple_rrf,
    };

    #[test]
    fn test_apply_entity_boost_with_entities() {
        // Base results without entity boost
        let results = vec![
            HybridSearchResult {
                tool_name: "git.commit".to_string(),
                rrf_score: 0.1,
                vector_score: 0.9,
                keyword_score: 0.5,
            },
            HybridSearchResult {
                tool_name: "python.run".to_string(),
                rrf_score: 0.09,
                vector_score: 0.8,
                keyword_score: 0.4,
            },
        ];

        // Entities to boost with
        let entities = vec![EntityMatch {
            entity_name: "Git".to_string(),
            entity_type: "TOOL".to_string(),
            confidence: 0.9,
            match_type: EntityMatchType::NameMatch,
        }];

        let aware_results = apply_entity_boost(results, entities, 0.3, None);

        // Check that results are returned
        assert_eq!(aware_results.len(), 2);

        // Check that git.commit got boosted
        let git_result = aware_results
            .iter()
            .find(|r| r.base.tool_name == "git.commit")
            .expect("Should have git.commit result");

        // Should have entity matches
        assert!(!git_result.entity_matches.is_empty());
        assert_eq!(git_result.entity_matches[0].entity_name, "Git");

        // Boosted score should be higher than base
        assert!(git_result.boosted_score >= git_result.base.rrf_score);
    }

    #[test]
    fn test_apply_entity_boost_empty_entities() {
        let results = vec![HybridSearchResult {
            tool_name: "test.tool".to_string(),
            rrf_score: 0.1,
            vector_score: 0.9,
            keyword_score: 0.5,
        }];

        let aware_results = apply_entity_boost(results, vec![], 0.3, None);

        assert_eq!(aware_results.len(), 1);
        // No entity boost applied
        assert_eq!(aware_results[0].entity_matches.len(), 0);
        assert_eq!(
            aware_results[0].boosted_score,
            aware_results[0].base.rrf_score
        );
    }

    #[test]
    fn test_apply_triple_rrf() {
        // Semantic results (vector search)
        let semantic = vec![
            ("python.run".to_string(), 0.9),
            ("git.commit".to_string(), 0.85),
        ];

        // Keyword results
        let keyword: Vec<ToolSearchResult> = vec![];

        // Entity-aware results
        let entity_aware = vec![EntityAwareSearchResult {
            base: HybridSearchResult {
                tool_name: "python.run".to_string(),
                rrf_score: 0.05,
                vector_score: 0.0,
                keyword_score: 0.0,
            },
            entity_matches: vec![EntityMatch {
                entity_name: "Python".to_string(),
                entity_type: "SKILL".to_string(),
                confidence: 0.95,
                match_type: EntityMatchType::NameMatch,
            }],
            boosted_score: 0.06,
        }];

        let results = apply_triple_rrf(semantic, keyword, entity_aware, 10.0);

        assert!(!results.is_empty());
        // python.run should be first (boosted by entity)
        assert_eq!(results[0].base.tool_name, "python.run");
    }

    #[test]
    fn test_entity_match_types() {
        let name_match = EntityMatch {
            entity_name: "Test".to_string(),
            entity_type: "CONCEPT".to_string(),
            confidence: 1.0,
            match_type: EntityMatchType::NameMatch,
        };

        let alias_match = EntityMatch {
            entity_name: "Test".to_string(),
            entity_type: "CONCEPT".to_string(),
            confidence: 0.9,
            match_type: EntityMatchType::AliasMatch,
        };

        let meta_match = EntityMatch {
            entity_name: "Test".to_string(),
            entity_type: "CONCEPT".to_string(),
            confidence: 0.8,
            match_type: EntityMatchType::MetadataMatch,
        };

        assert!(matches!(name_match.match_type, EntityMatchType::NameMatch));
        assert!(matches!(
            alias_match.match_type,
            EntityMatchType::AliasMatch
        ));
        assert!(matches!(
            meta_match.match_type,
            EntityMatchType::MetadataMatch
        ));
    }

    #[test]
    fn test_entity_boost_sorting() {
        let results = vec![
            HybridSearchResult {
                tool_name: "low_score".to_string(),
                rrf_score: 0.01,
                vector_score: 0.1,
                keyword_score: 0.05,
            },
            HybridSearchResult {
                tool_name: "high_score".to_string(),
                rrf_score: 0.1,
                vector_score: 0.9,
                keyword_score: 0.5,
            },
        ];

        // Entity that matches high_score
        let entities = vec![EntityMatch {
            entity_name: "High Score".to_string(),
            entity_type: "CONCEPT".to_string(),
            confidence: 0.95,
            match_type: EntityMatchType::NameMatch,
        }];

        let aware_results = apply_entity_boost(results, entities, 0.5, None);

        // high_score should be first due to entity boost
        assert_eq!(aware_results[0].base.tool_name, "high_score");
    }
}
