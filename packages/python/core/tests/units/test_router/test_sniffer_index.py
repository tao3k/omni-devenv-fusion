"""
test_sniffer_index.py - Unit tests for LanceDB-based rule loading in Sniffer.

Verifies:
1. IntentSniffer correctly loads rules from LanceDB via RustVectorStore.
2. Declarative rules are correctly registered and matched.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from omni.test_kit.fixtures.vector import make_tool_search_payload

from omni.core.router.sniffer import IntentSniffer


def _mock_sniffer_tool(
    *,
    skill_name: str,
    tool_name: str,
    routing_keywords: list[str],
    description: str,
) -> dict[str, object]:
    payload = make_tool_search_payload(
        name=f"{skill_name}.{tool_name}",
        skill_name=skill_name,
        tool_name=tool_name,
        routing_keywords=routing_keywords,
        description=description,
    )
    return {
        "skill_name": payload["skill_name"],
        "tool_name": payload["tool_name"],
        "routing_keywords": payload["routing_keywords"],
        "description": payload["description"],
    }


class TestLoadRulesFromLanceDB:
    """Tests for loading rules from LanceDB."""

    @pytest.mark.asyncio
    async def test_load_rules_from_lancedb_happy_path(self):
        """Test loading rules from LanceDB (Happy Path)."""
        # Mock tools with routing_keywords
        mock_tools = [
            _mock_sniffer_tool(
                skill_name="python_engineering",
                tool_name="read_files",
                routing_keywords=["python", "pyproject"],
                description="Read files",
            ),
            _mock_sniffer_tool(
                skill_name="git",
                tool_name="git_commit",
                routing_keywords=["git", "commit"],
                description="Git commit",
            ),
        ]

        # Mock get_vector_store function which returns the store singleton
        # Patch where it's imported, not where it's used (import is inside the function)
        with patch("omni.foundation.bridge.rust_vector.get_vector_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all_tools = MagicMock(return_value=mock_tools)
            mock_get_store.return_value = mock_store

            sniffer = IntentSniffer()
            count = await sniffer.load_rules_from_lancedb()

            assert count == 4  # 2 routing keywords per skill
            assert len(sniffer._declarative_rules) == 4

    @pytest.mark.asyncio
    async def test_load_rules_from_lancedb_empty(self):
        """Test loading from empty LanceDB returns zero rules."""
        with patch("omni.foundation.bridge.rust_vector.get_vector_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all_tools = MagicMock(return_value=[])
            mock_get_store.return_value = mock_store

            sniffer = IntentSniffer()
            count = await sniffer.load_rules_from_lancedb()

            assert count == 0
            assert len(sniffer._declarative_rules) == 0

    @pytest.mark.asyncio
    async def test_load_rules_from_lancedb_skills_without_routing_keywords(self):
        """Test that skills without routing_keywords don't add declarative rules."""
        mock_tools = [
            _mock_sniffer_tool(
                skill_name="filesystem",
                tool_name="read_file",
                routing_keywords=[],  # No routing keywords
                description="Read file",
            ),
            _mock_sniffer_tool(
                skill_name="python",
                tool_name="run_python",
                routing_keywords=["python"],
                description="Run Python",
            ),
        ]

        with patch("omni.foundation.bridge.rust_vector.get_vector_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all_tools = MagicMock(return_value=mock_tools)
            mock_get_store.return_value = mock_store

            sniffer = IntentSniffer()
            count = await sniffer.load_rules_from_lancedb()

            assert count == 1  # Only 1 routing keyword from python skill
            assert len(sniffer._declarative_rules) == 1


class TestDeclarativeMatchingLogic:
    """Test that loaded declarative rules actually trigger sniffing."""

    @pytest.mark.parametrize(
        "skill_name,rule_pattern",
        [("python", "pyproject.toml"), ("git", ".git")],
        ids=["python-rule", "git-rule"],
    )
    def test_declarative_keyword_match(self, skill_name: str, rule_pattern: str):
        """Test routing_keyword rules trigger on file existence matches."""
        sniffer = IntentSniffer()
        sniffer.register_rules(skill_name, [{"type": "file_exists", "pattern": rule_pattern}])

        with tempfile.TemporaryDirectory() as tmpdir:
            if rule_pattern == ".git":
                os.makedirs(os.path.join(tmpdir, ".git"))
            else:
                with open(os.path.join(tmpdir, rule_pattern), "w", encoding="utf-8") as f:
                    f.write("[project]\n")
            result = sniffer.sniff(tmpdir)
            assert skill_name in result

    def test_multiple_keyword_rules(self):
        """Test multiple keyword rules from different skills."""
        sniffer = IntentSniffer()

        sniffer.register_rules("git", [{"type": "file_exists", "pattern": ".git"}])
        sniffer.register_rules("python", [{"type": "file_exists", "pattern": "pyproject.toml"}])

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .git directory (simulating git repo)
            os.makedirs(os.path.join(tmpdir, ".git"))

            result = sniffer.sniff(tmpdir)
            assert "git" in result

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create pyproject.toml
            with open(os.path.join(tmpdir, "pyproject.toml"), "w") as f:
                f.write("[project]\n")

            result = sniffer.sniff(tmpdir)
            assert "python" in result
