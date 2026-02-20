"""Link graph fixtures for testing markdown extraction.

Provides pytest fixtures for:
- Extraction results with different content types
- Tag extraction tests
- Entity and wikilink extraction tests
- Statistics validation
- Sample markdown content

Usage:
    def test_with_link_graph(link_graph_content_fixture):
        result = link_graph_extract(
            link_graph_content_fixture,
            extract_tags=True,
            extract_wikilinks=True,
        )
        assert len(result.tags) == 3

    def test_entity_extraction(link_graph_entity_fixture):
        assert link_graph_entity_fixture.name == "FactoryPattern"
        assert link_graph_entity_fixture.entity_type == "py"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pytest

# =============================================================================
# Sample Content Fixtures
# =============================================================================


@pytest.fixture
def link_graph_content_with_tags() -> str:
    """Markdown with various tag formats."""
    return """
# Rust Design Patterns

This is a document about #pattern and #rust programming.
Multiple tags like #design, #factory, and #singleton are used here.
Also #multi-word tags work correctly.
"""


@pytest.fixture
def link_graph_content_with_wikilinks() -> str:
    """Markdown with various wikilink formats."""
    return """
See [[FactoryMethod]] for object creation.
Also [[SingletonPattern]] for single instance.
Typed reference: [[Entity#rust]].
With alias: [[FactoryPattern|Factory]].
Combined: [[Combined#pattern|Alias]].
"""


@pytest.fixture
def link_graph_content_combined() -> str:
    """Markdown with both tags and wikilinks."""
    return """
# Rust

See [[FactoryMethod]] for details.
Also [[SingletonPattern#py]] for single instance.

Tags: #rust #python #pattern
"""


@pytest.fixture
def link_graph_content_empty() -> str:
    """Empty markdown content."""
    return ""


@pytest.fixture
def link_graph_content_no_markup() -> str:
    """Markdown without any link graph markup."""
    return """Just regular text without any special markup.
This has no tags or wikilinks at all.
"""


@pytest.fixture
def link_graph_content_duplicates() -> str:
    """Markdown with duplicate wikilinks (tests deduplication)."""
    return """
See [[FactoryPattern]] [[FactoryPattern]] and [[FactoryPattern]] again.
Also [[SingletonPattern]] [[SingletonPattern]].
"""


@pytest.fixture
def link_graph_content_complex() -> str:
    """Complex markdown with mixed content."""
    return """# Design Patterns in Rust

## Creational Patterns

[[FactoryMethod]] defines an interface for creating objects.
[[AbstractFactory]] provides an interface for creating families of objects.
[[BuilderPattern]] separates construction from representation.
[[SingletonPattern]] ensures only one instance exists.

## Structural Patterns

[[AdapterPattern]] converts interface of class to another.
[[BridgePattern]] decouples abstraction from implementation.
[[DecoratorPattern]] adds behavior dynamically.

## Tags

#rust #design #pattern #creational #structural #behavioral

## References

See also [[GoF]] for original patterns.
[[DesignPatternsBook#author]] mentions these patterns.
"""


# =============================================================================
# Extraction Result Fixtures
# =============================================================================


@pytest.fixture
def link_graph_extraction_simple() -> dict[str, Any]:
    """Simple extraction result for basic tests."""
    return {
        "tags": ["rust", "python"],
        "entities": [
            {"name": "FactoryMethod", "entity_type": None, "original": "[[FactoryMethod]]"},
            {"name": "SingletonPattern", "entity_type": None, "original": "[[SingletonPattern]]"},
        ],
        "wikilinks": ["FactoryMethod", "SingletonPattern"],
    }


@pytest.fixture
def link_graph_extraction_typed() -> dict[str, Any]:
    """Extraction result with typed entities."""
    return {
        "tags": ["rust", "pattern"],
        "entities": [
            {"name": "FactoryMethod", "entity_type": "rust", "original": "[[FactoryMethod#rust]]"},
            {
                "name": "SingletonPattern",
                "entity_type": "py",
                "original": "[[SingletonPattern#py]]",
            },
            {
                "name": "BuilderPattern",
                "entity_type": "pattern",
                "original": "[[BuilderPattern#pattern]]",
            },
        ],
        "wikilinks": ["FactoryMethod#rust", "SingletonPattern#py", "BuilderPattern#pattern"],
    }


# =============================================================================
# Component Fixtures
# =============================================================================


@dataclass
class _Tag:
    name: str


@dataclass
class _Entity:
    name: str
    entity_type: str | None
    original: str


@dataclass
class _ExtractionResult:
    tags: list[_Tag]
    entities: list[_Entity]
    wikilinks: list[str]


@dataclass
class _Stats:
    tag_count: int
    wikilink_count: int
    unique_entities: int


def _extract_tags_py(content: str) -> list[_Tag]:
    return [_Tag(name=t) for t in re.findall(r"(?<!\\w)#([A-Za-z0-9_-]+)", content)]


def _extract_wikilinks_py(content: str) -> list[str]:
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)


def _extract_entities_py(content: str) -> list[_Entity]:
    entities: list[_Entity] = []
    seen: set[tuple[str, str | None]] = set()
    for item in _extract_wikilinks_py(content):
        if "#" in item:
            name, entity_type = item.split("#", 1)
        else:
            name, entity_type = item, None
        key = (name, entity_type)
        if key in seen:
            continue
        seen.add(key)
        entities.append(_Entity(name=name, entity_type=entity_type, original=f"[[{item}]]"))
    return entities


@pytest.fixture
def link_graph_extractor() -> Any:
    """Provide stable extraction function for tests."""

    def _extract(content: str, extract_tags: bool = True, extract_wikilinks: bool = True) -> Any:
        tags = _extract_tags_py(content) if extract_tags else []
        entities = _extract_entities_py(content) if extract_wikilinks else []
        wikilinks = _extract_wikilinks_py(content) if extract_wikilinks else []
        return _ExtractionResult(tags=tags, entities=entities, wikilinks=wikilinks)

    return _extract


@pytest.fixture
def link_graph_tag_extractor() -> Any:
    """Provide tag extraction function for tests."""
    return _extract_tags_py


@pytest.fixture
def link_graph_entity_extractor() -> Any:
    """Provide entity extraction function for tests."""
    return _extract_entities_py


@pytest.fixture
def link_graph_wikilink_extractor() -> Any:
    """Provide wikilink extraction function for tests."""
    return _extract_wikilinks_py


@pytest.fixture
def link_graph_stats_extractor() -> Any:
    """Provide stats extraction function for tests."""

    def _stats(content: str) -> _Stats:
        tags = _extract_tags_py(content)
        wikilinks = _extract_wikilinks_py(content)
        entities = _extract_entities_py(content)
        return _Stats(
            tag_count=len(tags),
            wikilink_count=len(wikilinks),
            unique_entities=len({(e.name, e.entity_type) for e in entities}),
        )

    return _stats


# =============================================================================
# Test Helper Class
# =============================================================================


class LinkGraphTestHelper:
    """Helper class for link graph testing.

    Provides common assertions and utilities for testing link graph extraction.
    """

    @staticmethod
    def assert_tags_equal(
        actual: list[Any],
        expected_names: list[str],
    ) -> None:
        """Assert that extracted tags match expected values."""
        actual_names = [t.name for t in actual]
        assert actual_names == expected_names, f"Expected tags {expected_names}, got {actual_names}"

    @staticmethod
    def assert_entities_equal(
        actual: list[Any],
        expected: list[tuple[str, str | None]],
    ) -> None:
        """Assert that extracted entities match expected values.

        Args:
            actual: List of PyLinkGraphEntityRef objects
            expected: List of (name, entity_type) tuples
        """
        assert len(actual) == len(expected), f"Expected {len(expected)} entities, got {len(actual)}"

        for i, (entity, (exp_name, exp_type)) in enumerate(zip(actual, expected, strict=False)):
            assert entity.name == exp_name, (
                f"Entity {i}: expected name '{exp_name}', got '{entity.name}'"
            )
            assert entity.entity_type == exp_type, (
                f"Entity {i}: expected type '{exp_type}', got '{entity.entity_type}'"
            )

    @staticmethod
    def assert_wikilinks_equal(
        actual: list[str],
        expected: list[str],
    ) -> None:
        """Assert that extracted wikilinks match expected values."""
        assert actual == expected, f"Expected wikilinks {expected}, got {actual}"

    @staticmethod
    def assert_extraction_complete(
        result: Any,
        min_tags: int = 0,
        min_entities: int = 0,
        min_wikilinks: int = 0,
    ) -> None:
        """Assert that extraction has minimum required items."""
        assert len(result.tags) >= min_tags, (
            f"Expected at least {min_tags} tags, got {len(result.tags)}"
        )
        assert len(result.entities) >= min_entities, (
            f"Expected at least {min_entities} entities, got {len(result.entities)}"
        )
        assert len(result.wikilinks) >= min_wikilinks, (
            f"Expected at least {min_wikilinks} wikilinks, got {len(result.wikilinks)}"
        )

    @staticmethod
    def assert_stats_valid(
        stats: Any,
        expected_tag_count: int | None = None,
        expected_wikilink_count: int | None = None,
    ) -> None:
        """Assert that stats are valid."""
        assert stats.tag_count >= 0
        assert stats.wikilink_count >= 0
        assert stats.unique_entities >= 0
        assert stats.unique_entities <= stats.wikilink_count

        if expected_tag_count is not None:
            assert stats.tag_count == expected_tag_count, (
                f"Expected tag_count {expected_tag_count}, got {stats.tag_count}"
            )

        if expected_wikilink_count is not None:
            assert stats.wikilink_count == expected_wikilink_count, (
                f"Expected wikilink_count {expected_wikilink_count}, got {stats.wikilink_count}"
            )

    @staticmethod
    def assert_no_duplicates_in_entities(entities: list[Any]) -> None:
        """Assert that entities have no duplicate names."""
        names = [e.name for e in entities]
        assert len(names) == len(set(names)), f"Found duplicate entity names in {names}"

    @staticmethod
    def create_entity(
        name: str,
        entity_type: str | None = None,
        original: str | None = None,
    ) -> Any:
        """Create a PyLinkGraphEntityRef for testing."""
        if original is None:
            original = f"[[{name}#{entity_type}]]" if entity_type else f"[[{name}]]"
        try:
            from omni_core_rs import PyLinkGraphEntityRef

            return PyLinkGraphEntityRef(name, entity_type, original)
        except Exception:
            return _Entity(name=name, entity_type=entity_type, original=original)

    @staticmethod
    def create_tag(name: str) -> Any:
        """Create a PyLinkGraphTag for testing."""
        return _Tag(name=name)


@pytest.fixture
def link_graph_test_helper() -> LinkGraphTestHelper:
    """Provide a link graph test helper instance."""
    return LinkGraphTestHelper()


# =============================================================================
# Test Content Builders
# =============================================================================


class LinkGraphContentBuilder:
    """Builder for creating test markdown content.

    Usage:
        content = (LinkGraphContentBuilder()
            .add_tag("rust")
            .add_tag("python")
            .add_wikilink("FactoryMethod")
            .add_wikilink("SingletonPattern#py")
            .build())

        result = link_graph_extract(content, extract_tags=True, extract_wikilinks=True)
    """

    def __init__(self):
        self._tags: list[str] = []
        self._wikilinks: list[tuple[str, str | None]] = []  # (target, type)
        self._header: str = ""
        self._body: str = ""

    def set_header(self, text: str) -> LinkGraphContentBuilder:
        """Set the header (H1)."""
        self._header = text
        return self

    def add_tag(self, name: str) -> LinkGraphContentBuilder:
        """Add a tag."""
        self._tags.append(name)
        return self

    def add_tags(self, *names: str) -> LinkGraphContentBuilder:
        """Add multiple tags."""
        self._tags.extend(names)
        return self

    def add_wikilink(
        self,
        target: str,
        entity_type: str | None = None,
    ) -> LinkGraphContentBuilder:
        """Add a wikilink."""
        self._wikilinks.append((target, entity_type))
        return self

    def add_body(self, text: str) -> LinkGraphContentBuilder:
        """Add body text."""
        self._body += text + "\n"
        return self

    def build(self) -> str:
        """Build the markdown content."""
        lines = []

        if self._header:
            lines.append(f"# {self._header}")

        if self._tags:
            tags_line = " ".join(f"#{t}" for t in self._tags)
            lines.append(tags_line)

        if self._wikilinks:
            for target, entity_type in self._wikilinks:
                if entity_type:
                    lines.append(f"See [[{target}#{entity_type}]] for details.")
                else:
                    lines.append(f"See [[{target}]] for details.")

        if self._body:
            lines.append(self._body)

        return "\n".join(lines)


@pytest.fixture
def link_graph_content_builder() -> LinkGraphContentBuilder:
    """Provide a link graph content builder instance."""
    return LinkGraphContentBuilder()


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "LinkGraphContentBuilder",
    "LinkGraphTestHelper",
    # Builder
    "link_graph_content_builder",
    "link_graph_content_combined",
    "link_graph_content_complex",
    "link_graph_content_duplicates",
    "link_graph_content_empty",
    "link_graph_content_no_markup",
    # Content fixtures
    "link_graph_content_with_tags",
    "link_graph_content_with_wikilinks",
    "link_graph_entity_extractor",
    # Extraction result fixtures
    "link_graph_extraction_simple",
    "link_graph_extraction_typed",
    # Component fixtures
    "link_graph_extractor",
    "link_graph_stats_extractor",
    "link_graph_tag_extractor",
    # Helper
    "link_graph_test_helper",
    "link_graph_wikilink_extractor",
]
