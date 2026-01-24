"""
End-to-End Mission: Log Standardization
Verifies the full interaction loop of the Modern Toolchain.

Scenario:
A developer asks the Agent: "Refactor existing_script.py to use standard logging instead of print."

Mission Flow:
1. knowledge.get_best_practice (Consult standard)
2. advanced_tools.smart_search (Find targets)
3. advanced_tools.batch_replace (Preview mode)
4. advanced_tools.batch_replace (Apply mode)
5. testing.run_pytest (Regression test)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Add assets to path for skill imports
ASSETS_ROOT = PROJECT_ROOT / "assets"
sys.path.insert(0, str(ASSETS_ROOT))


@pytest.fixture
def mission_env(tmp_path):
    """Setup a sandbox environment with a 'legacy' file."""
    # 1. Create Legacy File
    legacy_file = tmp_path / "legacy_service.py"
    legacy_file.write_text("""
import os

def process_data(data):
    print(f"Processing {len(data)} items")  # TODO: Convert to logger
    result = [x * 2 for x in data]
    print(f"Processed {len(data)} items, result: {result}")
    return result

def cleanup():
    print("Cleaning up resources")
    pass
""")

    # 2. Create Dummy Test
    test_file = tmp_path / "test_legacy.py"
    test_file.write_text("""
from legacy_service import process_data, cleanup

def test_process():
    result = process_data([1, 2, 3])
    assert result == [2, 4, 6]

def test_cleanup():
    cleanup()  # Should not raise
""")

    return legacy_file, test_file


class TestMissionLogStandardization:
    """End-to-end test for the complete Modern Toolchain workflow."""

    def test_mission_log_standardization_flow(self, mission_env, tmp_path):
        """Test the complete toolchain integration flow."""
        legacy_file, test_file = mission_env

        print("\n" + "=" * 60)
        print("🚀 Mission Start: Standardize Logging")
        print("=" * 60)

        # Import the skills directly for testing
        from assets.skills.advanced_tools.scripts.mutation import batch_replace


        # Create a proper mock paths object
        class MockPaths:
            project_root = tmp_path

        mock_paths = MockPaths()

        # --- Step 1: Discovery (Find Targets) ---
        print("\n[Step 1] Agent searches for 'print' statements...")

        # Mock shutil.which at the mutation module level
        with (
            patch(
                "assets.skills.advanced_tools.scripts.mutation.shutil.which",
                return_value="/usr/bin/rg",
            ),
            patch("assets.skills.advanced_tools.scripts.mutation.subprocess.run") as mock_run,
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "legacy_service.py\0"
            mock_run.return_value = mock_proc

            # Note: In a real scenario, Agent would use smart_search first
            # For this test, we directly invoke batch_replace to verify functionality
            print("    ℹ️  Using batch_replace for discovery (mocked rg)")

        # --- Step 2: Refactoring - Dry Run (Safety First) ---
        print("\n[Step 2] Agent attempts BATCH REPLACE (Dry-Run)...")

        pattern = r"print\((.*)\)"
        replacement = r"logger.debug(\1)"

        with (
            patch(
                "assets.skills.advanced_tools.scripts.mutation.shutil.which",
                return_value="/usr/bin/rg",
            ),
            patch("assets.skills.advanced_tools.scripts.mutation.subprocess.run") as mock_run,
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "legacy_service.py\0"
            mock_run.return_value = mock_proc

            dry_run_res = batch_replace(
                pattern=pattern,
                replacement=replacement,
                file_glob="**/*.py",
                dry_run=True,
                paths=mock_paths,
            )

            assert dry_run_res["success"] is True
            assert dry_run_res["mode"] == "Dry-Run"
            assert dry_run_res["files_matched"] >= 1
            print("    ✅ Dry-Run complete:")
            print(f"       - Files matched: {dry_run_res['files_matched']}")
            print(f"       - Files to change: {dry_run_res['files_changed']}")
            print(f"       - Total replacements: {dry_run_res['total_replacements']}")

            # Verify no actual file modification happened
            original_content = legacy_file.read_text()
            assert "logger.debug" not in original_content
            assert "print" in original_content
            print("    ✅ Verified: No files modified (Dry-Run)")

        # --- Step 3: Refactoring - Apply (Execution) ---
        print("\n[Step 3] Agent applies changes (Live)...")

        with (
            patch(
                "assets.skills.advanced_tools.scripts.mutation.shutil.which",
                return_value="/usr/bin/rg",
            ),
            patch("assets.skills.advanced_tools.scripts.mutation.subprocess.run") as mock_run,
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "legacy_service.py\0"
            mock_run.return_value = mock_proc

            live_res = batch_replace(
                pattern=pattern,
                replacement=replacement,
                file_glob="**/*.py",
                dry_run=False,
                paths=mock_paths,
            )

            assert live_res["success"] is True
            assert live_res["mode"] == "Live"
            assert live_res["changes"][0]["status"] == "Modified"

            # Verify Content on Disk
            new_content = legacy_file.read_text()
            assert "logger.debug" in new_content
            assert "print" not in new_content
            print("    ✅ Code modified successfully:")
            print(f"       - {live_res['files_changed']} file(s) changed")
            print(f"       - {live_res['total_replacements']} replacement(s) made")

            # Show diff preview
            diff = live_res["changes"][0]["diff"]
            print("    📋 Diff preview:")
            for line in diff.split("\n")[:8]:
                print(f"       {line}")

        # --- Step 4: Quality Loop (Verification) ---
        print("\n[Step 4] Agent runs tests to verify fix...")

        from assets.skills.testing.scripts.pytest import run_pytest

        with (
            patch(
                "assets.skills.testing.scripts.pytest.shutil.which", return_value="/usr/bin/pytest"
            ),
            patch("assets.skills.testing.scripts.pytest.subprocess.run") as mock_run,
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 0  # Tests Pass
            mock_proc.stdout = """============================= test session starts ==============================
collected 2 items

test_legacy.py::test_process PASSED
test_legacy.py::test_cleanup PASSED

======================= 2 passed in 0.02s ======================="""
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc

            test_res = run_pytest(target=".", paths=mock_paths)

            assert test_res["success"] is True
            assert test_res["failed"] is False
            print("    ✅ Tests passed")

        print("\n" + "=" * 60)
        print("🎉 Mission Complete: Log Standardization Successful!")
        print("=" * 60)

        # Summary of the toolchain interaction
        print("\n📊 Toolchain Interaction Summary:")
        print("   1. advanced_tools.smart_search → Would find print statements")
        print("   2. advanced_tools.batch_replace (dry_run=True) → Previewed changes")
        print("   3. advanced_tools.batch_replace (dry_run=False) → Applied changes")
        print("   4. testing.run_pytest → Verified no regressions")


class TestBatchReplaceIntegration:
    """Integration tests for batch_replace with real files."""

    def test_batch_replace_dry_run_no_modification(self, tmp_path):
        """Verify dry_run does not modify files."""
        from assets.skills.advanced_tools.scripts.mutation import batch_replace


        # Setup
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world\nhello again\n")

        class MockPaths:
            project_root = tmp_path

        # Execute dry run
        with (
            patch(
                "assets.skills.advanced_tools.scripts.mutation.shutil.which",
                return_value="/usr/bin/rg",
            ),
            patch("assets.skills.advanced_tools.scripts.mutation.subprocess.run") as mock_run,
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "test.txt\0"
            mock_run.return_value = mock_proc

            result = batch_replace(
                pattern="hello", replacement="goodbye", dry_run=True, paths=MockPaths()
            )

        # Verify
        assert result["success"] is True
        assert result["mode"] == "Dry-Run"
        content = test_file.read_text()
        assert "hello world" in content  # Original unchanged
        assert "goodbye" not in content  # No modification

    def test_batch_replace_live_modifies_file(self, tmp_path):
        """Verify live mode actually modifies files."""
        from assets.skills.advanced_tools.scripts.mutation import batch_replace

        # Setup
        test_file = tmp_path / "test.txt"
        test_file.write_text("foo bar\nfoo baz\n")

        class MockPaths:
            project_root = tmp_path

        # Execute live
        with (
            patch(
                "assets.skills.advanced_tools.scripts.mutation.shutil.which",
                return_value="/usr/bin/rg",
            ),
            patch("assets.skills.advanced_tools.scripts.mutation.subprocess.run") as mock_run,
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            # Return relative path (as ripgrep would with cwd)
            mock_proc.stdout = "test.txt"
            mock_run.return_value = mock_proc

            result = batch_replace(
                pattern="foo", replacement="baz", dry_run=False, paths=MockPaths()
            )

        # Verify
        assert result["success"] is True, f"Failed: {result.get('error')}"
        assert result["mode"] == "Live"
        assert result["count"] == 1, f"Expected 1 change, got {result['count']}: {result}"
        content = test_file.read_text()
        assert "baz bar" in content, f"Expected 'baz bar' in: {content!r}"
        assert "baz baz" in content, f"Expected 'baz baz' in: {content!r}"
        assert "foo" not in content, f"Should have no 'foo' in: {content!r}"

    def test_batch_replace_generates_diff(self, tmp_path):
        """Verify diff is generated correctly."""
        from assets.skills.advanced_tools.scripts.mutation import batch_replace

        # Setup
        test_file = tmp_path / "test.txt"
        test_file.write_text("old_value\n")

        class MockPaths:
            project_root = tmp_path

        # Execute dry run
        with (
            patch(
                "assets.skills.advanced_tools.scripts.mutation.shutil.which",
                return_value="/usr/bin/rg",
            ),
            patch("assets.skills.advanced_tools.scripts.mutation.subprocess.run") as mock_run,
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "test.txt"
            mock_run.return_value = mock_proc

            result = batch_replace(
                pattern="old_value", replacement="new_value", dry_run=True, paths=MockPaths()
            )

        # Verify diff (uses ed diff format: < for old, > for new)
        assert result["success"] is True, f"Failed: {result.get('error')}"
        assert result["count"] == 1, f"Expected 1 change, got {result['count']}: {result}"
        diff = result["changes"][0]["diff"]
        assert "< old_value" in diff, f"Expected '< old_value' in diff: {diff}"
        assert "> new_value" in diff, f"Expected '> new_value' in diff: {diff}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
