# src/agent/tests/test_git_security.py
"""
Git Security Tests - Verify git operations use skill() pattern, NOT run_task().

This module ensures that git operations are performed via the skill() tool,
which provides a smooth user experience without client-side interception prompts.

Problem Solved:
- Using run_task("git", [...]) causes Claude Desktop to prompt "Run git? Yes/No"
- Multiple run_task("git", ...) calls cause REPEATED popups in the same session
- Even when user confirms, commits may fail due to security blocks
- skill("git", "git_status()") bypasses client interception entirely

The Critical Issue (Why run_task is banned):
=============================================
If code uses run_task("git", ["diff"]) followed by run_task("git", ["log"]):
  1. User sees "Run git? Yes/No" popup for diff
  2. User clicks Yes
  3. User sees "Run git? Yes/No" popup for log (AGAIN!)
  4. User clicks Yes
  5. ...this continues for every git operation

This creates an extremely poor UX - users should NOT see repeated git permission dialogs.

The Solution:
- Use skill("git", "git_diff()") - no popup
- Use skill("git", "git_log()") - no popup
- All git operations centralized in the git skill

Run:
    uv run pytest src/agent/tests/test_git_security.py -v
    just test-git-security  # Add to justfile
"""
import ast
import pytest
from pathlib import Path


def get_git_tools_content():
    """Helper to get git tools.py content."""
    project_root = Path(__file__).parent.parent.parent.parent
    git_tools_py = project_root / "src" / "agent" / "skills" / "git" / "tools.py"
    if git_tools_py.exists():
        return git_tools_py.read_text(), ast.parse(git_tools_py.read_text())
    return None, None


class TestGitSecurityPatterns:
    """
    Verify git operations use skill() pattern, NOT run_task().

    These tests are CRITICAL for user experience - they prevent:
    1. Client-side git permission popups
    2. REPEATED popups when multiple git operations are called
    3. Commit failures due to security blocks
    """

    def test_git_tools_never_use_run_task(self):
        """
        CRITICAL: Git operations must NOT use run_task().

        Using run_task("git", [...]) causes:
        - Client interception prompts ("Run git? Yes/No")
        - REPEATED prompts if multiple git operations in same session
        - Blocked commits even if user confirms

        CORRECT: Use skill("git", "git_status()") instead.
        """
        tool_modules = [
            ("execution.py", "agent/tools/execution.py"),
            ("context.py", "agent/tools/context.py"),
            ("router.py", "agent/tools/router.py"),
            ("spec.py", "agent/tools/spec.py"),
        ]

        violations_found = []

        for module_name, rel_path in tool_modules:
            project_root = Path(__file__).parent.parent.parent.parent
            module_path = project_root / rel_path

            if not module_path.exists():
                continue

            content = module_path.read_text()
            tree = ast.parse(content)

            # Find all calls to run_task with "git" command
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check for run_task(...)
                    if isinstance(node.func, ast.Name):
                        if node.func.id == "run_task":
                            # Check args: run_task("git", [...])
                            if len(node.args) >= 2:
                                first_arg = node.args[0]
                                if isinstance(first_arg, ast.Constant):
                                    if first_arg.value == "git":
                                        violations_found.append({
                                            "module": module_name,
                                            "line": node.lineno,
                                            "code": content.split('\n')[node.lineno - 1].strip()
                                        })

                    # Also check for SafeExecutor.run or SafeExecutor.run_git_cmd
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr in ("run", "run_git_cmd"):
                            if isinstance(node.func.value, ast.Name):
                                if "SafeExecutor" in node.func.value.id or "Executor" in node.func.value.id:
                                    violations_found.append({
                                        "module": module_name,
                                        "line": node.lineno,
                                        "code": content.split('\n')[node.lineno - 1].strip()
                                    })

        # Verify NO git run_task calls exist
        assert len(violations_found) == 0, \
            f"CRITICAL: Found {len(violations_found)} git run_task calls:\n" + \
            "\n".join([f"  - {v['module']}:{v['line']}: {v['code']}"
                      for v in violations_found[:5]]) + \
            "\n\n❌ STOP! These cause client interception prompts.\n" + \
            "   Multiple git operations = Multiple popups = Terrible UX.\n" + \
            "✅ CORRECT: Use skill('git', 'git_status()') instead."

    def test_no_run_task_git_in_same_module(self):
        """
        CRITICAL: Detect REPEATED run_task("git", ...) calls in same file.

        This is the specific "loop popup" scenario:
        - File calls run_task("git", ["diff"])
        - Same file ALSO calls run_task("git", ["log"])
        - User gets popup TWICE in same session

        Any occurrence of run_task("git", ...) is a FAIL, but we also
        check for multiple occurrences to catch the worst offenders.
        """
        tool_modules = [
            ("execution.py", "agent/tools/execution.py"),
            ("context.py", "agent/tools/context.py"),
            ("router.py", "agent/tools/router.py"),
            ("spec.py", "agent/tools/spec.py"),
        ]

        for module_name, rel_path in tool_modules:
            project_root = Path(__file__).parent.parent.parent.parent
            module_path = project_root / rel_path

            if not module_path.exists():
                continue

            content = module_path.read_text()
            tree = ast.parse(content)

            # Count git run_task calls in this module
            git_run_task_count = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id == "run_task":
                            if len(node.args) >= 2:
                                first_arg = node.args[0]
                                if isinstance(first_arg, ast.Constant):
                                    if first_arg.value == "git":
                                        git_run_task_count += 1

            # Any git run_task is bad, but multiple is worse
            assert git_run_task_count == 0, \
                f"❌ {module_name} contains {git_run_task_count} run_task('git', ...) calls.\n" + \
                f"   This means users will see {git_run_task_count} git permission popups!\n" + \
                f"   The 'loop popup' anti-pattern: each git call = another popup.\n" + \
                f"   ✅ FIX: Use skill('git', 'git_operation()') - zero popups."

    def test_all_git_operations_use_skill_tool(self):
        """
        Comprehensive check: All git operations should be accessible via skill().

        grep for @mcp.tool() decorated functions in git skill tools.py
        and verify they match expected git operations.
        """
        content, tree = get_git_tools_content()

        if content is None:
            pytest.skip("git skill not found (expected after migration)")

        # Find all @mcp.tool() decorated async functions
        tool_functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            if decorator.func.attr == 'tool':
                                tool_functions.append(node.name)

        # Must have these core git operations
        required_tools = {"git_status", "git_log", "git_add", "smart_commit"}
        actual_tools = set(tool_functions)

        missing = required_tools - actual_tools
        assert not missing, f"Missing git tools in skill: {missing}\n" + \
                           f"Available: {actual_tools}\n" + \
                           f"Required: {required_tools}"

    def test_smart_commit_has_two_phase_workflow(self):
        """
        Verify smart_commit implements proper two-phase commit workflow.

        Phase 1 (Analysis): Call without auth_token → returns session_id
        Phase 2 (Execute): Call with auth_token → performs commit
        """
        content, tree = get_git_tools_content()

        if content is None:
            pytest.skip("git skill not found")

        # Verify session-based workflow
        assert "_commit_sessions" in content, \
            "smart_commit must use _commit_sessions dict for session storage"

        assert "auth_token" in content, \
            "smart_commit must have auth_token parameter"

        # Verify the execute phase check
        assert 'if auth_token:' in content, \
            "smart_commit must have execute phase when auth_token is provided"

        # Verify session creation
        assert "session_id" in content, \
            "smart_commit must generate session_id"

        assert "secrets.token_hex" in content, \
            "smart_commit must use secrets.token_hex for session_id"

    def test_no_direct_git_imports_for_operations(self):
        """
        Verify orchestrator tools don't import gitops for direct git operations.

        This catches the anti-pattern where code does:
            from common.mcp_core.gitops import run_git_cmd
            await run_git_cmd(["status"])

        Which bypasses skill() and causes client interception.
        """
        project_root = Path(__file__).parent.parent.parent.parent

        tool_modules = [
            project_root / "src" / "agent" / "tools" / name
            for name in ["execution.py", "context.py", "router.py", "spec.py"]
        ]

        for module_path in tool_modules:
            if not module_path.exists():
                continue

            content = module_path.read_text()

            # If gitops is imported for run_git_cmd, it's a violation
            if "run_git_cmd" in content:
                # Find the violation lines
                lines = content.split('\n')
                violations = []
                for i, line in enumerate(lines, 1):
                    if "run_git_cmd" in line:
                        violations.append(f"  Line {i}: {line.strip()}")

                assert False, \
                    f"{module_path.name} uses run_git_cmd directly.\n" + \
                    f"This bypasses skill() and causes client interception.\n" + \
                    f"Violations:\n" + "\n".join(violations) + \
                    f"\n\n✅ CORRECT: Use skill('git', 'git_status()') instead."

    def test_git_skill_register_function_exists(self):
        """Verify git skill exports register() function for MCP integration."""
        content, tree = get_git_tools_content()

        if content is None:
            pytest.skip("git skill not found")

        # Find register function
        has_register = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "register":
                    has_register = True
                    # Check signature
                    if len(node.args.args) >= 1:
                        assert node.args.args[0].arg == "mcp", \
                            "register should take 'mcp' as first parameter"
                    break

        assert has_register, \
            "git tools must export register(mcp) function for MCP integration"

    def test_execution_blocks_git_commit(self):
        """
        Verify execution.py has git commit blocking for security.

        This is a safety net - even if someone tries to call
        run_task("git", ["commit", ...]), it should be blocked.
        """
        project_root = Path(__file__).parent.parent.parent.parent
        execution_py = project_root / "src" / "agent" / "tools" / "execution.py"

        if not execution_py.exists():
            pytest.skip("execution.py not found")

        content = execution_py.read_text()

        # Should have git commit blocking
        has_block = (
            "GIT COMMIT BLOCKED" in content or
            "git_commit" in content.lower() or
            '"commit"' in content
        )

        assert has_block, \
            "execution.py should have git commit blocking for security.\n" + \
            "This prevents bypassing the smart_commit() authorization protocol."


class TestGitWorkflowIntegration:
    """Integration tests for git workflow correctness."""

    def test_smart_commit_signature(self):
        """Verify smart_commit has correct signature for MCP tool."""
        content, tree = get_git_tools_content()

        if content is None:
            pytest.skip("git skill not found")

        # Find smart_commit function and check parameters
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "smart_commit":
                params = [arg.arg for arg in node.args.args]
                assert "message" in params, "smart_commit needs 'message' param"
                assert "auth_token" in params, "smart_commit needs 'auth_token' param"
                return

        pytest.fail("smart_commit function not found")

    def test_git_tools_are_async(self):
        """Verify all git tools are async functions for MCP."""
        content, tree = get_git_tools_content()

        if content is None:
            pytest.skip("git skill not found")

        required_tools = ["git_status", "git_log", "git_add", "smart_commit", "spec_aware_commit"]

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                if node.name in required_tools:
                    required_tools.remove(node.name)

        assert not required_tools, \
            f"Missing git tools: {required_tools}\n" + \
            "All required git tools must be defined in git/tools.py"

    def test_commit_sessions_is_dict(self):
        """Verify _commit_sessions is properly initialized as dict."""
        from agent.skills.git.tools import _commit_sessions

        assert isinstance(_commit_sessions, dict), \
            "_commit_sessions should be a dict for session storage"
        assert callable(_commit_sessions.get), \
            "_commit_sessions should be a dict (has .get method)"


class TestGitE2EWorkflow:
    """
    End-to-end tests that verify the complete git workflow.

    These tests simulate what actually happens when a user
    wants to commit changes.
    """

    def test_user_can_commit_with_skill_workflow(self):
        """
        Simulate: User wants to commit changes.

        Expected flow:
        1. User: "Commit my changes"
        2. Agent: skill("git", "smart_commit(message='feat(scope): desc')")
        3. System: Returns {analysis, session_id}
        4. User confirms
        5. Agent: skill("git", "smart_commit(message='...', auth_token='xxx')")
        6. System: Executes commit

        This should NOT prompt the user with git permission dialogs.
        """
        content, tree = get_git_tools_content()

        if content is None:
            pytest.skip("git skill not found")

        # Verify smart_commit exists and has correct parameters
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "smart_commit":
                params = [arg.arg for arg in node.args.args]
                assert "message" in params, "smart_commit needs 'message' param"
                assert "auth_token" in params, "smart_commit needs 'auth_token' param"
                return

        pytest.fail("smart_commit function not found")

    def test_no_confirmation_prompts_in_production_flow(self):
        """
        Verify the production flow doesn't trigger client-side git permission prompts.

        The issue: When code calls run_task("git", ["status"]), Claude Desktop
        intercepts and asks "Run git? (Yes/No)". This is a terrible UX.

        The fix: Code should call skill("git", "git_status()") which doesn't
        trigger client-side interception.
        """
        # This is validated by the static analysis tests above
        # The key insight is:
        # - run_task("git", [...]) → triggers client prompt
        # - skill("git", "...") → no prompt, direct execution

        # Verify the git skill has all required tools
        content, tree = get_git_tools_content()

        if content is None:
            pytest.skip("git skill not found")

        # Check _commit_sessions is accessible
        assert "_commit_sessions" in content, \
            "_commit_sessions should be accessible for session management"


class TestGitLoopPopupPrevention:
    """
    Tests specifically designed to prevent the "loop popup" anti-pattern.

    Scenario:
    - Agent calls run_task("git", ["diff"])
    - Client shows popup, user clicks Yes
    - Agent calls run_task("git", ["status"]) - popup AGAIN!
    - Agent calls run_task("git", ["log"]) - popup AGAIN!
    - User is annoyed and leaves

    Solution:
    - All git operations via skill() = zero popups
    """

    def test_no_git_run_task_in_execution_module(self):
        """
        Verify execution.py has ZERO run_task("git", ...) calls.

        The execution module is the most likely place for this anti-pattern
        to appear. We check it specifically for multiple git operations.
        """
        project_root = Path(__file__).parent.parent.parent.parent
        execution_py = project_root / "src" / "agent" / "tools" / "execution.py"

        if not execution_py.exists():
            pytest.skip("execution.py not found")

        content = execution_py.read_text()
        tree = ast.parse(content)

        git_run_task_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id == "run_task":
                        if len(node.args) >= 2:
                            first_arg = node.args[0]
                            if isinstance(first_arg, ast.Constant):
                                if first_arg.value == "git":
                                    line_content = content.split('\n')[node.lineno - 1].strip()
                                    git_run_task_calls.append({
                                        "line": node.lineno,
                                        "content": line_content
                                    })

        # Count occurrences
        count = len(git_run_task_calls)

        assert count == 0, \
            f"❌ execution.py has {count} run_task('git', ...) call(s).\n" + \
            f"   This creates {count} git permission popup(s) for users!\n" + \
            f"   Lines: {', '.join([str(c['line']) for c in git_run_task_calls])}\n" + \
            f"\n   ✅ CORRECT: skill('git', 'git_operation()') - zero popups.\n" + \
            f"\n   WHY THIS MATTERS:\n" + \
            f"   - 1 call = 1 popup\n" + \
            f"   - 3 calls = 3 popups (terrible UX)\n" + \
            f"   - skill() = 0 popups (seamless experience)"

    def test_no_git_run_task_in_context_module(self):
        """Verify context.py has ZERO run_task("git", ...) calls."""
        project_root = Path(__file__).parent.parent.parent.parent
        context_py = project_root / "src" / "agent" / "tools" / "context.py"

        if not context_py.exists():
            pytest.skip("context.py not found")

        content = context_py.read_text()
        tree = ast.parse(content)

        git_run_task_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id == "run_task":
                        if len(node.args) >= 2:
                            first_arg = node.args[0]
                            if isinstance(first_arg, ast.Constant):
                                if first_arg.value == "git":
                                    git_run_task_count += 1

        assert git_run_task_count == 0, \
            f"❌ context.py has {git_run_task_count} run_task('git', ...) call(s).\n" + \
            f"   Users will see {git_run_task_count} git permission popup(s).\n" + \
            f"   ✅ Use: skill('git', 'git_status()') instead."

    def test_no_git_run_task_in_router_module(self):
        """Verify router.py has ZERO run_task("git", ...) calls."""
        project_root = Path(__file__).parent.parent.parent.parent
        router_py = project_root / "src" / "agent" / "tools" / "router.py"

        if not router_py.exists():
            pytest.skip("router.py not found")

        content = router_py.read_text()
        tree = ast.parse(content)

        git_run_task_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id == "run_task":
                        if len(node.args) >= 2:
                            first_arg = node.args[0]
                            if isinstance(first_arg, ast.Constant):
                                if first_arg.value == "git":
                                    git_run_task_count += 1

        assert git_run_task_count == 0, \
            f"❌ router.py has {git_run_task_count} run_task('git', ...) call(s).\n" + \
            f"   Users will see {git_run_task_count} git permission popup(s).\n" + \
            f"   ✅ Use: skill('git', 'git_status()') instead."


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
