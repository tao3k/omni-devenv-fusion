"""
MCP Tool Test - Verifies manage_context returns problem-solving.md content

This test verifies that:
1. The MCP tool manage_context is registered and working
2. It returns problem-solving.md content when action="read"
3. The content includes "Actions Over Apologies" principle

Usage:
    uv run python mcp-server/tests/test_mcp_session.py

This is a unit test that tests the MCP server directly via JSON-RPC,
not a real LLM session test.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
CONFIG_CANDIDATES = [
    PROJECT_ROOT / ".mcp.json",
    PROJECT_ROOT / ".claude" / "settings.json",
]


def find_config() -> Path | None:
    """Find MCP config file."""
    for path in CONFIG_CANDIDATES:
        if path.exists():
            return path
    return None


def read_json_rpc(process):
    """Reads the next JSON-RPC message from the server's stdout."""
    if process.poll() is not None:
        return None
    try:
        line = process.stdout.readline()
        if not line:
            return None
        return json.loads(line.strip())
    except json.JSONDecodeError:
        return None


def send_tool(process, name: str, arguments: dict, tool_id: int) -> tuple[bool, str]:
    """Send a tool call and return (success, response_text)."""
    tool_msg = {
        "jsonrpc": "2.0",
        "id": tool_id,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments
        }
    }
    process.stdin.write(json.dumps(tool_msg) + "\n")
    process.stdin.flush()
    response = read_json_rpc(process)
    if response and "result" in response:
        content_list = response["result"].get("content", [])
        text_output = "".join(item.get("text", "") for item in content_list)
        return True, text_output
    elif response and "error" in response:
        return False, f"Error: {response['error']['message']}"
    return False, str(response)


def test_manage_context():
    """Test that manage_context returns problem-solving.md content."""
    config_path = find_config()

    if not config_path:
        print("Error: No config file found (.mcp.json or .claude/settings.json)")
        return False

    print(f"Using config: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Failed to parse config: {e}")
        return False

    servers = config.get("mcpServers", {})
    if "orchestrator" not in servers:
        print("Error: No 'orchestrator' in config")
        return False

    server_conf = servers["orchestrator"]
    env_vars = server_conf.get("env", {})

    run_env = os.environ.copy()
    run_env.update(env_vars)

    cmd = server_conf.get("command")
    args = server_conf.get("args", [])
    executable = sys.executable if cmd in ["python", "python3"] else cmd

    print(f"Starting MCP server: {executable} {' '.join(args)}")

    process = subprocess.Popen(
        [executable] + args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=run_env,
        text=True,
        bufsize=1
    )

    try:
        print("\n" + "=" * 60)
        print("TESTING: manage_context returns problem-solving.md")
        print("=" * 60)

        # Initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-script", "version": "1.0"}
            }
        }
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()

        response = read_json_rpc(process)
        if not response or "result" not in response:
            print(f"Init failed: {response}")
            return False

        print("Server initialized")

        # Send initialized notification
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()

        # Test manage_context
        print("\n[Step 1] Calling manage_context(action='read')...")
        success, text = send_tool(process, "manage_context", {"action": "read"}, 2)

        if not success:
            print(f"Failed: {text}")
            return False

        print(f"Response length: {len(text)} chars")

        # Verify problem-solving content is present
        print("\n[Step 2] Verifying problem-solving content...")

        checks = {
            "Has Project Instructions": "Project Instructions" in text or "project instructions" in text.lower(),
            "Has Problem Solving": "problem-solving" in text.lower() or "problem solving" in text.lower(),
            "Has Actions Over Apologies": "Actions Over Apologies" in text or "actions over apologies" in text.lower(),
            "Has Identify Problem formula": "Identify Problem" in text,
            "Has Do NOT Apologize": "Do NOT Apologize" in text or "don't apologize" in text.lower(),
            "Has Document Lessons": "Document" in text and ("Lesson" in text or "lesson" in text.lower()),
        }

        all_passed = True
        print("\nVerification Results:")
        print("-" * 50)

        for check_name, passed in checks.items():
            status = "PASSED" if passed else "FAILED"
            symbol = "[OK]" if passed else "[X]"
            print(f"  {symbol} {check_name}: {status}")
            if not passed:
                all_passed = False

        print("-" * 50)

        # Show relevant snippet
        if "Actions Over Apologies" in text or "actions over apologies" in text.lower():
            print("\n[Content Snippet]")
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if 'Action' in line or 'Problem' in line:
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    print("---")
                    for l in lines[start:end]:
                        print(l)
                    print("---\n")

        if all_passed:
            print("\n" + "=" * 60)
            print("ALL CHECKS PASSED!")
            print("manage_context correctly returns problem-solving.md content")
            print("=" * 60)
            return True
        else:
            print("\n" + "=" * 60)
            print("SOME CHECKS FAILED")
            print("problem-solving.md may not be included in manage_context output")
            print("=" * 60)
            return False

    finally:
        process.terminate()
        try:
            stderr = process.stderr.read()
            if stderr:
                print(f"Server logs: {stderr[:500]}")
        except:
            pass
        process.wait()


def test_start_spec_enforcement():
    """Test that start_spec enforces Legislation (spec requirement)."""
    config_path = find_config()

    if not config_path:
        print("Error: No config file found (.mcp.json or .claude/settings.json)")
        return False

    print(f"Using config: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Failed to parse config: {e}")
        return False

    servers = config.get("mcpServers", {})
    if "orchestrator" not in servers:
        print("Error: No 'orchestrator' in config")
        return False

    server_conf = servers["orchestrator"]
    env_vars = server_conf.get("env", {})

    run_env = os.environ.copy()
    run_env.update(env_vars)

    cmd = server_conf.get("command")
    args = server_conf.get("args", [])
    executable = sys.executable if cmd in ["python", "python3"] else cmd

    print(f"Starting MCP server: {executable} {' '.join(args)}")

    process = subprocess.Popen(
        [executable] + args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=run_env,
        text=True,
        bufsize=1
    )

    try:
        print("\n" + "=" * 60)
        print("TESTING: start_spec enforces Legislation (spec requirement)")
        print("=" * 60)

        # Initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-script", "version": "1.0"}
            }
        }
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()

        response = read_json_rpc(process)
        if not response or "result" not in response:
            print(f"Init failed: {response}")
            return False

        print("Server initialized")

        # Send initialized notification
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()

        # Test 1: start_spec with existing "Hive Architecture" (should allow)
        print("\n[Step 1] Testing start_spec('Hive Architecture') - existing spec...")
        success, text = send_tool(process, "start_spec", {"name": "Hive Architecture"}, 3)

        if not success:
            print(f"Failed: {text}")
            return False

        result = json.loads(text)
        print(f"Response: {result.get('status')} - {result.get('message', '')}")

        if result.get("status") != "allowed":
            print("ERROR: Hive Architecture spec exists but start_spec blocked!")
            return False

        print("[OK] Hive Architecture: Allowed (spec exists)")

        # Test 2: start_spec with new feature (should block)
        print("\n[Step 2] Testing start_spec('New Feature X') - missing spec...")
        success, text = send_tool(process, "start_spec", {"name": "New Feature X"}, 3)

        if not success:
            print(f"Failed: {text}")
            return False

        result = json.loads(text)
        print(f"Response: {result.get('status')} - {result.get('reason', '')}")

        if result.get("status") != "blocked":
            print("ERROR: New Feature X missing spec but start_spec allowed!")
            return False

        if not result.get("spec_required"):
            print("ERROR: start_spec should indicate spec_required=true")
            return False

        if result.get("next_action") != "draft_feature_spec":
            print("ERROR: start_spec should require draft_feature_spec")
            return False

        print("[OK] New Feature X: Blocked (spec required)")

        # Test 3: Empty name (should error)
        print("\n[Step 3] Testing start_spec('') - empty name...")
        success, text = send_tool(process, "start_spec", {"name": ""}, 3)

        if not success:
            print(f"Failed: {text}")
            return False

        if "Invalid name" not in text:
            print("ERROR: Empty name should return error")
            return False

        print("[OK] Empty name: Rejected")

        print("\n" + "=" * 60)
        print("ALL CHECKS PASSED!")
        print("start_spec correctly enforces Legislation for any new work")
        print("=" * 60)
        return True

    finally:
        process.terminate()
        try:
            stderr = process.stderr.read()
            if stderr:
                print(f"Server logs: {stderr[:500]}")
        except:
            pass
        process.wait()


if __name__ == "__main__":
    print("\nTesting MCP tool: manage_context returns problem-solving.md")
    print("This verifies the file is auto-loaded in new sessions.\n")

    result = test_manage_context()
    if result:
        print("\n" + "=" * 60)
        print("Running start_spec test...")
        print("=" * 60)
        result = test_start_spec_enforcement()
    sys.exit(0 if result else 1)
