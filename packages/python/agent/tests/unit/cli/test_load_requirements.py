"""
test_load_requirements.py - Declarative load requirements registry tests.
"""

from __future__ import annotations

import pytest

from omni.agent.cli.load_requirements import (
    LoadRequirements,
    get_requirements,
    get_registry,
    register_requirements,
)


class TestLoadRequirements:
    """Tests for LoadRequirements dataclass and registry."""

    def test_default_requirements(self):
        """Unknown command gets full bootstrap (ollama=True, embedding_index=True)."""
        reqs = get_requirements("nonexistent")
        assert reqs.ollama is True
        assert reqs.embedding_index is True

    def test_none_command_returns_default(self):
        """None command returns default."""
        reqs = get_requirements(None)
        assert reqs.ollama is True
        assert reqs.embedding_index is True

    def test_register_skill_requirements(self):
        """Skill command declares light loading."""
        register_requirements("skill", ollama=False, embedding_index=False)
        reqs = get_requirements("skill")
        assert reqs.ollama is False
        assert reqs.embedding_index is False

    def test_register_partial_override(self):
        """Partial override keeps other fields at default."""
        register_requirements("route", ollama=False)
        reqs = get_requirements("route")
        assert reqs.ollama is False
        assert reqs.embedding_index is True  # default

    def test_registry_contains_registered_commands(self):
        """get_registry returns copy of registry."""
        register_requirements("test_cmd", ollama=False)
        reg = get_registry()
        assert "test_cmd" in reg
        assert reg["test_cmd"].ollama is False

    def test_all_cli_commands_have_declarative_requirements(self):
        """All top-level CLI commands declare load requirements (audit)."""
        # Trigger app registration (imports all register_*_command)
        from omni.agent.cli.app import app  # noqa: F401

        reg = get_registry()
        expected = {
            "version",
            "completions",
            "commands",
            "dashboard",
            "db",
            "skill",
            "mcp",
            "route",
            "run",
            "gateway",
            "agent",
            "sync",
            "knowledge",
            "reindex",
        }
        missing = expected - set(reg.keys())
        assert not missing, f"Commands missing register_requirements: {missing}"
