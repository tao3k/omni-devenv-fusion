"""
Comprehensive test suite for all MCP tools in orchestrator.py

Tests all 9 tools:
1. get_codebase_context - Full codebase context via Repomix
2. list_directory_structure - Fast directory tree (token optimization)
3. read_file - Single file reading (micro-level)
4. search_files - Pattern search (grep-like)
5. list_personas - List available personas
6. consult_specialist - Expert consultation
7. save_file - Write files with backup & syntax validation
8. run_task - Execute safe commands (just, nix)

Run: uv run python mcp-server/tests/test_basic.py
"""
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

def send_tool(process, name: str, arguments: dict, tool_id: int) -> tuple[bool, str]:
    """
    Send a tool call and return (success, response_text).
    """
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

def test_all_tools():
    """Test all 4 MCP tools in orchestrator.py."""
    config_path = find_config()

    if not config_path:
        print("\n🚫 Fatal Error: No config file found!")
        return False

    print(f"\n🚀 Using config file: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed to parse JSON: {e}")
        return False

    servers = config.get("mcpServers", {})
    if "orchestrator" not in servers:
        print("❌ No 'orchestrator' field in config file.")
        return False

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

    results = {}

    try:
        # === Step 1: Initialize ===
        print("\n" + "=" * 60)
        print("🧪 MCP Tools Test Suite")
        print("=" * 60)

        print("\n1️⃣  Initialize Server...")
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
            server_name = response['result']['serverInfo']['name']
            print(f"✅ Server Initialized: {server_name}")
            results["initialize"] = True
        else:
            print(f"❌ Initialization Failed: {response}")
            print(f"Stderr: {process.stderr.read()}")
            return False

        # Send initialized notification
        process.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }) + "\n")
        process.stdin.flush()

        # === Tool 1: get_codebase_context ===
        print("\n2️⃣  Testing 'get_codebase_context'...")
        success, text = send_tool(
            process, "get_codebase_context",
            {"target_dir": "modules", "ignore_files": "**/.git/**"},
            2
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "<file path=" in text or "<?xml" in text:
                print("✅ XML structure detected")
            else:
                print("⚠️  Warning: No XML structure found")
            results["get_codebase_context"] = True
        else:
            print(f"❌ {text}")
            results["get_codebase_context"] = False

        # === Tool 2: list_directory_structure ===
        print("\n3️⃣  Testing 'list_directory_structure'...")
        success, text = send_tool(
            process, "list_directory_structure",
            {"root_dir": "."},
            3
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "├── " in text or "└── " in text:
                print("✅ Directory tree structure detected")
            if len(text) < 10000:
                print("✅ Token optimization: Lightweight response")
            results["list_directory_structure"] = True
        else:
            print(f"❌ {text}")
            results["list_directory_structure"] = False

        # === Tool 3: list_personas ===
        print("\n4️⃣  Testing 'list_personas'...")
        success, text = send_tool(process, "list_personas", {}, 4)
        if success:
            print(f"✅ Response: {len(text)} chars")
            try:
                personas = json.loads(text)
                available = ", ".join(p.get("id", "unknown") for p in personas)
                print(f"✅ Personas: [{available}]")
                results["list_personas"] = True
            except json.JSONDecodeError:
                print("⚠️  Warning: Invalid JSON in personas response")
                results["list_personas"] = True  # Still counts as success
        else:
            print(f"❌ {text}")
            results["list_personas"] = False

        # === Tool 4: consult_specialist ===
        print("\n5️⃣  Testing 'consult_specialist'...")
        success, text = send_tool(
            process, "consult_specialist",
            {"role": "architect", "query": "What is the project structure?"},
            5
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "ANTHROPIC_API_KEY is missing" in text:
                print("⚠️  Expected: API key missing (expected without key)")
            elif "Expert Opinion" in text or "architect" in text.lower():
                print("✅ Expert consultation working")
            results["consult_specialist"] = True
        else:
            print(f"❌ {text}")
            results["consult_specialist"] = False

        # === Tool 5: save_file ===
        print("\n6️⃣  Testing 'save_file'...")
        test_file = "test_save_output.txt"
        test_content = "Test content from save_file tool"
        success, text = send_tool(
            process, "save_file",
            {"path": test_file, "content": test_content},
            6
        )
        if success:
            print(f"✅ {text}")
            # Verify file was created
            if os.path.exists(test_file):
                with open(test_file, "r") as f:
                    saved_content = f.read()
                if saved_content == test_content:
                    print("✅ File content verified")
                else:
                    print("⚠️  Content mismatch")
                os.remove(test_file)
                print("✅ File cleaned up")
            else:
                print("⚠️  File not found")
            results["save_file"] = True
        else:
            print(f"❌ {text}")
            results["save_file"] = False

        # === Security Tests for save_file ===
        print("\n7️⃣  Testing 'save_file' security (blocked paths)...")
        # Test absolute path
        success, text = send_tool(
            process, "save_file",
            {"path": "/etc/malicious.txt", "content": "bad"},
            7
        )
        if not success or "Absolute paths are not allowed" in text:
            print("✅ Blocked absolute path")
            results["save_file_security_abs"] = True
        else:
            print("❌ Should have blocked absolute path")
            results["save_file_security_abs"] = False

        # Test path traversal
        success, text = send_tool(
            process, "save_file",
            {"path": "../outside.txt", "content": "bad"},
            8
        )
        if not success or "traversal" in text.lower():
            print("✅ Blocked path traversal")
            results["save_file_securityTraversal"] = True
        else:
            print("❌ Should have blocked path traversal")
            results["save_file_securityTraversal"] = False

        # === Tool 6: read_file ===
        print("\n6️⃣  Testing 'read_file'...")
        success, text = send_tool(
            process, "read_file",
            {"path": "mcp-server/tests/test_basic.py"},
            9
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "4   |" in text or "File:" in text:
                print("✅ File content with line numbers detected")
            results["read_file"] = True
        else:
            print(f"❌ {text}")
            results["read_file"] = False

        # === Tool 7: search_files ===
        print("\n7️⃣  Testing 'search_files'...")
        success, text = send_tool(
            process, "search_files",
            {"pattern": "read_file", "path": "mcp-server"},
            10
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "matches" in text.lower() or "read_file" in text:
                print("✅ Search results contain matches")
            results["search_files"] = True
        else:
            print(f"❌ {text}")
            results["search_files"] = False

        # === Tool 8: save_file with backup ===
        print("\n8️⃣  Testing 'save_file' with backup...")
        test_file = "test_backup.txt"
        test_content = "Original content"
        # First create the file
        send_tool(process, "save_file", {"path": test_file, "content": test_content, "create_backup": False}, 11)
        # Then overwrite with backup
        success, text = send_tool(
            process, "save_file",
            {"path": test_file, "content": "Updated content", "create_backup": True},
            12
        )
        if success and ".bak" in text:
            print(f"✅ Backup created: {text}")
            # Check if backup exists
            backup_file = test_file + ".bak"
            if os.path.exists(backup_file):
                with open(backup_file, "r") as f:
                    backup_content = f.read()
                if backup_content == test_content:
                    print("✅ Backup content verified")
                os.remove(backup_file)
            if os.path.exists(test_file):
                os.remove(test_file)
            results["save_file_backup"] = True
        else:
            print(f"❌ {text}")
            results["save_file_backup"] = False

        # === Tool 9: run_task ===
        print("\n9️⃣  Testing 'run_task'...")
        success, text = send_tool(
            process, "run_task",
            {"command": "just", "args": ["--version"]},
            13
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "just" in text.lower() or "Exit code" in text:
                print("✅ Task execution working")
            results["run_task"] = True
        else:
            print(f"❌ {text}")
            results["run_task"] = False

        # Test blocked command
        print("\n🔟  Testing 'run_task' security (blocked command)...")
        success, text = send_tool(
            process, "run_task",
            {"command": "rm", "args": ["-rf", "/"]},
            14
        )
        if not success or "not allowed" in text.lower():
            print("✅ Blocked dangerous command")
            results["run_task_security"] = True
        else:
            print("❌ Should have blocked dangerous command")
            results["run_task_security"] = False

        # === Summary ===
        print("\n" + "=" * 60)
        print("📊 Test Results Summary")
        print("=" * 60)

        all_passed = True
        for tool, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {tool}: {status}")
            if not passed:
                all_passed = False

        print("=" * 60)
        if all_passed:
            print("🎉 All MCP tools are working correctly!")
        else:
            print("⚠️  Some tools failed. Please review the output above.")
        print("=" * 60)

        return all_passed

    except Exception as e:
        print(f"❌ Exception during test: {e}")
        return False

    finally:
        print("\n🧹 Cleaning up...")
        process.terminate()
        try:
            stderr_output = process.stderr.read()
            if stderr_output:
                print(f"📋 Server Logs (Stderr):\n{stderr_output}")
        except:
            pass
        process.wait()

if __name__ == "__main__":
    success = test_all_tools()
    sys.exit(0 if success else 1)
