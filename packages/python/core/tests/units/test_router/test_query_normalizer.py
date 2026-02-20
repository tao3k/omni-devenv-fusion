"""Tests for router query normalizer (config typos + URL placeholder)."""

from unittest.mock import patch

from omni.core.router.query_normalizer import normalize_for_routing


class TestNormalizeForRouting:
    """Normalizer: config-only typos (router.normalize.typos), URL → token."""

    def test_empty_or_whitespace_unchanged(self):
        assert normalize_for_routing("") == ""
        assert normalize_for_routing("   ") == ""

    def test_no_builtin_typos(self):
        """Without config, typos are left as-is (use model + semantic/XML for robust correction)."""
        with patch("omni.core.router.query_normalizer.get_setting", return_value={}):
            assert "helo" in normalize_for_routing("helo me")
            assert "analzye" in normalize_for_routing("analzye this")
            assert normalize_for_routing("reserach repo") == "reserach repo"

    def test_settings_typo_corrections_applied(self):
        """Typos configured in settings (system: packages/conf/settings.yaml, user: $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml) are corrected."""
        typos = {"analzye": "analyze", "reserach": "research"}
        with patch("omni.core.router.query_normalizer.get_setting", return_value=typos):
            assert normalize_for_routing("analzye this") == "analyze this"
            assert normalize_for_routing("reserach repo") == "research repo"

    def test_url_replaced_with_token(self):
        q = "analyze https://example.com/page"
        out = normalize_for_routing(q)
        assert "https://" not in out
        assert " url " in out or out.strip().endswith("url")

    def test_github_url_replaced_with_github_url(self):
        q = "help me analyze https://github.com/org/repo/path"
        out = normalize_for_routing(q)
        assert "https://" not in out
        assert "github" in out
        assert "url" in out
        assert "help" in out
        assert "analyze" in out

    def test_query_without_url_passthrough(self):
        assert normalize_for_routing("git commit") == "git commit"
        assert normalize_for_routing("research repository") == "research repository"

    def test_config_typos_applied_when_set(self):
        """When router.normalize.typos is set, corrections are applied."""
        typos = {"helo": "help", "analzye": "analyze"}

        def get_setting(key, default=None):
            if key == "router.normalize.typos":
                return typos
            return default

        with patch("omni.core.router.query_normalizer.get_setting", side_effect=get_setting):
            out = normalize_for_routing("helo me analzye")
        assert "help" in out
        assert "analyze" in out
        assert "helo" not in out
        assert "analzye" not in out
