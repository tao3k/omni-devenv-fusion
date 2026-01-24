"""
test_sniffer_index.py - Unit tests for Rust-First Indexing integration in Sniffer.

Verifies:
1. IntentSniffer correctly loads rules from PythonSkillScanner (Index Reader).
2. Declarative rules are correctly registered and matched.
3. Fallback logic behaves as expected.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from omni.core.router.sniffer import IntentSniffer

# Mock Foundation objects to avoid dependency on actual JSON file
from omni.foundation.bridge.scanner import DiscoveredSkillRules, SnifferRule


@pytest.fixture
def mock_scanner_cls():
    """Mock the PythonSkillScanner class."""
    with patch("omni.foundation.bridge.scanner.PythonSkillScanner") as mock:
        yield mock


@pytest.fixture
def mock_skills_path(skills_root: Path) -> str:
    """Get skills path as string for mock data (uses centralized fixture)."""
    return str(skills_root)


class TestLoadFromIndexIntegration:
    """Integration tests for loading rules from index."""

    def test_load_from_index_happy_path(self, mock_scanner_cls, mock_skills_path: str):
        """Test loading rules from index (Happy Path)."""
        # 1. Setup Mock Data (Simulate reading from skill_index.json)
        scanner_instance = mock_scanner_cls.return_value

        # Simulate finding two skills, one with rules, one without
        # Using centralized skills path fixture
        skill_with_rules = DiscoveredSkillRules(
            skill_name="python_engineering",
            skill_path=f"{mock_skills_path}/python_engineering",
            rules=[
                SnifferRule(rule_type="file_exists", pattern="pyproject.toml"),
                SnifferRule(rule_type="file_pattern", pattern="*.py"),
            ],
        )
        skill_empty = DiscoveredSkillRules(
            skill_name="docs",
            skill_path=f"{mock_skills_path}/docs",
            rules=[],
        )

        scanner_instance.scan_directory.return_value = [skill_with_rules, skill_empty]

        # 2. Execute
        sniffer = IntentSniffer()
        count = sniffer.load_from_index()

        # 3. Verify
        assert count == 2
        assert len(sniffer._declarative_rules) == 2

        # Verify the rules were converted correctly
        rule1 = sniffer._declarative_rules[0]
        assert rule1.skill_name == "python_engineering"
        assert rule1.rule_type == "file_exists"
        assert rule1.pattern == "pyproject.toml"

    def test_load_from_index_empty_index(self, mock_scanner_cls):
        """Test loading from empty index returns zero rules."""
        scanner_instance = mock_scanner_cls.return_value
        scanner_instance.scan_directory.return_value = []

        sniffer = IntentSniffer()
        count = sniffer.load_from_index()

        assert count == 0
        assert len(sniffer._declarative_rules) == 0

    def test_load_from_index_skills_without_rules(self, mock_scanner_cls, mock_skills_path: str):
        """Test that skills without rules don't add declarative rules."""
        scanner_instance = mock_scanner_cls.return_value

        # Multiple skills, some with rules, some without
        # Using centralized skills path fixture
        skills = [
            DiscoveredSkillRules(skill_name="git", skill_path=f"{mock_skills_path}/git", rules=[]),
            DiscoveredSkillRules(
                skill_name="filesystem", skill_path=f"{mock_skills_path}/filesystem", rules=[]
            ),
            DiscoveredSkillRules(
                skill_name="python",
                skill_path=f"{mock_skills_path}/python",
                rules=[SnifferRule("file_exists", "pyproject.toml")],
            ),
        ]
        scanner_instance.scan_directory.return_value = skills

        sniffer = IntentSniffer()
        count = sniffer.load_from_index()

        # Only 1 rule from the python skill
        assert count == 1
        assert len(sniffer._declarative_rules) == 1


class TestDeclarativeMatchingLogic:
    """Test that loaded declarative rules actually trigger sniffing."""

    def test_declarative_file_exists_match(self):
        """Test file_exists rule triggers on exact file match."""
        sniffer = IntentSniffer()

        # Manually register a declarative rule (simulating load_from_index)
        sniffer.register_rules(
            "rust_engineering", [{"type": "file_exists", "pattern": "Cargo.toml"}]
        )

        # Setup mock file system context
        cwd = "/tmp/my_rust_project"
        mock_files = {"Cargo.toml", "src", "README.md"}

        with patch("os.listdir", return_value=list(mock_files)):
            suggestions = sniffer.sniff(cwd)

        assert "rust_engineering" in suggestions
        assert len(suggestions) == 1

    def test_declarative_file_pattern_match(self):
        """Test file_pattern rule triggers on glob match."""
        sniffer = IntentSniffer()

        sniffer.register_rules("python_skill", [{"type": "file_pattern", "pattern": "*.py"}])

        cwd = "/tmp/python_project"
        mock_files = {"main.py", "utils.py", "README.md"}

        with patch("os.listdir", return_value=list(mock_files)):
            suggestions = sniffer.sniff(cwd)

        assert "python_skill" in suggestions

    def test_declarative_no_match(self):
        """Test rule doesn't trigger when pattern doesn't match."""
        sniffer = IntentSniffer()

        sniffer.register_rules("go_skill", [{"type": "file_exists", "pattern": "go.mod"}])

        cwd = "/tmp/rust_project"
        mock_files = {"Cargo.toml", "src", "README.md"}

        with patch("os.listdir", return_value=list(mock_files)):
            suggestions = sniffer.sniff(cwd)

        assert "go_skill" not in suggestions

    def test_multiple_rules_multiple_skills(self):
        """Test multiple skills with multiple rules."""
        sniffer = IntentSniffer()

        # Register rules for multiple skills
        sniffer.register_rules("python", [{"type": "file_exists", "pattern": "pyproject.toml"}])
        sniffer.register_rules("rust", [{"type": "file_exists", "pattern": "Cargo.toml"}])
        sniffer.register_rules("nodejs", [{"type": "file_exists", "pattern": "package.json"}])

        cwd = "/tmp/fullstack_project"
        mock_files = {"pyproject.toml", "Cargo.toml", "package.json", "src"}

        with patch("os.listdir", return_value=list(mock_files)):
            suggestions = sniffer.sniff(cwd)

        assert len(suggestions) == 3
        assert "python" in suggestions
        assert "rust" in suggestions
        assert "nodejs" in suggestions


class TestLoadFromIndexMissingModule:
    """Test defensive behavior when Foundation layer is missing."""

    def test_missing_foundation_module(self):
        """Test graceful failure if Foundation layer is missing."""
        # Mock sys.modules to simulate missing foundation
        original_modules = dict(sys.modules)

        try:
            # Simulate Foundation module as None (failed import)
            with patch.dict("sys.modules", {"omni.foundation.bridge.scanner": None}):
                sniffer = IntentSniffer()
                count = sniffer.load_from_index()
                assert count == 0
        finally:
            # Restore original modules
            sys.modules.clear()
            sys.modules.update(original_modules)


class TestSniffWithScores:
    """Test sniff_with_scores returns scores for declarative rules."""

    def test_declarative_rules_get_full_score(self):
        """Declarative rules should contribute full score (1.0)."""
        sniffer = IntentSniffer()

        sniffer.register_rules("python", [{"type": "file_exists", "pattern": "pyproject.toml"}])

        cwd = "/tmp/project"
        mock_files = {"pyproject.toml", "src"}

        with patch("os.listdir", return_value=list(mock_files)):
            scored = sniffer.sniff_with_scores(cwd)

        assert len(scored) == 1
        skill_name, score = scored[0]
        assert skill_name == "python"
        assert score == 1.0


class TestIndexRuleConversion:
    """Test that Foundation rules are converted to Core rules correctly."""

    def test_rule_type_conversion(self, mock_scanner_cls, mock_skills_path: str):
        """Test that rule types are preserved during conversion."""
        scanner_instance = mock_scanner_cls.return_value

        skill = DiscoveredSkillRules(
            skill_name="test_skill",
            skill_path=f"{mock_skills_path}/test",
            rules=[
                SnifferRule("file_exists", "test.txt"),
                SnifferRule("file_pattern", "*.test"),
            ],
        )
        scanner_instance.scan_directory.return_value = [skill]

        sniffer = IntentSniffer()
        sniffer.load_from_index()

        rules = sniffer._declarative_rules
        assert len(rules) == 2

        # Check first rule
        assert rules[0].rule_type == "file_exists"
        assert rules[0].pattern == "test.txt"

        # Check second rule
        assert rules[1].rule_type == "file_pattern"
        assert rules[1].pattern == "*.test"

    def test_rule_skill_name_preserved(self, mock_scanner_cls, mock_skills_path: str):
        """Test that skill names are preserved in rules."""
        scanner_instance = mock_scanner_cls.return_value

        skill = DiscoveredSkillRules(
            skill_name="my_custom_skill",
            skill_path=f"{mock_skills_path}/my_custom_skill",
            rules=[SnifferRule("file_exists", "custom.toml")],
        )
        scanner_instance.scan_directory.return_value = [skill]

        sniffer = IntentSniffer()
        sniffer.load_from_index()

        rule = sniffer._declarative_rules[0]
        assert rule.skill_name == "my_custom_skill"
