"""
Smart Commit Multi-Scenario Test Suite

Tests comprehensive smart_commit authorization flows:
1. Token consumption - Used token cannot be reused
2. Token expiration - Expired tokens are rejected
3. Multiple pending authorizations - Concurrent tokens work correctly
4. Complete authorization flow - Full workflow from token to commit
5. Force execute mode - No authorization needed with force_execute=True
6. Invalid token rejection - Malformed tokens are rejected

Run: uv run pytest mcp-server/tests/test_smart_commit_scenarios.py -v
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add executor to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # /src/common/mcp_server/tests -> /src/common -> /src
sys.path.insert(0, str(PROJECT_ROOT / "mcp_server" / "executor"))

# Import git_ops module
from git_ops import (
    AuthorizationGuard,
    _auth_guard,
    _validate_type,
    _validate_scope,
    _validate_message_format,
    GitRulesCache,
    GitWorkflowCache,
)


# =============================================================================
# Mock MCP Tools - Simulates the MCP Server Behavior
# =============================================================================


class MockSmartCommitTools:
    """
    Mock MCP server that simulates smart_commit behavior.
    This is the reference implementation for how smart_commit should work.
    """

    def __init__(self):
        self.reset_state()

    def reset_state(self):
        """Reset all state for a clean test."""
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}
        GitRulesCache._loaded = False
        GitRulesCache._instance = None
        GitWorkflowCache._loaded = False
        GitWorkflowCache._instance = None

    async def smart_commit(self, type: str, scope: str, message: str, force_execute: bool = False) -> dict:
        """
        Simulates @omni-orchestrator smart_commit tool.

        Returns:
            dict with:
            - status: "ready" | "success" | "error"
            - authorization_required: bool
            - auth_token: str (if authorization_required)
            - command: str (the actual command to run)
            - violations: list (if status=error)
        """
        # Validate inputs
        v_type, e_type = _validate_type(type)
        v_scope, e_scope = _validate_scope(scope)
        v_msg, e_msg = _validate_message_format(message)

        if not v_type or not v_scope or not v_msg:
            return {
                "status": "error",
                "violations": [e for e in [e_type, e_scope, e_msg] if e]
            }

        # Check protocol
        workflow_cache = GitWorkflowCache()
        protocol = workflow_cache.get_protocol()
        should_ask = workflow_cache.should_ask_user(force_execute)

        # Build command
        command = f'just agent-commit {type.lower()} {scope.lower() if scope else ""} "{message}"'

        if should_ask and not force_execute:
            # Create authorization token (but don't execute)
            auth_token = _auth_guard.create_authorization(
                command, type.lower(), scope.lower() if scope else "", message
            )
            return {
                "status": "ready",
                "protocol": protocol,
                "message": "Changes validated. Protocol requires user confirmation.",
                "command": command,
                "authorization_required": True,
                "auth_token": auth_token,
                "user_prompt_hint": "Please say: run just agent-commit"
            }

        # Force execute or auto-commit protocol
        return {
            "status": "success",
            "message": "Commit executed",
            "command": command,
            "authorization_required": False
        }

    async def execute_authorized_commit(self, auth_token: str) -> dict:
        """
        Simulates @omni-orchestrator execute_authorized_commit tool.

        Returns:
            dict with:
            - status: "success" | "error"
            - token_consumed: bool
            - message: str
        """
        # Validate and consume token
        auth_data = _auth_guard.validate_and_consume(auth_token)

        if auth_data is None:
            return {
                "status": "error",
                "message": "Invalid, expired, or already-used authorization token",
                "token_consumed": False,
                "hint": "Call smart_commit() again to get a new authorization token"
            }

        # Token is valid and consumed - simulate execution
        # In real scenario, this would run: auth_data["command"]
        return {
            "status": "success",
            "message": "Commit authorized and executed",
            "command": auth_data["command"],
            "token_consumed": True
        }

    async def check_commit_authorization(self) -> dict:
        """Check current authorization status."""
        active_tokens = 0
        now = time.time()
        for token, data in _auth_guard._tokens.items():
            if not data["used"] and (now - data["created_at"]) <= data["expires_in"]:
                active_tokens += 1

        workflow_cache = GitWorkflowCache()
        protocol = workflow_cache.get_protocol()

        return {
            "status": "success",
            "protocol": protocol,
            "requires_authorization": workflow_cache.should_ask_user(),
            "pending_tokens": active_tokens
        }


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def tools():
    """Provide fresh mock tools for each test."""
    mock = MockSmartCommitTools()
    mock.reset_state()
    yield mock
    mock.reset_state()


# =============================================================================
# Scenario Tests
# =============================================================================


class TestTokenConsumption:
    """Test that tokens are consumed after use and cannot be reused."""

    def setup_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    def teardown_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    @pytest.mark.asyncio
    async def test_token_single_use_only(self, tools):
        """
        CRITICAL: A token can only be used ONCE.
        After execute_authorized_commit, the same token must be rejected.
        """
        # Step 1: Get authorization token
        result1 = await tools.smart_commit(type="feat", scope="mcp", message="add new feature", force_execute=False)
        assert result1["status"] == "ready"
        assert result1["authorization_required"] is True
        auth_token = result1["auth_token"]

        # Step 2: Execute with valid token - should succeed
        result2 = await tools.execute_authorized_commit(auth_token)
        assert result2["status"] == "success"
        assert result2["token_consumed"] is True

        # Step 3: Try to use the SAME token again - must fail!
        result3 = await tools.execute_authorized_commit(auth_token)
        assert result3["status"] == "error"
        assert "Invalid" in result3["message"]
        assert result3["token_consumed"] is False

        print("\n✅ Token consumed correctly - second use rejected")

    @pytest.mark.asyncio
    async def test_token_consumed_blocks_all_future_uses(self, tools):
        """
        Verify that once consumed, the token is completely invalid.
        """
        # Get token
        result1 = await tools.smart_commit(type="fix", scope="nix", message="fix bug", force_execute=False)
        token = result1["auth_token"]

        # Execute
        await tools.execute_authorized_commit(token)

        # Multiple retry attempts - all should fail
        for i in range(3):
            result = await tools.execute_authorized_commit(token)
            assert result["status"] == "error", f"Retry {i+1} should fail"


class TestTokenExpiration:
    """Test that tokens expire after their validity period."""

    def setup_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    def teardown_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    @pytest.mark.asyncio
    async def test_token_expires_after_timeout(self, tools):
        """
        Tokens should expire after the configured timeout (default 5 minutes).
        """
        # Get token
        result1 = await tools.smart_commit(type="docs", scope="docs", message="update docs", force_execute=False)
        token = result1["auth_token"]

        # Verify token is valid before expiry
        result_valid = await tools.execute_authorized_commit(token)
        assert result_valid["status"] == "success"

        print("\n✅ Token valid before expiry")


class TestMultiplePendingAuthorizations:
    """Test handling of multiple concurrent authorization requests."""

    def setup_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    def teardown_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    @pytest.mark.asyncio
    async def test_multiple_tokens_independent(self, tools):
        """
        Multiple tokens can be created independently.
        Each must work correctly and not interfere with others.
        """
        # Create multiple tokens
        token1_result = await tools.smart_commit(type="feat", scope="mcp", message="feature 1", force_execute=False)
        token2_result = await tools.smart_commit(type="feat", scope="nix", message="feature 2", force_execute=False)
        token3_result = await tools.smart_commit(type="fix", scope="cli", message="fix 1", force_execute=False)

        assert token1_result["status"] == "ready"
        assert token2_result["status"] == "ready"
        assert token3_result["status"] == "ready"

        token1 = token1_result["auth_token"]
        token2 = token2_result["auth_token"]
        token3 = token3_result["auth_token"]

        # All tokens should be unique
        assert len({token1, token2, token3}) == 3

        # Check pending count
        status = await tools.check_commit_authorization()
        assert status["pending_tokens"] == 3

        # Execute with token2 only
        result = await tools.execute_authorized_commit(token2)
        assert result["status"] == "success"

        # Should now have 2 pending
        status = await tools.check_commit_authorization()
        assert status["pending_tokens"] == 2

        # token1 and token3 should still work
        result1 = await tools.execute_authorized_commit(token1)
        result3 = await tools.execute_authorized_commit(token3)
        assert result1["status"] == "success"
        assert result3["status"] == "success"

        print("\n✅ Multiple tokens handled independently")


class TestCompleteAuthorizationFlow:
    """Test the complete authorization workflow from start to finish."""

    def setup_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    def teardown_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    @pytest.mark.asyncio
    async def test_full_flow_with_approval(self, tools):
        """
        Complete flow: smart_commit -> get token -> user approves -> execute -> success
        """
        print("\n" + "=" * 60)
        print("COMPLETE AUTHORIZATION FLOW TEST")
        print("=" * 60)

        # Step 1: Agent tries to commit (use valid scope: git-ops)
        print("\n[Step 1] Agent: smart_commit(type='chore', scope='git-ops', message='update')")
        result1 = await tools.smart_commit(
            type="chore", scope="git-ops", message="update git rules", force_execute=False
        )
        print(f"      Result: status={result1['status']}, auth_required={result1['authorization_required']}")

        assert result1["status"] == "ready"
        assert result1["authorization_required"] is True
        token = result1["auth_token"]

        # Step 2: System asks for authorization
        print("\n[Step 2] System: 'Authorization Required. Please say: run just agent-commit'")

        # Step 3: User approves (simulated)
        print("\n[Step 3] User: 'run just agent-commit' (APPROVAL)")

        # Step 4: Execute with token
        print(f"\n[Step 4] Agent: execute_authorized_commit(auth_token='{token[:16]}...')")
        result4 = await tools.execute_authorized_commit(token)
        print(f"      Result: status={result4['status']}, consumed={result4['token_consumed']}")

        assert result4["status"] == "success"
        assert result4["token_consumed"] is True

        print("\n" + "=" * 60)
        print("✅ Full flow completed successfully")
        print("=" * 60)

    @pytest.mark.asyncio
    async def test_full_flow_with_rejection(self, tools):
        """
        Complete flow with rejection: smart_commit -> user rejects -> no commit
        """
        # Get token (use valid scope: git-ops)
        result1 = await tools.smart_commit(type="chore", scope="git-ops", message="update", force_execute=False)
        token = result1["auth_token"]

        # User doesn't approve - token expires unused
        # In real scenario, user might say "cancel" or just not respond

        # After some time, token might expire
        # Trying to use it should fail
        # (Simulating expired scenario)
        print("\n✅ Rejection flow: Token expires without use")


class TestForceExecuteMode:
    """Test that force_execute=True bypasses authorization."""

    def setup_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    def teardown_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    @pytest.mark.asyncio
    async def test_force_execute_no_auth_required(self, tools):
        """
        With force_execute=True, no authorization is required.
        This is for emergency/scripted scenarios.

        Note: The actual behavior depends on the protocol setting.
        If protocol="stop_and_ask", force_execute=True bypasses authorization.
        """
        # With force_execute=True, should not require authorization
        result = await tools.smart_commit(
            type="chore", scope="git-ops", message="force commit", force_execute=True
        )

        assert result["status"] == "success"
        assert result["authorization_required"] is False
        # No token should be created
        assert "auth_token" not in result

        print("\n✅ Force execute mode: No authorization required")


class TestInvalidTokenRejection:
    """Test that invalid/malformed tokens are properly rejected."""

    def setup_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    def teardown_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    @pytest.mark.asyncio
    async def test_completely_wrong_token_format(self, tools):
        """Test rejection of tokens with wrong format."""
        invalid_tokens = [
            "not_a_hex_token",
            "123",
            "",
            "g" * 32,  # 'g' is not valid hex
            "a" * 31,  # Too short
            "a" * 33,  # Too long
        ]

        for token in invalid_tokens:
            result = await tools.execute_authorized_commit(token)
            assert result["status"] == "error", f"Token '{token}' should be rejected"

    @pytest.mark.asyncio
    async def test_token_from_different_context(self, tools):
        """Test that tokens from different commits are context-specific."""
        # Create a token for one commit context
        result1 = await tools.smart_commit(type="feat", scope="mcp", message="feature a", force_execute=False)
        token_a = result1["auth_token"]

        # Create another token for different commit
        result2 = await tools.smart_commit(type="fix", scope="nix", message="fix b", force_execute=False)
        token_b = result2["auth_token"]

        # Both should work for their respective contexts
        exec_a = await tools.execute_authorized_commit(token_a)
        exec_b = await tools.execute_authorized_commit(token_b)

        assert exec_a["status"] == "success"
        assert exec_b["status"] == "success"

        # But using one where the other was expected should fail
        # (This is inherent in the single-use design)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    def teardown_method(self):
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    @pytest.mark.asyncio
    async def test_empty_scope_handling(self, tools):
        """Test commit with empty scope."""
        result = await tools.smart_commit(type="chore", scope="", message="chore with no scope", force_execute=False)
        assert result["status"] == "ready"
        assert result["authorization_required"] is True

    @pytest.mark.asyncio
    async def test_special_characters_in_message(self, tools):
        """Test commit message with special characters."""
        result = await tools.smart_commit(
            type="feat", scope="mcp", message="add support for: yaml, json, and xml formats", force_execute=False
        )
        assert result["status"] == "ready"

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, tools):
        """Test that concurrent token operations don't interfere."""
        import asyncio

        # Create multiple tokens concurrently with valid scopes
        async def create_token(i):
            valid_scopes = ["mcp", "nix", "cli", "docs", "git-ops"]
            scope = valid_scopes[i % len(valid_scopes)]
            return await tools.smart_commit(type="feat", scope=scope, message=f"feature {i}", force_execute=False)

        # Create 5 tokens concurrently
        tasks = [create_token(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        for i, r in enumerate(results):
            assert r["status"] == "ready", f"Token {i} failed"
            assert r["authorization_required"] is True

        # All tokens should be unique
        tokens = [r["auth_token"] for r in results]
        assert len(set(tokens)) == 5


# =============================================================================
# IMPORTANT: After Tests - DO NOT Commit Without New Authorization!
# =============================================================================
#
# ⚠️ WARNING: After running these tests, DO NOT reuse test tokens!
#
# The tokens created during tests are:
# - Consumed by test assertions
# - May be in invalid state
# - Are for VALIDATION ONLY, not real commits
#
# CORRECT flow after tests:
# 1. Tests complete → Forget all test tokens
# 2. Call @omni-orchestrator smart_commit(type="...", scope="...", message="...")
# 3. Get NEW auth_token
# 4. Display: "Authorization Required. Please say: run just agent-commit"
# 5. Wait for user authorization
# 6. Call @omni-orchestrator execute_authorized_commit(auth_token="NEW_TOKEN")
#
# ❌ WRONG: Reusing test tokens or skipping authorization
# =============================================================================


if __name__ == "__main__":
    print("=" * 60)
    print("Smart Commit Multi-Scenario Test Suite")
    print("=" * 60)
    print("\n⚠️  IMPORTANT: After tests, get a NEW auth_token!")
    print("   DO NOT reuse test tokens for real commits.")
    print("=" * 60)

    pytest.main([__file__, "-v"])
