"""
Phase 11 Test Suite - Neural Matrix Authorization Flow (End-to-End)

Tests the complete Phase 11 authorization flow:
1. User: "Test smart_commit_v2 logic"
2. System: Returns "Authorization Required" analysis (no git commit executed)
3. User: "confirm_commit(decision="approved")"
4. System: Returns "Commit Successful"

Run: uv run pytest src/common/mcp_server/tests/test_phase11_auth.py -v
"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from common.mcp_core.gitops import get_project_root

PROJECT_ROOT = get_project_root()
sys.path.insert(0, str(PROJECT_ROOT / "mcp_server" / "executor"))

# Import git_ops module - only non-async functions
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
# Helper Class - Simulates MCP Tool Calls
# =============================================================================


class MockMCPTools:
    """Mock MCP server that exposes tool functions for testing."""

    def __init__(self):
        # Re-initialize caches for clean test state
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}
        GitRulesCache._loaded = False
        GitRulesCache._instance = None
        GitWorkflowCache._loaded = False
        GitWorkflowCache._instance = None

    async def smart_commit(self, type: str, scope: str, message: str, force_execute: bool = False) -> str:
        """
        Simulates smart_commit tool - creates authorization token without executing git.
        """
        # 1. Re-validate against dynamic rules
        v_type, e_type = _validate_type(type)
        v_scope, e_scope = _validate_scope(scope)
        v_msg, e_msg = _validate_message_format(message)

        if not v_type or not v_scope or not v_msg:
            return json.dumps(
                {"status": "error", "violations": [e for e in [e_type, e_scope, e_msg] if e]},
                indent=2,
            )

        # 2. Check protocol from GitWorkflowCache
        workflow_cache = GitWorkflowCache()
        protocol = workflow_cache.get_protocol()
        should_ask = workflow_cache.should_ask_user(force_execute)

        if should_ask:
            # Create authorization token (but don't execute git)
            command = f'just agent-commit {type.lower()} {scope.lower() if scope else ""} "{message}"'
            auth_token = _auth_guard.create_authorization(
                command, type.lower(), scope.lower() if scope else "", message
            )

            return json.dumps(
                {
                    "status": "ready",
                    "protocol": protocol,
                    "message": "Changes validated. Protocol requires user confirmation.",
                    "command": command,
                    "authorization_required": True,
                    "auth_token": auth_token,
                    "user_prompt_hint": "Run: execute_authorized_commit with the auth_token above",
                    "rules_source": "agent/how-to/gitops.md",
                },
                indent=2,
            )

        # Would execute here if force_execute=True
        return json.dumps(
            {"status": "success", "message": "Commit executed (force_execute=True)", "command": command},
            indent=2,
        )

    async def execute_authorized_commit(self, auth_token: str) -> str:
        """
        Simulates execute_authorized_commit tool - validates token and executes.
        """
        # Validate and consume token
        auth_data = _auth_guard.validate_and_consume(auth_token)

        if auth_data is None:
            return json.dumps(
                {
                    "status": "error",
                    "message": "Invalid, expired, or already-used authorization token",
                    "hint": "Call smart_commit() again to get a new authorization token",
                },
                indent=2,
            )

        # Token is valid - simulate execution (won't actually commit without staged changes)
        return json.dumps(
            {
                "status": "success",
                "message": "Commit authorized and token consumed",
                "token_consumed": True,
                "command": auth_data["command"],
            },
            indent=2,
        )

    async def check_commit_authorization(self) -> str:
        """
        Simulates check_commit_authorization tool.
        """
        import time

        active_tokens = 0
        for token, data in _auth_guard._tokens.items():
            if not data["used"] and (time.time() - data["created_at"]) <= data["expires_in"]:
                active_tokens += 1

        workflow_cache = GitWorkflowCache()
        protocol = workflow_cache.get_protocol()
        should_ask = workflow_cache.should_ask_user()

        return json.dumps(
            {
                "status": "success",
                "protocol": protocol,
                "requires_authorization": should_ask or protocol == "stop_and_ask",
                "pending_tokens": active_tokens,
                "workflow": {
                    "step_1": "Call smart_commit(type, scope, message)",
                    "step_2": "System returns auth_token if authorization required",
                    "step_3": "Ask user: 'Please say: confirm_commit(decision=\"approved\")'",
                    "step_4": "Call execute_authorized_commit(auth_token='...')",
                },
                "note": "Only execute_authorized_commit() can commit after authorization",
            },
            indent=2,
        )


# =============================================================================
# Phase 11 End-to-End Tests
# =============================================================================


class TestPhase11AuthorizationFlow:
    """Test complete Phase 11 authorization flow."""

    def setup_method(self):
        """Reset guard before each test."""
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}
        GitRulesCache._loaded = False
        GitRulesCache._instance = None
        GitWorkflowCache._loaded = False
        GitWorkflowCache._instance = None
        self.tools = MockMCPTools()

    def teardown_method(self):
        """Clean up after each test."""
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    @pytest.mark.asyncio
    async def test_step1_smart_commit_returns_authorization_required(self):
        """
        Step 1: User types 'Test smart_commit_v2 logic'
        Expected: Orchestrator returns 'Authorization Required' analysis, no git commit executed.
        """
        result = await self.tools.smart_commit(
            type="test",
            scope="mcp",
            message="phase 11 authorization test",  # lowercase
            force_execute=False
        )

        result_json = json.loads(result)

        # Assertions
        assert result_json["status"] == "ready", f"Expected 'ready', got: {result_json['status']}"
        assert result_json["authorization_required"] is True, "Authorization should be required"
        assert "auth_token" in result_json, "Auth token should be present"
        assert len(result_json["auth_token"]) == 32, "Token should be 32 hex chars"
        assert "just agent-commit" in result_json["command"], "Command should be just agent-commit"
        assert result_json["protocol"] == "stop_and_ask", "Protocol should be stop_and_ask"

        print("\n✅ Step 1 Passed: smart_commit returned authorization_required=True")
        print(f"   - Status: {result_json['status']}")
        print(f"   - Auth Token: {result_json['auth_token'][:16]}...")
        print(f"   - Protocol: {result_json['protocol']}")

    @pytest.mark.asyncio
    async def test_step2_check_authorization_status(self):
        """
        Step 2: Check authorization status.
        Expected: Shows pending token and workflow guidance.
        """
        # First create an authorization token
        await self.tools.smart_commit(
            type="test",
            scope="mcp",
            message="test message",
            force_execute=False
        )

        # Check status
        result = await self.tools.check_commit_authorization()
        result_json = json.loads(result)

        # Assertions
        assert result_json["status"] == "success", f"Expected success, got: {result_json['status']}"
        assert result_json["requires_authorization"] is True, "Authorization should be required"
        assert result_json["pending_tokens"] == 1, "Should have 1 pending token"
        assert "workflow" in result_json, "Should have workflow guidance"
        assert "step_1" in result_json["workflow"], "Should have step 1"
        assert "step_4" in result_json["workflow"], "Should have step 4"

        print("\n✅ Step 2 Passed: check_commit_authorization shows pending token")
        print(f"   - Pending tokens: {result_json['pending_tokens']}")
        print(f"   - Workflow: {result_json['workflow']}")

    @pytest.mark.asyncio
    async def test_step3_confirm_commit_with_valid_token(self):
        """
        Step 3: User confirms commit with valid token.
        Expected: Token validated, commit executed.
        """
        # Step 1: Get authorization token
        commit_result = await self.tools.smart_commit(
            type="test",
            scope="mcp",
            message="phase 11 authorization test",  # lowercase
            force_execute=False
        )
        commit_data = json.loads(commit_result)
        auth_token = commit_data["auth_token"]

        # Step 2: Execute authorized commit
        exec_result = await self.tools.execute_authorized_commit(auth_token=auth_token)
        exec_data = json.loads(exec_result)

        # Token should be consumed
        assert exec_data["status"] == "success", f"Expected success, got: {exec_data['status']}"
        assert exec_data.get("token_consumed") is True, "Token should be consumed"

        # Verify token was consumed by trying to use it again
        second_attempt = await self.tools.execute_authorized_commit(auth_token=auth_token)
        second_data = json.loads(second_attempt)
        assert second_data["status"] == "error", "Second use should fail (token consumed)"
        assert "Invalid" in second_data["message"], "Should indicate token invalid"

        print("\n✅ Step 3 Passed: Token validated and consumed correctly")
        print(f"   - Execution status: {exec_data['status']}")
        print(f"   - Token consumed: Second use rejected")

    @pytest.mark.asyncio
    async def test_full_phase11_flow(self):
        """
        Test full Phase 11 flow.
        Simulates: User -> "Test smart_commit_v2 logic" -> System -> User -> "confirm_commit" -> System
        """
        print("\n" + "=" * 60)
        print("Phase 11 End-to-End Authorization Flow Test")
        print("=" * 60)

        # Step 1: User types "Test smart_commit_v2 logic"
        print("\n📝 User: 'Test smart_commit_v2 logic'")
        commit_result = await self.tools.smart_commit(
            type="test",
            scope="mcp",
            message="phase 11 authorization flow test",  # lowercase
            force_execute=False
        )
        commit_data = json.loads(commit_result)

        print(f"\n🤖 System Response:")
        print(f"   Status: {commit_data['status']}")
        print(f"   Authorization Required: {commit_data['authorization_required']}")
        print(f"   Auth Token: {commit_data.get('auth_token', 'N/A')[:16]}...")
        print(f"   User Prompt: {commit_data.get('user_prompt_hint', 'N/A')}")

        # Verify Step 1 expectations
        assert commit_data["status"] == "ready"
        assert commit_data["authorization_required"] is True

        # Step 2: Check authorization status
        print("\n📝 Checking authorization status...")
        auth_status = await self.tools.check_commit_authorization()
        auth_data = json.loads(auth_status)
        print(f"   Pending Tokens: {auth_data['pending_tokens']}")

        # Step 3: Simulate user confirming
        print(f"\n📝 User: 'confirm_commit(decision=\"approved\")'")
        token = commit_data["auth_token"]

        exec_result = await self.tools.execute_authorized_commit(auth_token=token)
        exec_data = json.loads(exec_result)

        print(f"\n🤖 System Response:")
        print(f"   Status: {exec_data['status']}")
        print(f"   Token Consumed: {exec_data.get('token_consumed', 'N/A')}")
        print(f"   Message: {exec_data.get('message', 'N/A')}")

        # Verify token is consumed
        second_try = await self.tools.execute_authorized_commit(auth_token=token)
        second_data = json.loads(second_try)
        assert second_data["status"] == "error", "Token should be consumed"
        print(f"\n⚠️  Double-use attempt rejected: {second_data['message']}")

        print("\n" + "=" * 60)
        print("✅ Phase 11 Authorization Flow Test Complete")
        print("=" * 60)


class TestPhase11EdgeCases:
    """Test edge cases for Phase 11 authorization."""

    def setup_method(self):
        """Reset guard before each test."""
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}
        GitRulesCache._loaded = False
        GitRulesCache._instance = None
        GitWorkflowCache._loaded = False
        GitWorkflowCache._instance = None
        self.tools = MockMCPTools()

    def teardown_method(self):
        """Clean up after each test."""
        AuthorizationGuard._instance = None
        AuthorizationGuard._tokens = {}

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self):
        """Test that invalid tokens are rejected."""
        result = await self.tools.execute_authorized_commit(auth_token="invalid_token_xxxx")
        data = json.loads(result)

        assert data["status"] == "error"
        assert "Invalid" in data["message"]

    @pytest.mark.asyncio
    async def test_duplicate_commit_attempt_rejected(self):
        """Test that using the same token twice fails."""
        # Create token
        commit_result = await self.tools.smart_commit(
            type="test", scope="mcp", message="msg", force_execute=False
        )
        commit_data = json.loads(commit_result)
        token = commit_data["auth_token"]

        # First use should succeed
        result1 = await self.tools.execute_authorized_commit(auth_token=token)
        data1 = json.loads(result1)
        assert data1["status"] == "success"

        # Second use should fail
        result2 = await self.tools.execute_authorized_commit(auth_token=token)
        data2 = json.loads(result2)
        assert data2["status"] == "error"
        assert "Invalid" in data2["message"]

    @pytest.mark.asyncio
    async def test_multiple_pending_authorizations(self):
        """Test handling multiple pending authorization requests."""
        # Create multiple tokens - use valid types and messages
        await self.tools.smart_commit(type="feat", scope="mcp", message="first feature", force_execute=False)
        await self.tools.smart_commit(type="fix", scope="nix", message="second fix", force_execute=False)
        await self.tools.smart_commit(type="docs", scope="docs", message="third docs", force_execute=False)

        # Check status
        status = await self.tools.check_commit_authorization()
        data = json.loads(status)

        assert data["pending_tokens"] == 3, f"Expected 3 pending tokens, got {data['pending_tokens']}"


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 11 Authorization Flow Test Suite")
    print("=" * 60)
    print("\nTesting:")
    print("1. Full end-to-end authorization flow")
    print("2. Edge cases (invalid token, duplicate use)")
    print("3. Multiple pending authorizations")
    print("=" * 60)

    pytest.main([__file__, "-v"])
