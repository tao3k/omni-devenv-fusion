import json
import os
import subprocess
import sys
from pathlib import Path

# === Debug: Print current environment info ===
print(f"📂 Current Working Directory (CWD): {os.getcwd()}")
print(f"👤 Current User: {os.environ.get('USER')}")

CONFIG_CANDIDATES = [
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

def read_json_rpc(process):
    """
    Reads the next JSON-RPC message from the server's stdout.
    """
    if process.poll() is not None:
        return None
        
    try:
        line = process.stdout.readline()
        if not line:
            return None
        return json.loads(line.strip())
    except json.JSONDecodeError:
        print(f"⚠️  Received non-JSON output: {line.strip()}")
        return None

def test_orchestrator():
    config_path = find_config()

    if not config_path:
        print("\n🚫 Fatal Error: No config file found!")
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
    
    # Setup environment
    run_env = os.environ.copy()
    run_env.update(env_vars)
    
    # Command setup
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

    try:
        # === Step 1: Initialize ===
        print("\n1️⃣  Sending Initialize Request...")
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
        if response and "result" in response:
            print(f"✅ Server Initialized: {response['result']['serverInfo']['name']}")
            
            # Send initialized notification
            process.stdin.write(json.dumps({
                "jsonrpc": "2.0", 
                "method": "notifications/initialized"
            }) + "\n")
            process.stdin.flush()
        else:
            print(f"❌ Initialization Failed: {response}")
            print(f"Stderr: {process.stderr.read()}")
            return

        # === Step 2: Test XML (Repomix) Tool ===
        print("\n2️⃣  Testing 'get_codebase_context' (XML Generation)...")
        tool_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_codebase_context",
                "arguments": {
                    "target_dir": ".",  # Scan current directory
                    "ignore_files": "**/.git/**,**/uv.lock,**/node_modules/**" # Ignore heavy files for speed
                }
            }
        }
        process.stdin.write(json.dumps(tool_msg) + "\n")
        process.stdin.flush()

        # Wait for response (this might take a second for Repomix to run)
        response = read_json_rpc(process)

        if response and "result" in response:
            content_list = response["result"].get("content", [])
            text_output = ""
            for item in content_list:
                if item.get("type") == "text":
                    text_output += item.get("text", "")

            print(f"📊 Response Length: {len(text_output)} chars")

            # Verify XML content
            if "<file path=" in text_output or "&lt;file path=" in text_output:
                print("✅ XML structure detected (<file path=...)")
            elif "<?xml" in text_output:
                print("✅ XML header detected")
            else:
                print("⚠️  Warning: Output might not be XML. Snippet:")
                print(text_output[:200] + "...")

        elif response and "error" in response:
            print(f"❌ Tool execution error: {response['error']['message']}")
        else:
            print(f"❌ Unknown response: {response}")

        # === Step 3: Test list_directory_structure Tool (Phase 2 Optimization) ===
        print("\n3️⃣  Testing 'list_directory_structure' (Fast & Cheap)...")
        tool_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_directory_structure",
                "arguments": {
                    "root_dir": "."  # List current directory
                }
            }
        }
        process.stdin.write(json.dumps(tool_msg) + "\n")
        process.stdin.flush()

        response = read_json_rpc(process)

        if response and "result" in response:
            content_list = response["result"].get("content", [])
            text_output = ""
            for item in content_list:
                if item.get("type") == "text":
                    text_output += item.get("text", "")

            print(f"📊 Response Length: {len(text_output)} chars")

            # Verify directory tree structure (should NOT contain file content)
            if "├── " in text_output or "└── " in text_output:
                print("✅ Directory tree structure detected (├──/└──)")
                # Count lines - should be < 100 for a typical project
                line_count = len(text_output.split('\n'))
                print(f"📊 Line count: {line_count} (should be < 100 for token optimization)")
            elif "Directory Structure" in text_output:
                print("✅ Directory structure header detected")
            else:
                print("⚠️  Warning: Unexpected output format")

            # This tool should consume < 1k tokens (major optimization!)
            if len(text_output) < 5000:
                print("✅ Token optimization: Response is lightweight (< 5k chars)")
            else:
                print("⚠️  Warning: Response might be too large for optimal token usage")

        elif response and "error" in response:
            print(f"❌ Tool execution error: {response['error']['message']}")
        else:
            print(f"❌ Unknown response: {response}")

    except Exception as e:
        print(f"❌ Exception during test: {e}")
    
    finally:
        print("\n🧹 Cleaning up...")
        process.terminate()
        try:
            # Read any remaining stderr logs
            stderr_output = process.stderr.read()
            if stderr_output:
                print(f"📋 Server Logs (Stderr):\n{stderr_output}")
        except:
            pass
        process.wait()

if __name__ == "__main__":
    test_orchestrator()
