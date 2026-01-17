"""
Knowledge Skill Tests - Phase 63+ Architecture

Tests for knowledge skill commands with scripts/*.py pattern.
"""


def test_get_development_context_exists(knowledge):
    assert hasattr(knowledge, "get_development_context")
    assert callable(knowledge.get_development_context)


def test_consult_architecture_doc_exists(knowledge):
    assert hasattr(knowledge, "consult_architecture_doc")
    assert callable(knowledge.consult_architecture_doc)


def test_consult_language_expert_exists(knowledge):
    assert hasattr(knowledge, "consult_language_expert")
    assert callable(knowledge.consult_language_expert)


def test_get_language_standards_exists(knowledge):
    assert hasattr(knowledge, "get_language_standards")
    assert callable(knowledge.get_language_standards)


def test_list_supported_languages_exists(knowledge):
    assert hasattr(knowledge, "list_supported_languages")
    assert callable(knowledge.list_supported_languages)


def test_has_skill_commands(knowledge):
    """knowledge should have @skill_command decorated functions."""
    # Check via knowledge._skill.commands
    commands = list(knowledge._skill.commands.keys())
    assert len(commands) >= 5
    assert "get_development_context" in commands
    assert "consult_architecture_doc" in commands


def test_development_context_has_config(knowledge):
    """get_development_context should have _skill_config via the SkillCommand."""
    # Access via the original SkillCommand object
    cmd = knowledge._skill.commands.get("get_development_context")
    assert cmd is not None, "get_development_context command not found"
    assert hasattr(cmd, "_skill_config") or hasattr(cmd.func, "_skill_config")
    config = getattr(cmd, "_skill_config", None) or getattr(cmd.func, "_skill_config", None)
    assert config is not None, "config should not be None"
    assert config["name"] == "get_development_context"
    assert config["category"] == "read"


def test_all_commands_have_category(knowledge):
    """All knowledge commands should have category in config."""
    for cmd_name, cmd in knowledge._skill.commands.items():
        config = getattr(cmd, "_skill_config", None) or getattr(cmd.func, "_skill_config", None)
        assert config is not None, f"Command {cmd_name} should have _skill_config"
        assert "category" in config


def test_list_supported_languages_returns_json(knowledge):
    import json

    result = knowledge.list_supported_languages()

    # Handle CommandResultWrapper
    if hasattr(result, "data"):
        result = result.data if result.success else result.error

    assert isinstance(result, str)
    data = json.loads(result)
    assert "languages" in data
    assert "total" in data
    assert data["total"] > 0


def test_get_development_context_returns_json(knowledge):
    import json

    result = knowledge.get_development_context()

    # Handle CommandResultWrapper
    if hasattr(result, "data"):
        result = result.data if result.success else result.error

    assert isinstance(result, str)
    data = json.loads(result)
    assert "project" in data
    assert "git_rules" in data
    assert "guardrails" in data
