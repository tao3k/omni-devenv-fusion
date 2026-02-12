# test_sandbox_examples.py - Tests for Sandbox NCL Configurations
#
# These tests verify that the NCL sandbox configurations work correctly.
# Since we're on macOS, we test NCL export and validation without nsjail.
#
# Requirements:
#   - nickel CLI must be installed: cargo install nickel-lang

"""Tests for NCL sandbox configurations."""

import json
import subprocess
from pathlib import Path

import pytest


# Paths - use absolute paths
REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
NCL_SANDBOX_DIR = REPO_ROOT / "packages" / "ncl" / "sandbox"
NCL_EXAMPLES_DIR = NCL_SANDBOX_DIR / "examples"


class NickelAvailability:
    """Check if nickel CLI is available."""

    @staticmethod
    def is_available() -> bool:
        """Check if nickel CLI is installed."""
        result = subprocess.run(
            ["which", "nickel"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0


@pytest.fixture
def nickel_check():
    """Fixture that skips tests if nickel is not installed."""
    if not NickelAvailability.is_available():
        pytest.skip("nickel CLI not installed. Run: cargo install nickel-lang")


@pytest.fixture
def sandbox_main() -> Path:
    """Path to the sandbox main.ncl file."""
    return NCL_SANDBOX_DIR / "main.ncl"


@pytest.fixture
def examples_dir() -> Path:
    """Path to the examples directory."""
    return NCL_EXAMPLES_DIR


class TestNickelInstallation:
    """Test that nickel CLI is available."""

    def test_nickel_is_installed(self):
        """Verify nickel CLI is installed."""
        result = subprocess.run(
            ["which", "nickel"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "nickel CLI not found. Install with: cargo install nickel-lang"
        )


class TestSandboxImports:
    """Test that NCL sandbox modules can be imported."""

    def test_main_module_imports(self, nickel_check, sandbox_main: Path):
        """Test that main sandbox module can be imported and exported."""
        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(sandbox_main)],
            capture_output=True,
            text=True,
            cwd=str(NCL_SANDBOX_DIR),
        )
        assert result.returncode == 0, f"NCL export failed: {result.stderr}"

        # Parse exported JSON
        data = json.loads(result.stdout)
        assert "version" in data
        assert data["version"] == "1.0.0"

    def test_seatbelt_module_imports(self, nickel_check):
        """Test that seatbelt module can be imported."""
        seatbelt_path = NCL_SANDBOX_DIR / "seatbelt" / "main.ncl"
        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(seatbelt_path)],
            capture_output=True,
            text=True,
            cwd=str(NCL_SANDBOX_DIR),
        )
        assert result.returncode == 0, f"Seatbelt NCL export failed: {result.stderr}"

    def test_skill_module_imports(self, nickel_check):
        """Test that skill module can be imported."""
        skill_path = NCL_SANDBOX_DIR / "skill" / "main.ncl"
        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(skill_path)],
            capture_output=True,
            text=True,
            cwd=str(NCL_SANDBOX_DIR),
        )
        assert result.returncode == 0, f"Skill NCL export failed: {result.stderr}"


class TestSandboxStructure:
    """Test that exported sandbox configurations have correct structure."""

    def test_main_module_structure(self, nickel_check, sandbox_main: Path):
        """Verify main module exports expected keys."""
        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(sandbox_main)],
            capture_output=True,
            text=True,
            cwd=str(NCL_SANDBOX_DIR),
        )
        assert result.returncode == 0

        data = json.loads(result.stdout)

        # Check namespace exports
        assert "lib" in data
        assert "nsjail" in data
        assert "seatbelt" in data
        assert "skill" in data

        # Check lib submodules
        assert "rlimits" in data.get("lib", {})
        assert "mounts" in data.get("lib", {})
        assert "network" in data.get("lib", {})

    def test_seatbelt_profile_structure(self, nickel_check):
        """Verify seatbelt profile has required fields."""
        seatbelt_path = NCL_SANDBOX_DIR / "seatbelt" / "main.ncl"
        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(seatbelt_path)],
            capture_output=True,
            text=True,
            cwd=str(NCL_SANDBOX_DIR),
        )
        assert result.returncode == 0

        data = json.loads(result.stdout)

        # Check pre-built profiles exist
        assert "minimal" in data
        assert "standard" in data
        assert "development" in data

        # Verify profiles are strings (SBPL content)
        assert isinstance(data["minimal"], str)
        assert "(version 1)" in data["minimal"]
        assert "(deny default)" in data["minimal"]

    def test_skill_profile_structure(self, nickel_check):
        """Verify skill profile has required fields."""
        skill_path = NCL_SANDBOX_DIR / "skill" / "main.ncl"
        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(skill_path)],
            capture_output=True,
            text=True,
            cwd=str(NCL_SANDBOX_DIR),
        )
        assert result.returncode == 0

        data = json.loads(result.stdout)

        # Check lib exports (functions are not exported to JSON)
        assert "lib" in data


class TestExampleConfigurations:
    """Test example sandbox configurations."""

    def test_data_processor_example(self, nickel_check, examples_dir: Path):
        """Test data-processor example configuration."""
        example_path = examples_dir / "data-processor.ncl"
        if not example_path.exists():
            pytest.skip(f"Example not found: {example_path}")

        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(example_path)],
            capture_output=True,
            text=True,
            cwd=str(NCL_SANDBOX_DIR),
        )
        assert result.returncode == 0, f"Data processor NCL export failed: {result.stderr}"

        data = json.loads(result.stdout)

        # Verify required fields
        assert data.get("skill_id") == "data-processor"
        assert data.get("platform") == "linux"
        assert "cmd" in data
        assert "resources" in data

    def test_web_scraper_example(self, nickel_check, examples_dir: Path):
        """Test web-scraper example configuration."""
        example_path = examples_dir / "web-scraper.ncl"
        if not example_path.exists():
            pytest.skip(f"Example not found: {example_path}")

        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(example_path)],
            capture_output=True,
            text=True,
            cwd=str(NCL_SANDBOX_DIR),
        )
        assert result.returncode == 0, f"Web scraper NCL export failed: {result.stderr}"

        data = json.loads(result.stdout)

        # Verify required fields
        assert data.get("skill_id") == "web-scraper"
        assert data.get("platform") == "linux"
        assert "cmd" in data

    def test_example_imports_sandbox_main(self, nickel_check, examples_dir: Path):
        """Test that examples can import sandbox main module."""
        example_path = examples_dir / "data-processor.ncl"
        if not example_path.exists():
            pytest.skip(f"Example not found: {example_path}")

        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(example_path)],
            capture_output=True,
            text=True,
            cwd=str(NCL_SANDBOX_DIR),
        )
        assert result.returncode == 0, f"Example import failed: {result.stderr}"


class TestResourceLimits:
    """Test resource limit configurations."""

    def test_resource_presets_exist(self, nickel_check, sandbox_main: Path):
        """Verify resource presets are defined."""
        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(sandbox_main)],
            capture_output=True,
            text=True,
            cwd=str(NCL_SANDBOX_DIR),
        )
        assert result.returncode == 0

        data = json.loads(result.stdout)
        rlimits = data.get("lib", {}).get("rlimits", {})

        assert "minimal" in rlimits
        assert "small" in rlimits
        assert "medium" in rlimits
        assert "large" in rlimits


class TestMountConfigurations:
    """Test mount point configurations."""

    def test_mount_presets_exist(self, nickel_check, sandbox_main: Path):
        """Verify mount presets are defined."""
        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(sandbox_main)],
            capture_output=True,
            text=True,
            cwd=str(NCL_SANDBOX_DIR),
        )
        assert result.returncode == 0

        data = json.loads(result.stdout)
        mounts = data.get("lib", {}).get("mounts", {})

        assert "essential" in mounts
        assert "standard" in mounts
        assert "development" in mounts


class TestNetworkPolicies:
    """Test network policy configurations."""

    def test_network_presets_exist(self, nickel_check, sandbox_main: Path):
        """Verify network presets are defined."""
        result = subprocess.run(
            ["nickel", "export", "--format", "json", str(sandbox_main)],
            capture_output=True,
            text=True,
            cwd=str(NCL_SANDBOX_DIR),
        )
        assert result.returncode == 0

        data = json.loads(result.stdout)
        network = data.get("lib", {}).get("network", {})

        assert "deny" in network
        assert "localhost" in network
        assert "container" in network
        assert "allow" in network
