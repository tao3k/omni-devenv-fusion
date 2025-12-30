import json
import os
import subprocess
import sys
from pathlib import Path

# === Debug: Print current environment info ===
print(f"📂 Current Working Directory (CWD): {os.getcwd()}")
print(f"👤 Current User: {os.environ.get('USER')}")

CONFIG_CANDIDATES = [
    # Try absolute and relative paths
    Path(".mcp.json").absolute(),
    Path(".claude/settings.json").absolute(),
]

def find_config():
    print("\n🔎 Searching for config files...")
    found = None
    for path in CONFIG_CANDIDATES:
        exists = path.exists()
        status = "✅ Exists" if exists else "❌ Not found"
        print(f"   Check: {path} -> {status}")
        if exists and found is None:
            found = path
    return found

def test_orchestrator():
    config_path = find_config()

    if not config_path:
        print("\n🚫 Fatal Error: No config file found after checking all candidates!")
        print("💡 Suggestion: Run from project root and verify filename with 'ls -la .mcp.json'.")
        return

    print(f"\n🚀 Using config file: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed to parse JSON: {e}")
        return

    servers = config.get("mcpServers", {})
    if "orchestrator" not in servers:
        print("❌ No 'orchestrator' field in config file.")
        return

    server_conf = servers["orchestrator"]
    env_vars = server_conf.get("env", {})

    # Print API Key info (masked)
    api_key = env_vars.get("ANTHROPIC_API_KEY", "")
    if api_key:
        print(f"🔑 Successfully read API Key from JSON (prefix: {api_key[:5]}...)")
    else:
        print("⚠️  ANTHROPIC_API_KEY not found in JSON")

    # Start test
    cmd = server_conf.get("command")
    args = server_conf.get("args", [])
    executable = sys.executable if cmd in ["python", "python3"] else cmd

    run_env = os.environ.copy()
    run_env.update(env_vars)

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

    # Send initialize
    init_msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}
    process.stdin.write(json.dumps(init_msg) + "\n")
    process.stdin.flush()

    response = process.stdout.readline()
    if response:
        print(f"✅ Server Response:\n{response.strip()}")
    else:
        print(f"❌ No response. Stderr:\n{process.stderr.read()}")

    process.terminate()

if __name__ == "__main__":
    test_orchestrator()
