import pytest
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="git")
class TestGitCommandsModular:
    """Test git skill commands using modular SDK and GitOpsVerifier."""

    async def test_git_status(self, skill_tester, gitops_verifier):
        """Verify git status command returns a valid result."""
        # gitops_verifier fixture sets up the git environment and resets caches

        # Verify initial state
        gitops_verifier.assert_clean().assert_branch("main")

        # Explicitly pass repo_path="." to ensure we check the CWD (temp repo)
        # bypassing potentially cached ConfigPaths project root resolution
        result = await skill_tester.run("git", "status", repo_path=".")
        assert result.success
        # Should now correctly identify the temp repo
        assert result.output.get("branch") == "main"
        assert result.output.get("is_clean") is True

    async def test_git_commit(self, skill_tester, git_test_env, gitops_verifier):
        """Verify git commit command creates a new commit."""
        # git_test_env is the temp repo path, already CWD

        # Create dirty state
        (git_test_env / "new_file.txt").write_text("content")

        # Verify it's unstaged
        gitops_verifier.assert_unstaged("new_file.txt")

        # Stage it
        import subprocess

        subprocess.run(["git", "add", "."], cwd=git_test_env)

        gitops_verifier.assert_staged("new_file.txt")

        # Run commit (assuming commit command doesn't take repo_path, or ignores kwargs)
        # But monkeypatch.chdir ensures subprocess.run inside skill uses CWD
        result = await skill_tester.run("git", "commit", message="feat: add new file")
        assert result.success

        # Verify side effects using GitOpsVerifier
        gitops_verifier.assert_clean().assert_commit_exists(
            message_pattern="feat: add new file", files_changed=["new_file.txt"]
        )
