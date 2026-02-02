import pytest
import os
import shutil
from pathlib import Path
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="advanced_tools")
class TestAdvancedToolsModular:
    """Modular tests for advanced_tools skill."""

    async def test_smart_search(self, skill_tester):
        """Test smart_search execution."""
        result = await skill_tester.run("advanced_tools", "smart_search", pattern="import pytest")
        assert result.success
        assert result.output["tool"] == "ripgrep"
        assert isinstance(result.output["matches"], list)

    async def test_smart_find(self, skill_tester):
        """Test smart_find execution."""
        result = await skill_tester.run("advanced_tools", "smart_find", pattern="*.py")
        assert result.success
        assert result.output["tool"] == "fd"
        assert isinstance(result.output["files"], list)

    async def test_regex_replace(self, skill_tester, tmp_path, monkeypatch):
        """Test regex_replace execution."""
        if not shutil.which("sed"):
            pytest.skip("sed command not installed")

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")

        # advanced_tools typically works relative to project root
        # We use git_test_env or monkeypatch to simulate being in project root
        monkeypatch.chdir(tmp_path)

        result = await skill_tester.run(
            "advanced_tools",
            "regex_replace",
            file_path="test.txt",
            pattern="World",
            replacement="Modular",
        )

        assert result.success
        assert result.output["success"] is True
        assert test_file.read_text().strip() == "Hello Modular"

    async def test_batch_replace_dry_run(self, skill_tester, tmp_path, monkeypatch):
        """Test batch_replace execution (dry run)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "file1.py").write_text("old_val = 1")
        (tmp_path / "file2.py").write_text("old_val = 2")

        result = await skill_tester.run(
            "advanced_tools",
            "batch_replace",
            pattern="old_val",
            replacement="new_val",
            file_glob="*.py",
            dry_run=True,
        )

        assert result.success
        assert result.output["dry_run"] is True
        assert result.output["files_matched"] == 2
        # Files should NOT be changed
        assert "old_val" in (tmp_path / "file1.py").read_text()
