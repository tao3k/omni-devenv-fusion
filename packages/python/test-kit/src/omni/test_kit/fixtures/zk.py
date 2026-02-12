"""ZK (Zettelkasten) fixtures for testing markdown extraction.

Provides pytest fixtures for:
- ZkExtraction results with different content types
- Tag extraction tests
- Entity/wikilink extraction tests
- Statistics validation
- Sample markdown content

Usage:
    def test_with_zk(zk_content_fixture):
        result = zk_extract(zk_content_fixture, extract_tags=True, extract_wikilinks=True)
        assert len(result.tags) == 3

    def test_entity_extraction(zk_entity_fixture):
        assert zk_entity_fixture.name == "FactoryPattern"
        assert zk_entity_fixture.entity_type == "py"
"""

from __future__ import annotations

import pytest
from typing import Any
from dataclasses import dataclass
import re


# =============================================================================
# Sample Content Fixtures
# =============================================================================


@pytest.fixture
def zk_content_with_tags() -> str:
    """Markdown with various tag formats."""
    return """
# Rust Design Patterns

This is a document about #pattern and #rust programming.
Multiple tags like #design, #factory, and #singleton are used here.
Also #multi-word tags work correctly.
"""


@pytest.fixture
def zk_content_with_wikilinks() -> str:
    """Markdown with various wikilink formats."""
    return """
See [[FactoryMethod]] for object creation.
Also [[SingletonPattern]] for single instance.
Typed reference: [[Entity#rust]].
With alias: [[FactoryPattern|Factory]].
Combined: [[Combined#pattern|Alias]].
"""


@pytest.fixture
def zk_content_combined() -> str:
    """Markdown with both tags and wikilinks."""
    return """
# Rust

See [[FactoryMethod]] for details.
Also [[SingletonPattern#py]] for single instance.

Tags: #rust #python #pattern
"""


@pytest.fixture
def zk_content_empty() -> str:
    """Empty markdown content."""
    return ""


@pytest.fixture
def zk_content_no_markup() -> str:
    """Markdown without any zk markup."""
    return """Just regular text without any special markup.
This has no tags or wikilinks at all.
"""


@pytest.fixture
def zk_content_duplicates() -> str:
    """Markdown with duplicate wikilinks (tests deduplication)."""
    return """
See [[FactoryPattern]] [[FactoryPattern]] and [[FactoryPattern]] again.
Also [[SingletonPattern]] [[SingletonPattern]].
"""


@pytest.fixture
def zk_content_complex() -> str:
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
def zk_extraction_simple() -> dict[str, Any]:
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
def zk_extraction_typed() -> dict[str, Any]:
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
def zk_extractor() -> Any:
    """Provide stable extraction function for tests."""

    def _extract(content: str, extract_tags: bool = True, extract_wikilinks: bool = True) -> Any:
        tags = _extract_tags_py(content) if extract_tags else []
        entities = _extract_entities_py(content) if extract_wikilinks else []
        wikilinks = _extract_wikilinks_py(content) if extract_wikilinks else []
        return _ExtractionResult(tags=tags, entities=entities, wikilinks=wikilinks)

    return _extract


@pytest.fixture
def zk_tag_extractor() -> Any:
    """Provide tag extraction function for tests."""
    return _extract_tags_py


@pytest.fixture
def zk_entity_extractor() -> Any:
    """Provide entity extraction function for tests."""
    return _extract_entities_py


@pytest.fixture
def zk_wikilink_extractor() -> Any:
    """Provide wikilink extraction function for tests."""
    return _extract_wikilinks_py


@pytest.fixture
def zk_stats_extractor() -> Any:
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


class ZkTestHelper:
    """Helper class for ZK testing.

    Provides common assertions and utilities for testing zk extraction.
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
            actual: List of PyZkEntityRef objects
            expected: List of (name, entity_type) tuples
        """
        assert len(actual) == len(expected), f"Expected {len(expected)} entities, got {len(actual)}"

        for i, (entity, (exp_name, exp_type)) in enumerate(zip(actual, expected)):
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
        """Create a PyZkEntityRef for testing."""
        if original is None:
            if entity_type:
                original = f"[[{name}#{entity_type}]]"
            else:
                original = f"[[{name}]]"
        try:
            from omni_core_rs import PyZkEntityRef

            return PyZkEntityRef(name, entity_type, original)
        except Exception:
            return _Entity(name=name, entity_type=entity_type, original=original)

    @staticmethod
    def create_tag(name: str) -> Any:
        """Create a PyZkTag for testing."""
        return _Tag(name=name)


@pytest.fixture
def zk_test_helper() -> ZkTestHelper:
    """Provide a ZK test helper instance."""
    return ZkTestHelper()


# =============================================================================
# Test Content Builders
# =============================================================================


class ZkContentBuilder:
    """Builder for creating test markdown content.

    Usage:
        content = (ZkContentBuilder()
            .add_tag("rust")
            .add_tag("python")
            .add_wikilink("FactoryMethod")
            .add_wikilink("SingletonPattern#py")
            .build())

        result = zk_extract(content, extract_tags=True, extract_wikilinks=True)
    """

    def __init__(self):
        self._tags: list[str] = []
        self._wikilinks: list[tuple[str, str | None]] = []  # (target, type)
        self._header: str = ""
        self._body: str = ""

    def set_header(self, text: str) -> "ZkContentBuilder":
        """Set the header (H1)."""
        self._header = text
        return self

    def add_tag(self, name: str) -> "ZkContentBuilder":
        """Add a tag."""
        self._tags.append(name)
        return self

    def add_tags(self, *names: str) -> "ZkContentBuilder":
        """Add multiple tags."""
        self._tags.extend(names)
        return self

    def add_wikilink(
        self,
        target: str,
        entity_type: str | None = None,
    ) -> "ZkContentBuilder":
        """Add a wikilink."""
        self._wikilinks.append((target, entity_type))
        return self

    def add_body(self, text: str) -> "ZkContentBuilder":
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
def zk_content_builder() -> ZkContentBuilder:
    """Provide a ZK content builder instance."""
    return ZkContentBuilder()


# =============================================================================
# Export
# =============================================================================

__all__ = [
    # Content fixtures
    "zk_content_with_tags",
    "zk_content_with_wikilinks",
    "zk_content_combined",
    "zk_content_empty",
    "zk_content_no_markup",
    "zk_content_duplicates",
    "zk_content_complex",
    # Extraction result fixtures
    "zk_extraction_simple",
    "zk_extraction_typed",
    # Component fixtures
    "zk_extractor",
    "zk_tag_extractor",
    "zk_entity_extractor",
    "zk_wikilink_extractor",
    "zk_stats_extractor",
    # Helper
    "zk_test_helper",
    "ZkTestHelper",
    # Builder
    "zk_content_builder",
    "ZkContentBuilder",
]
