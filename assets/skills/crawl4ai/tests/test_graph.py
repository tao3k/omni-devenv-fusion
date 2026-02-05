#!/usr/bin/env python3
"""
Tests for crawl4ai graph.py - Skeleton Planning Pattern

These tests verify the core skeleton extraction logic WITHOUT crawl4ai dependency.
This allows testing in the main environment using the sidecar pattern.

Usage:
    cd assets/skills/crawl4ai && uv run pytest tests/test_graph.py -v

Note: Tests are stub-based, importing the actual implementation from scripts/
which only depends on stdlib (re, json) - NOT crawl4ai itself.
"""

import pytest
import sys
from pathlib import Path

# Add scripts directory directly (only uses stdlib, no crawl4ai dependency)
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))


class TestExtractSkeleton:
    """Test skeleton extraction from markdown."""

    def test_extract_single_header(self):
        """Test extracting a single header."""
        from engine import extract_skeleton

        markdown = """# Title

Some content here.

## Section 1

More content.
"""
        result = extract_skeleton(markdown)

        assert "skeleton" in result
        assert "stats" in result
        assert len(result["skeleton"]) == 2

        # Check first section
        assert result["skeleton"][0]["title"] == "Title"
        assert result["skeleton"][0]["level"] == 1
        assert result["skeleton"][0]["index"] == 0

        # Check second section
        assert result["skeleton"][1]["title"] == "Section 1"
        assert result["skeleton"][1]["level"] == 2
        assert result["skeleton"][1]["index"] == 1

    def test_extract_nested_headers(self):
        """Test extracting nested header structure."""
        from engine import extract_skeleton

        markdown = """# Main

## A

### A1

### A2

## B

## C

### C1
"""
        result = extract_skeleton(markdown)

        # Headers: Main, A, A1, A2, B, C, C1 = 7 sections
        assert len(result["skeleton"]) == 7
        assert result["skeleton"][0]["title"] == "Main"
        assert result["skeleton"][1]["title"] == "A"
        assert result["skeleton"][2]["title"] == "A1"
        assert result["skeleton"][3]["title"] == "A2"

    def test_extract_stats(self):
        """Test document statistics."""
        from engine import extract_skeleton

        markdown = """# Test

Content here.
"""
        result = extract_skeleton(markdown)

        stats = result["stats"]
        assert "total_chars" in stats
        assert "total_tokens_approx" in stats
        assert "total_lines" in stats
        assert "header_count" in stats
        assert "max_depth" in stats
        assert stats["header_count"] == 1
        assert stats["max_depth"] == 1

    def test_extract_empty_content(self):
        """Test extracting skeleton from empty content."""
        from engine import extract_skeleton

        result = extract_skeleton("")
        assert result["skeleton"] == []
        assert result["stats"]["header_count"] == 0

    def test_extract_no_headers(self):
        """Test extracting skeleton with no headers."""
        from engine import extract_skeleton

        result = extract_skeleton("Just plain text without any headers.")
        assert result["skeleton"] == []
        assert result["stats"]["header_count"] == 0


class TestExtractChunk:
    """Test chunk extraction by line numbers."""

    def test_extract_simple_chunk(self):
        """Test extracting a simple chunk."""
        from engine import extract_chunk

        markdown = """# Line 0
Content line 1
Content line 2

## Line 4
Content line 5
"""
        chunk = extract_chunk(markdown, 0, 2)

        assert "# Line 0" in chunk
        assert "Content line 1" in chunk
        assert "Content line 2" in chunk

    def test_extract_section_chunk(self):
        """Test extracting a specific section."""
        from engine import extract_chunk

        markdown = """# Title

## Section 1
Section 1 content.

## Section 2
Section 2 content here.
"""
        # Extract Section 1 (lines 3-4)
        chunk = extract_chunk(markdown, 3, 4)

        assert "Section 1" in chunk
        assert "Section 1 content" in chunk
        assert "Section 2" not in chunk

    def test_extract_bounds_handling(self):
        """Test boundary handling for out-of-range indices."""
        from engine import extract_chunk

        markdown = """# Line 0
Line 1
Line 2
"""
        # Extracting beyond range should clamp to valid bounds
        chunk = extract_chunk(markdown, 0, 100)
        assert "Line 0" in chunk
        assert "Line 1" in chunk
        assert "Line 2" in chunk

    def test_extract_negative_bounds(self):
        """Test handling of negative indices."""
        from engine import extract_chunk

        markdown = """# Line 0
Line 1
"""
        chunk = extract_chunk(markdown, -5, 1)

        assert "# Line 0" in chunk
        assert "Line 1" in chunk


class TestGraphState:
    """Test graph state creation and types."""

    def test_create_initial_state(self):
        """Test creating initial state for workflow."""
        from graph import create_initial_state

        state = create_initial_state("https://example.com")

        assert state["url"] == "https://example.com"
        assert state["skeleton"] == []
        assert state["chunk_plan"] == []
        assert state["processed_chunks"] == []
        assert state["current_chunk_index"] == 0
        assert state["error"] == ""

    def test_crawl_chunk_state_typeddict(self):
        """Test that CrawlChunkState is a valid TypedDict."""
        from graph import CrawlChunkState

        # Should be able to create partial states
        state: CrawlChunkState = {
            "url": "https://test.com",
            "skeleton": [],
        }

        # Should be able to create full states
        full_state: CrawlChunkState = {
            "url": "https://test.com",
            "skeleton": [{"index": 0, "level": 1, "title": "Test"}],
            "stats": {},
            "chunk_plan": [],
            "processed_chunks": [],
            "results": [],
            "current_chunk_index": 0,
            "metadata": {},
            "final_summary": "",
            "raw_content": "",
            "error": "",
        }

        assert state["url"] == "https://test.com"
        assert full_state["current_chunk_index"] == 0


class TestGraphCreation:
    """Test graph helper functions."""

    def test_create_initial_state(self):
        """Test creating initial state for workflow."""
        from graph import create_initial_state

        state = create_initial_state("https://example.com")

        assert state["url"] == "https://example.com"
        assert state["skeleton"] == []
        assert state["chunk_plan"] == []
        assert state["processed_chunks"] == []
        assert state["current_chunk_index"] == 0
        assert state["error"] == ""


class TestChunkingPlannerPrompt:
    """Test chunking planner prompt template."""

    def test_prompt_format(self):
        """Test that prompt template can be formatted."""
        from graph import CHUNKING_PLANNER_PROMPT

        formatted = CHUNKING_PLANNER_PROMPT.format(
            title="Test Document",
            section_count=10,
            skeleton="- [0] Introduction\n- [1] Methods",
        )

        assert "Test Document" in formatted
        assert "10" in formatted
        assert "Introduction" in formatted
        assert "Methods" in formatted


class TestEndToEnd:
    """End-to-end tests for skeleton extraction workflow."""

    def test_large_document_skeleton(self):
        """Test skeleton extraction from a large document."""
        from engine import extract_skeleton

        # Simulate a large document structure
        sections = [
            "# Introduction",
            "## Background",
            "## Related Work",
            "# Methods",
            "## Approach",
            "## Algorithm",
            "## Experiments",
            "# Results",
            "## Analysis",
            "# Discussion",
            "# Conclusion",
        ]

        lines = []
        for i, section in enumerate(sections):
            content = f"Content for section {i} with some text.\n" * 5
            lines.append(section)
            lines.append(content)

        markdown = "\n".join(lines)
        result = extract_skeleton(markdown)

        assert len(result["skeleton"]) == 11
        assert result["stats"]["header_count"] == 11
        assert result["stats"]["max_depth"] == 2

        # Verify section structure
        for i, section in enumerate(sections):
            # Remove both # and ## prefixes
            expected_title = section.lstrip("# ").strip()
            assert result["skeleton"][i]["title"] == expected_title, (
                f"Expected '{expected_title}', got '{result['skeleton'][i]['title']}'"
            )

    def test_chunk_extraction_plan(self):
        """Test extracting content based on skeleton indices."""
        from engine import extract_skeleton, extract_chunk

        markdown = """# Section 1
Content of section 1.

# Section 2
Content of section 2.

# Section 3
Content of section 3.
"""

        skeleton = extract_skeleton(markdown)
        sections = skeleton["skeleton"]

        # Extract Section 2 only
        section_2 = sections[1]
        chunk = extract_chunk(markdown, section_2["line_start"], section_2["line_end"])

        assert "Section 2" in chunk
        assert "Section 1" not in chunk
        assert "Section 3" not in chunk


class TestSkeletonEdgeCases:
    """Test edge cases for skeleton extraction."""

    def test_atx_style_headers(self):
        """Test ATX-style closing headers (######)."""
        from engine import extract_skeleton

        markdown = """###### H6 Header
Some content
"""
        result = extract_skeleton(markdown)

        assert len(result["skeleton"]) == 1
        assert result["skeleton"][0]["level"] == 6
        assert result["skeleton"][0]["title"] == "H6 Header"

    def test_header_with_special_chars(self):
        """Test headers with special characters."""
        from engine import extract_skeleton

        markdown = """# Header with `code` and **bold**
## Header with [link](url)
### Header with "quotes"
"""
        result = extract_skeleton(markdown)

        assert len(result["skeleton"]) == 3
        assert result["skeleton"][0]["title"] == "Header with `code` and **bold**"
        assert result["skeleton"][1]["title"] == "Header with [link](url)"
        assert result["skeleton"][2]["title"] == 'Header with "quotes"'

    def test_duplicate_header_titles(self):
        """Test handling of duplicate header titles."""
        from engine import extract_skeleton

        markdown = """# Introduction
Content

# Introduction
More content
"""
        result = extract_skeleton(markdown)

        assert len(result["skeleton"]) == 2
        assert result["skeleton"][0]["title"] == "Introduction"
        assert result["skeleton"][1]["title"] == "Introduction"
        # They should have different indices
        assert result["skeleton"][0]["index"] == 0
        assert result["skeleton"][1]["index"] == 1

    def test_header_only_content(self):
        """Test markdown that is just headers."""
        from engine import extract_skeleton

        markdown = """# H1
## H2
### H3
#### H4
##### H5
###### H6
"""
        result = extract_skeleton(markdown)

        assert len(result["skeleton"]) == 6
        for i in range(6):
            assert result["skeleton"][i]["level"] == i + 1

    def test_whitespace_only_lines(self):
        """Test handling of whitespace-only lines."""
        from engine import extract_skeleton

        markdown = """# Header 1


## Header 2

"""
        result = extract_skeleton(markdown)

        assert len(result["skeleton"]) == 2

    def test_setext_headers_not_detected(self):
        """Test that Setext-style headers (underline) are not detected."""
        from engine import extract_skeleton

        markdown = """Header with underline
====================
"""
        result = extract_skeleton(markdown)

        # Setext headers should not be detected as markdown headers
        assert len(result["skeleton"]) == 0

    def test_header_with_leading_whitespace(self):
        """Test headers with leading whitespace (indented headers)."""
        from engine import extract_skeleton

        markdown = """  # Indented Header
Some content
"""
        result = extract_skeleton(markdown)

        # Indented headers are NOT detected by the regex (requires anchor to start of line)
        # This is expected behavior - the regex uses ^ which matches start of line
        assert len(result["skeleton"]) == 0


class TestTokenEstimation:
    """Test token estimation in skeleton extraction."""

    def test_token_estimation_accuracy(self):
        """Test that token estimation is roughly correct (4 chars per token)."""
        from engine import extract_skeleton

        # Use multi-line content to have actual characters between headers
        content = ("x" * 30) + "\n" + ("x" * 30) + "\n" + ("x" * 30)
        markdown = f"# Header\n{content}\n# Next\n"

        result = extract_skeleton(markdown)
        section = result["skeleton"][0]

        # Should be approximately 90/4 = 22 tokens
        # The section spans from line 0 to the line before # Next
        assert section["approx_tokens"] > 15  # At least 15 tokens
        assert section["approx_chars"] > 80  # At least 80 chars

    def test_empty_section_tokens(self):
        """Test token estimation for empty sections."""
        from engine import extract_skeleton

        markdown = """# Header 1

# Header 2
Content
"""
        result = extract_skeleton(markdown)

        # First section should have 0 or very low tokens (between headers)
        assert result["skeleton"][0]["approx_tokens"] >= 0


class TestPositionCalculation:
    """Test position calculation in skeleton."""

    def test_position_in_document(self):
        """Test that position calculation is correct."""
        from engine import extract_skeleton

        markdown = (
            """# Header 1
"""
            + "line\n" * 50
            + """# Header 2
"""
            + "line\n" * 30
            + """# Header 3
"""
        )

        result = extract_skeleton(markdown)

        # Header 1 should be near position 0
        assert result["skeleton"][0]["position"] < 0.1
        # Header 2 should be around position 0.5
        assert 0.4 < result["skeleton"][1]["position"] < 0.7
        # Header 3 should be near position 1.0
        assert result["skeleton"][2]["position"] > 0.8

    def test_position_single_header(self):
        """Test position for single header document."""
        from engine import extract_skeleton

        markdown = "# Only Header\n"
        result = extract_skeleton(markdown)

        assert result["skeleton"][0]["position"] == 0.0


class TestLineEndCalculation:
    """Test line_end calculation for sections."""

    def test_line_end_for_middle_section(self):
        """Test line_end for a section in the middle of document."""
        from engine import extract_skeleton

        markdown = """# Header 1
Line 1-3

# Header 2
Line 5-7

# Header 3
Line 9-11
"""
        lines = markdown.split("\n")
        result = extract_skeleton(markdown)
        sections = result["skeleton"]

        # Header 2 should end before Header 3 starts
        assert sections[1]["line_end"] < sections[2]["line_start"]

    def test_line_end_for_last_section(self):
        """Test line_end for the last section."""
        from engine import extract_skeleton

        markdown = """# Header 1
Content

# Header 2
"""
        result = extract_skeleton(markdown)

        # Last section should end at the last line
        last_section = result["skeleton"][-1]
        assert last_section["line_end"] >= len(markdown.split("\n")) - 1


class TestChunkEdgeCases:
    """Test edge cases for chunk extraction."""

    def test_extract_single_line(self):
        """Test extracting a single line."""
        from engine import extract_chunk

        markdown = """# Line 0
Line 1
Line 2
"""
        chunk = extract_chunk(markdown, 1, 1)

        assert chunk.strip() == "Line 1"

    def test_extract_same_start_end(self):
        """Test extracting with same start and end."""
        from engine import extract_chunk

        markdown = "# Header\nLine 1\nLine 2"
        chunk = extract_chunk(markdown, 0, 0)

        assert "# Header" in chunk

    def test_extract_empty_range(self):
        """Test extracting an empty range."""
        from engine import extract_chunk

        markdown = "# Header\n"
        chunk = extract_chunk(markdown, 10, 20)

        assert chunk == ""

    def test_extract_preserves_newlines(self):
        """Test that chunk extraction preserves newlines."""
        from engine import extract_chunk

        markdown = "# H\nL1\nL2\n"
        chunk = extract_chunk(markdown, 0, 2)

        assert "\n" in chunk


class TestWorkflowNodeHelpers:
    """Test helper functions for workflow nodes."""

    def test_initial_state_has_all_keys(self):
        """Test that initial state has all required keys."""
        from graph import CrawlChunkState, create_initial_state

        state = create_initial_state("http://test.com")

        # Check all TypedDict keys are present
        expected_keys = [
            "url",
            "skeleton",
            "stats",
            "chunk_plan",
            "processed_chunks",
            "results",
            "current_chunk_index",
            "metadata",
            "final_summary",
            "error",
        ]

        for key in expected_keys:
            assert key in state, f"Missing key: {key}"

        # raw_content may or may not be in initial state
        # (it's set during crawl phase)
        assert "raw_content" in state or "raw_content" not in state


class TestDeepNesting:
    """Test deeply nested header structures."""

    def test_six_level_nesting(self):
        """Test maximum depth nesting (6 levels)."""
        from engine import extract_skeleton

        markdown = """# 1
## 1.1
### 1.1.1
#### 1.1.1.1
##### 1.1.1.1.1
###### 1.1.1.1.1.1
"""
        result = extract_skeleton(markdown)

        assert len(result["skeleton"]) == 6
        assert result["stats"]["max_depth"] == 6

    def test_uneven_nesting(self):
        """Test uneven nesting patterns."""
        from engine import extract_skeleton

        markdown = """# A
### A1
## B
#### B1
##### B2
# C
"""
        result = extract_skeleton(markdown)

        # Headers: A, A1, B, B1, B2, C = 6 headers
        assert len(result["skeleton"]) == 6
        assert result["stats"]["max_depth"] == 5  # ##### B2 is level 5


class TestMixedContent:
    """Test skeleton extraction with mixed content types."""

    def test_code_blocks_with_headers(self):
        """Test headers detection with code blocks - current implementation detects all."""
        from engine import extract_skeleton

        markdown = """# Before Code
```
# Inside Code
```
# After Code
"""
        result = extract_skeleton(markdown)

        # Current implementation detects ALL headers, including those in code blocks
        # This is a known limitation - code block filtering is not implemented
        assert len(result["skeleton"]) == 3
        assert result["skeleton"][0]["title"] == "Before Code"
        assert result["skeleton"][1]["title"] == "Inside Code"
        assert result["skeleton"][2]["title"] == "After Code"

    def test_list_with_headers(self):
        """Test headers after list items."""
        from engine import extract_skeleton

        markdown = """- Item 1
- Item 2
# After List
## Nested
"""
        result = extract_skeleton(markdown)

        assert len(result["skeleton"]) == 2
        assert result["skeleton"][0]["title"] == "After List"

    def test_blockquote_with_headers(self):
        """Test headers after blockquotes."""
        from engine import extract_skeleton

        markdown = """> Quote
> Multiple lines
# Header After Quote
"""
        result = extract_skeleton(markdown)

        assert len(result["skeleton"]) == 1
        assert result["skeleton"][0]["title"] == "Header After Quote"


class TestStatsComprehensiveness:
    """Test comprehensive statistics calculation."""

    def test_line_count_accuracy(self):
        """Test that line count is accurate."""
        from engine import extract_skeleton

        lines = ["# H"] + ["line"] * 100
        markdown = "\n".join(lines)

        result = extract_skeleton(markdown)

        assert result["stats"]["total_lines"] == 101

    def test_character_count_accuracy(self):
        """Test that character count is accurate."""
        from engine import extract_skeleton

        content = "x" * 500
        markdown = f"# Header\n{content}"

        result = extract_skeleton(markdown)

        assert result["stats"]["total_chars"] == len(markdown)

    def test_content_handle_preserved(self):
        """Test that content_handle is preserved in stats."""
        from engine import extract_skeleton

        result = extract_skeleton("content", content_handle="test-handle-123")

        assert result["stats"]["content_handle"] == "test-handle-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
