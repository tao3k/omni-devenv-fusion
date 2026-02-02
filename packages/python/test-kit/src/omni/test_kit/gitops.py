import subprocess
import re
from pathlib import Path
from typing import List, Optional


class GitOpsVerifier:
    """
    Verifier for GitOps workflows.
    Provides fluent assertions for Git repository state, facilitating
    concise and robust testing of Git-related skills and automations.
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def _run_git(self, args: List[str]) -> str:
        """Run a git command in the test repository."""
        try:
            result = subprocess.run(
                ["git"] + args, cwd=self.repo_path, capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise AssertionError(f"Git command failed: git {' '.join(args)}\nError: {e.stderr}")

    def assert_clean(self) -> "GitOpsVerifier":
        """Assert that the working directory is clean (no modified or untracked files)."""
        status = self._run_git(["status", "--porcelain"])
        assert not status, f"Git repo is dirty (expected clean):\n{status}"
        return self

    def assert_dirty(self) -> "GitOpsVerifier":
        """Assert that the working directory has changes."""
        status = self._run_git(["status", "--porcelain"])
        assert status, "Git repo is clean (expected dirty)"
        return self

    def assert_staged(self, *files: str) -> "GitOpsVerifier":
        """Assert that specific files are staged for commit."""
        status = self._run_git(["diff", "--name-only", "--cached"])
        staged = set(status.splitlines())
        for f in files:
            assert f in staged, f"File '{f}' is not staged. Staged files: {staged}"
        return self

    def assert_unstaged(self, *files: str) -> "GitOpsVerifier":
        """Assert that specific files are modified but NOT staged."""
        # diff --name-only shows unstaged changes
        status = self._run_git(["diff", "--name-only"])
        modified = set(status.splitlines())
        # Also check untracked
        untracked_status = self._run_git(["ls-files", "--others", "--exclude-standard"])
        untracked = set(untracked_status.splitlines())

        all_unstaged = modified.union(untracked)

        for f in files:
            assert f in all_unstaged, (
                f"File '{f}' is not in unstaged/untracked changes. Status: {all_unstaged}"
            )
        return self

    def assert_commit_exists(
        self, message_pattern: str, files_changed: Optional[List[str]] = None
    ) -> "GitOpsVerifier":
        """
        Assert that the latest commit matches criteria.

        Args:
            message_pattern: Regex pattern to match commit message subject.
            files_changed: Optional list of files that should have been changed in this commit.
        """
        log = self._run_git(["log", "-1", "--pretty=%s"])
        assert re.search(message_pattern, log), (
            f"Latest commit message '{log}' does not match pattern '{message_pattern}'"
        )

        if files_changed:
            changed = self._run_git(["show", "--name-only", "--format=", "HEAD"]).splitlines()
            changed_set = set(changed)
            for f in files_changed:
                assert f in changed_set, (
                    f"File '{f}' was not changed in HEAD commit. Changed: {changed_set}"
                )

        return self

    def assert_branch(self, branch_name: str) -> "GitOpsVerifier":
        """Assert current branch name."""
        current = self._run_git(["branch", "--show-current"])
        assert current == branch_name, f"Current branch is '{current}', expected '{branch_name}'"
        return self

    def assert_tag_exists(self, tag_name: str) -> "GitOpsVerifier":
        """Assert that a tag exists."""
        tags = self._run_git(["tag", "-l", tag_name])
        assert tags == tag_name, f"Tag '{tag_name}' does not exist"
        return self

    def create_remote_change(self, filename: str, content: str) -> "GitOpsVerifier":
        """
        Simulate a change on 'remote' (for sync testing).

        Since we usually test in a single repo, this creates a commit on a separate branch
        or modifies the 'upstream' if configured.
        For simplicity in unit tests, this might just modify a file and commit it
        so we can test pull/rebase logic if we switch branches.
        """
        # This implementation depends on how "remote" is mocked in fixtures.
        # For a simple temp_git_repo, we can simulate divergent history.
        return self
