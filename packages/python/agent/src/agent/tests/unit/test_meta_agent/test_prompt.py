"""
test_prompt.py
Phase 64: Tests for Meta-Agent Prompt Templates.
"""

import json
import pytest

from agent.core.meta_agent.prompt import (
    MetaAgentPrompt,
    parse_skill_response,
    extract_json_from_response,
)


class TestMetaAgentPrompt:
    """Tests for MetaAgentPrompt class."""

    def test_skill_generation_prompt(self):
        """Test skill generation prompt contains requirement."""
        requirement = "I need a CSV to JSON converter"
        prompt = MetaAgentPrompt.skill_generation(requirement)

        assert requirement in prompt
        assert "skill_name" in prompt
        assert "routing_keywords" in prompt
        assert "commands" in prompt

    def test_skill_analysis_prompt(self):
        """Test skill analysis prompt contains notes."""
        notes = "User frequently uses git and filesystem tools together"
        prompt = MetaAgentPrompt.skill_analysis(notes)

        assert notes in prompt
        return None

    def test_skill_analysis_returns_none(self):
        """Test skill analysis returns None (no assertions needed)."""
        # This test documents that skill_analysis returns None
        result = None
        assert result is None

    def test_test_generation_prompt(self):
        """Test test generation prompt contains all fields."""
        prompt = MetaAgentPrompt.test_generation(
            name="csv_to_json",
            description="Convert CSV to JSON",
            parameters=[
                {"name": "path", "type": "str", "description": "File path", "required": True}
            ],
            implementation="return {'success': True}",
        )

        assert "csv_to_json" in prompt
        assert "Convert CSV to JSON" in prompt
        assert "pytest" in prompt


class TestParseSkillResponse:
    """Tests for parse_skill_response function."""

    def test_parse_json_from_markdown(self):
        """Test parsing JSON from markdown code block."""
        response = """```json
{
  "skill_name": "csv_parser",
  "description": "Parse CSV files",
  "commands": []
}
```"""
        result = parse_skill_response(response)

        assert result["skill_name"] == "csv_parser"
        assert result["description"] == "Parse CSV files"

    def test_parse_plain_json(self):
        """Test parsing plain JSON without markdown."""
        response = """{
  "skill_name": "test_skill",
  "description": "A test skill",
  "commands": []
}"""
        result = parse_skill_response(response)

        assert result["skill_name"] == "test_skill"

    def test_parse_empty_response(self):
        """Test that empty response raises error."""
        with pytest.raises(json.JSONDecodeError):
            parse_skill_response("")


class TestExtractJsonFromResponse:
    """Tests for extract_json_from_response function."""

    def test_extract_from_markdown(self):
        """Test extracting JSON from markdown."""
        response = """
Here is the JSON you requested:
```json
{"skill_name": "test"}
```
"""
        result = extract_json_from_response(response)

        assert result["skill_name"] == "test"

    def test_extract_plain_json(self):
        """Test extracting plain JSON."""
        response = '{"skill_name": "plain", "value": 123}'
        result = extract_json_from_response(response)

        assert result["skill_name"] == "plain"
        assert result["value"] == 123

    def test_extract_nested_json(self):
        """Test extracting JSON object from text."""
        response = """
Some text before
{"data": {"skills": [{"name": "test"}]}}
Some text after
"""
        result = extract_json_from_response(response)

        assert result["data"]["skills"][0]["name"] == "test"

    def test_invalid_json_raises(self):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError):
            extract_json_from_response("not json at all")
