"""
src/agent/core/installer.py
 Skill Installer using GitPython + subprocess

Features:
- Smart stash & update for dirty repos
- Sparse checkout for Monorepo support
- Dependency cycle detection
- Lockfile generation
- Python dependency installation
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
        # This is skills_dir/git - find the real GitPython
        # Remove ALL paths containing skills_dir from sys.path
        from common.skills_path import SKILLS_DIR

        skills_dir_str = str(SKILLS_DIR())  # SSOT: assets/skills
        skills_paths = [p for p in sys.path if skills_dir_str in p]
        for p in skills_paths:
            sys.path.remove(p)
        try:
            # Clear cached git module to force re-import from correct location
            if "git" in sys.modules:
                del sys.modules["git"]
            if "git.exc" in sys.modules:
                del sys.modules["git.exc"]
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

GitCommandError = _git_exc.GitCommandError
InvalidGitRepositoryError = _git_exc.InvalidGitRepositoryError

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging
import subprocess

from agent.core.skill_discovery import parse_skill_md

logger = logging.getLogger(__name__)

# Default lockfile name
LOCKFILE_NAME = ".omni-lock.json"


class SkillInstaller:
    """
    Smart Skill Installer using GitPython + subprocess.

    Uses GitPython for git operations and subprocess for better compatibility.
    """

    # Track installed repos to prevent circular dependencies
    _installing_repos: set[str] = set()

    def _run_git(self, cwd: str, *args) -> subprocess.CompletedProcess:
        """Run a git command."""
        return subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
        )

    def install(
        self,
        repo_url: str,
        target_dir: Path,
        version: str = "main",
        subpath: Optional[str] = None,
        repo_url_override: Optional[str] = None,
    ) -> dict:
        """
        Install or update a skill from a Git repository.

        Args:
            repo_url: URL of the Git repository
            target_dir: Target directory for the skill
            version: Git ref (branch, tag, commit) to checkout
            subpath: Optional subdirectory path (for Monorepo support)
            repo_url_override: Override URL for lockfile

        Returns:
            dict with installation metadata (revision, subpath, etc.)
        """
        # Check for circular dependencies
        cache_key = f"{repo_url}:{subpath or ''}"
        if cache_key in self._installing_repos:
            logger.warning(f"Circular dependency detected for {repo_url}, skipping")
            return {"success": True, "skipped": True, "reason": "circular_dependency"}
        self._installing_repos.add(cache_key)

        try:
            target_dir = Path(target_dir)

            # Check if directory is already a git repo
            is_new_clone = not (target_dir / ".git").exists()

            if is_new_clone:
                # Clone the repository
                logger.info(f"Cloning {repo_url} to {target_dir}")
                result = subprocess.run(
                    ["git", "clone", repo_url, str(target_dir)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    raise SkillInstallError(f"Failed to clone: {result.stderr}")
            else:
                # Pull latest changes
                logger.info(f"Updating {target_dir}")
                result = self._run_git(str(target_dir), "pull", "origin", version)
                if result.returncode != 0:
                    # Try fetch + reset if pull fails
                    result = self._run_git(str(target_dir), "fetch", "origin")
                    if result.returncode == 0:
                        result = self._run_git(
                            str(target_dir), "reset", "--hard", f"origin/{version}"
                        )

            # Checkout specified version
            if version and version != "HEAD":
                result = self._run_git(str(target_dir), "checkout", version)
                if result.returncode != 0:
                    # Try with -B for branch creation
                    result = self._run_git(
                        str(target_dir), "checkout", "-B", version, f"origin/{version}"
                    )

            # Configure Sparse Checkout for Monorepo support
            if subpath:
                self._configure_sparse_checkout(target_dir, subpath, refresh=True)

            #  Security scan before continuing
            security_result = self._security_scan(target_dir, repo_url)
            if not security_result["passed"]:
                raise SkillInstallError(
                    f"Security scan failed: {security_result['error']}",
                    hint="The skill failed security checks. Use --trust to bypass for trusted sources.",
                )

            # Get revision info
            revision = self.get_revision(target_dir)

            # Generate lockfile
            lock_path = target_dir / LOCKFILE_NAME
            self._generate_lockfile(
                lock_path,
                repo_url=repo_url_override or repo_url,
                revision=revision,
                subpath=subpath,
            )

            logger.info(f"Skill installed at {target_dir}")
            logger.info(f"Revision: {revision}")

            return {
                "success": True,
                "path": str(target_dir),
                "revision": revision,
                "subpath": subpath,
            }

        except SkillInstallError:
            raise

        except Exception as e:
            logger.error(f"Failed to install skill: {e}")
            raise SkillInstallError(
                f"Failed to install skill from {repo_url}: {e}",
                hint=self._get_error_hint(e),
            ) from e

        finally:
            self._installing_repos.discard(cache_key)

    def _configure_sparse_checkout(
        self, target_dir: Path, subpath: str, refresh: bool = True
    ) -> None:
        """
        Configure Git sparse checkout for Monorepo subdirectory support.
        """
        if not subpath:
            return

        logger.info(f"Configuring sparse checkout for subpath: {subpath}")

        repo = git.Repo(target_dir)

        # Enable sparse checkout
        repo.git.config("core.sparseCheckout", "true")

        # Write sparse-checkout rules
        sparse_info = target_dir / ".git" / "info" / "sparse-checkout"
        sparse_info.write_text(f"/{subpath}\n")

        # Use modern sparse-checkout (Git >= 2.25)
        try:
            repo.git.sparse_checkout("init", "--cone")
            repo.git.sparse_checkout("set", subpath)
        except GitCommandError:
            # Fallback for older Git versions
            logger.debug("Using legacy sparse-checkout method")

        # Force refresh working tree to match sparse checkout
        if refresh:
            try:
                repo.git.read_tree("-mu", "HEAD")
                logger.info(f"Working tree refreshed for sparse checkout: {subpath}")
            except GitCommandError as e:
                logger.warning(
                    f"Could not refresh working tree (may be normal if files were deleted): {e}"
                )

    def update(self, target_dir: Path, strategy: str = "stash") -> dict:
        """
        Update an already installed skill to the latest version.

        Args:
            target_dir: Directory of the installed skill
            strategy: Update strategy for dirty repos:
                - "stash": Stash local changes, pull, then pop (default)
                - "abort": Abort if local changes detected
                - "overwrite": Force overwrite (dangerous!)

        Returns:
            dict with update metadata
        """
        if not target_dir.exists():
            raise SkillInstallError(f"Skill directory does not exist: {target_dir}")

        logger.info(f"Updating skill at {target_dir}")

        repo_git = git.Repo(str(target_dir))

        # Check for dirty state
        if repo_git.is_dirty():
            if strategy == "abort":
                raise SkillInstallError(
                    "Local changes detected. Aborting update. "
                    "Please commit or stash your changes first.",
                    hint="Run 'git status' to see changes, then 'git stash' or 'git commit'.",
                )
            elif strategy == "overwrite":
                logger.warning("OVERWRITE mode: Discarding local changes!")
                repo_git.git.reset("--hard", "HEAD")
            else:  # stash strategy (default)
                self._smart_stash_update(repo_git)

        try:
            # Pull latest changes
            result = self._run_git(str(target_dir), "pull")
            if result.returncode != 0:
                # Try fetch + reset
                result = self._run_git(str(target_dir), "fetch", "origin")
                if result.returncode == 0:
                    result = self._run_git(str(target_dir), "reset", "--hard", "origin/HEAD")

            # Get current sparse checkout subpath if exists
            subpath = self._read_lockfile(target_dir).get("subpath")

            # Refresh sparse checkout if needed
            if subpath:
                self._configure_sparse_checkout(target_dir, subpath, refresh=True)

            revision = self.get_revision(target_dir)

            # Update lockfile
            lock_path = target_dir / LOCKFILE_NAME
            lock_data = self._read_lockfile(target_dir)
            self._generate_lockfile(
                lock_path,
                repo_url=lock_data.get("url", ""),
                revision=revision,
                subpath=subpath,
            )

            logger.info(f"Skill updated. Revision: {revision}")

            return {
                "success": True,
                "path": str(target_dir),
                "revision": revision,
            }

        except SkillInstallError:
            raise

        except Exception as e:
            logger.error(f"Failed to update skill: {e}")
            raise SkillInstallError(
                f"Failed to update skill: {e}",
                hint=self._get_error_hint(e),
            ) from e

    def _smart_stash_update(self, repo_git: git.Repo) -> None:
        """
        Smart stash & update strategy.
        Stashes local changes, pulls, then attempts to pop stash.
        """
        logger.info("Stashing local changes before update...")

        # Stash with a descriptive message
        stash_msg = f"Auto-stash before omni update at {datetime.now().isoformat()}"
        repo_git.git.stash("push", "-m", stash_msg)

        try:
            # Pull latest changes
            repo_git.git.pull()

            # Try to restore local changes
            logger.info("Restoring local changes...")
            repo_git.git.stash("pop")
            logger.info("Local changes restored successfully!")

        except GitCommandError as e:
            # Merge conflict occurred
            logger.error(f"Merge conflict during update! Changes left in stash. Error: {e}")
            raise SkillInstallError(
                f"Merge conflict occurred. Your changes are stashed safely.\n"
                f"Resolve conflicts manually, then run:\n"
                f"  git stash drop  # to remove the stash after resolving",
                hint="Run 'git status' and 'git stash list' to see the stashed changes.",
            )

    def _get_error_hint(self, error: Exception) -> str:
        """Provide helpful hints based on common error types."""
        error_str = str(error).lower()

        if "authentication" in error_str or "permission" in error_str:
            return (
                "Authentication failed. Check your Git credentials or SSH keys.\n"
                "For GitHub, ensure your SSH key is added to ssh-agent, or use a personal access token."
            )
        elif "could not resolve host" in error_str or "network" in error_str:
            return (
                "Network error. Check your internet connection.\n"
                "If behind a firewall, ensure Git can access the remote repository."
            )
        elif "not found" in error_str or "does not exist" in error_str:
            return (
                "git.Repository not found. Check the URL is correct.\n"
                "For private repos, ensure you have access permissions."
            )
        else:
            return "Check the error message above for details."

    def _generate_lockfile(
        self,
        lock_path: Path,
        repo_url: str,
        revision: str,
        subpath: Optional[str] = None,
    ) -> None:
        """Generate or update the lockfile for a skill."""
        lock_data = {
            "url": repo_url,
            "revision": revision,
            "subpath": subpath,
            "updated_at": datetime.now().isoformat(),
        }
        lock_path.write_text(json.dumps(lock_data, indent=2))
        logger.debug(f"Generated lockfile: {lock_path}")

    def _read_lockfile(self, target_dir: Path) -> dict:
        """Read the lockfile for a skill."""
        lock_path = target_dir / LOCKFILE_NAME
        if lock_path.exists():
            try:
                return json.loads(lock_path.read_text())
            except json.JSONDecodeError:
                logger.warning(f"Corrupted lockfile: {lock_path}")
        return {}

    def get_revision(self, target_dir: Path) -> Optional[str]:
        """
        Get the current revision (commit hash) of an installed skill.

        Args:
            target_dir: Directory of the installed skill

        Returns:
            Commit hash or None if not a git repo
        """
        try:
            # Use GitPython directly for better compatibility
            repo = git.Repo(str(target_dir))
            return repo.head.commit.hexsha
        except (InvalidGitgit.RepositoryError, ValueError):
            pass

        # Fallback to git rev-parse
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        return None

    def is_dirty(self, target_dir: Path) -> bool:
        """
        Check if the skill directory has uncommitted changes (only within this skill).

        Args:
            target_dir: Directory of the installed skill

        Returns:
            True if there are uncommitted changes in this skill directory
        """
        try:
            import subprocess

            # Check modified files within the skill directory
            result = subprocess.run(
                ["git", "diff", "--name-only", "--", "."],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
            )
            modified = bool(result.stdout.strip())

            # Check untracked files within the skill directory
            # Exclude .omni-lock.json as it's generated by the installer
            untracked_result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard", "--", "."],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
            )
            untracked_files = [
                f for f in untracked_result.stdout.strip().split("\n") if f and f != LOCKFILE_NAME
            ]
            untracked = bool(untracked_files)

            return modified or untracked
        except Exception:
            return False

    def install_python_deps(self, target_dir: Path) -> dict:
        """
        Install Python dependencies from manifest.

        Args:
            target_dir: Directory of the installed skill

        Returns:
            dict with installation results
        """
        skill_md_path = target_dir / "SKILL.md"
        if not skill_md_path.exists():
            return {"success": True, "message": "No SKILL.md found"}

        try:
            # Use Rust scanner for high-performance parsing
            meta = parse_skill_md(target_dir) or {}
            python_deps = meta.get("dependencies", {}).get("python", {})

            if not python_deps:
                return {"success": True, "message": "No Python dependencies"}

            logger.info(f"Installing Python dependencies: {list(python_deps.keys())}")

            # Build pip install command
            pkgs = " ".join(f"{pkg}{ver}" for pkg, ver in python_deps.items())
            cmd = ["pip", "install", "-q", pkgs]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return {"success": True, "packages": list(python_deps.keys())}
            else:
                return {
                    "success": False,
                    "error": result.stderr,
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _security_scan(self, target_dir: Path, repo_url: str) -> dict:
        """
         Security scan for newly installed skill.

        Args:
            target_dir: Directory of the installed skill
            repo_url: git.Repository URL for trusted source check

        Returns:
            dict with scan result: {"passed": bool, "error": str or None, "report": dict}
        """
        from common.config.settings import get_setting

        # Check if security is enabled
        if not get_setting("security.enabled", True):
            return {"passed": True, "error": None, "report": {}}

        try:
            from agent.core.security.immune_system import ImmuneSystem, Decision

            immune = ImmuneSystem()
            assessment = immune.assess(target_dir)

            # Check if skill is from trusted source
            is_trusted, _ = immune._check_trusted(target_dir, assessment.scanner_report)

            # Prepare report
            report = assessment.to_dict()

            # Make decision
            if assessment.decision == Decision.BLOCK:
                logger.warning(f"Skill blocked by security scan: {target_dir.name}")
                return {
                    "passed": False,
                    "error": f"Security concerns detected (score: {assessment.scanner_report.total_score})",
                    "report": report,
                }
            elif assessment.decision == Decision.WARN:
                logger.info(f"Skill has security warnings: {target_dir.name}")
                return {
                    "passed": True,
                    "error": None,
                    "report": report,
                }
            else:
                logger.info(f"Skill passed security scan: {target_dir.name}")
                return {
                    "passed": True,
                    "error": None,
                    "report": report,
                }

        except Exception as e:
            logger.error(f"Security scan error: {e}")
            # Fail open - don't block installation on scan error
            return {
                "passed": True,
                "error": str(e),
                "report": {"error": str(e)},
            }


class SkillInstallError(Exception):
    """Raised when skill installation fails."""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self):
        if self.hint:
            return f"{self.message}\n\nHint: {self.hint}"
        return self.message


# Convenience function
def install_skill(
    repo_url: str,
    target_dir: Path,
    version: str = "main",
    subpath: Optional[str] = None,
) -> dict:
    """
    Convenience function to install a skill.

    Args:
        repo_url: URL of the Git repository
        target_dir: Target directory for the skill
        version: Git ref to checkout
        subpath: Optional subdirectory path (for Monorepo)

    Returns:
        Installation metadata dict
    """
    installer = SkillInstaller()
    return installer.install(
        repo_url=repo_url,
        target_dir=target_dir,
        version=version,
        subpath=subpath,
    )
