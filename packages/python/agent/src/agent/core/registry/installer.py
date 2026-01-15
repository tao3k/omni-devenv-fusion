"""
agent/core/registry/installer.py
 Remote Installer

Handle remote skill installation and updates using libvcs + GitPython.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from git import Repo

from agent.core.installer import SkillInstaller as BaseInstaller

if TYPE_CHECKING:
    from agent.core.registry.core import SkillRegistry

logger = structlog.get_logger(__name__)


class RemoteInstaller:
    """
    Handle remote skill installation and updates.

    Responsibilities:
    - Clone skills from Git repositories
    - Update existing skills
    - Install Python dependencies
    """

    __slots__ = ("registry", "_base_installer")

    def __init__(self, registry: "SkillRegistry") -> None:
        self.registry = registry
        self._base_installer = BaseInstaller()

    def install(self, target_dir: Path, repo_url: str, version: str = "main") -> tuple[bool, str]:
        """
        Install a skill from a remote Git repository.

        Args:
            target_dir: Target directory for the skill
            repo_url: URL of the Git repository
            version: Git ref (branch, tag, commit) to checkout

        Returns:
            Tuple of (success, message)
        """
        try:
            result = self._base_installer.install(
                repo_url=repo_url,
                target_dir=target_dir,
                version=version,
            )
            return True, f"Skill installed from {repo_url}"

        except Exception as e:
            logger.error("Installation failed", error=str(e))
            return False, f"Installation failed: {e}"

    def update(self, target_dir: Path, strategy: str = "stash") -> dict[str, Any]:
        """
        Update an already installed skill.

        Args:
            target_dir: Target directory for the skill
            strategy: Update strategy (stash, abort, overwrite)

        Returns:
            Dict with update result
        """
        return self._base_installer.update(target_dir, strategy=strategy)

    def install_python_deps(self, target_dir: Path) -> dict[str, Any]:
        """Install Python dependencies from skill's manifest."""
        return self._base_installer.install_python_deps(target_dir)

    def get_revision(self, target_dir: Path) -> str | None:
        """Get the current git revision of a skill."""
        return self._base_installer.get_revision(target_dir)

    def is_dirty(self, target_dir: Path) -> bool:
        """Check if a skill has uncommitted changes."""
        return self._base_installer.is_dirty(target_dir)


def install_remote_skill(
    registry: "SkillRegistry",
    skill_name: str,
    repo_url: str,
    version: str = "main",
    install_deps: bool = True,
) -> tuple[bool, str]:
    """
    Convenience function to install a remote skill.
    """
    installer = RemoteInstaller(registry)
    return installer.install(registry.skills_dir / skill_name, repo_url, version)


def update_remote_skill(
    registry: "SkillRegistry",
    skill_name: str,
    strategy: str = "stash",
) -> tuple[bool, str]:
    """
    Convenience function to update a remote skill.
    """
    installer = RemoteInstaller(registry)
    target_dir = registry.skills_dir / skill_name
    return installer.update(target_dir, strategy)


def install_with_dependencies(
    registry: "SkillRegistry",
    skill_name: str,
    repo_url: str,
    version: str = "main",
    visited: set[str] | None = None,
) -> tuple[bool, str]:
    """
    Install a skill and recursively install its dependencies.
    """
    if visited is None:
        visited = set()

    # Prevent circular dependencies
    if skill_name in visited:
        return True, f"Skill '{skill_name}' (skipped - circular dependency)"

    visited.add(skill_name)
    target_dir = registry.skills_dir / skill_name

    # Install main skill
    return install_remote_skill(registry, skill_name, repo_url, version)
