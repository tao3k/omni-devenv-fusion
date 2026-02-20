"""Test Link Graph fixtures from test-kit."""


class TestLinkGraphFixturesDemo:
    """Demo tests for Link Graph fixtures."""

    def test_content_with_tags(self, link_graph_content_with_tags):
        """Test link_graph_content_with_tags fixture provides correct content."""
        assert "#pattern" in link_graph_content_with_tags
        assert "#rust" in link_graph_content_with_tags
        assert "#design" in link_graph_content_with_tags

    def test_content_with_wikilinks(self, link_graph_content_with_wikilinks):
        """Test link_graph_content_with_wikilinks fixture."""
        assert "[[FactoryMethod]]" in link_graph_content_with_wikilinks
        assert "[[SingletonPattern]]" in link_graph_content_with_wikilinks

    def test_content_complex(self, link_graph_content_complex):
        """Test complex content with both tags and wikilinks."""
        assert "#rust" in link_graph_content_complex
        assert "[[FactoryMethod]]" in link_graph_content_complex
        assert "[[BuilderPattern]]" in link_graph_content_complex

    def test_content_empty(self, link_graph_content_empty):
        """Test empty content fixture."""
        assert link_graph_content_empty == ""

    def test_content_no_markup(self, link_graph_content_no_markup):
        """Test content without markup."""
        assert "#" not in link_graph_content_no_markup
        assert "[[" not in link_graph_content_no_markup


class TestLinkGraphExtractors:
    """Tests for Link Graph extractor fixtures."""

    def test_link_graph_extract_function_exists(self, link_graph_extractor):
        """Test link_graph_extractor fixture provides callable."""
        assert callable(link_graph_extractor)

    def test_link_graph_extract_tags_function_exists(self, link_graph_tag_extractor):
        """Test link_graph_tag_extractor fixture provides callable."""
        assert callable(link_graph_tag_extractor)

    def test_link_graph_extract_entities_function_exists(self, link_graph_entity_extractor):
        """Test link_graph_entity_extractor fixture provides callable."""
        assert callable(link_graph_entity_extractor)

    def test_link_graph_extract_wikilinks_function_exists(self, link_graph_wikilink_extractor):
        """Test link_graph_wikilink_extractor fixture provides callable."""
        assert callable(link_graph_wikilink_extractor)

    def test_link_graph_extract_with_content(
        self, link_graph_extractor, link_graph_content_with_tags
    ):
        """Test link_graph_extract with sample content."""
        result = link_graph_extractor(
            link_graph_content_with_tags, extract_tags=True, extract_wikilinks=False
        )
        assert hasattr(result, "tags")
        assert len(result.tags) > 0

    def test_link_graph_extract_tags_only(
        self, link_graph_tag_extractor, link_graph_content_with_tags
    ):
        """Test link_graph_extract_tags with sample content."""
        tags = link_graph_tag_extractor(link_graph_content_with_tags)
        assert len(tags) > 0
        assert any(t.name == "rust" for t in tags)

    def test_link_graph_extract_entities_only(
        self, link_graph_entity_extractor, link_graph_content_complex
    ):
        """Test link_graph_extract_entities with sample content."""
        entities = link_graph_entity_extractor(link_graph_content_complex)
        assert len(entities) > 0

    def test_link_graph_extract_wikilinks_only(
        self, link_graph_wikilink_extractor, link_graph_content_with_wikilinks
    ):
        """Test link_graph_extract_wikilinks with sample content."""
        wikilinks = link_graph_wikilink_extractor(link_graph_content_with_wikilinks)
        assert len(wikilinks) > 0


class TestLinkGraphStatsExtractor:
    """Tests for Link Graph stats extractor."""

    def test_stats_function_exists(self, link_graph_stats_extractor):
        """Test link_graph_stats_extractor fixture provides callable."""
        assert callable(link_graph_stats_extractor)

    def test_stats_with_complex_content(
        self, link_graph_stats_extractor, link_graph_content_complex
    ):
        """Test stats extraction from complex content."""
        stats = link_graph_stats_extractor(link_graph_content_complex)
        assert stats is not None
        assert stats.tag_count >= 0
        assert stats.wikilink_count >= 0


class TestLinkGraphTestHelper:
    """Tests for LinkGraphTestHelper assertions."""

    def test_helper_instance(self, link_graph_test_helper):
        """Test link_graph_test_helper provides LinkGraphTestHelper instance."""
        assert link_graph_test_helper is not None

    def test_assert_tags_equal(
        self, link_graph_test_helper, link_graph_tag_extractor, link_graph_content_with_tags
    ):
        """Test assert_tags_equal assertion."""
        tags = link_graph_tag_extractor(link_graph_content_with_tags)
        tag_names = [t.name for t in tags]
        link_graph_test_helper.assert_tags_equal(tags, tag_names)

    def test_assert_entities_equal(
        self,
        link_graph_test_helper,
        link_graph_entity_extractor,
        link_graph_content_combined,
    ):
        """Test assert_entities_equal assertion."""
        entities = link_graph_entity_extractor(link_graph_content_combined)
        expected = [(e.name, e.entity_type) for e in entities]
        link_graph_test_helper.assert_entities_equal(entities, expected)

    def test_assert_extraction_complete(
        self, link_graph_test_helper, link_graph_extractor, link_graph_content_complex
    ):
        """Test assert_extraction_complete assertion."""
        result = link_graph_extractor(
            link_graph_content_complex, extract_tags=True, extract_wikilinks=True
        )
        link_graph_test_helper.assert_extraction_complete(
            result, min_tags=3, min_entities=5, min_wikilinks=5
        )

    def test_assert_no_duplicates(self, link_graph_test_helper, link_graph_entity_extractor):
        """Test assert_no_duplicates_in_entities assertion."""
        content = """
        See [[FactoryPattern]] [[FactoryPattern]] and [[FactoryPattern]] again.
        Also [[SingletonPattern]] [[SingletonPattern]].
        """
        entities = link_graph_entity_extractor(content)
        link_graph_test_helper.assert_no_duplicates_in_entities(entities)


class TestLinkGraphContentBuilder:
    """Tests for LinkGraphContentBuilder."""

    def test_builder_instance(self, link_graph_content_builder):
        """Test link_graph_content_builder provides builder instance."""
        assert link_graph_content_builder is not None

    def test_build_empty(self, link_graph_content_builder):
        """Test building empty content."""
        result = link_graph_content_builder.build()
        assert result == ""

    def test_build_with_header(self, link_graph_content_builder):
        """Test building content with header."""
        result = link_graph_content_builder.set_header("Test Title").build()
        assert "# Test Title" in result

    def test_build_with_tags(self, link_graph_content_builder):
        """Test building content with tags."""
        result = (
            link_graph_content_builder.add_tag("rust").add_tag("python").add_tag("pattern").build()
        )
        assert "#rust" in result
        assert "#python" in result
        assert "#pattern" in result

    def test_build_with_wikilinks(self, link_graph_content_builder):
        """Test building content with wikilinks."""
        result = (
            link_graph_content_builder.add_wikilink("FactoryMethod")
            .add_wikilink("SingletonPattern", "py")
            .build()
        )
        assert "[[FactoryMethod]]" in result
        assert "[[SingletonPattern#py]]" in result

    def test_build_complex(self, link_graph_content_builder):
        """Test building complex content."""
        result = (
            link_graph_content_builder.set_header("Design Patterns")
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
