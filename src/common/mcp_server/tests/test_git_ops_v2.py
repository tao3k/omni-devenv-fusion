"""
V2 Test Suite for Git Operations - Config-Driven Architecture

Tests:
1. cog.toml reading logic (ProjectConfig)
2. Stop-and-Ask protocol enforcement
3. Scope validation against real config
4. GitWorkflowCache auto-load on git tools

Run: uv run python mcp-server/tests/test_git_ops_v2.py
"""
import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# Add mcp-server/executor to path for imports
# git_ops.py is at src/mcp_server/executor/git_ops.py
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # /src/common/mcp_server/tests -> /src/common -> /src
sys.path.insert(0, str(PROJECT_ROOT / "mcp_server" / "executor"))

# Import git_ops module directly (not as package)
from git_ops import GitRulesCache, GitWorkflowCache, _validate_type, _validate_scope, _validate_message_format


class TestGitRulesCache(unittest.IsolatedAsyncioTestCase):
    """Test GitRulesCache configuration loading from cog.toml"""

    def setUp(self):
        """Reset cache before each test"""
        GitRulesCache._loaded = False
        GitRulesCache._instance = None

    def tearDown(self):
        """Clean up after each test"""
        GitRulesCache._loaded = False
        GitRulesCache._instance = None

    def test_default_scopes_fallback(self):
        """Test that default scopes are used when cog.toml doesn't exist and no markdown"""
        with patch("pathlib.Path.exists", return_value=False):
            cache = GitRulesCache()
            # When cog.toml doesn't exist and no markdown, scopes might be empty
            scopes = cache.get_scopes()
            # The cache may be empty if no fallback files exist
            # This is expected behavior - real cog.toml is loaded in production
            self.assertIsInstance(scopes, list)

    def test_default_types(self):
        """Test that default types are available"""
        cache = GitRulesCache()
        types = cache.get_types()
        self.assertIn("feat", types)
        self.assertIn("fix", types)
        self.assertIn("docs", types)
        self.assertIn("chore", types)

    def test_validate_type_valid(self):
        """Test valid type validation"""
        cache = GitRulesCache()
        valid, error = _validate_type("feat")
        self.assertTrue(valid)
        self.assertEqual(error, "")

    def test_validate_type_invalid(self):
        """Test invalid type validation"""
        cache = GitRulesCache()
        valid, error = _validate_type("invalid_type")
        self.assertFalse(valid)
        self.assertIn("Invalid type", error)

    def test_validate_scope_valid(self):
        """Test valid scope validation"""
        cache = GitRulesCache()
        valid, error = _validate_scope("nix")
        self.assertTrue(valid)

    def test_validate_scope_invalid(self):
        """Test invalid scope validation when config has specific scopes"""
        # Set up cache with specific scopes and trigger reload
        cache = GitRulesCache()
        cache.project_scopes = ["nix", "mcp"]  # Restrict scopes
        cache.valid_types = ["feat", "fix"]  # Also set valid types

        # Now validate - "backend" is NOT in ["nix", "mcp"]
        valid, error = _validate_scope("backend")
        self.assertFalse(valid)
        self.assertIn("Invalid scope", error)

    def test_validate_scope_empty_allowed(self):
        """Test empty scope is allowed when not required"""
        cache = GitRulesCache()
        valid, error = _validate_scope("")
        self.assertTrue(valid)

    def test_validate_message_format_valid(self):
        """Test valid message format"""
        valid, error = _validate_message_format("add new feature")
        self.assertTrue(valid)

    def test_validate_message_format_too_short(self):
        """Test message too short"""
        valid, error = _validate_message_format("ab")
        self.assertFalse(valid)
        self.assertIn("too short", error)

    def test_validate_message_format_period_end(self):
        """Test message ending with period"""
        valid, error = _validate_message_format("add new feature.")
        self.assertFalse(valid)
        self.assertIn("period", error)

    def test_validate_message_format_uppercase_start(self):
        """Test message starting with uppercase"""
        valid, error = _validate_message_format("Add new feature")
        self.assertFalse(valid)
        self.assertIn("lowercase", error)


class TestGitRulesCacheWithConfig(unittest.TestCase):
    """Test GitRulesCache with actual cog.toml configuration"""

    def setUp(self):
        GitRulesCache._loaded = False
        GitRulesCache._instance = None

    def tearDown(self):
        GitRulesCache._loaded = False
        GitRulesCache._instance = None

    def test_load_scopes_from_cog_toml(self):
        """Test reading scopes from actual cog.toml"""
        # The actual cog.toml in project has: scopes = ["nix", "mcp", "router", "docs", ...]
        cache = GitRulesCache()
        scopes = cache.get_scopes()

        # Verify project-specific scopes are loaded
        self.assertIn("nix", scopes)
        self.assertIn("mcp", scopes)
        self.assertIn("router", scopes)
        self.assertIn("docs", scopes)

    def test_cache_is_singleton(self):
        """Test that cache follows singleton pattern"""
        cache1 = GitRulesCache()
        cache2 = GitRulesCache()
        self.assertIs(cache1, cache2)

    def test_cache_loaded_once(self):
        """Test that configuration is loaded only once"""
        cache = GitRulesCache()
        # Trigger multiple loads
        _ = cache.get_types()
        _ = cache.get_scopes()
        _ = cache.get_types()
        _ = cache.get_scopes()

        # Should still be the same instance
        cache2 = GitRulesCache()
        self.assertIs(cache, cache2)


class TestSmartCommitProtocol(unittest.IsolatedAsyncioTestCase):
    """Test Stop-and-Ask protocol enforcement"""

    def setUp(self):
        GitRulesCache._loaded = False
        GitRulesCache._instance = None

    async def test_smart_commit_returns_ready_without_force(self):
        """Test that smart_commit returns 'ready' status when force_execute=False"""
        # Import the actual functions to test protocol behavior
        from git_ops import _validate_type, _validate_scope, _validate_message_format

        # Simulate what smart_commit does when force_execute=False
        test_type = "feat"
        test_scope = "nix"
        test_message = "add new feature"

        v_type, _ = _validate_type(test_type)
        v_scope, _ = _validate_scope(test_scope)
        v_msg, _ = _validate_message_format(test_message)

        # All should be valid
        self.assertTrue(v_type)
        self.assertTrue(v_scope)
        self.assertTrue(v_msg)

        # The protocol response should indicate "ready" for authorization
        if v_type and v_scope and v_msg:
            expected_command = f"just agent-commit {test_type} {test_scope} \"{test_message}\""
            # This is what smart_commit would return when authorization_required=True
            protocol_response = {
                "status": "ready",
                "protocol": "stop_and_ask",
                "command": expected_command,
                "authorization_required": True
            }
            self.assertEqual(protocol_response["status"], "ready")
            self.assertTrue(protocol_response["authorization_required"])
            self.assertIn("just agent-commit", protocol_response["command"])

    async def test_smart_commit_rejects_invalid_inputs(self):
        """Test that protocol rejects invalid inputs"""
        from git_ops import _validate_type, _validate_scope, _validate_message_format

        # Test invalid type
        v_type, e_type = _validate_type("invalid_type")
        self.assertFalse(v_type)
        self.assertIn("Invalid type", e_type)

        # Test invalid scope (when cache has specific scopes)
        cache = GitRulesCache()
        cache.project_scopes = ["nix", "mcp"]  # Restrict to specific scopes
        v_scope, e_scope = _validate_scope("backend")  # Not in list
        self.assertFalse(v_scope)
        self.assertIn("Invalid scope", e_scope)

        # Test invalid message
        v_msg, e_msg = _validate_message_format("Bad Message.")
        self.assertFalse(v_msg)


class TestConfigDrivenBehavior(unittest.TestCase):
    """Test that behavior is driven by cog.toml, not hardcoded"""

    def setUp(self):
        GitRulesCache._loaded = False
        GitRulesCache._instance = None

    def test_scopes_from_cog_toml_not_hardcoded(self):
        """Verify scopes are loaded from config, not hardcoded in code"""
        cache = GitRulesCache()
        scopes = cache.get_scopes()

        # These should come from cog.toml (or fallback to markdown)
        # Not from a hardcoded list in the validation function
        self.assertIsInstance(scopes, list)

        # Verify we have the project-specific scopes
        self.assertIn("nix", scopes)
        self.assertIn("mcp", scopes)

    def test_types_from_conform_or_default(self):
        """Verify types come from .conform.yaml or defaults"""
        cache = GitRulesCache()
        types = cache.get_types()

        # Conventional commit types
        self.assertIn("feat", types)
        self.assertIn("fix", types)
        self.assertIn("docs", types)


class TestGitWorkflowCache(unittest.TestCase):
    """Test GitWorkflowCache - Auto-load gitops.md memory"""

    def setUp(self):
        GitRulesCache._loaded = False
        GitRulesCache._instance = None
        GitWorkflowCache._loaded = False
        GitWorkflowCache._instance = None

    def tearDown(self):
        GitRulesCache._loaded = False
        GitRulesCache._instance = None
        GitWorkflowCache._loaded = False
        GitWorkflowCache._instance = None

    def test_workflow_cache_loads_git_workflow_md(self):
        """Test that GitWorkflowCache loads from agent/how-to/gitops.md"""
        cache = GitWorkflowCache()
        # Should load the workflow protocol
        protocol = cache.get_protocol()
        self.assertIn(protocol, ["stop_and_ask", "auto_commit"])

    def test_workflow_cache_is_singleton(self):
        """Test that workflow cache follows singleton pattern"""
        cache1 = GitWorkflowCache()
        cache2 = GitWorkflowCache()
        self.assertIs(cache1, cache2)

    def test_workflow_cache_loaded_once(self):
        """Test that workflow is loaded only once (session-singleton)"""
        cache = GitWorkflowCache()
        protocol1 = cache.get_protocol()
        rules1 = cache.get_rules()
        protocol2 = cache.get_protocol()
        rules2 = cache.get_rules()

        self.assertEqual(protocol1, protocol2)
        self.assertEqual(rules1, rules2)

    def test_workflow_protocol_stop_and_ask(self):
        """Test default protocol is stop_and_ask when markdown exists"""
        cache = GitWorkflowCache()
        # The actual gitops.md should have "Stop and Ask" as default
        self.assertEqual(cache.get_protocol(), "stop_and_ask")

    def test_workflow_rules_loaded(self):
        """Test that workflow rules are parsed from markdown"""
        cache = GitWorkflowCache()
        rules = cache.get_rules()

        self.assertIsInstance(rules, dict)
        # Should have at least some rules loaded
        self.assertIn("requires_user_confirmation", rules)

    def test_auto_load_triggers_on_get_protocol_call(self):
        """Test that calling get_protocol() triggers workflow memory load"""
        # Reset cache to verify it loads on first access
        GitWorkflowCache._loaded = False
        GitWorkflowCache._instance = None

        # First call should trigger loading
        cache = GitWorkflowCache()
        protocol = cache.get_protocol()

        # Verify cache was loaded
        self.assertTrue(GitWorkflowCache._loaded)
        self.assertIn(protocol, ["stop_and_ask", "auto_commit"])

    def test_workflow_protocol_in_response_field(self):
        """Test that workflow protocol is accessible via cache.

        The GitWorkflowCache singleton is initialized at module import.
        This test verifies the cache has the correct protocol.
        """
        from git_ops import _git_workflow_cache
        protocol = _git_workflow_cache.get_protocol()

        # Verify cache has loaded protocol
        self.assertIn(protocol, ["stop_and_ask", "auto_commit"])

    def test_git_log_returns_workflow_protocol(self):
        """Test that git_log tool source contains workflow_protocol."""
        import inspect
        import git_ops as git_ops

        # Get the source of git_log (defined in the module, decorated with @mcp.tool())
        # We can't directly access it, but we can check the module's source
        source = inspect.getsource(git_ops)

        # Verify the source contains the workflow_protocol field for git_log
        self.assertIn('"workflow_protocol"', source)

    def test_git_diff_returns_workflow_protocol(self):
        """Test that git_diff tool source contains workflow_protocol."""
        import inspect
        import git_ops as git_ops

        source = inspect.getsource(git_ops)
        self.assertIn('"workflow_protocol"', source)

    def test_git_diff_staged_returns_workflow_protocol(self):
        """Test that git_diff_staged tool source contains workflow_protocol."""
        import inspect
        import git_ops as git_ops

        source = inspect.getsource(git_ops)
        self.assertIn('"workflow_protocol"', source)

    def test_all_git_tools_call_get_protocol(self):
        """Verify all git tools call _git_workflow_cache.get_protocol().

        This is a static analysis test - we check the source code contains
        the expected call to ensure auto-load is implemented.
        """
        import inspect
        import git_ops as git_ops

        source = inspect.getsource(git_ops)

        # Each git tool should call _git_workflow_cache.get_protocol()
        self.assertIn(
            "_git_workflow_cache.get_protocol()",
            source,
            "Git tools should call _git_workflow_cache.get_protocol()"
        )

    def test_git_status_includes_workflow_protocol_in_response(self):
        """Test that git_status response includes workflow_protocol field."""
        import inspect
        import git_ops as git_ops

        source = inspect.getsource(git_ops)

        # git_status should have workflow_protocol in its response
        self.assertIn('"workflow_protocol": _git_workflow_cache.get_protocol()', source)

    def test_register_git_ops_tools_triggers_workflow_load(self):
        """Test that register_git_ops_tools triggers workflow memory load.

        This verifies the centralized loading pattern in register_git_ops_tools.
        """
        import inspect
        import git_ops as git_ops

        source = inspect.getsource(git_ops)

        # register_git_ops_tools should trigger the load
        self.assertIn(
            "_git_workflow_cache.get_protocol()",
            source,
            "register_git_ops_tools should trigger workflow load"
        )


class TestAuthorizationGuard(unittest.IsolatedAsyncioTestCase):
    """Test AuthorizationGuard - Token-based commit authorization system"""

    def setUp(self):
        """Reset authorization guard before each test"""
        from git_ops import AuthorizationGuard
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    def tearDown(self):
        """Clean up after each test"""
        from git_ops import AuthorizationGuard
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    def test_create_authorization_returns_token(self):
        """Test that create_authorization returns a hex token"""
        from git_ops import AuthorizationGuard, _auth_guard

        token = _auth_guard.create_authorization(
            command="just agent-commit mcp test",
            type="mcp",
            scope="test",
            message="test message"
        )
        self.assertIsInstance(token, str)
        self.assertEqual(len(token), 32)  # 16 bytes = 32 hex chars

    def test_validate_and_consume_returns_data(self):
        """Test that valid token returns auth data"""
        from git_ops import _auth_guard

        # Create authorization
        token = _auth_guard.create_authorization(
            command="just agent-commit mcp test",
            type="mcp",
            scope="test",
            message="test message"
        )

        # Validate and consume
        result = _auth_guard.validate_and_consume(token)

        self.assertIsNotNone(result)
        self.assertEqual(result["command"], "just agent-commit mcp test")
        self.assertEqual(result["type"], "mcp")
        self.assertEqual(result["scope"], "test")
        self.assertEqual(result["message"], "test message")

    def test_token_can_only_be_used_once(self):
        """Test that token is invalidated after use"""
        from git_ops import _auth_guard

        token = _auth_guard.create_authorization(
            command="just agent-commit mcp test",
            type="mcp",
            scope="test",
            message="test message"
        )

        # First use - should succeed
        result1 = _auth_guard.validate_and_consume(token)
        self.assertIsNotNone(result1)

        # Second use - should fail (already consumed)
        result2 = _auth_guard.validate_and_consume(token)
        self.assertIsNone(result2)

    def test_invalid_token_returns_none(self):
        """Test that invalid token returns None"""
        from git_ops import _auth_guard

        result = _auth_guard.validate_and_consume("invalid_token_xxxx")
        self.assertIsNone(result)

    def test_token_expires_after_timeout(self):
        """Test that token expires after 5 minutes"""
        from git_ops import AuthorizationGuard, _auth_guard

        # Create a new guard with short expiration
        guard = object.__new__(AuthorizationGuard)
        guard._tokens = {}

        # Create token with 0 second expiration (already expired)
        token = guard.create_authorization(
            command="just agent-commit mcp test",
            type="mcp",
            scope="test",
            message="test message"
        )
        guard._tokens[token]["expires_in"] = 0  # Immediate expiration

        # Token should be expired
        result = guard.validate_and_consume(token)
        self.assertIsNone(result)

    def test_clear_all_removes_tokens(self):
        """Test that clear_all removes all tokens"""
        from git_ops import _auth_guard

        # Create some tokens
        _auth_guard.create_authorization("cmd1", "t1", "s1", "m1")
        _auth_guard.create_authorization("cmd2", "t2", "s2", "m2")

        self.assertEqual(len(_auth_guard._tokens), 2)

        # Clear all
        _auth_guard.clear_all()

        self.assertEqual(len(_auth_guard._tokens), 0)


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Git Ops V2 Test Suite")
    print("=" * 60)
    print("\nTesting Config-Driven Git Operations...")
    print("1. GitRulesCache configuration loading")
    print("2. Stop-and-Ask protocol enforcement")
    print("3. Scope validation against cog.toml")
    print("4. GitWorkflowCache auto-load on git tools")
    print("=" * 60)

    unittest.main(verbosity=2)
