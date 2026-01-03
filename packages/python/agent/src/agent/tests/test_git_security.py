# packages/python/agent/src/agent/tests/test_git_security.py
"""
Git Security Tests - Verify git operations use skill() pattern, NOT run_task().

This module ensures that git operations are performed via the skill() tool,
which provides a smooth user experience without client-side interception prompts.

In uv workspace, modules are imported directly from installed packages.
"""
import ast
import pytest
from pathlib import Path


class TestGitSecurityPatterns:
    """
    Verify git operations use skill() pattern, NOT run_task().

    These tests are CRITICAL for user experience - they prevent:
    1. Client-side git permission popups
    2. REPEATED popups if multiple git operations in same session
    3. Commit failures due to security blocks
    """

    def test_tools_never_use_run_task(self):
        """
        CRITICAL: Git operations must NOT use run_task().

        Using run_task("git", [...]) causes:
        - Client interception prompts ("Run git? Yes/No")
        - REPEATED prompts if multiple git operations in same session
        - Blocked commits even if user confirms

        CORRECT: Use skill("git", "git_status()") instead.
        """
        # Import tools directly from installed package
        from agent.tools import context, router, spec

        modules = [
            (context, "context"),
            (router, "router"),
            (spec, "spec"),
        ]

        violations_found = []

        for module, name in modules:
            source = Path(module.__file__).read_text()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "run_task":
                        violations_found.append(f"{name}.py: run_task() call")
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr == "run_task":
                            violations_found.append(f"{name}.py: module.run_task() call")

        assert not violations_found, (
            f"Found run_task() calls - must use skill() instead:\n"
            + "\n".join(f"  - {v}" for v in violations_found)
        )

    def test_core_modules_no_run_task(self):
        """Verify core modules don't use run_task."""
        from agent.core import context_loader, bootstrap

        modules = [
            (context_loader, "context_loader"),
            (bootstrap, "bootstrap"),
        ]

        violations_found = []

        for module, name in modules:
            source = Path(module.__file__).read_text()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "run_task":
                        violations_found.append(f"{name}: run_task() call")

        assert not violations_found, (
            f"Core modules should not use run_task():\n"
            + "\n".join(f"  - {v}" for v in violations_found)
        )
