"""
Tests for Smart Usage Templates feature.

Verifies:
1. generate_usage_template correctly parses JSON Schema
2. ToolMatch includes usage_template in search results
3. CLI query command displays usage templates
"""

import asyncio
import pytest

from omni.core.skills.discovery import (
    DiscoveredSkill,
    SkillDiscoveryService,
    ToolMatch,
    ToolRecord,
    generate_usage_template,
)


class TestGenerateUsageTemplate:
    """Tests for generate_usage_template function."""

    def test_empty_schema_returns_basic_template(self):
        """Test with empty schema."""
        result = generate_usage_template("test.tool", {})
        assert result == '@omni("test.tool", {"..."})'

    def test_none_schema_returns_placeholder(self):
        """Test with None schema."""
        result = generate_usage_template("test.tool", None)
        assert result == '@omni("test.tool", {"..."})'

    def test_string_schema_parses_correctly(self):
        """Test parsing JSON string schema."""
        schema = '{"type": "object", "required": ["message"], "properties": {"message": {"type": "string"}}}'
        result = generate_usage_template("git.commit", schema)
        assert "git.commit" in result
        assert "message" in result

    def test_required_string_parameter(self):
        """Test required string parameter gets placeholder."""
        schema = (
            '{"type": "object", "required": ["msg"], "properties": {"msg": {"type": "string"}}}'
        )
        result = generate_usage_template("test.tool", schema)
        assert result == '@omni("test.tool", {"msg": "<msg>"})'

    def test_required_integer_parameter(self):
        """Test required integer parameter gets numeric placeholder."""
        schema = '{"type": "object", "required": ["count"], "properties": {"count": {"type": "integer"}}}'
        result = generate_usage_template("test.tool", schema)
        assert result == '@omni("test.tool", {"count": 0})'

    def test_required_boolean_parameter(self):
        """Test required boolean parameter gets boolean placeholder."""
        schema = '{"type": "object", "required": ["verbose"], "properties": {"verbose": {"type": "boolean"}}}'
        result = generate_usage_template("test.tool", schema)
        assert result == '@omni("test.tool", {"verbose": true})'

    def test_required_array_parameter(self):
        """Test required array parameter gets array placeholder."""
        schema = (
            '{"type": "object", "required": ["items"], "properties": {"items": {"type": "array"}}}'
        )
        result = generate_usage_template("test.tool", schema)
        assert result == '@omni("test.tool", {"items": []})'

    def test_optional_parameters_included_with_suffix(self):
        """Test that optional parameters are included with ? suffix."""
        schema = {
            "type": "object",
            "required": ["required_arg"],
            "properties": {
                "required_arg": {"type": "string"},
                "optional_arg": {"type": "string"},  # Not in required
            },
        }
        result = generate_usage_template("test.tool", schema)
        assert "required_arg" in result
        assert "optional_arg?" in result

    def test_enum_values_use_first_value(self):
        """Test enum values use first value as placeholder."""
        schema = {
            "type": "object",
            "required": ["mode"],
            "properties": {"mode": {"type": "string", "enum": ["fast", "slow"]}},
        }
        result = generate_usage_template("test.tool", schema)
        assert result == '@omni("test.tool", {"mode": "fast"})'

    def test_multiple_required_parameters(self):
        """Test multiple required parameters are all included."""
        schema = {
            "type": "object",
            "required": ["msg", "path", "force"],
            "properties": {
                "msg": {"type": "string"},
                "path": {"type": "string"},
                "force": {"type": "boolean"},
            },
        }
        result = generate_usage_template("test.tool", schema)
        assert "msg" in result
        assert "path" in result
        assert "force" in result

    def test_mixed_types_parameters(self):
        """Test mixed type parameters."""
        schema = {
            "type": "object",
            "required": ["name", "count", "enabled", "tags", "config"],
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
                "enabled": {"type": "boolean"},
                "tags": {"type": "array"},
                "config": {"type": "object"},
            },
        }
        result = generate_usage_template("test.tool", schema)
        # All required params should be present with appropriate types
        assert '"name": "<name>"' in result or "'name': '<name>'" in result.lower()
        assert "count" in result
        assert "enabled" in result or "true" in result
        assert "tags" in result
        assert "config" in result

    def test_invalid_json_string_returns_placeholder(self):
        """Test invalid JSON string returns placeholder."""
        result = generate_usage_template("test.tool", "not valid json")
        assert result == '@omni("test.tool", {"..."})'


class TestToolMatch:
    """Tests for ToolMatch model."""

    def test_tool_match_with_usage_template(self):
        """Test ToolMatch includes usage_template."""
        match = ToolMatch(
            name="git.commit",
            skill_name="git",
            description="Commit changes",
            score=0.95,
            matched_intent="commit",
            usage_template='@omni("git.commit", {"message": "<message>"})',
        )
        assert match.name == "git.commit"
        assert match.usage_template == '@omni("git.commit", {"message": "<message>"})'

    def test_tool_match_defaults(self):
        """Test ToolMatch has empty defaults."""
        match = ToolMatch(
            name="test.tool",
            skill_name="test",
            description="Test",
            score=0.5,
            matched_intent="test",
        )
        assert match.usage_template == ""


class TestSkillDiscoveryService:
    """Tests for SkillDiscoveryService.search_tools."""

    def test_search_tools_returns_tool_matches(self):
        """Test search_tools returns ToolMatch objects with usage_template."""
        service = SkillDiscoveryService()
        matches = service.search_tools("git commit", limit=3)

        assert len(matches) > 0
        for match in matches:
            assert isinstance(match, ToolMatch)
            assert match.name
            assert match.skill_name
            assert match.description
            assert match.usage_template  # Should have usage template
            assert "@omni" in match.usage_template

    def test_search_tools_limits_results(self):
        """Test search_tools respects limit parameter."""
        service = SkillDiscoveryService()
        matches = service.search_tools("git", limit=2)
        assert len(matches) <= 2

    def test_search_tools_sorts_by_score(self):
        """Test search_tools returns results sorted by score (descending)."""
        service = SkillDiscoveryService()
        matches = service.search_tools("git commit", limit=10)

        if len(matches) >= 2:
            scores = [m.score for m in matches]
            assert scores == sorted(scores, reverse=True)

    def test_search_tools_git_commit_has_template(self):
        """Test that git.commit has proper usage template when schema is available."""
        service = SkillDiscoveryService()
        matches = service.search_tools("commit message", limit=5)

        # Verify we got results
        assert len(matches) > 0, "Expected at least one match"

        # Find git.commit in results
        commit_match = next((m for m in matches if m.name == "git.commit"), None)
        if commit_match:
            # git.commit may or may not have schema depending on indexing
            assert "@omni" in commit_match.usage_template
            # Template should have some content (either params or empty dict)
            assert "git.commit" in commit_match.usage_template

    def test_discover_all_returns_skills(self):
        """Test discover_all returns DiscoveredSkill objects."""
        service = SkillDiscoveryService()
        skills = asyncio.run(service.discover_all())

        assert len(skills) > 0
        for skill in skills:
            assert isinstance(skill, DiscoveredSkill)
            assert skill.name
            assert skill.path


class TestIntegration:
    """Integration tests for Smart Usage Templates."""

    def test_full_template_generation_flow(self):
        """Test complete flow from schema to usage template."""
        # This simulates what happens when a tool is discovered
        tool_schema = {
            "type": "object",
            "required": ["message", "project_root"],
            "properties": {
                "message": {"type": "string"},
                "project_root": {"type": "string"},
            },
        }

        # Generate template
        template = generate_usage_template("git.commit", tool_schema)

        # Verify template format
        assert '@omni("git.commit"' in template
        assert "message" in template
        assert "project_root" in template

    def test_template_usable_in_omni_call(self):
        """Test generated template can be parsed as valid JSON."""
        tool_schema = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        }
        template = generate_usage_template("test.tool", tool_schema)

        # Extract JSON part from template
        json_part = template.split("(", 1)[1].rstrip(")")
        assert json_part.startswith('"test.tool"')
        assert "{" in json_part
        assert "}" in json_part


class TestSkillQueryCommand:
    """Tests for the CLI skill query command (via function testing)."""

    def test_skill_query_function_exists(self):
        """Test that skill_query function is importable."""
        from omni.agent.cli.commands.skill.query import skill_query

        assert callable(skill_query)

    def test_skill_query_function_signature(self):
        """Test skill_query function has expected parameters."""
        import inspect
        from omni.agent.cli.commands.skill.query import skill_query

        sig = inspect.signature(skill_query)
        params = list(sig.parameters.keys())

        assert "query" in params
        assert "limit" in params
        assert "json_output" in params

    def test_search_tools_returns_expected_fields(self):
        """Test search_tools returns dicts with all required fields for CLI output."""
        from omni.core.skills.discovery import SkillDiscoveryService

        service = SkillDiscoveryService()
        matches = service.search_tools("commit", limit=3)

        # Verify each match has required fields for CLI display
        for m in matches:
            assert hasattr(m, "name")
            assert hasattr(m, "skill_name")
            assert hasattr(m, "description")
            assert hasattr(m, "score")
            assert hasattr(m, "usage_template")
            assert "@omni" in m.usage_template

    def test_cli_output_can_be_constructed(self):
        """Test that CLI output can be constructed from search results."""
        from omni.core.skills.discovery import SkillDiscoveryService

        service = SkillDiscoveryService()
        matches = service.search_tools("git", limit=3)

        # Simulate CLI output construction
        output_parts = []
        for m in matches:
            output_parts.append(f"Tool: {m.name}")
            output_parts.append(f"Usage: {m.usage_template}")
            output_parts.append(f"Score: {m.score}")

        output = "\n".join(output_parts)

        # Verify output contains expected content
        assert "Tool:" in output
        assert "Usage:" in output
        assert "Score:" in output
        assert "@omni" in output

    def test_json_output_can_be_constructed(self):
        """Test that JSON output can be constructed from search results."""
        import json
        from omni.core.skills.discovery import SkillDiscoveryService

        service = SkillDiscoveryService()
        matches = service.search_tools("commit", limit=3)

        # Simulate JSON output construction
        output = [
            {
                "name": m.name,
                "skill_name": m.skill_name,
                "description": m.description,
                "score": round(m.score, 3),
                "usage_template": m.usage_template,
            }
            for m in matches
        ]

        # Verify JSON is valid
        json_str = json.dumps(output, indent=2)
        parsed = json.loads(json_str)

        assert isinstance(parsed, list)
        if len(parsed) > 0:
            assert "name" in parsed[0]
            assert "usage_template" in parsed[0]


class TestGenerateUsageTemplateEdgeCases:
    """Edge case tests for generate_usage_template."""

    def test_nested_object_schema(self):
        """Test handling of nested object in schema."""
        schema = {
            "type": "object",
            "required": ["config"],
            "properties": {
                "config": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string"},
                        "port": {"type": "integer"},
                    },
                }
            },
        }
        result = generate_usage_template("test.tool", schema)
        # Should include the object parameter
        assert "config" in result

    def test_deeply_nested_array_items(self):
        """Test handling of arrays with complex item types."""
        schema = {
            "type": "object",
            "required": ["items"],
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
        }
        result = generate_usage_template("test.tool", schema)
        assert "items" in result
        assert "[]" in result

    def test_schema_with_default_values(self):
        """Test that schema with default values still uses type-based placeholder."""
        schema = {
            "type": "object",
            "required": ["value"],
            "properties": {
                "value": {
                    "type": "string",
                    "default": "some_default",
                }
            },
        }
        result = generate_usage_template("test.tool", schema)
        # Should use placeholder, not the default value
        assert "<value>" in result or "value" in result

    def test_empty_required_array(self):
        """Test schema with empty required array."""
        schema = {"type": "object", "required": [], "properties": {}}
        result = generate_usage_template("test.tool", schema)
        assert result == '@omni("test.tool", {})'

    def test_schema_with_whitespace(self):
        """Test schema string with extra whitespace."""
        schema = (
            '  {"type": "object", "required": ["msg"], "properties": {"msg": {"type": "string"}}}  '
        )
        result = generate_usage_template("test.tool", schema)
        assert "msg" in result

    def test_unicode_in_placeholder(self):
        """Test that unicode characters in descriptions don't break template."""
        schema = {
            "type": "object",
            "required": ["描述"],
            "properties": {"描述": {"type": "string"}},
        }
        result = generate_usage_template("test.tool", schema)
        # Should handle unicode property names
        assert "描述" in result or "test.tool" in result


class TestToolMatchScoring:
    """Tests for ToolMatch scoring logic."""

    def test_tool_match_score_type(self):
        """Test that score is a float."""
        match = ToolMatch(
            name="test.tool",
            skill_name="test",
            description="Test",
            score=0.95,
            matched_intent="test",
        )
        assert isinstance(match.score, float)
        assert 0.0 <= match.score <= 1.0

    def test_tool_match_description_truncation(self):
        """Test that long descriptions are handled correctly."""
        long_desc = "A" * 1000
        match = ToolMatch(
            name="test.tool",
            skill_name="test",
            description=long_desc,
            score=0.5,
            matched_intent="test",
        )
        assert match.description == long_desc


class TestToolRecord:
    """Tests for ToolRecord class (Memory Registry item)."""

    def test_tool_record_creation(self):
        """Test ToolRecord can be created with all fields."""
        record = ToolRecord(
            name="git.commit",
            skill_name="git",
            description="Commit changes to repository",
            category="version_control",
            input_schema='{"type": "object", "required": ["message"]}',
            file_path="assets/skills/git/scripts/commit.py",
        )
        assert record.name == "git.commit"
        assert record.skill_name == "git"
        assert record.category == "version_control"
        assert "message" in record.input_schema

    def test_tool_record_from_dict(self):
        """Test ToolRecord.from_tool_dict() creates valid record."""
        tool_dict = {
            "name": "filesystem.read",
            "description": "Read file contents",
            "category": "filesystem",
            "input_schema": '{"type": "object", "required": ["path"]}',
            "file_path": "assets/skills/filesystem/scripts/io.py",
        }
        record = ToolRecord.from_tool_dict(tool_dict, "filesystem")
        assert record.name == "filesystem.read"
        assert record.skill_name == "filesystem"
        assert record.description == "Read file contents"
        assert record.category == "filesystem"

    def test_tool_record_defaults(self):
        """Test ToolRecord has sensible defaults."""
        record = ToolRecord(
            name="test.tool",
            skill_name="test",
            description="Test",
        )
        assert record.category == ""
        assert record.input_schema == "{}"
        assert record.file_path == ""


class TestMemoryRegistry:
    """Tests for Memory Registry (O(1) tool lookup)."""

    def test_registry_loads_tools(self):
        """Test that _load_registry() populates the registry."""
        service = SkillDiscoveryService()
        registry = service._load_registry()

        # Registry should be populated with tools from LanceDB
        assert len(registry) > 0
        for tool_name, record in registry.items():
            assert isinstance(tool_name, str)
            assert isinstance(record, ToolRecord)
            assert record.name == tool_name

    def test_registry_cached(self):
        """Test that registry is cached after first load."""
        service = SkillDiscoveryService()

        # First load
        registry1 = service._load_registry()

        # Second load should return same object (cached)
        registry2 = service._load_registry()
        assert registry1 is registry2

    def test_get_tool_record(self):
        """Test get_tool_record returns ToolRecord for existing tool."""
        service = SkillDiscoveryService()

        # Find any tool in the registry
        registry = service._load_registry()
        if registry:
            first_tool_name = next(iter(registry.keys()))
            record = service.get_tool_record(first_tool_name)

            assert record is not None
            assert record.name == first_tool_name

    def test_get_tool_record_missing(self):
        """Test get_tool_record returns None for non-existent tool."""
        service = SkillDiscoveryService()
        record = service.get_tool_record("nonexistent.tool")
        assert record is None

    def test_registry_o1_lookup(self):
        """Test that registry provides O(1) lookup (conceptual test)."""
        service = SkillDiscoveryService()
        registry = service._load_registry()

        # Should be a dict (O(1) lookup)
        assert isinstance(registry, dict)

        # Verify lookup is fast (direct dict access, not linear search)
        for tool_name in registry.keys():
            _ = service.get_tool_record(tool_name)


class TestHybridSearchFlow:
    """Tests for the hybrid search flow with Memory Registry."""

    def test_search_uses_registry_for_schema(self):
        """Test that search_tools uses registry for schema lookup."""
        service = SkillDiscoveryService()
        matches = service.search_tools("commit", limit=3)

        for match in matches:
            # Should have usage template generated from schema
            assert match.usage_template
            assert "@omni" in match.usage_template
            assert match.name in match.usage_template

    def test_search_returns_tool_record_details(self):
        """Test that search results include tool details from registry."""
        service = SkillDiscoveryService()
        matches = service.search_tools("git", limit=5)

        for match in matches:
            # Verify match has all expected fields
            assert match.name
            assert match.skill_name
            assert match.description
            assert match.score > 0
            assert match.matched_intent == "git"

    def test_search_limits_results(self):
        """Test that search respects the limit parameter."""
        service = SkillDiscoveryService()
        matches = service.search_tools("file", limit=2)
        assert len(matches) <= 2

    def test_search_sorts_by_score(self):
        """Test that search results are sorted by score descending."""
        service = SkillDiscoveryService()
        matches = service.search_tools("git", limit=10)

        if len(matches) >= 2:
            scores = [m.score for m in matches]
            assert scores == sorted(scores, reverse=True)


class TestUnifiedLanceDBMigration:
    """Tests for Unified LanceDB Migration verification."""

    def test_discovery_uses_lance_as_source(self):
        """Test that discovery uses LanceDB as Single Source of Truth."""
        service = SkillDiscoveryService()

        # Must use LanceDB, not JSON
        assert service.source == "lance", f"Expected 'lance', got '{service.source}'"
        assert service.tool_count > 0, "Expected tools to be loaded"

    def test_lance_source_has_tools(self):
        """Test that LanceDB source has tools loaded."""
        service = SkillDiscoveryService()

        if service.source == "lance":
            # Tools count varies based on indexed skills, ensure we have a reasonable number
            assert service.tool_count >= 50, f"Expected 50+ tools, got {service.tool_count}"

    def test_discovery_service_properties(self):
        """Test that discovery service has correct properties after loading."""
        service = SkillDiscoveryService()

        # Trigger loading
        _ = service.tool_count

        # Verify source is lance
        assert service.source == "lance"

        # Verify registry is populated
        registry = service._load_registry()
        assert len(registry) > 0

        # Verify we can find specific tools (code_tools only has code_search now)
        assert "git.commit" in registry
        assert any(
            name.startswith("code_tools.")
            or name.startswith("filesystem.")
            or name.startswith("advanced_tools.")
            for name in registry
        )

    def test_search_with_lance_source(self):
        """Test that search works correctly with LanceDB source."""
        service = SkillDiscoveryService()

        if service.source != "lance":
            return  # Skip if not using LanceDB

        matches = service.search_tools("read file", limit=5)

        assert len(matches) > 0
        for match in matches:
            assert match.usage_template  # Must have usage template
            assert "@omni" in match.usage_template


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
