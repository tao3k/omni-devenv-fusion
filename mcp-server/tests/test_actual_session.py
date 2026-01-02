"""
Actual LLM Session Test - Verifies CLAUDE.md principles are understood

This test creates a NEW Claude session and verifies that:
1. LLM reads CLAUDE.md (automatically for Claude Code, manually for others)
2. LLM understands the "Actions Over Apologies" principle
3. LLM provides the correct formula: Identify Problem → Do NOT Apologize → Execute Concrete Actions → Verify Fix → Document Lessons

## Usage

### Claude Code CLI (auto-loads CLAUDE.md):
```bash
# In new Claude Code session:
Please call manage_context(action="read")

When problems occur, what should I do according to project rules?
```

### Aider (manual system prompt):
```bash
# Create a test script that passes CLAUDE.md as system prompt
aider --system-prompts claude.md --model sonnet-4-20250514
# Then ask:
When problems occur, what should I do according to project rules?
```

### Programmatic (this test):
```bash
uv run python mcp-server/tests/test_actual_session.py
```

## How It Works

1. Claude Code CLI automatically loads CLAUDE.md as system context
2. Other tools (aider, API calls) need CLAUDE.md passed manually
3. This test simulates: "What would LLM answer if CLAUDE.md is loaded?"

## Requirements

- Claude Code CLI: No setup needed (auto-loads)
- Aider: `aider --system-prompts claude.md`
- This test: ANTHROPIC_API_KEY in .mcp.json orchestrator env
"""

import json
import os
import sys
from pathlib import Path

# MCP Server tests directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
CONFIG_CANDIDATES = [
    PROJECT_ROOT / ".mcp.json",
    PROJECT_ROOT / ".claude" / "settings.json",
]
CLAUDE_MD_PATH = PROJECT_ROOT / "CLAUDE.md"


def find_config() -> Path | None:
    """Find MCP config file."""
    for path in CONFIG_CANDIDATES:
        if path.exists():
            return path
    return None


def get_claude_md_content() -> str:
    """Load CLAUDE.md content - simulates what Claude Code CLI does automatically."""
    if CLAUDE_MD_PATH.exists():
        return CLAUDE_MD_PATH.read_text()
    return ""


def get_api_key() -> str | None:
    """Extract ANTHROPIC_API_KEY from MCP config."""
    config_path = find_config()
    if not config_path:
        print("Error: No config file found (.mcp.json or .claude/settings.json)")
        return None

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        servers = config.get("mcpServers", {})
        orchestrator = servers.get("orchestrator", {})
        env = orchestrator.get("env", {})

        return env.get("ANTHROPIC_API_KEY")
    except Exception as e:
        print(f"Error reading config: {e}")
        return None


def extract_text(content) -> str:
    """Extract text from Claude response content (handles ThinkingBlock)."""
    # Try text attribute first
    if hasattr(content, 'text') and content.text:
        return content.text
    # Try reasoning (for ThinkingBlock)
    if hasattr(content, 'reasoning') and content.reasoning:
        return content.reasoning
    # Try type-based extraction
    content_type = getattr(content, 'type', None)
    if content_type == 'text':
        return getattr(content, 'text', '') or ''
    if content_type == 'thinking':
        return getattr(content, 'thinking', '') or ''
    return str(content)


def test_actual_session():
    """
    Test that LLM understands CLAUDE.md principles.

    This simulates what Claude Code CLI does automatically:
    - Loads CLAUDE.md as system prompt
    - LLM follows the rules defined in CLAUDE.md

    For other tools (aider, etc.), you need to pass CLAUDE.md manually:
        aider --system-prompts claude.md --model sonnet-4-20250514
    """
    from anthropic import Anthropic

    api_key = get_api_key()
    if not api_key:
        print("Error: Could not get ANTHROPIC_API_KEY from .mcp.json")
        print("Make sure .mcp.json has:")
        print('  "mcpServers": { "orchestrator": { "env": { "ANTHROPIC_API_KEY": "..." } } }')
        return False

    client = Anthropic(api_key=api_key)

    # Load CLAUDE.md content - simulates what Claude Code CLI does automatically
    claude_md = get_claude_md_content()
    if not claude_md:
        print("Error: CLAUDE.md not found")
        return False

    print("=" * 60)
    print("ACTUAL LLM SESSION TEST")
    print("Testing: LLM understands CLAUDE.md (Actions Over Apologies)")
    print("=" * 60)

    print(f"\n[Info] Loaded CLAUDE.md ({len(claude_md)} chars)")

    # Step 1: Ask about problem-solving principle
    print("\n" + "=" * 60)
    print("[Step 1] Asking: 'When problems occur, what should I do according to project rules?'")
    print("(CLAUDE.md is passed as system prompt, simulating Claude Code CLI behavior)")

    message = client.messages.create(
        model="sonnet-4-20250514",
        max_tokens=4096,
        system=claude_md,  # Pass CLAUDE.md as system prompt
        messages=[
            {
                "role": "user",
                "content": "When problems occur, what should I do according to project rules?"
            }
        ]
    )

    # Extract all text from content blocks
    response = ""
    for block in message.content:
        if hasattr(block, 'text') and block.text:
            response += block.text + "\n"
        elif hasattr(block, 'reasoning') and block.reasoning:
            response += block.reasoning + "\n"

    print("\n--- LLM Response ---")
    print(response)

    # Step 3: Verify response
    print("\n" + "=" * 60)
    print("[Step 3] Verifying response...")

    checks = {
        "Actions Over Apologies": "Actions Over Apologies" in response or "actions over apologies" in response.lower(),
        "Identify Problem formula": "Identify Problem" in response,
        "Do NOT Apologize": "Do NOT Apologize" in response or "don't apologize" in response.lower(),
        "Verify Fix": "Verify" in response and "Fix" in response,
        "Document Lessons": "Document" in response and "Lesson" in response,
    }

    all_passed = True
    print("\nVerification Results:")
    print("-" * 40)

    for check_name, passed in checks.items():
        status = "PASSED" if passed else "FAILED"
        symbol = "[OK]" if passed else "[X]"
        print(f"  {symbol} {check_name}: {status}")
        if not passed:
            all_passed = False

    print("-" * 40)

    if all_passed:
        print("\n" + "=" * 60)
        print("ALL CHECKS PASSED!")
        print("LLM correctly understands CLAUDE.md principles.")
        print("This verifies: Actions Over Apologies is working.")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("SOME CHECKS FAILED")
        print("LLM did not demonstrate understanding of CLAUDE.md principles.")
        print("=" * 60)
        return False


if __name__ == "__main__":
    print("\nStarting actual LLM session test...")
    print("This will consume API tokens.\n")

    result = test_actual_session()
    sys.exit(0 if result else 1)
