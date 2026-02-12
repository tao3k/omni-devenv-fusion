import pytest
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

    async def test_smart_find(self, skill_tester, project_root):
        """Test smart_find execution."""
        # Check if fd is available
        if not shutil.which("fd"):
            pytest.skip("fd command not installed")

        # Use specific pattern to limit results
        result = await skill_tester.run(
            "advanced_tools", "smart_find", pattern="test_*.py", extension="py"
        )
        assert result.success, f"Expected success but got error: {result.error}"
        assert result.output["tool"] == "fd"
        assert isinstance(result.output["files"], list)

    async def test_regex_replace(self, skill_tester, project_root):
        """Test regex_replace execution."""
        if not shutil.which("sed"):
            pytest.skip("sed command not installed")

        # Use project_root fixture instead of hardcoded path
        test_file = project_root / "test_regex_replace_temp.txt"
        test_file.write_text("Hello World")

        try:
            result = await skill_tester.run(
                "advanced_tools",
                "regex_replace",
                file_path=str(test_file),
                pattern="World",
                replacement="Modular",
            )

            assert result.success, f"Expected success but got error: {result.error}"
            assert test_file.read_text().strip() == "Hello Modular"
        finally:
            # Cleanup
            test_file.unlink(missing_ok=True)

    async def test_batch_replace_dry_run(self, skill_tester, project_root):
        """Test batch_replace execution (dry run)."""
        # Use project_root fixture - create test files in a subdir
        test_dir = project_root / "test_batch_temp"
        test_dir.mkdir(exist_ok=True)

        try:
            (test_dir / "file1.py").write_text("old_val = 1")
            (test_dir / "file2.py").write_text("old_val = 2")

            result = await skill_tester.run(
                "advanced_tools",
                "batch_replace",
                pattern="old_val",
                replacement="new_val",
                file_glob="test_batch_temp/*.py",
                dry_run=True,
            )

            assert result.success, f"Expected success but got error: {result.error}"
            assert result.output["mode"] == "Dry-Run"
            assert result.output["count"] == 2
            # Files should NOT be changed
            assert "old_val" in (test_dir / "file1.py").read_text()
        finally:
            # Cleanup
            shutil.rmtree(test_dir, ignore_errors=True)
