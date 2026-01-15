"""
agent/core/registry/resolver.py
 Version Resolver

Multi-strategy skill version resolution.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import structlog
from git import Repo, InvalidGitRepositoryError

logger = structlog.get_logger(__name__)


class VersionResolver:
    """
    Resolve skill versions using multiple strategies:

    1. .omni-lock.json (Omni Managed)
    2. SKILL.md frontmatter (Static version)
    3. git rev-parse HEAD (Dev Mode)
    """

    @staticmethod
    def resolve_version(skill_path: Path) -> str:
        """
        Resolve skill version using multi-strategy approach.
        """
        # Strategy 1: Lockfile
        lockfile_path = skill_path / ".omni-lock.json"
        if lockfile_path.exists():
            try:
                data = json.loads(lockfile_path.read_text())
                revision = data.get("revision", "")[:7]
                updated = data.get("updated_at", "")[:10]
                return f"{revision} ({updated})"
            except Exception:
                pass

        # Strategy 2: SKILL.md
        import frontmatter

        skill_md_path = skill_path / "SKILL.md"
        if skill_md_path.exists():
            try:
                with open(skill_md_path) as f:
                    post = frontmatter.load(f)
                meta = post.metadata or {}
                if "version" in meta:
                    return meta["version"]
            except Exception:
                pass

        # Strategy 3: Git HEAD
        try:
            repo = Repo(skill_path)
            sha = repo.head.commit.hexsha
            is_dirty = repo.is_dirty()
            suffix = " *" if is_dirty else ""
            return f"{sha[:7]}{suffix}"
        except (InvalidGitRepositoryError, ValueError):
            pass

        # Strategy 4: Git rev-parse from parent repo
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(skill_path),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                sha = result.stdout.strip()
                diff_result = subprocess.run(
                    ["git", "diff", "--name-only", "--", "."],
                    cwd=str(skill_path),
                    capture_output=True,
                    text=True,
                )
                untracked_result = subprocess.run(
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    cwd=str(skill_path),
                    capture_output=True,
                    text=True,
                )
                is_dirty = bool(diff_result.stdout.strip() or untracked_result.stdout.strip())
                suffix = " *" if is_dirty else ""
                return f"{sha[:7]}{suffix}"
        except Exception:
            pass

        return "unknown"

    @staticmethod
    def resolve_revision(skill_path: Path) -> str | None:
        """
        Get the current git revision of an installed skill.
        """
        try:
            repo = Repo(skill_path)
            return repo.head.commit.hexsha[:7]
        except (InvalidGitRepositoryError, ValueError):
            pass

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(skill_path),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()[:7]
        except Exception:
            pass

        return None

    @staticmethod
    def is_dirty(skill_path: Path) -> bool:
        """Check if a skill has uncommitted changes."""
        try:
            repo = Repo(skill_path)
            return repo.is_dirty()
        except (InvalidGitRepositoryError, ValueError):
            pass

        try:
            diff_result = subprocess.run(
                ["git", "diff", "--name-only", "--", "."],
                cwd=str(skill_path),
                capture_output=True,
                text=True,
            )
            untracked_result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=str(skill_path),
                capture_output=True,
                text=True,
            )
            return bool(diff_result.stdout.strip() or untracked_result.stdout.strip())
        except Exception:
            return False

    @staticmethod
    def get_lock_info(skill_path: Path) -> dict[str, Any] | None:
        """Get information from .omni-lock.json."""
        lockfile_path = skill_path / ".omni-lock.json"
        if not lockfile_path.exists():
            return None

        try:
            return json.loads(lockfile_path.read_text())
        except Exception:
            return None
