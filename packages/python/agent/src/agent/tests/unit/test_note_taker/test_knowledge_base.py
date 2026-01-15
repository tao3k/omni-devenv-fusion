"""
test_knowledge_base.py
Phase 63: Tests for Knowledge Base functions.
"""

import tempfile
import importlib.util
from pathlib import Path

from common.skills_path import SKILLS_DIR


def load_script_module(script_path: Path):
    """Dynamically load a Python module from assets/skills."""
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestKnowledgeBaseSave:
    """Tests for update_knowledge_base function."""

    def test_save_to_patterns(self):
        """Test saving knowledge to patterns category."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        update_mod = load_script_module(script_path)
        update_knowledge_base = update_mod.update_knowledge_base

        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            os.chdir(tmpdir)

            try:
                result = update_knowledge_base(
                    category="patterns",
                    title="Test Pattern",
                    content="This is a test pattern content.",
                    tags=["test", "example"],
                )

                assert result["success"] is True
                assert result["category"] == "patterns"
                assert result["title"] == "Test Pattern"

                output_path = Path(result["path"])
                assert output_path.exists()

                content = output_path.read_text()
                assert "Test Pattern" in content
                assert "patterns" in content
                assert "test" in content
            finally:
                os.chdir(original_cwd)

    def test_save_to_solutions(self):
        """Test saving knowledge to solutions category."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        update_mod = load_script_module(script_path)
        update_knowledge_base = update_mod.update_knowledge_base

        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            os.chdir(tmpdir)

            try:
                result = update_knowledge_base(
                    category="solutions",
                    title="Fix for Bug X",
                    content="To fix bug X, do Y.",
                    tags=["bugfix", "known-issue"],
                )

                assert result["success"] is True
                assert result["category"] == "solutions"
            finally:
                os.chdir(original_cwd)

    def test_save_invalid_category(self):
        """Test saving with invalid category defaults to notes."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        update_mod = load_script_module(script_path)
        update_knowledge_base = update_mod.update_knowledge_base

        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            os.chdir(tmpdir)

            try:
                result = update_knowledge_base(
                    category="invalid_category",
                    title="Test",
                    content="Content",
                )

                assert result["success"] is True
                assert result["category"] == "notes"
            finally:
                os.chdir(original_cwd)

    def test_save_empty_tags(self):
        """Test saving with empty tags list."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        update_mod = load_script_module(script_path)
        update_knowledge_base = update_mod.update_knowledge_base

        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            os.chdir(tmpdir)

            try:
                result = update_knowledge_base(
                    category="notes",
                    title="No Tags",
                    content="Content without tags",
                    tags=[],
                )

                assert result["success"] is True
            finally:
                os.chdir(original_cwd)


class TestSearchNotes:
    """Tests for search_notes function."""

    def test_search_no_results(self):
        """Test searching when no matches found."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        search_mod = load_script_module(script_path)
        search_notes = search_mod.search_notes

        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            os.chdir(tmpdir)

            try:
                result = search_notes(query="nonexistent term", limit=5)

                assert result["success"] is True
                assert result["count"] == 0
            finally:
                os.chdir(original_cwd)

    def test_search_with_results(self):
        """Test searching with matches."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        update_mod = load_script_module(script_path)
        search_mod = load_script_module(script_path)
        update_knowledge_base = update_mod.update_knowledge_base
        search_notes = search_mod.search_notes

        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            os.chdir(tmpdir)

            try:
                # First, save some knowledge
                update_knowledge_base(
                    category="solutions",
                    title="Async Pattern",
                    content="Use asyncio for async operations.",
                    tags=["async", "python"],
                )

                # Then search for it
                result = search_notes(query="asyncio", limit=5)

                assert result["success"] is True
                assert result["count"] >= 1
                assert any("async" in r["tags"] or "Async" in r["title"] for r in result["results"])
            finally:
                os.chdir(original_cwd)

    def test_search_with_category_filter(self):
        """Test searching with category filter."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        update_mod = load_script_module(script_path)
        search_mod = load_script_module(script_path)
        update_knowledge_base = update_mod.update_knowledge_base
        search_notes = search_mod.search_notes

        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            os.chdir(tmpdir)

            try:
                # Save to specific category
                update_knowledge_base(
                    category="patterns",
                    title="Test Pattern",
                    content="This is a test pattern.",
                    tags=["test"],
                )

                # Search in wrong category
                result = search_notes(query="test", category="solutions", limit=5)

                assert result["success"] is True
                assert result["count"] == 0
            finally:
                os.chdir(original_cwd)


class TestParseFrontmatter:
    """Tests for _parse_frontmatter helper."""

    def test_parse_simple_frontmatter(self):
        """Test parsing simple frontmatter."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        search_mod = load_script_module(script_path)
        _parse_frontmatter = search_mod._parse_frontmatter

        content = """---
title: Test Title
category: patterns
tags: [tag1, tag2]
---

# Content
"""

        frontmatter = _parse_frontmatter(content)
        assert frontmatter["title"] == "Test Title"
        assert frontmatter["category"] == "patterns"

    def test_parse_no_frontmatter(self):
        """Test parsing content without frontmatter."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        search_mod = load_script_module(script_path)
        _parse_frontmatter = search_mod._parse_frontmatter

        content = "# Content only\nNo frontmatter here."

        frontmatter = _parse_frontmatter(content)
        assert frontmatter == {}

    def test_parse_empty_frontmatter(self):
        """Test parsing with empty frontmatter block."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        search_mod = load_script_module(script_path)
        _parse_frontmatter = search_mod._parse_frontmatter

        content = """---
---

# Content
"""

        frontmatter = _parse_frontmatter(content)
        assert frontmatter == {}


class TestGetSnippet:
    """Tests for _get_snippet helper."""

    def test_get_snippet_with_match(self):
        """Test getting snippet around a match."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        search_mod = load_script_module(script_path)
        _get_snippet = search_mod._get_snippet

        content = "This is some test content with the keyword in the middle of the text."
        snippet = _get_snippet(content, "keyword", context_chars=20)

        assert "keyword" in snippet
        assert len(snippet) < len(content)

    def test_get_snippet_no_match(self):
        """Test getting snippet when no match."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        search_mod = load_script_module(script_path)
        _get_snippet = search_mod._get_snippet

        content = "This is some content."
        snippet = _get_snippet(content, "nonexistent", context_chars=50)

        assert snippet in content

    def test_get_snippet_at_start(self):
        """Test getting snippet at start of content."""
        script_path = SKILLS_DIR(skill="note_taker", filename="scripts/update_knowledge_base.py")
        search_mod = load_script_module(script_path)
        _get_snippet = search_mod._get_snippet

        content = "Keyword at the start of content."
        snippet = _get_snippet(content, "Keyword", context_chars=10)

        assert snippet.startswith("Keyword")
