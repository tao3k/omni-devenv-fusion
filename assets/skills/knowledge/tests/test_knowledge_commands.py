"""
Knowledge Skill Tests - Zero Configuration (Phase 35.1)

Usage:
    def test_knowledge_query(knowledge):  # 'knowledge' fixture auto-injected
        assert knowledge.get_development_context().success

No conftest.py, no imports needed!
"""

import inspect


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
    commands = [
        name
        for name, func in inspect.getmembers(knowledge, inspect.isfunction)
        if hasattr(func, "_is_skill_command")
    ]
    assert len(commands) >= 5
    assert "get_development_context" in commands
    assert "consult_architecture_doc" in commands


def test_development_context_has_config(knowledge):
    assert hasattr(knowledge.get_development_context, "_skill_config")
    config = knowledge.get_development_context._skill_config
    assert config["name"] == "get_development_context"
    assert config["category"] == "read"


def test_all_commands_have_category(knowledge):
    for name, func in inspect.getmembers(knowledge, inspect.isfunction):
        if hasattr(func, "_is_skill_command"):
            assert hasattr(func, "_skill_config")
            config = func._skill_config
            assert "category" in config


def test_list_supported_languages_returns_json(knowledge):
    import asyncio
    import json

    result = asyncio.run(knowledge.list_supported_languages())

    from agent.skills.decorators import CommandResult

    if isinstance(result, CommandResult):
        result = result.data if result.success else result.error

    assert isinstance(result, str)
    data = json.loads(result)
    assert "languages" in data
    assert "total" in data
    assert data["total"] > 0


def test_get_development_context_returns_json(knowledge):
    import asyncio
    import json

    result = asyncio.run(knowledge.get_development_context())

    from agent.skills.decorators import CommandResult

    if isinstance(result, CommandResult):
        result = result.data if result.success else result.error

    assert isinstance(result, str)
    data = json.loads(result)
    assert "project" in data
    assert "git_rules" in data
    assert "guardrails" in data
