"""
test_sniffer_index.py - Unit tests for LanceDB-based rule loading in Sniffer.

Verifies:
1. IntentSniffer correctly loads rules from LanceDB via RustVectorStore.
2. Declarative rules are correctly registered and matched.
"""

from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from omni.core.router.sniffer import IntentSniffer


class TestLoadRulesFromLanceDB:
    """Tests for loading rules from LanceDB."""

    @pytest.mark.asyncio
    async def test_load_rules_from_lancedb_happy_path(self):
        """Test loading rules from LanceDB (Happy Path)."""
        # Mock tools with keywords
        mock_tools = [
            {
                "skill_name": "python_engineering",
                "tool_name": "read_files",
                "keywords": ["python", "pyproject"],
                "description": "Read files",
            },
            {
                "skill_name": "git",
                "tool_name": "git_commit",
                "keywords": ["git", "commit"],
                "description": "Git commit",
            },
        ]

        # Mock get_vector_store function which returns the store singleton
        # Patch where it's imported, not where it's used (import is inside the function)
        with patch("omni.foundation.bridge.rust_vector.get_vector_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all_tools = AsyncMock(return_value=mock_tools)
            mock_get_store.return_value = mock_store

            sniffer = IntentSniffer()
            count = await sniffer.load_rules_from_lancedb()

            assert count == 4  # 2 keywords per skill
            assert len(sniffer._declarative_rules) == 4

    @pytest.mark.asyncio
    async def test_load_rules_from_lancedb_empty(self):
        """Test loading from empty LanceDB returns zero rules."""
        with patch("omni.foundation.bridge.rust_vector.get_vector_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all_tools = AsyncMock(return_value=[])
            mock_get_store.return_value = mock_store

            sniffer = IntentSniffer()
            count = await sniffer.load_rules_from_lancedb()

            assert count == 0
            assert len(sniffer._declarative_rules) == 0

    @pytest.mark.asyncio
    async def test_load_rules_from_lancedb_skills_without_keywords(self):
        """Test that skills without keywords don't add declarative rules."""
        mock_tools = [
            {
                "skill_name": "filesystem",
                "tool_name": "read_file",
                "keywords": [],  # No keywords
                "description": "Read file",
            },
            {
                "skill_name": "python",
                "tool_name": "run_python",
                "keywords": ["python"],
                "description": "Run Python",
            },
        ]

        with patch("omni.foundation.bridge.rust_vector.get_vector_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_all_tools = AsyncMock(return_value=mock_tools)
            mock_get_store.return_value = mock_store

            sniffer = IntentSniffer()
            count = await sniffer.load_rules_from_lancedb()

            assert count == 1  # Only 1 keyword from python skill
            assert len(sniffer._declarative_rules) == 1


class TestDeclarativeMatchingLogic:
    """Test that loaded declarative rules actually trigger sniffing."""

    def test_declarative_keyword_match(self):
        """Test routing_keyword rule triggers on keyword match."""
        sniffer = IntentSniffer()

        # Manually register a keyword rule (simulating load_rules_from_lancedb)
        sniffer.register_rules(
            "python",
            [
                {"type": "file_exists", "pattern": "pyproject.toml"},
            ],
        )

        # Create a temp directory with pyproject.toml
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create pyproject.toml
            with open(os.path.join(tmpdir, "pyproject.toml"), "w") as f:
                f.write("[project]\n")

            # The sniffer should detect python skill based on file_exists rule
            result = sniffer.sniff(tmpdir)
            assert "python" in result

    def test_multiple_keyword_rules(self):
        """Test multiple keyword rules from different skills."""
        import tempfile
        import os

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
