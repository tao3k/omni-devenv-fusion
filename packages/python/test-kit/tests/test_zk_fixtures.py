"""Test ZK fixtures from test-kit."""

import pytest


class TestZKFixturesDemo:
    """Demo tests for ZK fixtures."""

    def test_content_with_tags(self, zk_content_with_tags):
        """Test zk_content_with_tags fixture provides correct content."""
        assert "#pattern" in zk_content_with_tags
        assert "#rust" in zk_content_with_tags
        assert "#design" in zk_content_with_tags

    def test_content_with_wikilinks(self, zk_content_with_wikilinks):
        """Test zk_content_with_wikilinks fixture."""
        assert "[[FactoryMethod]]" in zk_content_with_wikilinks
        assert "[[SingletonPattern]]" in zk_content_with_wikilinks

    def test_content_complex(self, zk_content_complex):
        """Test complex content with both tags and wikilinks."""
        assert "#rust" in zk_content_complex
        assert "[[FactoryMethod]]" in zk_content_complex
        assert "[[BuilderPattern]]" in zk_content_complex

    def test_content_empty(self, zk_content_empty):
        """Test empty content fixture."""
        assert zk_content_empty == ""

    def test_content_no_markup(self, zk_content_no_markup):
        """Test content without markup."""
        assert "#" not in zk_content_no_markup
        assert "[[" not in zk_content_no_markup


class TestZKExtractors:
    """Tests for ZK extractor fixtures."""

    def test_zk_extract_function_exists(self, zk_extractor):
        """Test zk_extractor fixture provides callable."""
        assert callable(zk_extractor)

    def test_zk_extract_tags_function_exists(self, zk_tag_extractor):
        """Test zk_tag_extractor fixture provides callable."""
        assert callable(zk_tag_extractor)

    def test_zk_extract_entities_function_exists(self, zk_entity_extractor):
        """Test zk_entity_extractor fixture provides callable."""
        assert callable(zk_entity_extractor)

    def test_zk_extract_wikilinks_function_exists(self, zk_wikilink_extractor):
        """Test zk_wikilink_extractor fixture provides callable."""
        assert callable(zk_wikilink_extractor)

    def test_zk_extract_with_content(self, zk_extractor, zk_content_with_tags):
        """Test zk_extract with sample content."""
        result = zk_extractor(zk_content_with_tags, extract_tags=True, extract_wikilinks=False)
        assert hasattr(result, "tags")
        assert len(result.tags) > 0

    def test_zk_extract_tags_only(self, zk_tag_extractor, zk_content_with_tags):
        """Test zk_extract_tags with sample content."""
        tags = zk_tag_extractor(zk_content_with_tags)
        assert len(tags) > 0
        assert any(t.name == "rust" for t in tags)

    def test_zk_extract_entities_only(self, zk_entity_extractor, zk_content_complex):
        """Test zk_extract_entities with sample content."""
        entities = zk_entity_extractor(zk_content_complex)
        assert len(entities) > 0

    def test_zk_extract_wikilinks_only(self, zk_wikilink_extractor, zk_content_with_wikilinks):
        """Test zk_extract_wikilinks with sample content."""
        wikilinks = zk_wikilink_extractor(zk_content_with_wikilinks)
        assert len(wikilinks) > 0


class TestZKStatsExtractor:
    """Tests for ZK stats extractor."""

    def test_stats_function_exists(self, zk_stats_extractor):
        """Test zk_stats_extractor fixture provides callable."""
        assert callable(zk_stats_extractor)

    def test_stats_with_complex_content(self, zk_stats_extractor, zk_content_complex):
        """Test stats extraction from complex content."""
        stats = zk_stats_extractor(zk_content_complex)
        assert stats is not None
        assert stats.tag_count >= 0
        assert stats.wikilink_count >= 0


class TestZKTestHelper:
    """Tests for ZkTestHelper assertions."""

    def test_helper_instance(self, zk_test_helper):
        """Test zk_test_helper provides ZkTestHelper instance."""
        assert zk_test_helper is not None

    def test_assert_tags_equal(self, zk_test_helper, zk_tag_extractor, zk_content_with_tags):
        """Test assert_tags_equal assertion."""
        tags = zk_tag_extractor(zk_content_with_tags)
        tag_names = [t.name for t in tags]
        zk_test_helper.assert_tags_equal(tags, tag_names)

    def test_assert_entities_equal(self, zk_test_helper, zk_entity_extractor, zk_content_combined):
        """Test assert_entities_equal assertion."""
        entities = zk_entity_extractor(zk_content_combined)
        expected = [(e.name, e.entity_type) for e in entities]
        zk_test_helper.assert_entities_equal(entities, expected)

    def test_assert_extraction_complete(self, zk_test_helper, zk_extractor, zk_content_complex):
        """Test assert_extraction_complete assertion."""
        result = zk_extractor(zk_content_complex, extract_tags=True, extract_wikilinks=True)
        zk_test_helper.assert_extraction_complete(
            result, min_tags=3, min_entities=5, min_wikilinks=5
        )

    def test_assert_no_duplicates(self, zk_test_helper, zk_entity_extractor):
        """Test assert_no_duplicates_in_entities assertion."""
        content = """
        See [[FactoryPattern]] [[FactoryPattern]] and [[FactoryPattern]] again.
        Also [[SingletonPattern]] [[SingletonPattern]].
        """
        entities = zk_entity_extractor(content)
        zk_test_helper.assert_no_duplicates_in_entities(entities)


class TestZKContentBuilder:
    """Tests for ZkContentBuilder."""

    def test_builder_instance(self, zk_content_builder):
        """Test zk_content_builder provides builder instance."""
        assert zk_content_builder is not None

    def test_build_empty(self, zk_content_builder):
        """Test building empty content."""
        result = zk_content_builder.build()
        assert result == ""

    def test_build_with_header(self, zk_content_builder):
        """Test building content with header."""
        result = zk_content_builder.set_header("Test Title").build()
        assert "# Test Title" in result

    def test_build_with_tags(self, zk_content_builder):
        """Test building content with tags."""
        result = zk_content_builder.add_tag("rust").add_tag("python").add_tag("pattern").build()
        assert "#rust" in result
        assert "#python" in result
        assert "#pattern" in result

    def test_build_with_wikilinks(self, zk_content_builder):
        """Test building content with wikilinks."""
        result = (
            zk_content_builder.add_wikilink("FactoryMethod")
            .add_wikilink("SingletonPattern", "py")
            .build()
        )
        assert "[[FactoryMethod]]" in result
        assert "[[SingletonPattern#py]]" in result

    def test_build_complex(self, zk_content_builder):
        """Test building complex content."""
        result = (
            zk_content_builder.set_header("Design Patterns")
            .add_tag("rust")
            .add_tag("pattern")
            .add_wikilink("FactoryMethod")
            .add_wikilink("BuilderPattern", "rust")
            .add_body("Some content about design patterns.")
            .build()
        )

        assert "# Design Patterns" in result
        assert "#rust" in result
        assert "#pattern" in result
        assert "[[FactoryMethod]]" in result
        assert "[[BuilderPattern#rust]]" in result
        assert "Some content" in result
