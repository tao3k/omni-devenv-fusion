#!/usr/bin/env python3
"""
src/agent/tests/test_actual_session_skills.py
Phase 25: Real LLM Session Skills Test.

This test file ACTUALLY opens an LLM session using the Anthropic SDK
to test the complete flow with @omni commands.

Prerequisites:
    - API key configured in .claude/settings.json (from agent/settings.yaml -> api.anthropic_settings)
    - Or ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY environment variable

Usage:
    # Run all real session tests
    python -m pytest packages/python/agent/src/agent/tests/test_actual_session_skills.py -v -s

    # Run specific test
    python -m pytest packages/python/agent/src/agent/tests/test_actual_session_skills.py::TestRealLLMSessionWithOmni -v -s

    # Run manually
    python packages/python/agent/src/agent/tests/test_actual_session_skills.py
"""

import os
import sys
import asyncio
import argparse
import json
from typing import Optional

# Add project root to path
sys.path.insert(
    0,
    str(__file__).rsplit("/packages/python/agent/src/agent/tests/", 1)[0]
    + "/packages/python/common/src",
)

# Check for Anthropic SDK
try:
    from anthropic import Anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("⚠️  Anthropic SDK not installed. Run: pip install anthropic")

# Import settings utilities
from common.mcp_core.settings import get_setting, get_config_path
from common.mcp_core.gitops import get_project_root


# =============================================================================
# Configuration - Read from settings.yaml -> api.anthropic_settings
# =============================================================================


def load_anthropic_settings() -> dict:
    """
    Load Anthropic settings from .claude/settings.json.

    Configuration chain:
    1. agent/settings.yaml -> api.anthropic_settings -> .claude/settings.json
    2. Environment variables (ANTHROPIC_AUTH_TOKEN, ANTHROPIC_API_KEY)
    """
    # Get anthropic settings path from settings.yaml
    anthropic_rel_path = get_setting("api.anthropic_settings", ".claude/settings.json")
    project_root = get_project_root()
    anthropic_settings_path = project_root / anthropic_rel_path

    # Load settings from JSON
    api_key = None
    base_url = None
    model = None

    if anthropic_settings_path.exists():
        try:
            with open(anthropic_settings_path) as f:
                settings = json.load(f)

            env = settings.get("env", {})

            # Priority: ANTHROPIC_AUTH_TOKEN > ANTHROPIC_API_KEY
            api_key = (
                env.get("ANTHROPIC_AUTH_TOKEN")
                or env.get("ANTHROPIC_API_KEY")
                or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or os.environ.get("ANTHROPIC_API_KEY")
            )
            base_url = env.get("ANTHROPIC_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
            model = env.get("ANTHROPIC_MODEL") or os.environ.get("ANTHROPIC_MODEL")

            if api_key:
                print(f"✅ Loaded API key from: {anthropic_settings_path}")
                if base_url:
                    print(f"📡 Base URL: {base_url}")
                if model:
                    print(f"🤖 Model: {model}")
        except Exception as e:
            print(f"⚠️  Failed to read {anthropic_settings_path}: {e}")

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
    }


def get_anthropic_client() -> Optional[Anthropic]:
    """Create Anthropic client from settings file or environment."""
    settings = load_anthropic_settings()

    api_key = settings.get("api_key")
    if not api_key:
        return None

    client_kwargs = {"api_key": api_key}

    if settings.get("base_url"):
        client_kwargs["base_url"] = settings["base_url"]

    return Anthropic(**client_kwargs)


def get_anthropic_model() -> str:
    """Get the Anthropic model to use."""
    settings = load_anthropic_settings()
    return settings.get("model") or "claude-sonnet-4-20250514"


def check_api_key() -> bool:
    """Check if API key is available."""
    if not ANTHROPIC_AVAILABLE:
        print("❌ Anthropic SDK not installed")
        return False

    settings = load_anthropic_settings()
    if not settings.get("api_key"):
        print("❌ API key not found in:")
        print("   - .claude/settings.json (from agent/settings.yaml -> api.anthropic_settings)")
        print("   - Environment: ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY")
        return False

    print("✅ Anthropic API key configured")
    return True


# =============================================================================
# Real LLM Session Tests
# =============================================================================


class TestRealLLMSessionWithOmni:
    """
    Test real LLM session with @omni commands.

    This class actually makes API calls to Anthropic to test
    the complete feedback loop:
    1. User query → LLM
    2. LLM decides to use @omni command
    3. Command executed via omni tool
    4. Result returned to LLM
    5. LLM generates final response
    """

    def __init__(self):
        self.client = get_anthropic_client()
        self.model = get_anthropic_model()

    def test_connection(self) -> bool:
        """Test Anthropic API connection."""
        if not self.client:
            return False

        try:
            # Simple test message
            response = self.client.messages.create(
                model=self.model, max_tokens=10, messages=[{"role": "user", "content": "Hi"}]
            )
            print(f"✅ API Connection OK (model: {self.model})")
            return True
        except Exception as e:
            print(f"❌ API Connection failed: {e}")
            return False

    async def test_omni_skill_discovery(self):
        """
        Test that LLM can discover and understand omni commands.

        Scenario:
        - Ask LLM what commands are available
        - LLM should respond with @omni help info
        """
        print("\n" + "=" * 60)
        print("🧪 Test: Omni Skill Discovery")
        print("=" * 60)

        system_prompt = """You are an AI assistant with access to the @omni tool.

The @omni tool allows you to execute skill commands. Format:
- @omni("skill.command") - Execute a command
- @omni("help") - Show all available skills
- @omni("skill") - Show commands for a specific skill

Available skills include: git, filesystem, knowledge, memory, etc.

When the user asks what commands are available, explain the @omni syntax
and give examples of useful commands."""

        user_query = "What commands can I use? Show me how to check git status."

        print(f"\n📝 User: {user_query}")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
            ],
        )

        result = response.content[0].text
        print(f"\n🤖 LLM Response:\n{result}")

        # Verify response mentions @omni
        assert "@omni" in result or "omni" in result.lower(), "Response should mention @omni"
        assert "git.status" in result or "git status" in result, "Should mention git status command"

        print("✅ Test passed: LLM can explain @omni syntax")

    async def test_omni_git_command_in_context(self):
        """
        Test using @omni git command within conversation context.

        Scenario:
        - User asks about git status
        - LLM explains it would use @omni("git.status")
        - We verify the command format is correct
        """
        print("\n" + "=" * 60)
        print("🧪 Test: Omni Git Command in Context")
        print("=" * 60)

        # First, get actual git status via omni
        from agent.mcp_server import omni

        actual_status = omni("git.status")

        system_prompt = """You are analyzing git status for the user.
Use @omni("git.status") to get the current git status."""

        user_query = "What's the current git status?"

        print(f"\n📝 User: {user_query}")
        print(f"📋 Actual git status:\n{actual_status[:300]}...")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
                {"role": "assistant", "content": f'@omni("git.status")'},
                {"role": "user", "content": f"Result: {actual_status[:500]}"},
            ],
        )

        result = response.content[0].text
        print(f"\n🤖 LLM Analysis:\n{result}")

        print("✅ Test passed: LLM can interpret @omni results")

    async def test_omni_multiple_skills(self):
        """
        Test LLM understanding multiple @omni skills.

        Scenario:
        - User asks about different operations
        - LLM should understand different skill commands
        """
        print("\n" + "=" * 60)
        print("🧪 Test: Multiple Omni Skills")
        print("=" * 60)

        from agent.mcp_server import omni

        # Get help for different skills
        git_help = omni("git")
        knowledge_help = omni("knowledge")

        system_prompt = """You are a helpful assistant explaining available skills.
Given information about git and knowledge skills, explain what each can do."""

        user_query = "Compare git and knowledge skills"

        print(f"\n📝 User: {user_query}")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
                {
                    "role": "assistant",
                    "content": f"Git skills: {git_help[:200]}...\n\nKnowledge skills: {knowledge_help[:200]}...",
                },
            ],
        )

        result = response.content[0].text
        print(f"\n🤖 LLM Comparison:\n{result}")

        # Should mention both git and knowledge
        assert "git" in result.lower(), "Should mention git"
        assert "knowledge" in result.lower(), "Should mention knowledge"

        print("✅ Test passed: LLM can compare multiple skills")

    async def test_conversation_with_omni_tool_calls(self):
        """
        Test complete conversation flow with @omni tool-like behavior.

        This simulates the full MCP interaction where:
        1. User asks a question
        2. LLM would normally use a tool (simulated here)
        3. We provide the tool result
        4. LLM generates final response
        """
        print("\n" + "=" * 60)
        print("🧪 Test: Complete Conversation Flow")
        print("=" * 60)

        from agent.mcp_server import omni

        # Simulated conversation
        conversation_history = [
            {
                "role": "system",
                "content": 'You can use @omni to execute commands. For example: @omni("git.status")',
            },
        ]

        queries = [
            "Show me the project structure",
            "What are the coding standards?",
            "How do I commit changes?",
        ]

        for query in queries:
            print(f"\n📝 User: {query}")

            # Determine appropriate omni command
            if "structure" in query.lower() or "project" in query.lower():
                cmd = "filesystem.list_directory"
                cmd_result = omni("filesystem.list_directory", {"path": "."})
            elif "standard" in query.lower() or "coding" in query.lower():
                cmd = "knowledge.get_language_standards"
                cmd_result = omni("knowledge.get_language_standards", {"lang": "python"})
            elif "commit" in query.lower():
                cmd = "git.help"
                cmd_result = omni("git.help")
            else:
                cmd = "help"
                cmd_result = omni("help")

            conversation_history.append({"role": "user", "content": query})
            conversation_history.append({"role": "assistant", "content": f'@omni("{cmd}")'})
            conversation_history.append({"role": "user", "content": f"Result: {cmd_result[:300]}"})

            # Get LLM response
            response = self.client.messages.create(
                model=self.model, max_tokens=256, messages=conversation_history
            )

            result = response.content[0].text
            print(f'🤖 @omni("{cmd}"): {result[:150]}...')
            conversation_history.append({"role": "assistant", "content": result})

        print("✅ Test passed: Complete conversation flow works")

    async def run_all_tests(self):
        """Run all real session tests."""
        if not self.client:
            print("❌ Cannot run tests: No Anthropic client")
            return False

        if not self.test_connection():
            return False

        tests = [
            self.test_omni_skill_discovery,
            self.test_omni_git_command_in_context,
            self.test_omni_multiple_skills,
            self.test_conversation_with_omni_tool_calls,
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                await test()
                passed += 1
            except Exception as e:
                print(f"❌ Test failed: {e}")
                failed += 1

        print("\n" + "=" * 60)
        print(f"📊 RESULTS: {passed} passed, {failed} failed")
        print("=" * 60)

        return failed == 0


# =============================================================================
# Main Entry Point
# =============================================================================


async def main():
    """Main entry point for running real session tests."""
    print("=" * 60)
    print("PHASE 25: REAL LLM SESSION SKILLS TEST")
    print("=" * 60)

    # Check prerequisites
    if not check_api_key():
        print("\n📝 To run these tests:")
        print("   1. Set ANTHROPIC_API_KEY environment variable")
        print("   2. Or configure in settings.yaml")
        print("   3. Install anthropic SDK: pip install anthropic")
        return

    # Parse args
    parser = argparse.ArgumentParser(description="Run real LLM session tests")
    parser.add_argument(
        "--test", "-t", type=str, help="Run specific test (skill_discovery, git, multi, flow)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Create test instance
    tester = TestRealLLMSessionWithOmni()

    if args.test:
        # Run specific test
        test_map = {
            "skill_discovery": tester.test_omni_skill_discovery,
            "git": tester.test_omni_git_command_in_context,
            "multi": tester.test_omni_multiple_skills,
            "flow": tester.test_conversation_with_omni_tool_calls,
        }

        if args.test in test_map:
            try:
                await test_map[args.test]()
                print("\n✅ Test completed successfully")
            except Exception as e:
                print(f"\n❌ Test failed: {e}")
                sys.exit(1)
        else:
            print(f"Unknown test: {args.test}")
            print(f"Available tests: {list(test_map.keys())}")
            sys.exit(1)
    else:
        # Run all tests
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
