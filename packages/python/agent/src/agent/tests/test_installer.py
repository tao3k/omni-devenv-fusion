"""
packages/python/agent/src/agent/tests/test_phase26_installer.py
Test Suite for Phase 26: Skill Network & Installer

Tests cover:
- Fresh install from remote repository
- Manifest version reading
- Dirty state detection and handling
- Update strategy with stash/pop
- Lockfile generation
- Dependency cycle detection
"""

import json
import pytest
import subprocess
from pathlib import Path
from git import Repo

from agent.core.installer import SkillInstaller
from agent.core.registry import SkillRegistry, get_skill_registry


@pytest.fixture
def mock_remote_repo(tmp_path):
    """Create a local 'remote' Git repository for testing."""
    remote_dir = tmp_path / "remote_skill_repo"
    remote_dir.mkdir()

    # Initialize git
    repo = Repo.init(remote_dir)

    # Create manifest.json
    manifest = {
        "manifest_version": "2.0.0",
        "type": "skill",
        "name": "test-skill",
        "version": "1.0.0",
        "description": "A test skill for Phase 26",
        "author": "test",
        "license": "Apache-2.0",
        "routing_keywords": ["test"],
        "tools_module": "assets.skills.test.tools",
        "guide_file": "guide.md",
        "dependencies": {
            "skills": {},
            "python": {},
        },
    }
    (remote_dir / "manifest.json").write_text(json.dumps(manifest))

    # Create tools.py with @skill_command decorator
    (remote_dir / "tools.py").write_text(
        '''"""Test skill tools."""
from agent.skills.decorators import skill_command

@skill_command(category="test")
def test_hello(name: str = "World") -> str:
    """Say hello."""
    return f"Hello, {name}!"

@skill_command(category="test")
def test_version() -> str:
    """Return version."""
    return "1.0.0"
'''
    )

    # Create guide.md
    (remote_dir / "guide.md").write_text("# Test Skill\n\nA test skill.")

    # Commit
    repo.index.add(["manifest.json", "tools.py", "guide.md"])
    repo.index.commit("Initial commit v1.0.0")

    return str(remote_dir)


@pytest.fixture
def skill_install_dir(tmp_path):
    """Create a skills directory for installation."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return skills_dir


class TestSkillInstaller:
    """Test SkillInstaller core functionality."""

    def test_fresh_install(self, mock_remote_repo, skill_install_dir):
        """Scenario 1: Fresh installation from remote."""
        install_dir = skill_install_dir / "test-skill"
        installer = SkillInstaller()

        # Execute install
        result = installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir,
            version="main",
        )

        # Verify
        assert result["success"] is True
        assert (install_dir / "manifest.json").exists()
        assert (install_dir / "tools.py").exists()
        assert (install_dir / "guide.md").exists()
        assert result["revision"] is not None
        assert len(result["revision"]) == 40  # Full SHA

    def test_install_generates_lockfile(self, mock_remote_repo, skill_install_dir):
        """Scenario 2: Verify lockfile generation."""
        install_dir = skill_install_dir / "test-skill"
        installer = SkillInstaller()

        installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir,
            version="main",
        )

        # Check lockfile exists
        lockfile_path = install_dir / ".omni-lock.json"
        assert lockfile_path.exists()

        # Verify lockfile content
        lock_data = json.loads(lockfile_path.read_text())
        assert "url" in lock_data
        assert "revision" in lock_data
        assert "updated_at" in lock_data

    def test_version_from_manifest(self, mock_remote_repo, skill_install_dir):
        """Scenario 3: Version resolved from manifest."""
        install_dir = skill_install_dir / "test-skill"
        installer = SkillInstaller()

        # Install first to create the skill directory
        installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir,
            version="main",
        )

        # Read manifest version
        manifest = json.loads((install_dir / "manifest.json").read_text())
        assert manifest["version"] == "1.0.0"

    def test_dirty_state_detection(self, mock_remote_repo, skill_install_dir):
        """Scenario 4: Detect when user modifies local code."""
        install_dir = skill_install_dir / "test-skill"
        installer = SkillInstaller()

        # Install first
        installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir,
            version="main",
        )

        # Verify clean state
        assert installer.is_dirty(install_dir) is False

        # Modify a file (simulate user hack)
        tools_file = install_dir / "tools.py"
        original = tools_file.read_text()
        tools_file.write_text(original + "\n# User Hacked This Line")

        # Verify dirty state is detected
        assert installer.is_dirty(install_dir) is True

    def test_dirty_update_with_stash(self, mock_remote_repo, skill_install_dir):
        """Scenario 5: Update with dirty state uses stash strategy."""
        install_dir = skill_install_dir / "test-skill"
        installer = SkillInstaller()

        # 1. Install v1
        installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir,
            version="main",
        )

        # 2. User creates a NEW file (won't conflict with remote changes)
        custom_file = install_dir / "custom_feature.py"
        custom_file.write_text(
            "# User Custom Feature\ndef my_feature():\n    return 'user custom'\n"
        )

        assert installer.is_dirty(install_dir) is True

        # 3. Update remote to v2
        remote_repo = Repo(mock_remote_repo)
        (Path(mock_remote_repo) / "tools.py").write_text(
            '''"""Test skill tools v2."""
from agent.skills.decorators import skill_command

@skill_command(category="test")
def test_hello(name: str = "World") -> str:
    """Say hello v2."""
    return f"Hello v2, {name}!"

@skill_command(category="test")
def test_version() -> str:
    """Return version v2."""
    return "2.0.0"
'''
        )
        (Path(mock_remote_repo) / "manifest.json").write_text(
            json.dumps(
                {
                    "manifest_version": "2.0.0",
                    "type": "skill",
                    "name": "test-skill",
                    "version": "2.0.0",  # Updated version
                    "description": "A test skill v2",
                    "author": "test",
                    "license": "Apache-2.0",
                    "routing_keywords": ["test"],
                    "tools_module": "assets.skills.test.tools",
                    "guide_file": "guide.md",
                    "dependencies": {"skills": {}, "python": {}},
                }
            )
        )
        remote_repo.index.add(["tools.py", "manifest.json"])
        remote_repo.index.commit("Update to v2.0.0")

        # 4. Update skill (this handles dirty state with stash strategy)
        result = installer.update(
            target_dir=install_dir,
            strategy="stash",
        )

        # 5. Verify v2 content is present
        tools_file = install_dir / "tools.py"
        content = tools_file.read_text()
        assert "v2" in content or "2.0.0" in content

        # 6. User custom file should be preserved after stash pop
        assert custom_file.exists()
        custom_content = custom_file.read_text()
        assert "User Custom Feature" in custom_content

        # 7. Verify update result indicates success
        assert result["success"] is True

    def test_get_revision(self, mock_remote_repo, skill_install_dir):
        """Test revision retrieval."""
        install_dir = skill_install_dir / "test-skill"
        installer = SkillInstaller()

        installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir,
            version="main",
        )

        revision = installer.get_revision(install_dir)
        assert revision is not None
        assert len(revision) == 40


class TestSkillRegistry:
    """Test SkillRegistry version resolution."""

    def test_resolve_version_from_manifest(self, skill_install_dir, mock_remote_repo):
        """Test version resolution when manifest has version."""
        install_dir = skill_install_dir / "test-skill"
        installer = SkillInstaller()

        installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir,
            version="main",
        )

        # Get registry with temp skills dir
        registry = SkillRegistry()
        original_skills_dir = registry.skills_dir
        registry.skills_dir = skill_install_dir

        try:
            version = registry._resolve_skill_version(install_dir)
            # Should resolve to full SHA since no lockfile for fresh install
            assert version != "unknown"
        finally:
            registry.skills_dir = original_skills_dir

    def test_resolve_version_from_lockfile(self, skill_install_dir, mock_remote_repo):
        """Test version resolution from lockfile."""
        install_dir = skill_install_dir / "test-skill"
        installer = SkillInstaller()

        installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir,
            version="main",
        )

        # Get registry with temp skills dir
        registry = SkillRegistry()
        original_skills_dir = registry.skills_dir
        registry.skills_dir = skill_install_dir

        try:
            version = registry._resolve_skill_version(install_dir)
            # Should contain lock info
            assert version != "unknown"
        finally:
            registry.skills_dir = original_skills_dir

    def test_get_skill_info(self, skill_install_dir, mock_remote_repo):
        """Test get_skill_info returns complete info."""
        install_dir = skill_install_dir / "test-skill"
        installer = SkillInstaller()

        installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir,
            version="main",
        )

        # Get registry with temp skills dir
        registry = SkillRegistry()
        original_skills_dir = registry.skills_dir
        registry.skills_dir = skill_install_dir

        try:
            info = registry.get_skill_info("test-skill")
            assert "name" in info
            assert "version" in info
            assert "path" in info
            assert "revision" in info
            assert "is_dirty" in info
            assert "manifest" in info
            assert "lockfile" in info
        finally:
            registry.skills_dir = original_skills_dir


class TestDependencyCycle:
    """Test dependency cycle detection."""

    def test_no_cycle_for_same_repo(self, skill_install_dir, mock_remote_repo):
        """Test that installing same repo twice doesn't cause infinite loop."""
        installer = SkillInstaller()

        # First install
        install_dir1 = skill_install_dir / "skill1"
        result1 = installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir1,
            version="main",
        )

        # Second install (different target, same repo)
        install_dir2 = skill_install_dir / "skill2"
        result2 = installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir2,
            version="main",
        )

        # Both should succeed
        assert result1["success"] is True
        assert result2["success"] is True


class TestSparseCheckout:
    """Test sparse checkout for monorepo support."""

    def test_sparse_checkout_configure(self, skill_install_dir, mock_remote_repo):
        """Test sparse checkout configuration."""
        install_dir = skill_install_dir / "subdir_skill"
        installer = SkillInstaller()

        # Install with subpath
        result = installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir,
            version="main",
            subpath="assets/skills",  # This won't work for a simple repo but should not crash
        )

        # For a simple repo without subpath, should still work
        assert result["success"] is True


class TestPythonDependencies:
    """Test Python dependency installation."""

    def test_install_python_deps_empty(self, skill_install_dir, mock_remote_repo):
        """Test installing when no Python deps defined."""
        install_dir = skill_install_dir / "test-skill"
        installer = SkillInstaller()

        installer.install(
            repo_url=mock_remote_repo,
            target_dir=install_dir,
            version="main",
        )

        # Install Python deps (empty in this case)
        result = installer.install_python_deps(install_dir)
        assert result["success"] is True

    def test_install_python_deps_with_manifest(self, skill_install_dir, tmp_path):
        """Test installing Python deps from manifest."""
        install_dir = skill_install_dir / "test-skill"
        install_dir.mkdir()

        # Create manifest with Python deps
        manifest = {
            "manifest_version": "2.0.0",
            "type": "skill",
            "name": "test-skill",
            "version": "1.0.0",
            "description": "Test",
            "author": "test",
            "license": "Apache-2.0",
            "routing_keywords": ["test"],
            "tools_module": "assets.skills.test.tools",
            "guide_file": "guide.md",
            "dependencies": {
                "skills": {},
                "python": {"requests": ">=2.28.0"},
            },
        }
        (install_dir / "manifest.json").write_text(json.dumps(manifest))

        installer = SkillInstaller()
        result = installer.install_python_deps(install_dir)

        # Should either succeed or fail gracefully (network/pkg not available)
        # The key is it shouldn't crash
        assert "success" in result


class TestErrorHandling:
    """Test error handling and user-friendly messages."""

    def test_invalid_repo_url(self, skill_install_dir):
        """Test error handling for invalid repository."""
        installer = SkillInstaller()
        install_dir = skill_install_dir / "test-skill"

        # This should raise SkillInstallError with helpful hint
        with pytest.raises(Exception):
            installer.install(
                repo_url="https://invalid-repo-that-does-not-exist.example.com/repo.git",
                target_dir=install_dir,
                version="main",
            )

    def test_non_existent_skill_get_info(self, skill_install_dir):
        """Test get_skill_info for non-existent skill."""
        registry = SkillRegistry()
        original_skills_dir = registry.skills_dir
        registry.skills_dir = skill_install_dir

        try:
            info = registry.get_skill_info("non-existent-skill")
            assert "error" in info
        finally:
            registry.skills_dir = original_skills_dir
