"""Tests for omni.core.router.sniffer module - Asset-Driven Sniffer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from omni.core.router.sniffer import (
    ActivationRule,
    ContextualSniffer,
    DeclarativeRule,
    DynamicSniffer,
    IntentSniffer,
)


class TestActivationRule:
    """Test ActivationRule class."""

    def test_init_with_files(self):
        """Test initialization with file list."""
        rule = ActivationRule(skill_name="python", files=["pyproject.toml", "requirements.txt"])

        assert rule.skill_name == "python"
        assert "pyproject.toml" in rule.files
        assert "requirements.txt" in rule.files

    def test_init_with_pattern(self):
        """Test initialization with regex pattern."""
        rule = ActivationRule(skill_name="test", pattern=".*_test\\.py$")

        assert rule.skill_name == "test"
        assert rule.pattern == ".*_test\\.py$"

    @patch("os.listdir")
    def test_matches_files_found(self, mock_listdir):
        """Test matching when files are found."""
        mock_listdir.return_value = ["pyproject.toml", "README.md"]

        rule = ActivationRule(skill_name="python", files=["pyproject.toml"])
        assert rule.matches("/tmp/test") is True
        mock_listdir.assert_called_once_with("/tmp/test")

    @patch("os.listdir")
    def test_matches_files_not_found(self, mock_listdir):
        """Test matching when files are not found."""
        mock_listdir.return_value = ["README.md", "main.go"]

        rule = ActivationRule(skill_name="python", files=["pyproject.toml"])
        assert rule.matches("/tmp/test") is False

    @patch("os.listdir")
    def test_matches_permission_error(self, mock_listdir):
        """Test matching when permission error occurs."""
        mock_listdir.side_effect = PermissionError()

        rule = ActivationRule(skill_name="python", files=["pyproject.toml"])
        assert rule.matches("/tmp/test") is False


class TestIntentSniffer:
    """Test IntentSniffer class."""

    def test_init(self):
        """Test initialization."""
        sniffer = IntentSniffer()

        assert sniffer._rules == []
        assert sniffer._cached_suggestions == {}

    def test_register_rule(self):
        """Test registering a rule."""
        sniffer = IntentSniffer()
        rule = ActivationRule(skill_name="python", files=["pyproject.toml"])

        sniffer.register_rule(rule)

        assert len(sniffer._rules) == 1
        assert sniffer._rules[0].skill_name == "python"

    def test_register_skill_activation(self):
        """Test convenience method for skill activation."""
        sniffer = IntentSniffer()

        sniffer.register_skill_activation("python", files=["pyproject.toml"])

        assert len(sniffer._rules) == 1
        assert sniffer._rules[0].skill_name == "python"
        assert "pyproject.toml" in sniffer._rules[0].files

    @patch("os.listdir")
    def test_sniff_with_registered_rules(self, mock_listdir):
        """Test sniffing with registered rules."""
        mock_listdir.return_value = ["pyproject.toml", "Cargo.toml"]

        sniffer = IntentSniffer()
        sniffer.register_skill_activation("python", files=["pyproject.toml"])
        sniffer.register_skill_activation("rust", files=["Cargo.toml"])

        suggestions = sniffer.sniff("/tmp/test")

        assert "python" in suggestions
        assert "rust" in suggestions

    @patch("omni.core.router.sniffer.os.listdir")
    def test_sniff_caching(self, mock_listdir):
        """Test that sniff results are cached."""
        mock_listdir.return_value = ["pyproject.toml"]

        sniffer = IntentSniffer()
        sniffer.register_skill_activation("python", files=["pyproject.toml"])

        suggestions1 = sniffer.sniff("/tmp/test")
        suggestions2 = sniffer.sniff("/tmp/test")

        assert suggestions1 == suggestions2
        assert mock_listdir.call_count == 1  # Second call should use cache

    def test_clear_cache(self):
        """Test clearing the cache."""
        sniffer = IntentSniffer()

        sniffer._cached_suggestions["/tmp/test"] = ["python"]
        sniffer.clear_cache()

        assert sniffer._cached_suggestions == {}

    def test_sniff_file(self):
        """Test sniffing a specific file."""
        sniffer = IntentSniffer()
        sniffer.register_skill_activation("python", files=["pyproject.toml"])
        sniffer.register_skill_activation("rust", files=["Cargo.toml"])

        suggestions = sniffer.sniff_file("pyproject.toml")

        assert suggestions == ["python"]

    def test_sniff_file_no_match(self):
        """Test sniffing a file that doesn't match any rule."""
        sniffer = IntentSniffer()
        sniffer.register_skill_activation("python", files=["pyproject.toml"])

        suggestions = sniffer.sniff_file("unknown.xyz")

        assert suggestions == []

    def test_sniff_no_rules(self):
        """Test sniffing with no registered rules."""
        sniffer = IntentSniffer()

        suggestions = sniffer.sniff("/tmp/test")

        assert suggestions == []


class TestDynamicSniffer:
    """Test DynamicSniffer class."""

    def test_init_with_function(self):
        """Test initialization with a function."""
        func = lambda cwd: 0.8
        sniffer = DynamicSniffer(func=func, skill_name="python", name="test_sniffer")

        assert sniffer.skill_name == "python"
        assert sniffer.name == "test_sniffer"
        assert sniffer.priority == 100
        assert sniffer.func is func

    def test_init_with_priority(self):
        """Test initialization with custom priority."""
        func = lambda cwd: 0.5
        sniffer = DynamicSniffer(func=func, skill_name="test", priority=200)

        assert sniffer.priority == 200

    def test_check_returns_score(self):
        """Test that check returns the function score."""
        func = MagicMock(return_value=0.75)
        sniffer = DynamicSniffer(func=func, skill_name="python")

        score = sniffer.check("/tmp/test")

        assert score == 0.75
        func.assert_called_once_with("/tmp/test")

    def test_check_handles_exception(self):
        """Test that check returns 0.0 on exception."""
        func = MagicMock(side_effect=Exception("error"))
        sniffer = DynamicSniffer(func=func, skill_name="python")

        score = sniffer.check("/tmp/test")

        assert score == 0.0


class TestIntentSnifferHybrid:
    """Test hybrid sniffer (static + dynamic)."""

    def test_register_dynamic_sniffer(self):
        """Test registering a dynamic sniffer."""
        sniffer = IntentSniffer()
        func = lambda cwd: 0.8

        sniffer.register_dynamic(func, "python", name="venv_check")

        assert len(sniffer._dynamic_sniffers) == 1
        assert sniffer._dynamic_sniffers[0].skill_name == "python"
        assert sniffer._dynamic_sniffers[0].name == "venv_check"

    @patch("omni.core.router.sniffer.os.listdir")
    def test_sniff_with_dynamic_above_threshold(self, mock_listdir):
        """Test sniffing with dynamic sniffer above threshold."""
        mock_listdir.return_value = ["pyproject.toml"]
        sniffer = IntentSniffer()
        sniffer.register_dynamic(lambda cwd: 0.8, "python", name="venv_check")

        suggestions = sniffer.sniff("/tmp/test")

        assert "python" in suggestions

    def test_sniff_with_dynamic_below_threshold(self):
        """Test sniffing with dynamic sniffer below threshold."""
        sniffer = IntentSniffer()
        sniffer.register_dynamic(lambda cwd: 0.3, "python", name="venv_check")

        suggestions = sniffer.sniff("/tmp/test")

        assert "python" not in suggestions

    def test_sniff_combines_static_and_dynamic(self):
        """Test that sniff combines static and dynamic results."""
        sniffer = IntentSniffer()
        # Static rule for git
        sniffer.register_skill_activation("git", files=[".git"])
        # Dynamic sniffer for python
        sniffer.register_dynamic(lambda cwd: 0.8, "python")

        with patch("os.listdir", return_value=[".git"]):
            suggestions = sniffer.sniff("/tmp/test")

            assert "git" in suggestions
            assert "python" in suggestions

    def test_sniff_with_scores(self):
        """Test sniff_with_scores returns scores."""
        sniffer = IntentSniffer()
        sniffer.register_skill_activation("git", files=[".git"])
        sniffer.register_dynamic(lambda cwd: 0.8, "python", name="venv")

        with patch("os.listdir", return_value=[".git"]):
            scores = sniffer.sniff_with_scores("/tmp/test")

            # Should return (skill_name, score) tuples
            assert len(scores) == 2
            # Static rules get score 1.0
            assert ("git", 1.0) in scores
            # Dynamic sniffer gets its score
            assert ("python", 0.8) in scores

    def test_score_threshold_property(self):
        """Test score threshold getter and setter."""
        sniffer = IntentSniffer()

        assert sniffer.score_threshold == 0.5

        sniffer.score_threshold = 0.7
        assert sniffer.score_threshold == 0.7

        # Threshold should be clamped
        sniffer.score_threshold = 1.5
        assert sniffer.score_threshold == 1.0

        sniffer.score_threshold = -0.5
        assert sniffer.score_threshold == 0.0


class TestContextualSniffer:
    """Test ContextualSniffer class."""

    def test_init(self):
        """Test initialization."""
        sniffer = ContextualSniffer()

        assert sniffer._sniffer is not None
        assert sniffer._session_context == {}
        assert sniffer._last_suggestions == []

    @patch("os.listdir")
    def test_register_rule(self, mock_listdir):
        """Test registering a rule."""
        mock_listdir.return_value = ["pyproject.toml"]

        sniffer = ContextualSniffer()
        sniffer.register_rule(ActivationRule("python", files=["pyproject.toml"]))

        suggestions = sniffer.sniff("/tmp/test")
        assert "python" in suggestions

    def test_update_and_get_session(self):
        """Test session context updates."""
        sniffer = ContextualSniffer()

        sniffer.update_session("last_skill", "git")
        assert sniffer.get_session("last_skill") == "git"
        assert sniffer.get_session("unknown", "default") == "default"

    @patch("os.listdir")
    def test_sniff_boosts_last_used(self, mock_listdir):
        """Test that last used skill is boosted in suggestions."""
        mock_listdir.return_value = ["pyproject.toml"]

        sniffer = ContextualSniffer()
        sniffer.register_skill_activation("python", files=["pyproject.toml"])
        sniffer.update_session("last_used_skill", "git")

        suggestions = sniffer.sniff("/tmp/test")

        # Last used should be first
        assert suggestions[0] == "git"

    def test_mark_used(self):
        """Test marking a skill as used."""
        sniffer = ContextualSniffer()

        sniffer.mark_used("git")

        assert sniffer.get_session("last_used_skill") == "git"

    @patch("os.listdir")
    def test_sniff_with_session_memory(self, mock_listdir):
        """Test sniffing uses session context."""
        mock_listdir.return_value = ["pyproject.toml"]

        sniffer = ContextualSniffer()
        sniffer.register_skill_activation("python", files=["pyproject.toml"])
        sniffer.mark_used("rust")

        suggestions = sniffer.sniff("/tmp/test")

        # Should have both python (from file) and rust (from session)
        assert "python" in suggestions
        assert "rust" in suggestions
        assert suggestions[0] == "rust"  # Last used is boosted


class TestDeclarativeRule:
    """Test DeclarativeRule class for TOML-based rules."""

    def test_init_file_exists(self):
        """Test initialization with file_exists rule type."""
        rule = DeclarativeRule(
            skill_name="python", rule_type="file_exists", pattern="pyproject.toml"
        )

        assert rule.skill_name == "python"
        assert rule.rule_type == "file_exists"
        assert rule.pattern == "pyproject.toml"

    def test_init_file_pattern(self):
        """Test initialization with file_pattern rule type."""
        rule = DeclarativeRule(skill_name="test", rule_type="file_pattern", pattern="test_*.py")

        assert rule.skill_name == "test"
        assert rule.rule_type == "file_pattern"
        assert rule.pattern == "test_*.py"

    def test_matches_file_exists_found(self):
        """Test file_exists matching when file is found."""
        rule = DeclarativeRule(
            skill_name="python", rule_type="file_exists", pattern="pyproject.toml"
        )

        root_files = {"pyproject.toml", "README.md", "main.py"}
        assert rule.matches("/tmp/test", root_files) is True

    def test_matches_file_exists_not_found(self):
        """Test file_exists matching when file is not found."""
        rule = DeclarativeRule(
            skill_name="python", rule_type="file_exists", pattern="pyproject.toml"
        )

        root_files = {"README.md", "main.go"}
        assert rule.matches("/tmp/test", root_files) is False

    def test_matches_file_pattern_asterisk(self):
        """Test file_pattern matching with asterisk glob."""
        rule = DeclarativeRule(skill_name="test", rule_type="file_pattern", pattern="test_*.py")

        root_files = {"test_main.py", "test_utils.py", "main.py", "utils.py"}
        assert rule.matches("/tmp/test", root_files) is True

    def test_matches_file_pattern_wildcard(self):
        """Test file_pattern matching with wildcard."""
        rule = DeclarativeRule(skill_name="python", rule_type="file_pattern", pattern="*.py")

        root_files = {"main.py", "utils.py", "test.js"}
        assert rule.matches("/tmp/test", root_files) is True

        root_files = {"main.js", "index.html"}
        assert rule.matches("/tmp/test", root_files) is False

    def test_matches_file_pattern_suffix(self):
        """Test file_pattern matching with suffix pattern."""
        rule = DeclarativeRule(skill_name="test", rule_type="file_pattern", pattern="*_test.py")

        root_files = {"main_test.py", "utils_test.py", "main.py"}
        assert rule.matches("/tmp/test", root_files) is True

    def test_matches_unknown_type(self):
        """Test matching with unknown rule type returns False."""
        rule = DeclarativeRule(skill_name="unknown", rule_type="unknown", pattern="*")

        root_files = {"file.txt"}
        assert rule.matches("/tmp/test", root_files) is False

    def test_repr(self):
        """Test string representation."""
        rule = DeclarativeRule(
            skill_name="python", rule_type="file_exists", pattern="pyproject.toml"
        )
        assert repr(rule) == "DeclarativeRule(python, file_exists, pyproject.toml)"


class TestIntentSnifferDeclarative:
    """Test IntentSniffer with declarative rules."""

    def test_register_rules_file_exists(self):
        """Test registering declarative rules with file_exists type."""
        sniffer = IntentSniffer()

        sniffer.register_rules(
            "python",
            [
                {"type": "file_exists", "pattern": "pyproject.toml"},
                {"type": "file_exists", "pattern": "requirements.txt"},
            ],
        )

        assert len(sniffer._declarative_rules) == 2
        assert sniffer._declarative_rules[0].rule_type == "file_exists"
        assert sniffer._declarative_rules[0].pattern == "pyproject.toml"

    def test_register_rules_file_pattern(self):
        """Test registering declarative rules with file_pattern type."""
        sniffer = IntentSniffer()

        sniffer.register_rules(
            "python",
            [
                {"type": "file_pattern", "pattern": "*.py"},
                {"type": "file_pattern", "pattern": "test_*.py"},
            ],
        )

        assert len(sniffer._declarative_rules) == 2
        assert sniffer._declarative_rules[0].rule_type == "file_pattern"

    def test_register_rules_ignores_unknown_type(self):
        """Test registering rules ignores unknown rule types."""
        sniffer = IntentSniffer()

        sniffer.register_rules(
            "python",
            [
                {"type": "file_exists", "pattern": "pyproject.toml"},
                {"type": "unknown_type", "pattern": "file.txt"},  # Should be ignored
            ],
        )

        assert len(sniffer._declarative_rules) == 1

    def test_register_rules_ignores_empty_pattern(self):
        """Test registering rules ignores empty patterns."""
        sniffer = IntentSniffer()

        sniffer.register_rules(
            "python",
            [
                {"type": "file_exists", "pattern": ""},  # Should be ignored
            ],
        )

        assert len(sniffer._declarative_rules) == 0

    @patch("os.listdir")
    def test_sniff_with_declarative_file_exists(self, mock_listdir):
        """Test sniffing with declarative file_exists rule."""
        mock_listdir.return_value = ["pyproject.toml", "README.md"]

        sniffer = IntentSniffer()
        sniffer.register_rules(
            "python",
            [
                {"type": "file_exists", "pattern": "pyproject.toml"},
            ],
        )

        suggestions = sniffer.sniff("/tmp/test")

        assert "python" in suggestions

    @patch("os.listdir")
    def test_sniff_with_declarative_file_pattern(self, mock_listdir):
        """Test sniffing with declarative file_pattern rule."""
        mock_listdir.return_value = ["main.py", "test_main.py", "README.md"]

        sniffer = IntentSniffer()
        sniffer.register_rules(
            "python",
            [
                {"type": "file_pattern", "pattern": "*.py"},
            ],
        )

        suggestions = sniffer.sniff("/tmp/test")

        assert "python" in suggestions

    @patch("os.listdir")
    def test_sniff_with_declarative_no_match(self, mock_listdir):
        """Test sniffing with declarative rules that don't match."""
        mock_listdir.return_value = ["main.go", "README.md"]

        sniffer = IntentSniffer()
        sniffer.register_rules(
            "python",
            [
                {"type": "file_exists", "pattern": "pyproject.toml"},
            ],
        )

        suggestions = sniffer.sniff("/tmp/test")

        assert "python" not in suggestions

    @patch("os.listdir")
    def test_sniff_combines_static_and_declarative(self, mock_listdir):
        """Test that sniff combines static and declarative rules."""
        mock_listdir.return_value = [".git", "pyproject.toml"]

        sniffer = IntentSniffer()
        # Static rule for git
        sniffer.register_skill_activation("git", files=[".git"])
        # Declarative rule for python
        sniffer.register_rules(
            "python",
            [
                {"type": "file_exists", "pattern": "pyproject.toml"},
            ],
        )

        suggestions = sniffer.sniff("/tmp/test")

        assert "git" in suggestions
        assert "python" in suggestions

    @patch("os.listdir")
    def test_sniff_combines_all_three_modes(self, mock_listdir):
        """Test sniff combines static, dynamic, and declarative rules."""
        mock_listdir.return_value = [".git", "pyproject.toml"]

        sniffer = IntentSniffer()
        # Static rule
        sniffer.register_skill_activation("git", files=[".git"])
        # Declarative rule
        sniffer.register_rules(
            "python",
            [
                {"type": "file_exists", "pattern": "pyproject.toml"},
            ],
        )
        # Dynamic sniffer
        sniffer.register_dynamic(lambda cwd: 0.8, "rust", name="cargo_check")

        suggestions = sniffer.sniff("/tmp/test")

        assert "git" in suggestions
        assert "python" in suggestions
        assert "rust" in suggestions

    @patch("omni.core.router.sniffer.os.listdir")
    def test_sniff_with_scores_declarative(self, mock_listdir):
        """Test sniff_with_scores includes declarative rules."""
        mock_listdir.return_value = ["pyproject.toml"]

        sniffer = IntentSniffer()
        sniffer.register_rules(
            "python",
            [
                {"type": "file_exists", "pattern": "pyproject.toml"},
            ],
        )

        scores = sniffer.sniff_with_scores("/tmp/test")

        # Declarative rules should contribute score 1.0
        assert ("python", 1.0) in scores


class TestDeclarativeRuleIntegration:
    """Integration tests for declarative rules with real file operations."""

    def test_file_exists_o1_performance(self):
        """Test that file_exists uses O(1) lookup."""
        import time

        rule = DeclarativeRule(skill_name="python", rule_type="file_exists", pattern="target.py")

        # Create a large set simulating many files
        root_files = {f"file_{i}.txt" for i in range(10000)}
        root_files.add("target.py")

        start = time.perf_counter()
        result = rule.matches("/tmp/test", root_files)
        elapsed = time.perf_counter() - start

        assert result is True
        assert elapsed < 0.001  # Should be very fast (O(1))

    def test_file_pattern_o_n_performance(self):
        """Test that file_pattern iterates through files."""
        import time

        rule = DeclarativeRule(skill_name="test", rule_type="file_pattern", pattern="test_*.py")

        # Create a set of files
        root_files = {f"file_{i}.txt" for i in range(1000)}
        root_files.add("test_main.py")

        start = time.perf_counter()
        result = rule.matches("/tmp/test", root_files)
        elapsed = time.perf_counter() - start

        assert result is True
        # Slower than O(1) but still fast for 1000 files
        assert elapsed < 0.01
