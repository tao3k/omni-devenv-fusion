"""
agent/core/registry/resolver.py
 Version Resolver

Multi-strategy skill version resolution.
Uses Rust scanner for SKILL.md parsing.
"""

# Import GitPython FIRST, before any other imports
# This must be done before skills path is added to sys.path
import importlib.util
import os
import sys

_git_spec = importlib.util.find_spec("git")
if _git_spec:
    # Check if this is the real GitPython package (has exc.py)
    git_origin = _git_spec.origin
    git_dir = os.path.dirname(git_origin) if git_origin else ""
    has_exc = os.path.exists(os.path.join(git_dir, "exc.py"))

    if has_exc:
        # This is the real GitPython package
        git = importlib.import_module("git")
        _git_exc = importlib.import_module("git.exc")
    else:
        # This is assets/skills/git - find the real GitPython
        # Remove ALL paths containing assets/skills from sys.path
        skills_paths = [p for p in sys.path if "assets/skills" in p]
        for p in skills_paths:
            sys.path.remove(p)
        try:
            git = importlib.import_module("git")
            _git_exc = importlib.import_module("git.exc")
        finally:
            # Restore skills paths
            for p in reversed(skills_paths):
                sys.path.insert(0, p)
else:
    # GitPython not found at all
    import git  # noqa: F401
    import git.exc as _git_exc  # type: ignore

InvalidGitRepositoryError = _git_exc.InvalidGitRepositoryError

import json
import subprocess
from pathlib import Path
from typing import Any, Optional

import structlog

from agent.core.skill_discovery import parse_skill_md

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

        # Strategy 2: SKILL.md (using Rust scanner)
        skill_md_path = skill_path / "SKILL.md"
        if skill_md_path.exists():
            try:
                meta = parse_skill_md(skill_path)
                if meta and "version" in meta:
                    return meta["version"]
            except Exception:
                pass

        # Strategy 3: Git HEAD
        try:
            repo = git.Repo(skill_path)
            sha = repo.head.commit.hexsha
            is_dirty = repo.is_dirty()
            suffix = " *" if is_dirty else ""
            return f"{sha[:7]}{suffix}"
        except (InvalidGitgit.RepositoryError, ValueError):
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
            repo = git.Repo(skill_path)
            return repo.head.commit.hexsha[:7]
        except (InvalidGitgit.RepositoryError, ValueError):
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
            repo = git.Repo(skill_path)
            return repo.is_dirty()
        except (InvalidGitgit.RepositoryError, ValueError):
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
