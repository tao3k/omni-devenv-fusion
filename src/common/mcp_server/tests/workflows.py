# tests/test_workflow.py
"""
End-to-End Workflow Test

Tests the complete workflow:
1. Get codebase context
2. Consult specialist (requires API key)

Usage:
    uv run python src/common/mcp_server/tests/workflows.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

# Project root - go up from src/common/mcp_server/tests/ to project root (5 levels up)
PROJECT_ROOT = Path(__file__).resolve().parents[4]
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


def get_api_key() -> str | None:
    """Get ANTHROPIC_API_KEY from config files or environment.

    Priority:
    1. .claude/settings.json → env.ANTHROPIC_AUTH_TOKEN
    2. .mcp.json → mcpServers.orchestrator.env.ANTHROPIC_API_KEY
    3. Environment variable ANTHROPIC_API_KEY
    """
    # Check .claude/settings.json first (primary location for API key)
    claude_settings = PROJECT_ROOT / ".claude" / "settings.json"
    if claude_settings.exists():
        try:
            with open(claude_settings, 'r') as f:
                config = json.load(f)
            env = config.get("env", {})
            api_key = env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY")
            if api_key:
                return api_key
        except Exception:
            pass

    # Check .mcp.json format
    mcp_config = PROJECT_ROOT / ".mcp.json"
    if mcp_config.exists():
        try:
            with open(mcp_config, 'r') as f:
                config = json.load(f)
            servers = config.get("mcpServers", {})
            orchestrator = servers.get("orchestrator", {})
            env = orchestrator.get("env", {})
            api_key = env.get("ANTHROPIC_API_KEY")
            if api_key:
                return api_key
        except Exception:
            pass

    # Fall back to environment variable
    return os.environ.get("ANTHROPIC_API_KEY")


def read_json_rpc(process):
    """Read JSON-RPC response from server stdout."""
    try:
        line = process.stdout.readline()
        if not line:
            return None
        return json.loads(line.strip())
    except json.JSONDecodeError:
        return None


def start_server_process():
    """Start orchestrator MCP server with proper environment from .mcp.json."""
    config_path = find_config()
    if not config_path:
        print("Error: No config file found!")
        return None, None

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error reading config: {e}")
        return None, None

    servers = config.get("mcpServers", {})
    if "orchestrator" not in servers:
        print("Error: No 'orchestrator' in mcpServers config")
        return None, None

    server_conf = servers["orchestrator"]
    env_vars = server_conf.get("env", {})

    # Setup environment - merge config env with system env
    run_env = os.environ.copy()
    run_env.update(env_vars)

    cmd = server_conf.get("command")
    args = server_conf.get("args", [])
    executable = sys.executable if cmd in ["python", "python3"] else cmd

    print(f"▶️  Starting Server: {executable} {' '.join(args)}")

    process = subprocess.Popen(
        [executable] + args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=run_env,
        text=True,
        bufsize=1
    )

    return process, server_conf


def run_full_workflow():
    """Run end-to-end workflow test."""
    print("🚀 Starting End-to-End Workflow Test")

    # Check for API key first
    api_key = get_api_key()
    if not api_key:
        print("⚠️  Warning: ANTHROPIC_API_KEY not found in .mcp.json")
        print("   Step 2 (consult_specialist) will be skipped as it requires API key.")

    process, server_conf = start_server_process()
    if not process:
        sys.exit(1)

    try:
        # === 1. Initialize ===
        init_msg = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-workflow", "version": "1.0"}}
        }
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()
        read_json_rpc(process)  # Skip init response
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()

        # === Step 1: Read Context ===
        target_dir = "modules"  # Analyze modules directory
        print(f"\n🤖 Step 1: Reading context from '{target_dir}'...")

        ctx_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_codebase_context",
                "arguments": {"target_dir": target_dir, "ignore_files": "**/*.lock"}
            }
        }
        process.stdin.write(json.dumps(ctx_req) + "\n")
        process.stdin.flush()

        ctx_resp = read_json_rpc(process)
        context_text = ""
        if ctx_resp and "result" in ctx_resp:
            context_text = ctx_resp["result"]["content"][0]["text"]
            print(f"✅ Context acquired ({len(context_text)} chars).")
        else:
            print(f"❌ Failed to get context: {ctx_resp}")
            return

        # === Step 2: Consult Architect ===
        print("\n🤖 Step 2: Consulting 'Architect' with the code context...")

        if not api_key:
            print("⚠️  Skipping consult_specialist (no API key)")
            print("   To enable this test, add ANTHROPIC_API_KEY to .mcp.json:")
            print('   "mcpServers": { "orchestrator": { "env": { "ANTHROPIC_API_KEY": "sk-..." } } }')
            print("\n✅ Workflow test completed (Step 2 skipped - requires API key)")
            return

        # Truncate to 8000 chars to avoid token overflow
        snippet = context_text[:8000]
        query = (
            f"I have extracted the following Nix modules structure:\n\n{snippet}\n...\n(truncated)\n\n"
            "Question: Based on this, analyze the modularization strategy. Is it using standard NixOS module patterns?"
        )

        consult_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "consult_specialist",
                "arguments": {"role": "architect", "query": query}
            }
        }
        process.stdin.write(json.dumps(consult_req) + "\n")
        process.stdin.flush()

        print("⏳ Waiting for LLM response (this may take 5-10s)...")
        consult_resp = read_json_rpc(process)

        if consult_resp and "result" in consult_resp:
            print("\n💡 Expert Response:")
            print("=" * 60)
            print(consult_resp["result"]["content"][0]["text"])
            print("=" * 60)
            print("\n✅ Workflow test completed successfully!")
        else:
            print(f"❌ Consultation Failed: {consult_resp}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        process.terminate()
        process.wait()


if __name__ == "__main__":
    run_full_workflow()
